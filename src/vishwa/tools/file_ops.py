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

from vishwa.tools.base import ExactMatchNotFoundError, Tool, ToolResult, ApprovableTool


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

Reads up to 2000 lines by default from the beginning of the file.
You can specify start_line and end_line to read specific ranges.

Returns line-numbered content (cat -n format) making it easy to reference specific lines.

Optional parameters:
- start_line: Line number to start reading from (1-indexed)
- end_line: Line number to stop reading at (inclusive)
- show_whitespace: Show exact whitespace with repr() for debugging str_replace issues

IMPORTANT for str_replace:
- You MUST read the file first to get exact strings
- When preserving indentation from Read output, note the line number prefix format
- Line prefix is: spaces + line number + tab
- Everything AFTER the tab is the actual file content to match
- NEVER include the line number prefix in old_str or new_str

Use show_whitespace=true when str_replace fails with whitespace mismatch.
This shows exact spacing including trailing spaces and tabs.
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
                "show_whitespace": {
                    "type": "boolean",
                    "description": "Optional: Show exact whitespace with visible markers (use when str_replace fails)",
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
            show_whitespace: Show exact whitespace with repr()

        Returns:
            ToolResult with file contents or error
        """
        self.validate_params(**kwargs)
        path = kwargs["path"]
        start_line = kwargs.get("start_line")
        end_line = kwargs.get("end_line")
        show_whitespace = kwargs.get("show_whitespace", False)

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
            if show_whitespace:
                # Show exact content with visible whitespace
                numbered_lines = [
                    f"{i + line_offset + 1:4d} | {repr(line)}"
                    for i, line in enumerate(lines)
                ]
                content = "\n".join(numbered_lines)
                content += "\n\n[Whitespace visible mode: \\n=newline, \\t=tab, spaces shown as-is]"
            else:
                # Normal mode: strip trailing whitespace for readability
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


class StrReplaceTool(ApprovableTool):
    """
    Surgical file editing via exact string replacement.

    CRITICAL: Requires EXACT string match. This is the core philosophy
    of Vishwa - never rewrite entire files, only replace what changed.

    WHEN TO USE:
    - Small, localized edits (1-20 lines)
    - Modifying existing code
    - Surgical bug fixes or refactoring

    WHEN NOT TO USE (use write_file instead):
    - Adding multiple new functions to a file
    - Extensive changes (> 30% of file)
    - Whitespace matching keeps failing
    """

    @property
    def name(self) -> str:
        return "str_replace"

    @property
    def description(self) -> str:
        return """Performs exact string replacements in files.

CRITICAL: You MUST use Read tool at least once before editing.
This tool will error if you attempt an edit without reading the file.

EXACT MATCHING REQUIREMENTS:
- old_str must match EXACTLY (character-by-character)
- Preserve exact indentation (tabs/spaces) as it appears AFTER the line number prefix
- The edit will FAIL if old_str is not unique in the file
- Either provide larger string with more context or use replace_all=true

Line number format in Read output: spaces + line number + tab
Everything after that tab is the actual file content to match.
Never include any part of the line number prefix in old_str or new_str.

USAGE:
1. Read the file with read_file first
2. Copy the EXACT string to replace (including all whitespace)
3. Provide the new string
4. Tool verifies exact match and replaces

Use replace_all=true for replacing and renaming strings across the file.
This is useful for renaming variables.

WHEN TO USE:
- Small, localized edits (1-20 lines)
- Modifying existing code
- Surgical bug fixes or refactoring

WHEN NOT TO USE (use write_file or multi_edit instead):
- Adding multiple new functions to a file
- Extensive changes (> 30% of file)
- Whitespace matching keeps failing
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

    def generate_preview(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Generate preview of the replacement without applying it.

        Returns preview data containing old content, new content, and metadata.
        """
        path = kwargs["path"]
        old_str = kwargs["old_str"]
        new_str = kwargs["new_str"]

        # Read file
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for exact match
        if old_str not in content:
            # Check if it's a whitespace issue
            old_str_stripped = old_str.strip()
            content_normalized = content.replace(" \n", "\n").replace("\t\n", "\n")

            # Provide helpful diagnostic info
            error_details = []

            if old_str_stripped in content or old_str in content_normalized:
                error_details.append("⚠️  WHITESPACE MISMATCH DETECTED")
                error_details.append("The text exists but whitespace differs.")
                error_details.append("")
                error_details.append("Common causes:")
                error_details.append("- Trailing spaces in docstrings")
                error_details.append("- Tabs vs spaces")
                error_details.append("- Mixed line endings (\\r\\n vs \\n)")
                error_details.append("")
                error_details.append("Solutions:")
                error_details.append("1. Use read_file(path=..., show_whitespace=True) to see EXACT whitespace")
                error_details.append("2. Use a SMALLER, more unique string (e.g., just one line)")
                error_details.append("3. Use write_file instead for full file rewrites")
            else:
                # String doesn't exist at all
                error_details.append("String not found anywhere in the file.")
                error_details.append("")
                error_details.append(f"Looking for: {repr(old_str[:100])}")
                error_details.append("")
                error_details.append("Possible reasons:")
                error_details.append("- File was modified since you read it")
                error_details.append("- Wrong file path")
                error_details.append("- String was already replaced in a previous step")
                error_details.append("- You're trying to replace text that doesn't exactly match")
                error_details.append("")
                error_details.append("Next steps:")
                error_details.append("1. Use read_file to verify current file content")
                error_details.append("2. Try a SMALLER, more unique string (e.g., just the function name)")
                error_details.append("3. Use write_file(overwrite=true) to rewrite the entire file")

            raise ExactMatchNotFoundError("\n".join(error_details))

        # Check for unique match
        occurrences = content.count(old_str)
        if occurrences > 1:
            raise ValueError(
                f"String appears {occurrences} times in file (must be unique). "
                "Provide a larger context string that appears only once"
            )

        # Generate new content (but don't write yet)
        new_content = content.replace(old_str, new_str, 1)

        return {
            "path": file_path,
            "old_content": content,
            "new_content": new_content,
            "old_str": old_str,
            "new_str": new_str,
        }

    def show_preview(self, preview_data: Dict[str, Any], **kwargs: Any) -> None:
        """Show diff preview to user."""
        from vishwa.cli.ui import show_diff

        path = preview_data["path"]
        old_content = preview_data["old_content"]
        new_content = preview_data["new_content"]

        show_diff(str(path), old_content, new_content)

    def get_approval(self, preview_data: Dict[str, Any], **kwargs: Any) -> bool:
        """Ask user for approval to apply changes."""
        from vishwa.cli.ui import confirm_action

        path = preview_data["path"]
        return confirm_action(f"Apply changes to '{path.name}'?", default=False)

    def apply_changes(self, preview_data: Dict[str, Any], **kwargs: Any) -> ToolResult:
        """Apply the replacement after approval."""
        path = preview_data["path"]
        new_content = preview_data["new_content"]
        old_str = preview_data["old_str"]
        new_str = preview_data["new_str"]

        try:
            # Write the new content
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # Calculate diff stats
            old_lines = len(old_str.splitlines())
            new_lines = len(new_str.splitlines())

            return ToolResult(
                success=True,
                output=f"Successfully replaced {old_lines} line(s) with {new_lines} line(s) in {path.name}",
                metadata={
                    "path": str(path),
                    "old_lines": old_lines,
                    "new_lines": new_lines,
                    "chars_removed": len(old_str),
                    "chars_added": len(new_str),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to write file: {str(e)}",
                metadata={"path": str(path)},
            )


class WriteFileTool(ApprovableTool):
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
        return """Create a new file or completely rewrite an existing file.

USE CASES:
- Creating new files
- Completely rewriting a file when str_replace fails repeatedly
- Adding many new functions to a small file

REQUIREMENTS:
- Must use read_file first on existing files; this tool fails otherwise
- Overwrites existing files completely when overwrite=true
- Creates parent directories automatically if needed

WHEN TO USE:
- Creating new files
- Completely rewriting a file when str_replace fails repeatedly (use overwrite=true)
- Adding many new functions to a small file (use overwrite=true)

WHEN NOT TO USE:
- Small edits to existing files (use str_replace instead)
- Making surgical changes (use str_replace or multi_edit)

IMPORTANT:
- By default, will NOT overwrite existing files (safe mode)
- Set overwrite=true to rewrite existing files (requires approval)
- Only use emojis if user explicitly requests it
- Avoid creating new files unless absolutely necessary - ALWAYS prefer editing existing files
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
                "overwrite": {
                    "type": "boolean",
                    "description": "Allow overwriting existing files (default: false). Use when str_replace fails repeatedly.",
                },
            },
            "required": ["path", "content"],
        }

    def generate_preview(self, **kwargs: Any) -> Dict[str, Any]:
        """Generate preview for file creation/overwrite."""
        path = kwargs["path"]
        content = kwargs["content"]
        overwrite = kwargs.get("overwrite", False)

        file_path = Path(path)

        # Check if file already exists
        if file_path.exists() and not overwrite:
            raise ValueError(
                f"File already exists: {path}. "
                "Use str_replace for small edits, or set overwrite=true to completely rewrite the file"
            )

        # Read old content if overwriting
        old_content = ""
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                old_content = f.read()

        return {
            "path": file_path,
            "content": content,
            "old_content": old_content,
            "overwrite": overwrite,
            "is_new": not file_path.exists(),
        }

    def show_preview(self, preview_data: Dict[str, Any], **kwargs: Any) -> None:
        """Show file preview to user."""
        from vishwa.cli.ui import show_diff, show_file_preview_in_vscode, is_vscode
        from rich.console import Console

        console = Console()
        path = preview_data["path"]
        content = preview_data["content"]
        is_new = preview_data["is_new"]
        overwrite = preview_data["overwrite"]

        if is_new:
            console.print(f"\n[bold]Creating new file:[/bold] {path}")
        else:
            console.print(f"\n[bold]Overwriting file:[/bold] {path}")

        # Show diff if overwriting, otherwise show preview
        if not is_new:
            show_diff(str(path), preview_data["old_content"], content)
        else:
            # Try VS Code preview first
            if is_vscode():
                show_file_preview_in_vscode(str(path), content)

            # Also show summary in terminal
            lines = content.split('\n')
            console.print(f"Total: {len(lines)} lines, {len(content)} characters")

    def get_approval(self, preview_data: Dict[str, Any], **kwargs: Any) -> bool:
        """Ask user for approval."""
        from vishwa.cli.ui import confirm_action

        path = preview_data["path"]
        is_new = preview_data["is_new"]

        if is_new:
            return confirm_action(f"Create file '{path.name}'?", default=False)
        else:
            return confirm_action(f"Overwrite file '{path.name}'?", default=False)

    def apply_changes(self, preview_data: Dict[str, Any], **kwargs: Any) -> ToolResult:
        """Apply the file creation/overwrite."""
        path = preview_data["path"]
        content = preview_data["content"]
        is_new = preview_data["is_new"]

        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            lines = len(content.splitlines())
            chars = len(content)
            action = "Created" if is_new else "Overwrote"

            return ToolResult(
                success=True,
                output=f"{action} {path.name} with {lines} lines ({chars} characters)",
                metadata={
                    "path": str(path),
                    "lines": lines,
                    "chars": chars,
                    "is_new_file": is_new,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to write file: {str(e)}",
                metadata={"path": str(path)},
            )


class MultiEditTool(ApprovableTool):
    """
    Apply multiple edits to a file atomically.

    All edits are applied sequentially. If any edit fails, all changes are rolled back.
    This ensures file consistency - either all edits succeed or none do.
    """

    @property
    def name(self) -> str:
        return "multi_edit"

    @property
    def description(self) -> str:
        return """Apply multiple string replacements to a file atomically.

USE CASES:
- Making several related changes to one file
- Avoiding multiple approval prompts
- Ensuring all-or-nothing edits (atomic transactions)

IMPORTANT:
- All edits must succeed or file remains unchanged
- Edits are applied sequentially (later edits see earlier changes)
- Each old_str must be unique in the file
- Use read_file first to verify exact strings

Example:
edits = [
    {"old_str": "def foo():", "new_str": "def bar():"},
    {"old_str": "return 1", "new_str": "return 2"}
]

This is more efficient than multiple str_replace calls and ensures atomicity.
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
                "edits": {
                    "type": "array",
                    "description": "Array of edit operations to apply sequentially",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_str": {
                                "type": "string",
                                "description": "Exact string to replace",
                            },
                            "new_str": {
                                "type": "string",
                                "description": "Replacement string",
                            },
                            "replace_all": {
                                "type": "boolean",
                                "description": "Replace all occurrences (default: false)",
                            },
                        },
                        "required": ["old_str", "new_str"],
                    },
                },
            },
            "required": ["path", "edits"],
        }

    def generate_preview(self, **kwargs: Any) -> Dict[str, Any]:
        """Generate preview by applying all edits to get new content."""
        path = kwargs["path"]
        edits = kwargs["edits"]

        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Read original content
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        # Apply edits sequentially to generate preview
        current_content = original_content
        applied_edits = []

        for i, edit in enumerate(edits, 1):
            old_str = edit["old_str"]
            new_str = edit["new_str"]
            replace_all = edit.get("replace_all", False)

            # Check if old_str exists
            if old_str not in current_content:
                raise ValueError(
                    f"Edit #{i} failed: Exact string not found in file. "
                    f"String '{old_str[:50]}...' not found after {i-1} edits. "
                    "Use read_file to verify current content."
                )

            # Check uniqueness unless replace_all
            if not replace_all:
                occurrences = current_content.count(old_str)
                if occurrences > 1:
                    raise ValueError(
                        f"Edit #{i} failed: String appears {occurrences} times. "
                        "Use replace_all=true or provide more context"
                    )

            # Apply replacement
            if replace_all:
                current_content = current_content.replace(old_str, new_str)
            else:
                current_content = current_content.replace(old_str, new_str, 1)

            applied_edits.append(f"Edit #{i}: {len(old_str)} → {len(new_str)} chars")

        return {
            "path": file_path,
            "old_content": original_content,
            "new_content": current_content,
            "edits": edits,
            "edit_details": applied_edits,
        }

    def show_preview(self, preview_data: Dict[str, Any], **kwargs: Any) -> None:
        """Show cumulative diff of all edits."""
        from vishwa.cli.ui import show_diff
        from rich.console import Console

        console = Console()
        path = preview_data["path"]
        old_content = preview_data["old_content"]
        new_content = preview_data["new_content"]
        num_edits = len(preview_data["edits"])

        console.print(f"\n[bold]Applying {num_edits} edit(s) to:[/bold] {path}")
        show_diff(str(path), old_content, new_content)

    def get_approval(self, preview_data: Dict[str, Any], **kwargs: Any) -> bool:
        """Ask user for approval."""
        from vishwa.cli.ui import confirm_action

        path = preview_data["path"]
        num_edits = len(preview_data["edits"])
        return confirm_action(
            f"Apply {num_edits} edit(s) to '{path.name}'?", default=False
        )

    def apply_changes(self, preview_data: Dict[str, Any], **kwargs: Any) -> ToolResult:
        """Apply all edits after approval."""
        path = preview_data["path"]
        new_content = preview_data["new_content"]
        old_content = preview_data["old_content"]
        edit_details = preview_data["edit_details"]
        num_edits = len(preview_data["edits"])

        try:
            # Write the new content
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return ToolResult(
                success=True,
                output=f"Successfully applied {num_edits} edit(s) to {path.name}",
                metadata={
                    "path": str(path),
                    "edits_applied": num_edits,
                    "total_changes": len(new_content) - len(old_content),
                    "edit_details": edit_details,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to write file: {str(e)}",
                metadata={"path": str(path)},
            )
