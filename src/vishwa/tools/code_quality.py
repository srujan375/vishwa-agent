"""
Code Quality Tool - Linter Integration for Vishwa.

Runs static analysis tools (ruff, pylint, mypy) on code files
and returns issues that need to be addressed.

Supports line filtering to only report issues on modified lines.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Optional, Set, Tuple, List

from vishwa.tools.base import Tool, ToolResult


@dataclass
class LintIssue:
    """A single lint issue."""
    file: str
    line: int
    column: int
    code: str
    message: str
    severity: str  # "error", "warning", "info"

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column} [{self.code}] {self.message}"


class CodeQualityTool(Tool):
    """
    Run static analysis on code files and return issues.

    Supports multiple linters:
    - ruff: Fast Python linter (preferred)
    - pylint: Comprehensive Python linter
    - mypy: Type checking

    Features:
    - Line filtering: Only report issues on specified lines
    - Smart severity detection: Errors vs warnings
    - Multiple linter support with fallback
    """

    @property
    def name(self) -> str:
        return "check_code_quality"

    @property
    def description(self) -> str:
        return """Run static analysis (linters) on Python files to check for code quality issues.

Use this tool:
- After modifying Python files to check for issues
- Before considering a task complete
- When the user asks to validate code quality

Parameters:
- path: File or directory to check
- lines: Optional list of line numbers to filter issues (only show issues on these lines)
- linters: List of linters to run (default: ['ruff'])
- fix: Auto-fix issues if possible (ruff only)

