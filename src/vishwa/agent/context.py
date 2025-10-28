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

        Rough estimate: ~4 characters per token
        More accurate: use tiktoken library (optional dependency)

        Returns:
            Estimated token count
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

        Strategy:
        1. Remove old file contents (keep modified ones)
        2. Remove older messages, keeping only recent context
        3. Keep first user message (the task) and last 15 messages
        """
        if not self.is_approaching_limit():
            return

        before_tokens = self.estimate_tokens()

        # Step 1: Remove non-modified files
        modified_files = {mod.file_path for mod in self.modifications}
        for path in list(self.files_in_context.keys()):
            if path not in modified_files:
                del self.files_in_context[path]

        # Step 2: If still too large, aggressively prune messages
        if self.is_approaching_limit() and len(self.messages) > 15:
            # Keep first user message (the task) and last 14 messages
            first_user_msg = None
            for msg in self.messages:
                if msg.role == "user":
                    first_user_msg = msg
                    break

            recent_messages = self.messages[-14:]

            self.messages = []
            if first_user_msg and first_user_msg not in recent_messages:
                self.messages.append(first_user_msg)
            self.messages.extend(recent_messages)

        # Step 3: If STILL too large, truncate tool results in remaining messages
        if self.is_approaching_limit():
            for msg in self.messages:
                if msg.role == "tool" and msg.content and len(msg.content) > 1000:
                    # Truncate long tool outputs to 1000 chars
                    msg.content = msg.content[:1000] + "\n... (output truncated)"

        after_tokens = self.estimate_tokens()
        logger.context_pruned(before_tokens, after_tokens)

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
        logger.context_clear()
