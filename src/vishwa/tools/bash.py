"""
Bash tool - Execute shell commands.

This is the most versatile tool, used for:
- grep/ripgrep searches
- find commands
- running tests (pytest, npm test, etc.)
- git operations
- any shell command
"""

import subprocess
from typing import Any, Dict

from vishwa.tools.base import Tool, ToolResult


class BashTool(Tool):
    """
    Execute shell commands.

    Security notes:
    - Commands are executed in the current working directory
    - No input sanitization (agent is trusted)
    - Timeout of 120 seconds by default
    - Risky commands require user approval
    """

    def __init__(self, timeout: int = 120, auto_approve: bool = False) -> None:
        """
        Args:
            timeout: Maximum execution time in seconds (default: 120)
            auto_approve: Skip approval for risky commands (default: False)
        """
        self.timeout = timeout
        self.auto_approve = auto_approve

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return """Execute a shell command and return its output.

Use this for:
- Searching code with grep/ripgrep (e.g., "grep -rn 'def login' .")
- Finding files (e.g., "find . -name '*.py'")
- Running tests (e.g., "pytest tests/test_auth.py")
- Git operations (e.g., "git status", "git log")
- Any other shell command

The command will be executed in the current working directory.
Output is captured and returned (both stdout and stderr).
Commands timeout after 120 seconds.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                }
            },
            "required": ["command"],
        }

    def _is_risky_command(self, command: str) -> bool:
        """Check if command is risky and needs approval."""
        risky_patterns = [
            "rm ",
            "mv ",
            "git push",
            "git reset",
            "git rebase",
            "git force",
            "chmod",
            "chown",
            "sudo",
            "dd ",
            "mkfs",
            "fdisk",
            "> ",  # Redirection could overwrite files
        ]
        return any(pattern in command for pattern in risky_patterns)

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute a shell command.

        Args:
            command: The shell command to execute

        Returns:
            ToolResult with command output or error
        """
        self.validate_params(**kwargs)
        command = kwargs["command"]

        # Check if command is risky and needs approval
        if self._is_risky_command(command) and not self.auto_approve:
            from vishwa.cli.ui import confirm_action
            from rich.console import Console

            console = Console()
            console.print(f"\n[yellow bold]⚠️  Risky command detected:[/yellow bold]")
            console.print(f"[dim]{command}[/dim]\n")

            if not confirm_action("Execute this command?", default=False):
                return ToolResult(
                    success=False,
                    error="User rejected risky command",
                    suggestion="Command was not executed",
                    metadata={"command": command},
                )

        try:
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            # Combine stdout and stderr
            output = result.stdout
            if result.stderr:
                output += f"\n{result.stderr}" if output else result.stderr

            # Check exit code
            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"Command exited with code {result.returncode}",
                    output=output,
                    suggestion="Check the error message and try a different command",
                    metadata={"exit_code": result.returncode, "command": command},
                )

            return ToolResult(
                success=True,
                output=output or "(no output)",
                metadata={"exit_code": result.returncode, "command": command},
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Command timed out after {self.timeout} seconds",
                suggestion=f"Try a command that completes faster or increase timeout",
                metadata={"command": command, "timeout": self.timeout},
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to execute command: {str(e)}",
                suggestion="Check command syntax and try again",
                metadata={"command": command},
            )