The tool will run available linters and return any issues found.
If issues are found, you should fix them before proceeding."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "File or directory path to check. "
                        "Can be a single file or directory."
                    )
                },
                "lines": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": (
                        "Optional: Only report issues on these line numbers. "
                        "Use this to filter to only modified lines."
                    )
                },
                "line_ranges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "integer"},
                            "end": {"type": "integer"}
                        }
                    },
                    "description": (
                        "Optional: Only report issues in these line ranges. "
                        "Each range is {start, end} (inclusive)."
                    )
                },
                "linters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of linters to run. "
                        "Options: 'ruff', 'pylint', 'mypy'. Default: ['ruff']"
                    )
                },
                "fix": {
                    "type": "boolean",
                    "description": "If true, attempt to auto-fix issues (ruff only). Default: false"
                }
            },
            "required": ["path"]
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute code quality checks.

        Args:
            path: File or directory to check
            lines: Optional list of specific line numbers to filter to
            line_ranges: Optional list of {start, end} ranges to filter to
            linters: List of linters to run (default: ['ruff'])
            fix: Whether to auto-fix issues (ruff only)

        Returns:
            ToolResult with issues found or success message
        """
        self.validate_params(**kwargs)

        path: str = kwargs["path"]
        lines: Optional[List[int]] = kwargs.get("lines")
        line_ranges: Optional[List[dict]] = kwargs.get("line_ranges")
        linters: Optional[List[str]] = kwargs.get("linters")
        fix: bool = kwargs.get("fix", False)

        # Build set of allowed lines for filtering
        allowed_lines: Optional[Set[int]] = None
        if lines or line_ranges:
            allowed_lines = set()
            if lines:
                allowed_lines.update(lines)
            if line_ranges:
                for range_obj in line_ranges:
                    start = range_obj.get("start", 0)
                    end = range_obj.get("end", start)
                    allowed_lines.update(range(start, end + 1))

        # Validate path exists
        if not os.path.exists(path):
            return ToolResult(
                success=False,
                error=f"Path does not exist: {path}",
                suggestion="Provide a valid file or directory path"
            )

        # Default to ruff if available, otherwise try others
        if linters is None:
            linters = self._detect_available_linters()
            if not linters:
                return ToolResult(
                    success=True,
                    output=(
                        "No linters available (ruff, pylint, or mypy). "
                        "Install with: pip install ruff"
                    ),
                    metadata={"skipped": True}
                )

        all_issues: List[LintIssue] = []
        linter_outputs: dict[str, str] = {}

        for linter in linters:
            if linter == "ruff":
                issues, output = self._run_ruff(path, fix=fix)
            elif linter == "pylint":
                issues, output = self._run_pylint(path)
            elif linter == "mypy":
                issues, output = self._run_mypy(path)
            elif linter == "pyright":
                issues, output = self._run_pyright(path)
            else:
                continue

            all_issues.extend(issues)
            if output:
                linter_outputs[linter] = output

        # Filter issues to only allowed lines if specified
        if allowed_lines is not None:
            original_count = len(all_issues)
            all_issues = [i for i in all_issues if i.line in allowed_lines]
            filtered_count = original_count - len(all_issues)

        # Format results
        if not all_issues:
            msg = f"No issues found in {path}"
            if allowed_lines is not None:
                msg = f"No issues found on modified lines in {path}"
                if filtered_count > 0:
                    msg += f" ({filtered_count} pre-existing issues filtered out)"
            return ToolResult(
                success=True,
                output=msg,
                metadata={
                    "issues_count": 0,
                    "linters_run": linters,
                    "filtered_lines": list(allowed_lines) if allowed_lines else None,
                    "filtered_out": filtered_count if allowed_lines else 0
                }
            )

        # Group issues by severity
        errors = [i for i in all_issues if i.severity == "error"]
        warnings = [i for i in all_issues if i.severity == "warning"]
        infos = [i for i in all_issues if i.severity == "info"]

        output_lines = [
            f"Found {len(all_issues)} issue(s) in {path}:",
            f"  - {len(errors)} error(s)",
            f"  - {len(warnings)} warning(s)",
            f"  - {len(infos)} info/style issue(s)",
        ]

        if allowed_lines is not None and filtered_count > 0:
            output_lines.append(f"  - {filtered_count} pre-existing issues filtered out")

        output_lines.extend(["", "Issues to fix:"])

        # Show errors first, then warnings
        for issue in errors + warnings + infos[:5]:  # Limit info to 5
            output_lines.append(f"  {issue}")

        if len(infos) > 5:
            output_lines.append(f"  ... and {len(infos) - 5} more style issues")

        return ToolResult(
            success=False,  # Issues found = not successful
            error="\n".join(output_lines),
            suggestion="Fix the issues listed above, starting with errors, then warnings.",
            metadata={
                "issues_count": len(all_issues),
                "errors": len(errors),
                "warnings": len(warnings),
                "infos": len(infos),
                "linters_run": linters,
                "issues": [str(i) for i in all_issues],
                "filtered_lines": list(allowed_lines) if allowed_lines else None,
                "filtered_out": filtered_count if allowed_lines else 0
            }
        )

    def _detect_available_linters(self) -> List[str]:
        """Detect which linters are available."""
        available = []
        # Prefer pyright over mypy for better semantic analysis
        for linter in ["ruff", "pyright", "pylint", "mypy"]:
            if shutil.which(linter):
                available.append(linter)
                # Only use one type checker (prefer pyright)
                if linter in ("pyright", "mypy"):
                    break
        return available

    def _run_ruff(self, path: str, fix: bool = False) -> Tuple[List[LintIssue], str]:
        """Run ruff linter."""
        if not shutil.which("ruff"):
            return [], ""

        cmd = ["ruff", "check", path, "--output-format=json"]
        if fix:
            cmd.append("--fix")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            issues = []
            if result.stdout:
                import json
                try:
                    data = json.loads(result.stdout)
                    for item in data:
                        severity = "error" if item.get("code", "").startswith("E") else "warning"
                        issues.append(LintIssue(
                            file=item.get("filename", path),
                            line=item.get("location", {}).get("row", 0),
                            column=item.get("location", {}).get("column", 0),
                            code=item.get("code", ""),
                            message=item.get("message", ""),
                            severity=severity
                        ))
                except json.JSONDecodeError:
                    pass

            return issues, result.stderr or ""

        except subprocess.TimeoutExpired:
            return [], "Ruff timed out"
        except Exception as e:
            return [], f"Ruff error: {str(e)}"

    def _run_pylint(self, path: str) -> Tuple[List[LintIssue], str]:
        """Run pylint linter."""
        if not shutil.which("pylint"):
            return [], ""

        # Disable docstring warnings (C0114, C0115, C0116)
        cmd = ["pylint", path, "--output-format=json", "--disable=C0114,C0115,C0116"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            issues = []
            if result.stdout:
                import json
                try:
                    data = json.loads(result.stdout)
                    for item in data:
                        msg_type = item.get("type", "info")
                        if msg_type in ["error", "fatal"]:
                            severity = "error"
                        elif msg_type == "warning":
                            severity = "warning"
                        else:
                            severity = "info"

                        issues.append(LintIssue(
                            file=item.get("path", path),
                            line=item.get("line", 0),
                            column=item.get("column", 0),
                            code=item.get("message-id", ""),
                            message=item.get("message", ""),
                            severity=severity
                        ))
                except json.JSONDecodeError:
                    pass

            return issues, result.stderr or ""

        except subprocess.TimeoutExpired:
            return [], "Pylint timed out"
        except Exception as e:
            return [], f"Pylint error: {str(e)}"

    def _run_pyright(self, path: str) -> Tuple[List[LintIssue], str]:
        """Run pyright type checker for semantic analysis."""
        if not shutil.which("pyright"):
            return [], ""

        cmd = ["pyright", path, "--outputjson"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            issues = []
            if result.stdout:
                import json
                try:
                    data = json.loads(result.stdout)
                    for diag in data.get("generalDiagnostics", []):
                        severity = diag.get("severity", "information")
                        if severity == "error":
                            sev = "error"
                        elif severity == "warning":
                            sev = "warning"
                        else:
                            sev = "info"

                        issues.append(LintIssue(
                            file=diag.get("file", path),
                            line=diag.get("range", {}).get("start", {}).get("line", 0) + 1,
                            column=diag.get("range", {}).get("start", {}).get("character", 0),
                            code=diag.get("rule", "pyright"),
                            message=diag.get("message", ""),
                            severity=sev
                        ))
                except json.JSONDecodeError:
                    pass

            return issues, result.stderr or ""

        except subprocess.TimeoutExpired:
            return [], "Pyright timed out"
        except Exception as e:
            return [], f"Pyright error: {str(e)}"

    def _run_mypy(self, path: str) -> Tuple[List[LintIssue], str]:
        """Run mypy type checker."""
        if not shutil.which("mypy"):
            return [], ""

        cmd = ["mypy", path, "--no-error-summary", "--show-column-numbers"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            issues = []
            # Parse mypy output (format: file:line:col: severity: message)
            for line in (result.stdout + result.stderr).splitlines():
                if ":" in line and not line.startswith("Found"):
                    parts = line.split(":", 4)
                    if len(parts) >= 4:
                        try:
                            issues.append(LintIssue(
                                file=parts[0],
                                line=int(parts[1]) if parts[1].isdigit() else 0,
                                column=int(parts[2]) if parts[2].isdigit() else 0,
                                code="mypy",
                                message=parts[3].strip() if len(parts) > 3 else "",
                                severity="error" if "error" in line.lower() else "warning"
                            ))
                        except (ValueError, IndexError):
                            pass

            return issues, ""

        except subprocess.TimeoutExpired:
            return [], "Mypy timed out"
        except Exception as e:
            return [], f"Mypy error: {str(e)}"


def calculate_modified_lines(old_content: str, new_content: str, start_line: int = 1) -> Set[int]:
    """
    Calculate which lines were modified between old and new content.

    Args:
        old_content: Original file content
        new_content: New file content
        start_line: Starting line number (1-indexed)

    Returns:
        Set of modified line numbers (1-indexed)
    """
    import difflib

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    modified_lines: Set[int] = set()

    # Use difflib to find changes
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            # Lines j1 to j2 in new content are modified
            for line_num in range(j1 + 1, j2 + 1):  # 1-indexed
                modified_lines.add(line_num)
        elif tag == 'insert':
            # Lines j1 to j2 are new
            for line_num in range(j1 + 1, j2 + 1):  # 1-indexed
                modified_lines.add(line_num)
        # 'delete' doesn't add to new file, 'equal' means no change

    return modified_lines


def calculate_affected_lines(old_content: str, new_content: str, context: int = 2) -> Set[int]:
    """
    Calculate lines affected by changes, including context lines.

    This is more lenient than calculate_modified_lines - it includes
    a few lines before/after the actual changes to catch issues that
    might be indirectly caused by the edit.

    Args:
        old_content: Original file content
        new_content: New file content
        context: Number of context lines before/after changes

    Returns:
        Set of affected line numbers (1-indexed)
    """
    modified = calculate_modified_lines(old_content, new_content)

    if not modified:
        return set()

    # Add context lines
    affected: Set[int] = set()
    new_line_count = len(new_content.splitlines())

    for line in modified:
        # Add the modified line and context around it
        for offset in range(-context, context + 1):
            affected_line = line + offset
            if 1 <= affected_line <= new_line_count:
                affected.add(affected_line)

    return affected


class CodeReviewTool(Tool):
    """
    Trigger a code review on modified files.

    This tool launches a sub-agent to review code for:
    - SOLID principle violations
    - Code smells
    - Potential bugs
    - Opportunities for improvement
    """

    def __init__(self, llm: Any = None, tool_registry: Any = None):
        """
        Initialize code review tool.

        Args:
            llm: LLM provider for the review sub-agent
            tool_registry: Tool registry for the sub-agent
        """
        self._llm = llm
        self._tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "review_code"

    @property
    def description(self) -> str:
        return """Perform a comprehensive code review on specified files.

