"""
Git operations tool.

Provides git diff functionality to show changes before applying.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from vishwa.tools.base import Tool, ToolResult


class GitDiffTool(Tool):
    """
    Show git diff for changes.

    Used to:
    - Show what changed after str_replace
    - Verify modifications before committing
    - Review all changes in a session
    """

    @property
    def name(self) -> str:
        return "git_diff"

    @property
    def description(self) -> str:
        return """Show git diff for modified files.

Use this to:
- View changes after modifying files with str_replace
- Verify modifications before final approval
- Review all changes made during the session

Optional parameter:
- path: Show diff for specific file (default: all modified files)

Returns colored diff output showing added/removed lines.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional: specific file to show diff for",
                },
            },
            "required": [],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Show git diff.

        Args:
            path: Optional specific file path

        Returns:
            ToolResult with diff output or error
        """
        path = kwargs.get("path")

        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    error="Not a git repository",
                    suggestion="Initialize git with 'git init' or run from a git repository",
                )

            # Build git diff command
            cmd = ["git", "diff"]
            if path:
                # Verify path exists
                if not Path(path).exists():
                    return ToolResult(
                        success=False,
                        error=f"File not found: {path}",
                        suggestion="Check the file path and try again",
                    )
                cmd.append(path)

            # Run git diff
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"git diff failed: {result.stderr}",
                    metadata={"command": " ".join(cmd)},
                )

            diff_output = result.stdout

            if not diff_output.strip():
                return ToolResult(
                    success=True,
                    output="No changes detected" + (f" in {path}" if path else ""),
                    metadata={"path": path, "has_changes": False},
                )

            # Parse diff stats
            stats_result = subprocess.run(
                cmd + ["--stat"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            stats = stats_result.stdout if stats_result.returncode == 0 else None

            return ToolResult(
                success=True,
                output=diff_output,
                metadata={
                    "path": path,
                    "has_changes": True,
                    "stats": stats,
                    "lines": len(diff_output.splitlines()),
                },
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error="git diff command timed out",
                suggestion="Repository might be too large or unresponsive",
            )

        except FileNotFoundError:
            return ToolResult(
                success=False,
                error="git command not found",
                suggestion="Install git: https://git-scm.com/downloads",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to run git diff: {str(e)}",
            )


class GitRestoreTool(Tool):
    """
    Restore files to previous state (rollback).

    Used for undo/rollback functionality.
    """

    @property
    def name(self) -> str:
        return "git_restore"

    @property
    def description(self) -> str:
        return """Restore file(s) to git HEAD state (undo changes).

Use this to:
- Rollback changes if something went wrong
- Undo modifications to specific files
- Reset to clean state

CAUTION: This discards uncommitted changes!
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to restore (use '.' for all files)",
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Restore file to git HEAD state.

        Args:
            path: File path to restore

        Returns:
            ToolResult with success/failure
        """
        self.validate_params(**kwargs)
        path = kwargs["path"]

        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    error="Not a git repository",
                )

            # Run git restore
            result = subprocess.run(
                ["git", "restore", path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"git restore failed: {result.stderr}",
                    suggestion="File might not have any changes or doesn't exist",
                )

            return ToolResult(
                success=True,
                output=f"Successfully restored: {path}",
                metadata={"path": path},
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to restore file: {str(e)}",
            )
