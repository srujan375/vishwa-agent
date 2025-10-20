"""
Tools module - Implementation of the 5 core tools for the agent.

Core tools:
1. bash - Execute shell commands (grep, find, pytest, etc.)
2. read_file - Lazy file reading with optional line ranges
3. str_replace - Exact string replacement edits
4. write_file - Create new files only
5. git_diff - Show changes
"""

from vishwa.tools.base import Tool, ToolRegistry
from vishwa.tools.bash import BashTool
from vishwa.tools.file_ops import ReadFileTool, StrReplaceTool, WriteFileTool
from vishwa.tools.git_ops import GitDiffTool

__all__ = [
    "Tool",
    "ToolRegistry",
    "BashTool",
    "ReadFileTool",
    "StrReplaceTool",
    "WriteFileTool",
    "GitDiffTool",
]
