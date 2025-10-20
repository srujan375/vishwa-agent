"""
File operation tools.

Implements:
- read_file: Read file contents (with optional line ranges)
- str_replace: Surgical edits via exact string replacement
- write_file: Create new files (only, never overwrites)
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from vishwa.tools.base import ExactMatchNotFoundError, Tool, ToolResult


class ReadFileTool(Tool):
    """
    Read file contents, optionally with line range.

    Lazy reading strategy:
    - Read only what's needed
    - Use line ranges for large files
    - Return line-numbered output for easy reference
    """

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return """Read contents of a file.

Use this to:
- Read source code files
- Check current implementation before modifying
- Understand file structure
- Get exact strings for str_replace operations

Optional parameters:
- start_line: Line number to start reading from (1-indexed)
- end_line: Line number to stop reading at (inclusive)

Returns line-numbered content (format: "line_number: content").
This makes it easy to reference specific lines for editing.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative or absolute)",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional: Line number to start reading from (1-indexed)",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional: Line number to stop reading at (inclusive)",
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Read file contents.

        Args:
            path: File path to read
            start_line: Optional starting line (1-indexed)
            end_line: Optional ending line (inclusive)

        Returns:
            ToolResult with file contents or error
        """
        self.validate_params(**kwargs)
        path = kwargs["path"]
        start_line = kwargs.get("start_line")
        end_line = kwargs.get("end_line")

        try:
            # Resolve path
            file_path = Path(path)
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {path}",
                    suggestion="Use bash tool to search for the file (e.g., 'find . -name filename')",
                )

            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    error=f"Path is not a file: {path}",
                    suggestion="Provide a file path, not a directory",
                )

            # Read file
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Apply line range if specified
            total_lines = len(lines)
            if start_line is not None or end_line is not None:
                start = (start_line - 1) if start_line else 0
                end = end_line if end_line else total_lines

                # Validate range
                if start < 0 or end > total_lines or start >= end:
                    return ToolResult(
                        success=False,
                        error=f"Invalid line range: {start_line}-{end_line} (file has {total_lines} lines)",
                        suggestion=f"Use a valid range between 1 and {total_lines}",
                    )

                lines = lines[start:end]
                line_offset = start
            else:
                line_offset = 0

            # Format with line numbers
            numbered_lines = [
                f"{i + line_offset + 1:4d} | {line.rstrip()}"
                for i, line in enumerate(lines)
            ]
            content = "\n".join(numbered_lines)

            return ToolResult(
                success=True,
                output=content,
                metadata={
                    "path": str(file_path),
                    "total_lines": total_lines,
                    "lines_read": len(lines),
                    "start_line": line_offset + 1,
                    "end_line": line_offset + len(lines),
                },
            )

        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                error=f"Cannot read file (not a text file): {path}",
                suggestion="This appears to be a binary file",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to read file: {str(e)}",
                metadata={"path": path},
            )


class StrReplaceTool(Tool):
    """
    Surgical file editing via exact string replacement.

    CRITICAL: Requires EXACT string match. This is the core philosophy
    of Vishwa - never rewrite entire files, only replace what changed.
    """

    @property
    def name(self) -> str:
        return "str_replace"

    @property
    def description(self) -> str:
        return """Replace an exact string in a file with new content.

CRITICAL REQUIREMENTS:
- old_str must match EXACTLY (including whitespace, indentation)
- old_str must appear only ONCE in the file (unique match)
- Use read_file first to get the exact string

This is a surgical edit tool - it never rewrites entire files.

Steps for successful use:
1. Use read_file to see current content
2. Copy the EXACT text you want to replace (including all whitespace)
3. Provide the new text
4. Tool will verify exact match and replace

