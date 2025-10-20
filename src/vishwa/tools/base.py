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
    def load_default(cls) -> "ToolRegistry":
        """
        Load the default set of Vishwa tools.

        Returns:
            ToolRegistry with all 5 core tools registered
        """
        from vishwa.tools.bash import BashTool
        from vishwa.tools.file_ops import ReadFileTool, StrReplaceTool, WriteFileTool
        from vishwa.tools.git_ops import GitDiffTool

        registry = cls()
        registry.register(BashTool())
        registry.register(ReadFileTool())
        registry.register(StrReplaceTool())
        registry.register(WriteFileTool())
        registry.register(GitDiffTool())

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
