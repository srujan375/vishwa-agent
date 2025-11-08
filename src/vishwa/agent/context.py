"""
Context Manager for agent memory and conversation history.

Manages:
- Message history for LLM
- Files currently in context
- Modifications made during session
- Context pruning when approaching token limits
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from vishwa.llm.response import ToolCall
from vishwa.tools.base import ToolResult
from vishwa.utils.logger import logger


@dataclass
class Message:
    """Represents a single message in the conversation"""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to LLM API format"""
        msg = {"role": self.role, "content": self.content}

        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id

        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls

        return msg


@dataclass
class Modification:
    """Tracks a file modification"""

    file_path: str
    tool: str
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    timestamp: Optional[str] = None


class ContextManager:
    """
    Manages conversation context and memory for the agent.

    Responsibilities:
    - Track message history
    - Keep files in context
    - Track modifications
    - Prune context when needed
    - Estimate token usage
    """

    def __init__(self, max_tokens: int = 150000):
        """
        Initialize context manager.

        Args:
            max_tokens: Maximum context window size
        """
        self.max_tokens = max_tokens
        self.messages: List[Message] = []
        self.files_in_context: Dict[str, str] = {}
        self.modifications: List[Modification] = []
        self.recent_tool_outputs: deque = deque(maxlen=10)
        self.created_files: set = set()  # Track files created in this session
        self.file_summaries: Dict[str, str] = {}  # Summaries of removed files
        self.message_importance: Dict[int, int] = {}  # Message importance scores

    def add_message(
        self,
        role: str,
        content: str,
        tool_call_id: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a message to context.

        Args:
            role: Message role (system, user, assistant, tool)
            content: Message content
            tool_call_id: Optional tool call ID (for tool results)
            tool_calls: Optional tool calls (for assistant messages)
            metadata: Optional metadata
        """
        message = Message(
            role=role,
            content=content,
            tool_call_id=tool_call_id,
            tool_calls=tool_calls,
            metadata=metadata,
        )
        self.messages.append(message)

    def add_tool_result(
        self, tool_call: ToolCall, result: ToolResult
    ) -> None:
        """
        Add tool execution result to context.

        Args:
            tool_call: The tool call that was executed
            result: The result from tool execution
        """
        # Add assistant message with tool call
        self.add_message(
            role="assistant",
            content="",  # Fixed: Changed from None to empty string for API compatibility
            tool_calls=[
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": str(tool_call.arguments),
                    },
                }
            ],
        )

        # Add tool result message
        self.add_message(
            role="tool",
            content=str(result),
            tool_call_id=tool_call.id,
        )

        # Track in recent outputs
        self.recent_tool_outputs.append(
            {"tool": tool_call.name, "result": result}
        )

    def get_messages(self) -> List[Dict[str, Any]]:
        """
        Get messages formatted for LLM API.

        Returns:
            List of message dicts
        """
        return [msg.to_dict() for msg in self.messages]

    def add_file_to_context(self, path: str, content: str) -> None:
        """
        Track a file being worked on.

        Args:
            path: File path
            content: File content
        """
        self.files_in_context[path] = content

    def remove_file_from_context(self, path: str) -> None:
        """
        Remove a file from context.

        Args:
            path: File path
        """
        if path in self.files_in_context:
            del self.files_in_context[path]

    def track_modification(
        self,
        file_path: str,
        tool: str,
        old_content: Optional[str] = None,
        new_content: Optional[str] = None,
    ) -> None:
        """
        Track a file modification.

        Args:
            file_path: Path to modified file
            tool: Tool that made the modification
            old_content: Original content
            new_content: New content
        """
        from datetime import datetime

        modification = Modification(
            file_path=file_path,
            tool=tool,
            old_content=old_content,
            new_content=new_content,
            timestamp=datetime.now().isoformat(),
        )
        self.modifications.append(modification)

        # Log modification
        logger.context_file_mod(file_path, tool)

    def mark_file_created(self, file_path: str) -> None:
        """
        Mark a file as created in this session.

        Args:
            file_path: Path to the created file
        """
        self.created_files.add(file_path)

    def was_file_created(self, file_path: str) -> bool:
        """
        Check if a file was already created in this session.

        Args:
            file_path: Path to check

        Returns:
            True if file was created in this session
        """
        return file_path in self.created_files

    def estimate_tokens(self) -> int:
        """
        Estimate current token usage.

        Uses tiktoken for accurate counting if available,
        falls back to rough estimation (chars/4) if not.

        Returns:
            Estimated token count
        """
        try:
            import tiktoken
            return self._count_tokens_accurate()
        except ImportError:
            return self._count_tokens_rough()

    def _count_tokens_accurate(self) -> int:
        """
        Accurate token counting using tiktoken.

        Returns:
            Exact token count
        """
        import tiktoken

        # Use cl100k_base encoding (used by GPT-4, Claude)
        try:
            encoder = tiktoken.get_encoding("cl100k_base")
        except:
            # Fallback to rough if encoding not available
            return self._count_tokens_rough()

        total_tokens = 0

        # Count message tokens
        for msg in self.messages:
            if msg.content:
                total_tokens += len(encoder.encode(msg.content))

            # Count tool call arguments
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    total_tokens += len(encoder.encode(str(tool_call)))

        # Count files in context
        for content in self.files_in_context.values():
            total_tokens += len(encoder.encode(content))

        return total_tokens

    def _count_tokens_rough(self) -> int:
        """
        Rough token estimation (fallback).

        Returns:
            Approximate token count
        """
        total_chars = 0

        # Count message content
        for msg in self.messages:
            if msg.content:
                total_chars += len(msg.content)

        # Count files in context
        for content in self.files_in_context.values():
            total_chars += len(content)

        # Rough conversion: 4 chars = 1 token
        return total_chars // 4

    def is_approaching_limit(self, threshold: float = 0.6) -> bool:
        """
        Check if approaching token limit.

        Args:
            threshold: Percentage of max (0.0 to 1.0)
                      Default 0.6 (60%) to leave headroom for responses

        Returns:
            True if above threshold
        """
        current = self.estimate_tokens()
        limit = self.max_tokens * threshold
        return current > limit

    def prune_if_needed(self) -> None:
        """
        Prune context if approaching token limit.

        New improved strategy:
        1. Summarize files instead of deleting
        2. Use dependency graph to keep related files
        3. Score messages by importance
        4. Prune least important first
        5. Summarize message groups instead of deleting
        """
        if not self.is_approaching_limit():
            return

        before_tokens = self.estimate_tokens()

        # Step 1: Summarize and remove non-critical files
        self._prune_files_with_summarization()

        # Step 2: If still too large, prune messages by importance
        if self.is_approaching_limit():
            self._prune_messages_by_importance()

        # Step 3: If STILL too large, aggressive truncation
        if self.is_approaching_limit():
            self._aggressive_truncation()

        after_tokens = self.estimate_tokens()
        logger.context_pruned(before_tokens, after_tokens)

    def _prune_files_with_summarization(self) -> None:
        """
        Remove files from context but keep summaries.

        Uses dependency graph to keep related files together.
        """
        modified_files = {mod.file_path for mod in self.modifications}

        # Try to get dependency graph
        important_files = set(modified_files)
        try:
            from vishwa.code_intelligence import get_dependency_graph
            graph = get_dependency_graph()

            # Keep files related to modifications
            for file_path in modified_files:
                # Keep dependencies
                deps = graph.get_dependencies(file_path)
                important_files.update(deps)

                # Keep direct dependents
                dependents = graph.get_dependents(file_path)
                important_files.update(dependents[:3])  # Limit to 3 closest

        except Exception:
            # If dependency graph not available, just use modified files
            pass

        # Remove files not in important set, but summarize first
        for path in list(self.files_in_context.keys()):
            if path not in important_files:
                # Create summary before removing
                summary = self._summarize_file(path)
                self.file_summaries[path] = summary

                # Remove full content
                del self.files_in_context[path]

    def _summarize_file(self, path: str) -> str:
        """
        Create a smart summary of a file.

        Uses structure analysis if available.
        """
        try:
            from vishwa.code_intelligence import get_structure
            from pathlib import Path

            structure = get_structure(path)

            summary = f"[Summary of {Path(path).name}]\n"
            summary += f"Lines: {structure.total_lines}\n"
            summary += f"Language: {structure.language}\n"

            if structure.imports:
                summary += f"Imports ({len(structure.imports)}): "
                summary += ", ".join(structure.imports[:5])
                if len(structure.imports) > 5:
                    summary += f" ... and {len(structure.imports) - 5} more"
                summary += "\n"

            if structure.classes:
                summary += f"Classes ({len(structure.classes)}): "
                summary += ", ".join(name for name, _ in structure.classes[:5])
                if len(structure.classes) > 5:
                    summary += f" ... and {len(structure.classes) - 5} more"
                summary += "\n"

            if structure.functions:
                summary += f"Functions ({len(structure.functions)}): "
                summary += ", ".join(name for name, _ in structure.functions[:5])
                if len(structure.functions) > 5:
                    summary += f" ... and {len(structure.functions) - 5} more"
                summary += "\n"

            return summary

        except Exception:
            # Fallback: basic summary
            content = self.files_in_context.get(path, "")
            return f"[Summary of {path}]\nSize: {len(content)} chars\n"

    def _calculate_message_importance(self, msg_idx: int) -> int:
        """
        Calculate importance score for a message (0-100).

        Factors:
        - File modifications = very important
        - Errors = less important
        - Recency = more important
        - Referenced later = important
        """
        if msg_idx >= len(self.messages):
            return 0

        msg = self.messages[msg_idx]
        score = 50  # Base score

        # Modified files = very important
        if msg.role == "tool":
            content_lower = (msg.content or "").lower()
            if "success" in content_lower:
                if any(word in content_lower for word in ["wrote", "modified", "created", "replaced"]):
                    score += 40

        # Errors = less important (can be pruned)
        if msg.role == "tool" and msg.content and "error" in msg.content.lower():
            score -= 20

        # Recency = more important
        recency_factor = (msg_idx / max(len(self.messages), 1)) * 20
        score += recency_factor

        # User messages = important (preserve conversation)
        if msg.role == "user":
            score += 30

        # System messages with summaries = important
        if msg.role == "system" and "[Summary" in (msg.content or ""):
            score += 20

        return min(100, max(0, int(score)))

    def _prune_messages_by_importance(self) -> None:
        """
        Prune messages based on importance scores.

        Keeps most important messages, removes least important.
        """
        if len(self.messages) <= 20:
            return  # Don't prune if we have few messages

        # Calculate importance for all messages
        scored_messages = []
        for idx, msg in enumerate(self.messages):
            importance = self._calculate_message_importance(idx)
            scored_messages.append((importance, idx, msg))

        # Sort by importance (descending)
        scored_messages.sort(reverse=True)

        # Keep top 70% by importance, but at least 20 messages
        keep_count = max(20, int(len(scored_messages) * 0.7))
        messages_to_keep_indices = set(idx for _, idx, _ in scored_messages[:keep_count])

        # Always keep first user message (the task)
        for idx, msg in enumerate(self.messages):
            if msg.role == "user":
                messages_to_keep_indices.add(idx)
                break

        # Always keep last 10 messages (recent context)
        for idx in range(max(0, len(self.messages) - 10), len(self.messages)):
            messages_to_keep_indices.add(idx)

        # Rebuild messages list (preserve order)
        new_messages = []
        for idx, msg in enumerate(self.messages):
            if idx in messages_to_keep_indices:
                new_messages.append(msg)
            elif idx not in messages_to_keep_indices and idx > 0 and idx < len(self.messages) - 10:
                # Check if this is part of a sequence we're removing
                # Add a summary marker
                if not new_messages or new_messages[-1].role != "system":
                    summary_msg = Message(
                        role="system",
                        content="[Messages pruned - importance-based context management]"
                    )
                    new_messages.append(summary_msg)

        self.messages = new_messages

    def _aggressive_truncation(self) -> None:
        """
        Last resort: aggressively truncate to fit context.

        Only called if summarization and importance pruning aren't enough.
        """
        # Truncate long tool outputs
        for msg in self.messages:
            if msg.role == "tool" and msg.content and len(msg.content) > 1000:
                msg.content = msg.content[:1000] + "\n... (output truncated for context)"

        # If STILL too large, keep only essential messages
        if self.is_approaching_limit():
            # Keep first user message + last 15 messages
            first_user_msg = None
            for msg in self.messages:
                if msg.role == "user":
                    first_user_msg = msg
                    break

            recent_messages = self.messages[-15:]

            self.messages = []
            if first_user_msg and first_user_msg not in recent_messages:
                self.messages.append(first_user_msg)

            # Add summary of what was removed
            summary_msg = Message(
                role="system",
                content=f"[Aggressive pruning: Removed {len(recent_messages)} messages to fit context]"
            )
            self.messages.append(summary_msg)

            self.messages.extend(recent_messages)

    def get_summary(self) -> str:
        """
        Get summary of current context.

        Returns:
            Human-readable summary
        """
        return f"""Context Summary:
- Messages: {len(self.messages)}
- Files in context: {list(self.files_in_context.keys())}
- Modifications: {len(self.modifications)}
- Estimated tokens: {self.estimate_tokens()}/{self.max_tokens}
- Recent tools: {[out['tool'] for out in self.recent_tool_outputs]}
"""

    def get_last_tool_result(self, tool_name: Optional[str] = None) -> Optional[ToolResult]:
        """
        Get the last tool result, optionally filtered by tool name.

        Args:
            tool_name: Optional tool name to filter by

        Returns:
            Last matching tool result or None
        """
        for output in reversed(self.recent_tool_outputs):
            if tool_name is None or output["tool"] == tool_name:
                return output["result"]
        return None

    def clear(self) -> None:
        """Clear all context (for new task)"""
        self.messages.clear()
        self.files_in_context.clear()
        self.modifications.clear()
        self.recent_tool_outputs.clear()
        self.created_files.clear()
        self.file_summaries.clear()
        self.message_importance.clear()
        logger.context_clear()