Example:
old_str = "def login(user):\\n    return user"  # Exact match including \\n
new_str = "def login(user):\\n    verify_token()\\n    return user"
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to modify",
                },
                "old_str": {
                    "type": "string",
                    "description": "Exact string to replace (must match exactly, including whitespace)",
                },
                "new_str": {
                    "type": "string",
                    "description": "New string to replace with",
                },
            },
            "required": ["path", "old_str", "new_str"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Replace exact string in file.

        Args:
            path: File path to modify
            old_str: Exact string to find and replace
            new_str: Replacement string

        Returns:
            ToolResult with success/failure

        Raises:
            ExactMatchNotFoundError: If old_str not found or not unique
        """
        self.validate_params(**kwargs)
        path = kwargs["path"]
        old_str = kwargs["old_str"]
        new_str = kwargs["new_str"]

        try:
            # Read file
            file_path = Path(path)
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {path}",
                    suggestion="Use bash/grep to find the file first",
                )

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for exact match
            if old_str not in content:
                # Check if it's a whitespace issue
                old_str_stripped = old_str.strip()
                content_normalized = content.replace(" \n", "\n").replace("\t\n", "\n")

                suggestion = "Use read_file to get the exact string (including all whitespace)"
                if old_str_stripped in content or old_str in content_normalized:
                    suggestion = (
                        "Whitespace mismatch detected! The text exists but whitespace differs.\n"
                        "- The file may have trailing spaces or different indentation\n"
                        "- Use read_file to see the EXACT content with all spaces\n"
                        "- Copy the exact string including trailing whitespace"
                    )

                return ToolResult(
                    success=False,
                    error=f"Exact string not found in file",
                    suggestion=suggestion,
                    metadata={
                        "path": path,
                        "old_str_preview": old_str[:100] + "..." if len(old_str) > 100 else old_str,
                        "whitespace_issue": old_str_stripped in content,
                    },
                )

            # Check for unique match
            occurrences = content.count(old_str)
            if occurrences > 1:
                return ToolResult(
                    success=False,
                    error=f"String appears {occurrences} times in file (must be unique)",
                    suggestion="Provide a larger context string that appears only once",
                    metadata={"path": path, "occurrences": occurrences},
                )

            # Perform replacement
            new_content = content.replace(old_str, new_str, 1)

            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # Calculate diff stats
            old_lines = len(old_str.splitlines())
            new_lines = len(new_str.splitlines())

            return ToolResult(
                success=True,
                output=f"Successfully replaced {old_lines} line(s) with {new_lines} line(s)",
                metadata={
                    "path": str(file_path),
                    "old_lines": old_lines,
                    "new_lines": new_lines,
                    "chars_removed": len(old_str),
                    "chars_added": len(new_str),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to modify file: {str(e)}",
                metadata={"path": path},
            )


class WriteFileTool(Tool):
    """
    Create new files.

    IMPORTANT: This tool will NOT overwrite existing files.
    Use str_replace for modifying existing files.
    """

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return """Create a new file with given content.

IMPORTANT: This tool only creates NEW files.
- Will NOT overwrite existing files
- Use str_replace to modify existing files
- Creates parent directories if needed

Use this for:
- Creating new source files
- Creating configuration files
- Creating test files
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path for the new file",
                },
                "content": {
                    "type": "string",
                    "description": "File content",
                },
            },
            "required": ["path", "content"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Create a new file.

        Args:
            path: Path for new file
            content: File content

        Returns:
            ToolResult with success/failure
        """
        self.validate_params(**kwargs)
        path = kwargs["path"]
        content = kwargs["content"]

        try:
            file_path = Path(path)

            # Check if file already exists
            if file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File already exists: {path}",
                    suggestion="Use str_replace to modify existing files",
                )

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            lines = len(content.splitlines())
            chars = len(content)

            return ToolResult(
                success=True,
                output=f"Created file with {lines} lines ({chars} characters)",
                metadata={
                    "path": str(file_path),
                    "lines": lines,
                    "chars": chars,
                    "content": content,  # Include content for preview
                    "is_new_file": True,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to create file: {str(e)}",
                metadata={"path": path},
            )
