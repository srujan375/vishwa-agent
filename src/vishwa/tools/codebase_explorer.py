"""
Codebase Explorer - High-level tool for efficient code exploration.

This meta-tool combines multiple search operations into a single efficient query,
reducing the number of LLM iterations needed for code understanding.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from vishwa.tools.base import Tool, ToolResult
from vishwa.code_intelligence.smart_reader import get_structure


@dataclass
class ExplorationResult:
    """Results from codebase exploration"""
    files_found: List[str]
    structures: Dict[str, Any]
    grep_matches: Dict[str, List[str]]
    summary: str


class CodebaseExplorerTool(Tool):
    """
    Efficient multi-purpose codebase exploration tool.

    Instead of making 5-10 separate tool calls (glob, grep, analyze_structure, etc.),
    this tool performs common exploration patterns in a single operation.

    This reduces LLM iterations from 10+ down to 1-2 for common tasks.
    """

    @property
    def name(self) -> str:
        return "explore_codebase"

    @property
    def description(self) -> str:
        return """Efficient codebase exploration combining multiple search operations.

This tool reduces iteration count by performing common exploration patterns in one call:

COMMON PATTERNS:

1. Find all files of type X:
   explore_codebase(file_pattern="**/*.py", get_structure=true)
   → Finds all Python files AND gets their structure

2. Search for keyword across codebase:
   explore_codebase(
       search_pattern="authentication",
       file_pattern="**/*.py",
       include_content=true
   )
   → Finds files, shows matches with context

3. Understand a module:
   explore_codebase(
       file_pattern="src/auth/**/*.py",
       get_structure=true,
       max_files=10
   )
   → Finds auth files, shows structure of each

4. Find implementation of feature:
   explore_codebase(
       search_pattern="class.*User",
       file_pattern="**/*.py",
       get_structure=true
   )
   → Finds User class definitions with file structures

Parameters:
- file_pattern: Glob pattern (e.g., "**/*.py", "src/**/*.ts")
- search_pattern: Optional regex to search in files
- get_structure: Include file structures (imports, classes, functions)
- include_content: Show matching lines (for search_pattern)
- max_files: Limit results (default: 20)
- context_lines: Lines around matches (default: 2)

