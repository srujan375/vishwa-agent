"""
Search tools for finding files and content.

Provides Glob and Grep functionality.
"""

import fnmatch
import re
from pathlib import Path
from typing import Any, Dict, List

from vishwa.tools.base import Tool, ToolResult


class GlobTool(Tool):
    """
    Fast file pattern matching tool.

    Works with any codebase size. Use this instead of bash find commands.
    """

    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return """Fast file pattern matching tool that works with any codebase size.

Supports glob patterns like "**/*.js" or "src/**/*.ts"
Returns matching file paths sorted by modification time.

USE THIS instead of bash find commands for better UX.

Examples:
- glob(pattern="**/*.py") - Find all Python files recursively
- glob(pattern="src/**/*.tsx") - Find all TSX files in src
- glob(pattern="*.md") - Find markdown files in current directory
- glob(pattern="test_*.py", path="tests/") - Find test files in tests dir

Parameters:
- pattern: Glob pattern to match (e.g., "**/*.py")
- path: Directory to search in (default: current directory)

Returns matching file paths, most recently modified first.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files against (e.g., '**/*.py', 'src/**/*.ts')",
                },
                "path": {
                    "type": "string",
                    "description": "Optional: Directory to search in (default: current directory)",
                },
            },
            "required": ["pattern"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Find files matching glob pattern.

        Args:
            pattern: Glob pattern
            path: Optional base directory

        Returns:
            ToolResult with matching file paths
        """
        self.validate_params(**kwargs)
        pattern = kwargs["pattern"]
        base_path = Path(kwargs.get("path", "."))

        try:
            if not base_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {base_path}",
                    suggestion="Verify the path exists",
                )

            if not base_path.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {base_path}",
                    suggestion="Provide a directory path",
                )

            # Find matching files
            matches = []

            if "**" in pattern:
                # Recursive glob
                for file_path in base_path.rglob(pattern.replace("**/", "")):
                    if file_path.is_file():
                        matches.append(file_path)
            else:
                # Non-recursive glob
                for file_path in base_path.glob(pattern):
                    if file_path.is_file():
                        matches.append(file_path)

            # Sort by modification time (most recent first)
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            if not matches:
                return ToolResult(
                    success=True,
                    output=f"No files found matching pattern: {pattern}",
                    metadata={
                        "pattern": pattern,
                        "base_path": str(base_path),
                        "count": 0,
                    },
                )

            # Format output
            file_list = "\n".join(str(p.relative_to(base_path)) for p in matches[:100])

            if len(matches) > 100:
                file_list += f"\n... and {len(matches) - 100} more files"

            return ToolResult(
                success=True,
                output=file_list,
                metadata={
                    "pattern": pattern,
                    "base_path": str(base_path),
                    "count": len(matches),
                    "files": [str(p) for p in matches[:100]],
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to search files: {str(e)}",
                metadata={"pattern": pattern, "base_path": str(base_path)},
            )


class GrepTool(Tool):
    """
    Powerful content search tool built on ripgrep patterns.

    ALWAYS use this for searching file contents. NEVER invoke bash grep/rg.
    """

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return """A powerful search tool for finding content in files.

ALWAYS use this for search tasks. NEVER invoke grep or rg as a bash command.

Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
Can filter files with glob parameter (e.g., "*.js", "**/*.tsx")

Output modes:
- "files" (default): Show only file paths containing matches
- "content": Show matching lines with context
- "count": Show match counts per file

Examples:
- grep(pattern="TODO", output_mode="files") - Find files with TODO
- grep(pattern="def.*test", glob="**/*.py", output_mode="content") - Find test functions
- grep(pattern="import React", glob="src/**/*.tsx") - Find React imports
- grep(pattern="error", output_mode="content", context=3) - Show errors with 3 lines context

Parameters:
- pattern: Regex pattern to search for
- path: Directory to search in (default: current directory)
- glob: Filter files by glob pattern (e.g., "*.py")
- output_mode: "files" (default), "content", or "count"
- context: Number of lines before/after match (only with output_mode="content")
- case_sensitive: True/False (default: True)
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Optional: Directory to search in (default: current directory)",
                },
                "glob": {
                    "type": "string",
                    "description": "Optional: Glob pattern to filter files (e.g., '*.js', '**/*.tsx')",
                },
                "output_mode": {
                    "type": "string",
                    "enum": ["files", "content", "count"],
                    "description": "Output format: 'files' (paths only), 'content' (matching lines), 'count' (match counts)",
                },
                "context": {
                    "type": "integer",
                    "description": "Number of context lines before/after match (only for output_mode='content')",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case-sensitive search (default: true)",
                },
            },
            "required": ["pattern"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Search file contents with regex pattern.

        Args:
            pattern: Regex pattern
            path: Base directory
            glob: File filter pattern
            output_mode: Output format
            context: Context lines
            case_sensitive: Case sensitivity

        Returns:
            ToolResult with search results
        """
        self.validate_params(**kwargs)
        pattern = kwargs["pattern"]
        base_path = Path(kwargs.get("path", "."))
        glob_pattern = kwargs.get("glob")
        output_mode = kwargs.get("output_mode", "files")
        context = kwargs.get("context", 0)
        case_sensitive = kwargs.get("case_sensitive", True)

        try:
            if not base_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {base_path}",
                    suggestion="Verify the path exists",
                )

            # Compile regex pattern
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                return ToolResult(
                    success=False,
                    error=f"Invalid regex pattern: {e}",
                    suggestion="Check your regex syntax",
                )

            # Get files to search
            if glob_pattern:
                files_to_search = []
                if "**" in glob_pattern:
                    for f in base_path.rglob(glob_pattern.replace("**/", "")):
                        if f.is_file():
                            files_to_search.append(f)
                else:
                    for f in base_path.glob(glob_pattern):
                        if f.is_file():
                            files_to_search.append(f)
            else:
                # Search all files recursively
                files_to_search = [f for f in base_path.rglob("*") if f.is_file()]

            # Search files
            results = {}
            for file_path in files_to_search:
                try:
                    # Skip binary files
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    matches = list(regex.finditer(content))
                    if matches:
                        if output_mode == "count":
                            results[file_path] = len(matches)
                        elif output_mode == "content":
                            lines = content.splitlines()
                            match_lines = []
                            for match in matches[:10]:  # Limit to 10 matches per file
                                line_num = content[:match.start()].count("\n")
                                start_line = max(0, line_num - context)
                                end_line = min(len(lines), line_num + context + 1)

                                match_lines.append({
                                    "line_num": line_num + 1,
                                    "line": lines[line_num],
                                    "context": lines[start_line:end_line],
                                })
                            results[file_path] = match_lines
                        else:  # files mode
                            results[file_path] = True

                except (UnicodeDecodeError, PermissionError):
                    # Skip files we can't read
                    continue

            if not results:
                return ToolResult(
                    success=True,
                    output=f"No matches found for pattern: {pattern}",
                    metadata={
                        "pattern": pattern,
                        "files_searched": len(files_to_search),
                        "matches": 0,
                    },
                )

            # Format output
            if output_mode == "files":
                output = "\n".join(str(p.relative_to(base_path)) for p in results.keys())
            elif output_mode == "count":
                output = "\n".join(
                    f"{p.relative_to(base_path)}: {count} matches"
                    for p, count in sorted(results.items(), key=lambda x: x[1], reverse=True)
                )
            else:  # content
                output_lines = []
                for file_path, matches in list(results.items())[:20]:  # Limit files
                    output_lines.append(f"\n{file_path.relative_to(base_path)}:")
                    for match in matches:
                        output_lines.append(f"  Line {match['line_num']}: {match['line']}")
                output = "\n".join(output_lines)

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "pattern": pattern,
                    "files_with_matches": len(results),
                    "output_mode": output_mode,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}",
                metadata={"pattern": pattern},
            )
