"""
Base classes for Vishwa tools.

Defines the Tool interface and ToolRegistry for managing tools.
All tools use OpenAI's function calling format internally.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ToolResult:
    """Result from tool execution"""

    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    suggestion: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        if self.success:
            return f"Success: {self.output}"
        else:
            msg = f"Error: {self.error}"
            if self.suggestion:
                msg += f"\nSuggestion: {self.suggestion}"
            return msg


class Tool(ABC):
    """
    Abstract base class for all Vishwa tools.

    Each tool must implement:
    - name: Unique identifier
    - description: What the tool does (used by LLM)
    - parameters: JSON Schema (OpenAI format)
    - execute: The actual tool logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name (e.g., 'bash', 'read_file')"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Description of what the tool does.
        This is shown to the LLM to help it decide when to use the tool.
        """
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        JSON Schema for tool parameters (OpenAI format).

        Example:
        {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                }
            },
            "required": ["command"]
        }
        """
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Parameters matching the JSON schema

        Returns:
            ToolResult: Success/failure with output or error
        """
        pass

    def to_openai_format(self) -> Dict[str, Any]:
        """
        Convert tool to OpenAI function calling format.

        This is the internal standard format used by Vishwa.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def validate_params(self, **kwargs: Any) -> None:
        """
        Validate parameters against the schema.

        Raises:
            ValueError: If required parameters are missing
        """
        required = self.parameters.get("required", [])
        for param in required:
            if param not in kwargs:
                raise ValueError(
                    f"Missing required parameter: {param} for tool {self.name}"
                )


