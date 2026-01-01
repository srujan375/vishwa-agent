"""
Search tools for finding files and content.

Provides Glob and Grep functionality with:
- Smart directory exclusions (venv, node_modules, .git, etc.)
- Early termination with head_limit
- Ripgrep backend for fast content search
- Proper glob pattern handling
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from vishwa.tools.base import Tool, ToolResult


# Default directories to exclude from searches
DEFAULT_EXCLUDES: Set[str] = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
    ".next",
    ".nuxt",
    "coverage",
    ".coverage",
    "htmlcov",
    ".hypothesis",
}


def _should_exclude(path: Path, excludes: Set[str]) -> bool:
    """Check if a path should be excluded based on exclude patterns."""
    for part in path.parts:
        if part in excludes:
            return True
        # Handle wildcard patterns like *.egg-info
        for exclude in excludes:
            if "*" in exclude:
                import fnmatch
                if fnmatch.fnmatch(part, exclude):
                    return True
    return False


class GlobTool(Tool):
    """
    Fast file pattern matching tool.

    Works with any codebase size. Use this instead of bash find commands.
    Features:
    - Proper ** glob pattern support
    - Smart exclusions (venv, node_modules, .git by default)
    - Early termination with head_limit
    - Custom exclude patterns
    """

    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return """Fast file pattern matching tool that works with any codebase size.

Supports glob patterns like "**/*.js" or "src/**/*.ts"
Returns matching file paths sorted by modification time.

AUTOMATICALLY EXCLUDES: venv, node_modules, .git, __pycache__, build, dist, etc.

Examples:
- glob(pattern="**/*.py") - Find all Python files
- glob(pattern="src/**/*.tsx") - Find TSX files in src/
- glob(pattern="**/*.py", head_limit=10) - Find first 10 Python files
- glob(pattern="**/*.js", exclude=["vendor"]) - Exclude vendor/ directory