Returns comprehensive exploration results in ONE tool call instead of 5-10.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_pattern": {
                    "type": "string",
                    "description": "Glob pattern to find files (e.g., '**/*.py', 'src/**/*.ts')"
                },
                "search_pattern": {
                    "type": "string",
                    "description": "Optional: Regex pattern to search for in files"
                },
                "get_structure": {
                    "type": "boolean",
                    "description": "Include file structures (imports, classes, functions). Default: false"
                },
                "include_content": {
                    "type": "boolean",
                    "description": "Show matching lines when using search_pattern. Default: false"
                },
                "max_files": {
                    "type": "integer",
                    "description": "Maximum files to analyze. Default: 20"
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Lines of context around matches. Default: 2"
                },
                "exclude_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Patterns to exclude (e.g., ['test_*', '**/migrations/**'])"
                }
            },
            "required": ["file_pattern"]
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute comprehensive codebase exploration"""
        self.validate_params(**kwargs)

        file_pattern = kwargs["file_pattern"]
        search_pattern = kwargs.get("search_pattern")
        get_structure_flag = kwargs.get("get_structure", False)
        include_content = kwargs.get("include_content", False)
        max_files = kwargs.get("max_files", 20)
        context_lines = kwargs.get("context_lines", 2)
        exclude_patterns = kwargs.get("exclude_patterns", [])

        try:
            # Step 1: Find files matching pattern
            files = self._find_files(file_pattern, exclude_patterns)

            if not files:
                return ToolResult(
                    success=True,
                    output=f"No files found matching pattern: {file_pattern}",
                    metadata={"files_found": 0}
                )

            # Limit files
            files = files[:max_files]

            output_sections = []

            # Section 1: File list
            output_sections.append(f"Found {len(files)} files matching '{file_pattern}':\n")
            for i, file in enumerate(files[:10], 1):
                output_sections.append(f"  {i}. {file}")
            if len(files) > 10:
                output_sections.append(f"  ... and {len(files) - 10} more")

            # Step 2: Search for pattern if provided
            grep_results = {}
            if search_pattern:
                output_sections.append(f"\n\nSearching for '{search_pattern}':\n")
                grep_results = self._search_files(
                    files, search_pattern, include_content, context_lines
                )

                if grep_results:
                    output_sections.append(f"Found matches in {len(grep_results)} files:\n")
                    for file_path, matches in list(grep_results.items())[:5]:
                        rel_path = Path(file_path).relative_to(Path.cwd())
                        output_sections.append(f"\n{rel_path}:")

                        if include_content:
                            for line_num, line in matches[:3]:
                                output_sections.append(f"  Line {line_num}: {line.strip()}")
                            if len(matches) > 3:
                                output_sections.append(f"  ... and {len(matches) - 3} more matches")
                        else:
                            output_sections.append(f"  {len(matches)} matches")

                    if len(grep_results) > 5:
                        output_sections.append(f"\n... and {len(grep_results) - 5} more files with matches")
                else:
                    output_sections.append("No matches found")

            # Step 3: Get file structures if requested
            structures = {}
            if get_structure_flag:
                output_sections.append("\n\nFile Structures:\n")

                # Prioritize files with grep matches
                files_to_analyze = list(grep_results.keys()) if grep_results else files
                files_to_analyze = files_to_analyze[:5]  # Limit to 5 structures

                for file_path in files_to_analyze:
                    try:
                        structure = get_structure(file_path)
                        structures[file_path] = structure

                        rel_path = Path(file_path).relative_to(Path.cwd())
                        output_sections.append(f"\n{rel_path} ({structure.total_lines} lines):")

                        # Show key imports
                        if structure.imports[:3]:
                            output_sections.append("  Imports: " + ", ".join(structure.imports[:3]))

                        # Show classes
                        if structure.classes:
                            class_names = [name for name, _ in structure.classes[:5]]
                            output_sections.append(f"  Classes: {', '.join(class_names)}")

                        # Show functions
                        if structure.functions:
                            func_names = [name for name, _ in structure.functions[:5]]
                            output_sections.append(f"  Functions: {', '.join(func_names)}")

                    except Exception as e:
                        output_sections.append(f"\n{file_path}: Could not analyze structure - {str(e)}")

            # Build final output
            output = "\n".join(output_sections)

            # Generate actionable summary
            summary_parts = [f"Explored {len(files)} files"]
            if grep_results:
                summary_parts.append(f"found {len(grep_results)} with matches")
            if structures:
                summary_parts.append(f"analyzed {len(structures)} structures")

            summary = ", ".join(summary_parts)

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "files_found": len(files),
                    "files_with_matches": len(grep_results) if grep_results else 0,
                    "structures_analyzed": len(structures),
                    "summary": summary
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Exploration failed: {str(e)}"
            )

    def _find_files(self, pattern: str, exclude_patterns: List[str]) -> List[str]:
        """Find files matching glob pattern"""
        base_path = Path.cwd()
        matches = []

        if "**" in pattern:
            # Recursive glob
            for file_path in base_path.rglob(pattern.replace("**/", "")):
                if file_path.is_file() and not self._should_exclude(file_path, exclude_patterns):
                    matches.append(str(file_path))
        else:
            # Non-recursive glob
            for file_path in base_path.glob(pattern):
                if file_path.is_file() and not self._should_exclude(file_path, exclude_patterns):
                    matches.append(str(file_path))

        # Sort by modification time
        matches.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)

        return matches

    def _should_exclude(self, file_path: Path, exclude_patterns: List[str]) -> bool:
        """Check if file should be excluded"""
        import fnmatch

        # Always exclude common directories
        default_excludes = ['node_modules', '.git', '__pycache__', 'venv', '.venv', 'dist', 'build']

        path_str = str(file_path)

        # Check default excludes
        for exclude in default_excludes:
            if exclude in path_str:
                return True

        # Check custom patterns
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(str(file_path.name), pattern):
                return True

        return False

    def _search_files(
        self,
        files: List[str],
        pattern: str,
        include_content: bool,
        context_lines: int
    ) -> Dict[str, List]:
        """Search for pattern in files"""
        import re

        try:
            regex = re.compile(pattern)
        except re.error:
            return {}

        results = {}

        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                matches = []
                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        if include_content:
                            matches.append((i, line))
                        else:
                            matches.append((i, ""))

                if matches:
                    results[file_path] = matches

            except (UnicodeDecodeError, PermissionError):
                continue

        return results