class ApprovableTool(Tool):
    """
    Abstract base class for tools that require user approval.

    This implements Claude Code's approval pattern where:
    1. Tool generates a preview of changes (without applying)
    2. Shows the preview to the user (e.g., diff)
    3. Asks for approval
    4. Applies changes only if approved

    The approval logic is inside the tool execution, not in the agent loop.
    """

    def __init__(self, auto_approve: bool = False):
        """
        Initialize approvable tool.

        Args:
            auto_approve: If True, skip approval and apply changes automatically
        """
        self.auto_approve = auto_approve

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute tool with approval workflow.

        This implements the standard approval pattern:
        1. Validate parameters
        2. Generate preview
        3. Show preview to user
        4. Get approval
        5. Apply changes if approved

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult with success/failure
        """
        self.validate_params(**kwargs)

        try:
            # Step 1: Generate preview (without applying changes)
            preview_data = self.generate_preview(**kwargs)

            # Step 2: Show preview to user
            self.show_preview(preview_data, **kwargs)

            # Step 3: Get approval (skip if auto_approve)
            if not self.auto_approve:
                if not self.get_approval(preview_data, **kwargs):
                    # User rejected - return error with their feedback
                    feedback = self.get_rejection_feedback(**kwargs)
                    return ToolResult(
                        success=False,
                        error="User rejected the changes",
                        suggestion=feedback if feedback else "User did not provide feedback",
                    )

            # Step 4: Apply the changes
            return self.apply_changes(preview_data, **kwargs)

        except ExactMatchNotFoundError as e:
            # Preserve detailed error message for exact match failures
            return ToolResult(
                success=False,
                error=str(e),
                suggestion="Re-read the file or try a different approach",
            )
        except ValueError as e:
            # Preserve detailed error message for validation failures
            return ToolResult(
                success=False,
                error=str(e),
                suggestion="Check the parameters and try again",
            )
        except FileNotFoundError as e:
            return ToolResult(
                success=False,
                error=str(e),
                suggestion="Verify the file path is correct",
            )
        except Exception as e:
            # Generic error for unexpected issues
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
            )

    @abstractmethod
    def generate_preview(self, **kwargs: Any) -> Any:
        """
        Generate a preview of changes without applying them.

        This should compute what will change but not modify any files.

        Args:
            **kwargs: Tool parameters

        Returns:
            Preview data (format depends on tool - could be diff, new content, etc.)
        """
        pass

    def show_preview(self, preview_data: Any, **kwargs: Any) -> None:
        """
        Show preview to user.

        Default implementation does nothing. Override to show diffs, previews, etc.

        Args:
            preview_data: Preview data from generate_preview()
            **kwargs: Tool parameters
        """
        pass

    def get_approval(self, preview_data: Any, **kwargs: Any) -> bool:
        """
        Ask user for approval.

        Default implementation uses confirm_action from ui.py.
        Override for custom approval prompts.

        Args:
            preview_data: Preview data from generate_preview()
            **kwargs: Tool parameters

        Returns:
            True if user approved, False otherwise
        """
        from vishwa.cli.ui import confirm_action

        # Default approval message
        tool_name = self.name
        return confirm_action(f"Execute {tool_name}?", default=False)

    def get_rejection_feedback(self, **kwargs: Any) -> Optional[str]:
        """
        Ask user for feedback when they reject changes.

        This helps the agent understand what to change.

        Args:
            **kwargs: Tool parameters

        Returns:
            User feedback as string, or None if no feedback
        """
        from rich.console import Console
        from prompt_toolkit import prompt as pt_prompt

        console = Console()
        console.print("\n[yellow]💬 Help me understand:[/yellow]")
        console.print("[dim]What would you like me to change about this approach?[/dim]")
        console.print("[dim](Press Enter to skip)[/dim]\n")

        try:
            feedback = pt_prompt("Your feedback: ", multiline=False)
            return feedback.strip() if feedback.strip() else None
        except (KeyboardInterrupt, EOFError):
            return None

    @abstractmethod
    def apply_changes(self, preview_data: Any, **kwargs: Any) -> ToolResult:
        """
        Apply the changes after approval.

        This is where the actual file writes or destructive operations happen.

        Args:
            preview_data: Preview data from generate_preview()
            **kwargs: Tool parameters

        Returns:
            ToolResult with success/failure
        """
        pass


class ToolRegistry:
    """
    Registry for managing all available tools.

    Provides methods to register, retrieve, and list tools.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tools.get(name)

    def list_names(self) -> List[str]:
        """List all registered tool names"""
        return list(self._tools.keys())

    def all(self) -> List[Tool]:
        """Get all registered tools"""
        return list(self._tools.values())

    def to_openai_format(self) -> List[Dict[str, Any]]:
        """Convert all tools to OpenAI format for LLM"""
        return [tool.to_openai_format() for tool in self._tools.values()]

    @classmethod
    def load_default(cls, auto_approve: bool = False) -> "ToolRegistry":
        """
        Load the default set of Vishwa tools.

        Args:
            auto_approve: If True, tools will skip approval prompts (default: False)

        Returns:
            ToolRegistry with all core tools registered
        """
        from vishwa.tools.bash import BashTool
        from vishwa.tools.file_ops import ReadFileTool, StrReplaceTool, WriteFileTool, MultiEditTool
        from vishwa.tools.git_ops import GitDiffTool, GitRestoreTool
        from vishwa.tools.search import GlobTool, GrepTool
        from vishwa.tools.web import WebFetchTool, WebSearchTool
        from vishwa.tools.todo import TodoWriteTool
        from vishwa.tools.analyze import AnalyzeStructureTool, AnalyzeDependenciesTool, ReadSymbolTool
        from vishwa.tools.codebase_explorer import CodebaseExplorerTool

        registry = cls()

        # Tools that don't need approval
        registry.register(ReadFileTool())
        registry.register(GlobTool())
        registry.register(GrepTool())
        registry.register(GitDiffTool())
        registry.register(GitRestoreTool())
        registry.register(WebFetchTool())
        registry.register(WebSearchTool())
        registry.register(TodoWriteTool())

        # Code intelligence tools
        registry.register(AnalyzeStructureTool())
        registry.register(AnalyzeDependenciesTool())
        registry.register(ReadSymbolTool())

        # High-level exploration tool (reduces iteration count)
        registry.register(CodebaseExplorerTool())

        # Tools that support approval (ApprovableTool subclasses)
        registry.register(StrReplaceTool(auto_approve=auto_approve))
        registry.register(WriteFileTool(auto_approve=auto_approve))
        registry.register(MultiEditTool(auto_approve=auto_approve))
        registry.register(BashTool(auto_approve=auto_approve))

        return registry


# Exceptions
class ToolNotFoundError(Exception):
    """Raised when a tool is not found in the registry"""

    pass


class ToolExecutionError(Exception):
    """Raised when tool execution fails"""

    pass


class ExactMatchNotFoundError(ToolExecutionError):
    """Raised when str_replace cannot find exact match"""

    pass