Parameters:
- pattern: Glob pattern (e.g., "**/*.py", "src/**/*.ts")
- path: Directory to search (default: current directory)
- head_limit: Max files to return (default: 100, enables early exit)
- exclude: Additional directories to exclude (list)
- include_hidden: Include hidden files/dirs (default: false)
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (e.g., '**/*.py', 'src/**/*.ts')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
                "head_limit": {
                    "type": "integer",
                    "description": "Max number of files to return (enables early exit, default: 100)",
                },
                "exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional directories/patterns to exclude",
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden files and directories (default: false)",
                },
            },
            "required": ["pattern"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Find files matching glob pattern with smart exclusions.

        Args:
            pattern: Glob pattern
            path: Optional base directory
            head_limit: Max files to return (early exit)
            exclude: Additional exclusion patterns
            include_hidden: Whether to include hidden files

        Returns:
            ToolResult with matching file paths
        """
        self.validate_params(**kwargs)
        pattern = kwargs["pattern"]
        base_path = Path(kwargs.get("path", ".")).resolve()
        head_limit = kwargs.get("head_limit", 100)
        extra_excludes = set(kwargs.get("exclude", []))
        include_hidden = kwargs.get("include_hidden", False)

        # Combine default and custom excludes
        excludes = DEFAULT_EXCLUDES | extra_excludes

        # Check cache first (only for default params without extra excludes)
        cache_key_path = str(base_path)
        from_cache = False

        if self.context_store and not extra_excludes and not include_hidden:
            cached = self.context_store.get_glob(pattern, cache_key_path)
            if cached is not None:
                # Apply head_limit to cached results
                files = cached[:head_limit] if head_limit else cached
                truncated = len(cached) > head_limit if head_limit else False

                if not files:
                    return ToolResult(
                        success=True,
                        output=f"No files found matching pattern: {pattern}",
                        metadata={
                            "pattern": pattern,
                            "base_path": cache_key_path,
                            "count": 0,
                            "from_cache": True,
                        },
                    )

                file_list = "\n".join(files)
                if truncated:
                    file_list += f"\n... (limited to {head_limit} results)"

                return ToolResult(
                    success=True,
                    output=file_list,
                    metadata={
                        "pattern": pattern,
                        "base_path": cache_key_path,
                        "count": len(files),
                        "truncated": truncated,
                        "files": files,
                        "from_cache": True,
                    },
                )

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

            # Find matching files using pathlib.glob() directly
            # This properly handles ** patterns
            matches = []
            for file_path in base_path.glob(pattern):
                # Skip directories
                if not file_path.is_file():
                    continue

                # Skip excluded paths
                try:
                    rel_path = file_path.relative_to(base_path)
                except ValueError:
                    rel_path = file_path

                if _should_exclude(rel_path, excludes):
                    continue

                # Skip hidden files unless requested
                if not include_hidden:
                    if any(part.startswith(".") for part in rel_path.parts):
                        continue

                matches.append(file_path)

                # Early exit if we have enough matches
                if len(matches) >= head_limit:
                    break

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

            # Format output with relative paths
            try:
                relative_paths = [str(p.relative_to(base_path)) for p in matches]
                file_list = "\n".join(relative_paths)
            except ValueError:
                relative_paths = [str(p) for p in matches]
                file_list = "\n".join(relative_paths)

            truncated = len(matches) >= head_limit

            # Store in cache (store all found files, not just head_limit)
            if self.context_store and not extra_excludes and not include_hidden:
                self.context_store.store_glob(pattern, cache_key_path, relative_paths)

            if truncated:
                file_list += f"\n... (limited to {head_limit} results)"

            return ToolResult(
                success=True,
                output=file_list,
                metadata={
                    "pattern": pattern,
                    "base_path": str(base_path),
                    "count": len(matches),
                    "truncated": truncated,
                    "files": relative_paths,
                    "from_cache": False,
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
    Powerful content search tool using ripgrep when available.

    Falls back to Python implementation if ripgrep is not installed.
    Features:
    - Ripgrep backend for 10-100x speed improvement
    - Smart exclusions (venv, node_modules, .git by default)
    - Early termination with head_limit
    - Multiple output modes
    """

    def __init__(self):
        """Initialize GrepTool and detect ripgrep availability."""
        self._ripgrep_available: Optional[bool] = None

    @property
    def ripgrep_available(self) -> bool:
        """Check if ripgrep (rg) is available on the system."""
        if self._ripgrep_available is None:
            self._ripgrep_available = shutil.which("rg") is not None
        return self._ripgrep_available

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return """Fast content search tool using ripgrep.

ALWAYS use this for search tasks. NEVER invoke grep or rg as a bash command.

Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
AUTOMATICALLY EXCLUDES: venv, node_modules, .git, __pycache__, etc.

Output modes:
- "files" (default): Show only file paths containing matches (fastest)
- "content": Show matching lines with context
- "count": Show match counts per file

Examples:
- grep(pattern="TODO") - Find files containing TODO
- grep(pattern="def.*test", glob="*.py", output_mode="content")
- grep(pattern="error", head_limit=20) - Stop after 20 matching files
- grep(pattern="import", context=2) - Show 2 lines of context

Parameters:
- pattern: Regex pattern to search for
- path: Directory to search (default: current directory)
- glob: Filter by file pattern (e.g., "*.py", "*.ts")
- output_mode: "files" (default), "content", or "count"
- head_limit: Max results to return (enables early exit)
- context: Lines of context for content mode (default: 0)
- case_sensitive: Case-sensitive search (default: true)
- exclude: Additional directories to exclude
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
                    "description": "Directory to search in (default: current directory)",
                },
                "glob": {
                    "type": "string",
                    "description": "Filter files by glob pattern (e.g., '*.py', '*.tsx')",
                },
                "output_mode": {
                    "type": "string",
                    "enum": ["files", "content", "count"],
                    "description": "Output format: 'files', 'content', or 'count'",
                },
                "head_limit": {
                    "type": "integer",
                    "description": "Max results to return (enables early exit)",
                },
                "context": {
                    "type": "integer",
                    "description": "Lines of context before/after match (content mode only)",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case-sensitive search (default: true)",
                },
                "exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional directories/patterns to exclude",
                },
            },
            "required": ["pattern"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Search file contents with regex pattern.

        Uses ripgrep if available, falls back to Python otherwise.
        """
        self.validate_params(**kwargs)

        if self.ripgrep_available:
            return self._execute_ripgrep(**kwargs)
        else:
            return self._execute_python(**kwargs)

    def _execute_ripgrep(self, **kwargs: Any) -> ToolResult:
        """Execute search using ripgrep (fast path)."""
        pattern = kwargs["pattern"]
        base_path = Path(kwargs.get("path", ".")).resolve()
        glob_pattern = kwargs.get("glob")
        output_mode = kwargs.get("output_mode", "files")
        head_limit = kwargs.get("head_limit")
        context = kwargs.get("context", 0)
        case_sensitive = kwargs.get("case_sensitive", True)
        extra_excludes = kwargs.get("exclude", [])

        # Build cache key flags
        cache_flags = f"glob={glob_pattern or ''},mode={output_mode},case={case_sensitive}"

        # Check cache first (only for simple searches without extra excludes)
        if self.context_store and not extra_excludes and context == 0:
            cached = self.context_store.get_search(pattern, str(base_path), cache_flags)
            if cached is not None:
                # Apply head_limit to cached results
                results = cached[:head_limit] if head_limit else cached
                truncated = len(cached) > head_limit if head_limit else False

                if not results:
                    return ToolResult(
                        success=True,
                        output=f"No matches found for pattern: {pattern}",
                        metadata={
                            "pattern": pattern,
                            "matches": 0,
                            "backend": "ripgrep",
                            "from_cache": True,
                        },
                    )

                output = "\n".join(results)
                if truncated:
                    output += f"\n... (limited to {head_limit} results)"

                return ToolResult(
                    success=True,
                    output=output,
                    metadata={
                        "pattern": pattern,
                        "matches": len(results),
                        "output_mode": output_mode,
                        "truncated": truncated,
                        "backend": "ripgrep",
                        "from_cache": True,
                    },
                )

        try:
            if not base_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {base_path}",
                    suggestion="Verify the path exists",
                )

            # Build ripgrep command
            cmd = ["rg"]

            # Output mode flags
            if output_mode == "files":
                cmd.append("--files-with-matches")
            elif output_mode == "count":
                cmd.append("--count")
            else:  # content mode
                cmd.append("--line-number")
                if context > 0:
                    cmd.extend(["-C", str(context)])

            # Case sensitivity
            if not case_sensitive:
                cmd.append("--ignore-case")

            # Glob filter
            if glob_pattern:
                cmd.extend(["--glob", glob_pattern])

            # Default exclusions
            for exclude in DEFAULT_EXCLUDES:
                cmd.extend(["--glob", f"!{exclude}"])

            # Extra exclusions
            for exclude in extra_excludes:
                cmd.extend(["--glob", f"!{exclude}"])

            # Head limit (max results)
            if head_limit and output_mode == "files":
                cmd.extend(["--max-count", "1"])  # One match per file
                # We'll limit output lines below

            # Pattern and path
            cmd.append(pattern)
            cmd.append(str(base_path))

            # Execute ripgrep
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )

            # ripgrep returns 1 when no matches found (not an error)
            if result.returncode not in (0, 1):
                # Check if it's a regex error
                if "regex" in result.stderr.lower():
                    return ToolResult(
                        success=False,
                        error=f"Invalid regex pattern: {result.stderr.strip()}",
                        suggestion="Check your regex syntax",
                    )
                return ToolResult(
                    success=False,
                    error=f"ripgrep error: {result.stderr.strip()}",
                )

            output = result.stdout.strip()

            if not output:
                return ToolResult(
                    success=True,
                    output=f"No matches found for pattern: {pattern}",
                    metadata={
                        "pattern": pattern,
                        "matches": 0,
                        "backend": "ripgrep",
                    },
                )

            # Apply head_limit
            lines = output.split("\n")
            truncated = False
            if head_limit and len(lines) > head_limit:
                lines = lines[:head_limit]
                truncated = True
                output = "\n".join(lines) + f"\n... (limited to {head_limit} results)"

            # Make paths relative if possible
            relative_lines = lines  # Default to original
            try:
                relative_lines = []
                for line in lines:
                    # Handle different output formats
                    if ":" in line and output_mode != "files":
                        parts = line.split(":", 1)
                        path_part = Path(parts[0])
                        try:
                            rel_path = path_part.relative_to(base_path)
                            relative_lines.append(f"{rel_path}:{parts[1]}")
                        except ValueError:
                            relative_lines.append(line)
                    else:
                        try:
                            rel_path = Path(line).relative_to(base_path)
                            relative_lines.append(str(rel_path))
                        except ValueError:
                            relative_lines.append(line)
            except Exception:
                relative_lines = lines  # Keep original if relativization fails

            # Store in cache (store all results, not just head_limit)
            if self.context_store and not extra_excludes and context == 0:
                self.context_store.store_search(pattern, str(base_path), relative_lines, cache_flags)

            output = "\n".join(relative_lines[:head_limit] if head_limit else relative_lines)
            if truncated:
                output += f"\n... (limited to {head_limit} results)"

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "pattern": pattern,
                    "matches": len(relative_lines[:head_limit] if head_limit else relative_lines),
                    "output_mode": output_mode,
                    "truncated": truncated,
                    "backend": "ripgrep",
                    "from_cache": False,
                },
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error="Search timed out after 30 seconds",
                suggestion="Try a more specific pattern or path",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}",
                metadata={"pattern": pattern, "backend": "ripgrep"},
            )

    def _execute_python(self, **kwargs: Any) -> ToolResult:
        """Execute search using Python (fallback path)."""
        import re

        pattern = kwargs["pattern"]
        base_path = Path(kwargs.get("path", ".")).resolve()
        glob_pattern = kwargs.get("glob")
        output_mode = kwargs.get("output_mode", "files")
        head_limit = kwargs.get("head_limit", 100)
        context = kwargs.get("context", 0)
        case_sensitive = kwargs.get("case_sensitive", True)
        extra_excludes = set(kwargs.get("exclude", []))

        excludes = DEFAULT_EXCLUDES | extra_excludes

        try:
            if not base_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {base_path}",
                    suggestion="Verify the path exists",
                )

            # Compile regex
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
                files_to_search = list(base_path.glob(glob_pattern))
            else:
                files_to_search = list(base_path.glob("**/*"))

            # Filter to files only and apply exclusions
            files_to_search = [
                f for f in files_to_search
                if f.is_file() and not _should_exclude(f.relative_to(base_path), excludes)
            ]

            # Search files with early exit
            results = {}
            for file_path in files_to_search:
                if output_mode == "files" and len(results) >= head_limit:
                    break

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    matches = list(regex.finditer(content))
                    if matches:
                        if output_mode == "count":
                            results[file_path] = len(matches)
                        elif output_mode == "content":
                            lines = content.splitlines()
                            match_lines = []
                            for match in matches[:10]:
                                line_num = content[:match.start()].count("\n")
                                start_line = max(0, line_num - context)
                                end_line = min(len(lines), line_num + context + 1)
                                match_lines.append({
                                    "line_num": line_num + 1,
                                    "line": lines[line_num] if line_num < len(lines) else "",
                                    "context": lines[start_line:end_line],
                                })
                            results[file_path] = match_lines
                        else:
                            results[file_path] = True

                except (UnicodeDecodeError, PermissionError, OSError):
                    continue

            if not results:
                return ToolResult(
                    success=True,
                    output=f"No matches found for pattern: {pattern}",
                    metadata={
                        "pattern": pattern,
                        "files_searched": len(files_to_search),
                        "matches": 0,
                        "backend": "python",
                    },
                )

            # Format output
            truncated = len(results) >= head_limit
            if output_mode == "files":
                output_lines = [str(p.relative_to(base_path)) for p in list(results.keys())[:head_limit]]
                output = "\n".join(output_lines)
            elif output_mode == "count":
                output_lines = [
                    f"{p.relative_to(base_path)}: {count} matches"
                    for p, count in sorted(results.items(), key=lambda x: x[1], reverse=True)[:head_limit]
                ]
                output = "\n".join(output_lines)
            else:  # content
                output_lines = []
                for file_path, matches in list(results.items())[:20]:
                    output_lines.append(f"\n{file_path.relative_to(base_path)}:")
                    for match in matches:
                        output_lines.append(f"  Line {match['line_num']}: {match['line']}")
                output = "\n".join(output_lines)

            if truncated:
                output += f"\n... (limited to {head_limit} results)"

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "pattern": pattern,
                    "files_with_matches": len(results),
                    "output_mode": output_mode,
                    "truncated": truncated,
                    "backend": "python",
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}",
                metadata={"pattern": pattern, "backend": "python"},
            )
