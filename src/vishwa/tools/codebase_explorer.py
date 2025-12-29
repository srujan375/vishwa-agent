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
                },
                "find_symbol_usages": {
                    "type": "string",
                    "description": "Find all usages of a symbol using LSP (e.g., 'UserModel'). Requires file_pattern to narrow scope."
                },
                "symbol_file": {
                    "type": "string",
                    "description": "File where the symbol is defined (used with find_symbol_usages)"
                },
                "symbol_line": {
                    "type": "integer",
                    "description": "Line number where the symbol is defined (0-indexed, used with find_symbol_usages)"
                },
                "symbol_character": {
                    "type": "integer",
                    "description": "Character offset of the symbol (0-indexed, used with find_symbol_usages)"
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

        # Handle LSP symbol usage finding
        find_symbol_usages = kwargs.get("find_symbol_usages")
        if find_symbol_usages:
            symbol_file = kwargs.get("symbol_file")
            symbol_line = kwargs.get("symbol_line")
            symbol_character = kwargs.get("symbol_character")

            if symbol_file and symbol_line is not None and symbol_character is not None:
                return self._lsp_find_references(
                    symbol_file, symbol_line, symbol_character, max_files
                )

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
                        if structure.imports and len(structure.imports) > 0:
                            # Ensure imports is a list before slicing
                            imports_as_list = list(structure.imports) if not isinstance(structure.imports, list) else structure.imports
                            imports_list = imports_as_list[:3]
                            if imports_list:
                                output_sections.append("  Imports: " + ", ".join(imports_list))

                        # Show classes
                        if structure.classes and len(structure.classes) > 0:
                            # Ensure classes is a list before slicing
                            classes_as_list = list(structure.classes) if not isinstance(structure.classes, list) else structure.classes
                            classes_list = classes_as_list[:5]
                            class_names = [name for name, _ in classes_list]
                            if class_names:
                                output_sections.append(f"  Classes: {', '.join(class_names)}")

                        # Show functions
                        if structure.functions and len(structure.functions) > 0:
                            # Ensure functions is a list before slicing
                            functions_as_list = list(structure.functions) if not isinstance(structure.functions, list) else structure.functions
                            functions_list = functions_as_list[:5]
                            func_names = [name for name, _ in functions_list]
                            if func_names:
                                output_sections.append(f"  Functions: {', '.join(func_names)}")

                    except Exception as e:
                        import traceback
                        # Log the full traceback for debugging
                        tb_str = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                        error_msg = f"\n{file_path}: Could not analyze structure - {str(e)}\n"
                        error_msg += f"Structure types: imports={type(structure.imports)}, "
                        error_msg += f"classes={type(structure.classes)}, "
                        error_msg += f"functions={type(structure.functions)}\n"
                        error_msg += f"Traceback:\n{tb_str}"
                        output_sections.append(error_msg)

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

    def _lsp_find_references(
        self,
        file_path: str,
        line: int,
        character: int,
        max_results: int = 50
    ) -> ToolResult:
        """Find all references to a symbol using LSP."""
        try:
            from vishwa.lsp.server_manager import get_server_manager
            from vishwa.lsp.document_manager import get_document_manager

            # Ensure document is open
            doc_manager = get_document_manager()
            if not doc_manager.ensure_open(file_path):
                return ToolResult(
                    success=False,
                    error=f"No LSP server available for {file_path}",
                    suggestion="Install the appropriate language server"
                )

            # Get client and find references
            server_manager = get_server_manager()
            client = server_manager.get_client_for_file(file_path)

            if client is None:
                return ToolResult(success=False, error="LSP client not available")

            abs_path = str(Path(file_path).resolve())
            locations = client.find_references(abs_path, line, character, True)

            if not locations:
                return ToolResult(
                    success=True,
                    output="No references found",
                    metadata={"count": 0}
                )

            # Format output
            total_count = len(locations)
            locations = locations[:max_results]

            output = f"Found {total_count} references using LSP:\n\n"

            for loc in locations:
                ref_path = loc.to_file_path()
                try:
                    ref_path = str(Path(ref_path).relative_to(Path.cwd()))
                except ValueError:
                    pass
                ref_line = loc.range.start.line + 1

                # Get the line content
                try:
                    with open(loc.to_file_path(), 'r', encoding='utf-8') as f:
                        for i, content in enumerate(f):
                            if i == loc.range.start.line:
                                output += f"{ref_path}:{ref_line}\n"
                                output += f"  {ref_line}| {content.strip()}\n\n"
                                break
                except:
                    output += f"{ref_path}:{ref_line}\n\n"

            if total_count > max_results:
                output += f"... and {total_count - max_results} more references\n"

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "count": total_count,
                    "method": "lsp"
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"LSP reference search failed: {str(e)}",
                suggestion="Try using search_pattern for text-based search instead"
            )