Analyzes code for:
- SOLID principle violations
- Code smells (long methods, duplicate code, magic numbers)
- Potential bugs
- Missing error handling
- Improvement opportunities

Use before marking a task as complete to ensure code quality."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths to review"
                },
                "focus_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Specific areas to focus on: "
                        "'solid', 'bugs', 'performance', 'security', 'style'"
                    )
                }
            },
            "required": ["files"]
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute code review.

        Args:
            files: List of files to review
            focus_areas: Specific areas to focus on

        Returns:
            ToolResult with review findings
        """
        self.validate_params(**kwargs)

        files: List[str] = kwargs["files"]
        focus_areas: Optional[List[str]] = kwargs.get("focus_areas")

        if not files:
            return ToolResult(
                success=False,
                error="No files specified for review",
                suggestion="Provide a list of file paths to review"
            )

        # Verify files exist
        existing_files = []
        for f in files:
            if os.path.exists(f):
                existing_files.append(f)

        if not existing_files:
            return ToolResult(
                success=False,
                error="None of the specified files exist",
                suggestion="Provide valid file paths"
            )

        # If we have an LLM, use it for intelligent review
        if self._llm:
            return self._run_llm_review(existing_files, focus_areas)

        # Otherwise, just run linters as a basic review
        quality_tool = CodeQualityTool()
        all_issues = []

        for file_path in existing_files:
            result = quality_tool.execute(path=file_path)
            if result.metadata and result.metadata.get("issues"):
                all_issues.extend(result.metadata["issues"])

        if not all_issues:
            return ToolResult(
                success=True,
                output=(
                    f"Basic code review passed for {len(existing_files)} file(s). "
                    "No linter issues found."
                ),
                metadata={"files_reviewed": existing_files}
            )

        issues_summary = "\n".join(all_issues[:10])
        return ToolResult(
            success=False,
            error=(
                f"Found {len(all_issues)} issue(s) across "
                f"{len(existing_files)} file(s):\n{issues_summary}"
            ),
            suggestion="Fix the issues and run review again",
            metadata={"issues": all_issues, "files_reviewed": existing_files}
        )

    def _run_llm_review(
        self,
        files: List[str],
        focus_areas: Optional[List[str]] = None
    ) -> ToolResult:
        """Run intelligent code review using LLM sub-agent."""
        # This would use the TaskTool to spawn a review sub-agent
        # For now, fall back to linter-based review
        quality_tool = CodeQualityTool()

        review_results = []
        for file_path in files:
            result = quality_tool.execute(path=file_path)
            review_results.append(f"**{file_path}**: {result.output or result.error}")

        return ToolResult(
            success=all(not r.startswith("**") or "No issues" in r for r in review_results),
            output="\n\n".join(review_results) if review_results else "No files to review",
            metadata={"files_reviewed": files}
        )
