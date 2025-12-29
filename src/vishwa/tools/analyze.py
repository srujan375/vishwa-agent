"""
Code analysis tools - understand structure and dependencies.

These tools help the agent understand code WITHOUT reading entire files.
This is how Claude Code handles large codebases efficiently.
"""

from typing import Any, Dict
from pathlib import Path

from vishwa.tools.base import Tool, ToolResult
from vishwa.code_intelligence.smart_reader import get_structure, read_imports, read_symbol
from vishwa.code_intelligence.dependencies import get_dependency_graph


class AnalyzeStructureTool(Tool):
    """
    Get file structure WITHOUT reading entire file.

    This is Claude Code's strategy for large files:
    - Read just imports (top of file)
    - Grep for class/function definitions
    - Return summary

    Much faster than reading 5000-line files!
    """

    @property
    def name(self) -> str:
        return "analyze_structure"

    @property
    def description(self) -> str:
        return """Get file structure summary without reading entire file.

For large files (1000+ lines), this is MUCH faster than read_file.

Returns:
- Total line count
- All imports
- Class definitions with line numbers
- Function definitions with line numbers
- Programming language

Example:
analyze_structure(path="models.py")

Returns:
```
File: models.py (5234 lines, Python)

Imports:
- from django.db import models
- from .utils import validate_email

Classes:
- User (line 45)
- Order (line 234)
- Product (line 456)

Functions:
- validate_order (line 789)
- process_payment (line 890)
```

Use this to understand file structure before deciding what to read.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to analyze"
                }
            },
            "required": ["path"]
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self.validate_params(**kwargs)
        path = kwargs["path"]

        try:
            structure = get_structure(path)

            # Format output
            # Ensure all fields are lists
            imports_list = list(structure.imports) if structure.imports else []
            classes_list = list(structure.classes) if structure.classes else []
            functions_list = list(structure.functions) if structure.functions else []

            output = f"""File: {Path(path).name} ({structure.total_lines} lines, {structure.language})

Imports ({len(imports_list)}):
"""
            for imp in imports_list[:20]:  # Limit to 20
                output += f"  - {imp}\n"

            if len(imports_list) > 20:
                output += f"  ... and {len(imports_list) - 20} more\n"

            output += f"\nClasses ({len(classes_list)}):\n"
            for name, line in classes_list[:20]:
                output += f"  - {name} (line {line})\n"

            if len(classes_list) > 20:
                output += f"  ... and {len(classes_list) - 20} more\n"

            output += f"\nFunctions ({len(functions_list)}):\n"
            for name, line in functions_list[:20]:
                output += f"  - {name} (line {line})\n"

            if len(functions_list) > 20:
                output += f"  ... and {len(functions_list) - 20} more\n"

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "path": path,
                    "total_lines": structure.total_lines,
                    "imports_count": len(structure.imports),
                    "classes_count": len(structure.classes),
                    "functions_count": len(structure.functions)
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to analyze structure: {str(e)}",
                suggestion="Check that the file exists and is readable"
            )


class AnalyzeDependenciesTool(Tool):
    """
    Understand file dependencies and impact.

    Key questions answered:
    - What does this file import?
    - What files import this file?
    - If I change this file, what else might break?
    """

    @property
    def name(self) -> str:
        return "analyze_dependencies"

    @property
    def description(self) -> str:
        return """Analyze file dependencies and change impact.

Answers key questions:
1. What does this file import (dependencies)?
2. What files import this file (dependents)?
3. If I change this file, what else might break (impact radius)?

The tool builds a dependency graph of the codebase on first use (cached).

Example:
analyze_dependencies(
    path="auth.py",
    operation="impact_radius"
)

Returns:
```
Impact Analysis for auth.py:

Direct Dependencies (what auth.py imports):
- models.py
- utils/logger.py

Direct Dependents (what imports auth.py):
- views.py
- middleware.py
- tests/test_auth.py

Impact Radius (all files that might be affected by changes to auth.py):
- views.py
- middleware.py
- tests/test_auth.py
- main.py (imports middleware.py)

⚠️ Warning: Changing auth.py may affect 4 files!
```

Operations:
- "dependencies" - Show what this file imports
- "dependents" - Show what imports this file
- "impact_radius" - Show everything that transitively depends on this
- "import_chain" - Find import path from file A to file B
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to analyze"
                },
                "operation": {
                    "type": "string",
                    "enum": ["dependencies", "dependents", "impact_radius", "import_chain", "summary"],
                    "description": "What analysis to perform"
                },
                "target_file": {
                    "type": "string",
                    "description": "For import_chain operation: target file to find path to"
                },
                "rebuild": {
                    "type": "boolean",
                    "description": "Force rebuild of dependency graph (default: false)"
                }
            },
            "required": ["path", "operation"]
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self.validate_params(**kwargs)

        path = kwargs["path"]
        operation = kwargs["operation"]
        target_file = kwargs.get("target_file")
        rebuild = kwargs.get("rebuild", False)

        try:
            # Get dependency graph (builds on first use, then cached)
            graph = get_dependency_graph()

            # Build graph if needed
            if rebuild or not graph.graph:
                # Analyze from current working directory
                import os
                cwd = os.getcwd()
                graph.analyze_directory(cwd)

            if operation == "summary":
                return ToolResult(
                    success=True,
                    output=graph.get_summary()
                )

            # Make path absolute
            abs_path = str(Path(path).resolve())

            if operation == "dependencies":
                deps = graph.get_dependencies(abs_path)

                output = f"Dependencies of {Path(path).name}:\n\n"
                if deps:
                    output += "This file imports:\n"
                    for dep in deps:
                        output += f"  - {Path(dep).relative_to(Path.cwd())}\n"
                else:
                    output += "This file has no dependencies (doesn't import anything)\n"

                return ToolResult(
                    success=True,
                    output=output,
                    metadata={"count": len(deps)}
                )

            elif operation == "dependents":
                dependents = graph.get_dependents(abs_path)

                output = f"Dependents of {Path(path).name}:\n\n"
                if dependents:
                    output += "These files import this file:\n"
                    for dep in dependents:
                        output += f"  - {Path(dep).relative_to(Path.cwd())}\n"
                else:
                    output += "No files import this file\n"

                return ToolResult(
                    success=True,
                    output=output,
                    metadata={"count": len(dependents)}
                )

            elif operation == "impact_radius":
                deps = graph.get_dependencies(abs_path)
                dependents = graph.get_dependents(abs_path)
                impact = graph.get_impact_radius(abs_path)

                output = f"Impact Analysis for {Path(path).name}:\n\n"

                output += f"Direct Dependencies ({len(deps)}):\n"
                for dep in deps[:10]:
                    output += f"  - {Path(dep).relative_to(Path.cwd())}\n"
                if len(deps) > 10:
                    output += f"  ... and {len(deps) - 10} more\n"

                output += f"\nDirect Dependents ({len(dependents)}):\n"
                for dep in dependents[:10]:
                    output += f"  - {Path(dep).relative_to(Path.cwd())}\n"
                if len(dependents) > 10:
                    output += f"  ... and {len(dependents) - 10} more\n"

                output += f"\nImpact Radius ({len(impact)} files affected):\n"
                for file in list(impact)[:20]:
                    output += f"  - {Path(file).relative_to(Path.cwd())}\n"
                if len(impact) > 20:
                    output += f"  ... and {len(impact) - 20} more\n"

                if impact:
                    output += f"\n⚠️ Warning: Changing {Path(path).name} may affect {len(impact)} files!\n"

                return ToolResult(
                    success=True,
                    output=output,
                    metadata={
                        "dependencies_count": len(deps),
                        "dependents_count": len(dependents),
                        "impact_radius_count": len(impact)
                    }
                )

            elif operation == "import_chain":
                if not target_file:
                    return ToolResult(
                        success=False,
                        error="target_file required for import_chain operation"
                    )

                abs_target = str(Path(target_file).resolve())
                chain = graph.get_import_chain(abs_path, abs_target)

                if chain:
                    output = f"Import chain from {Path(path).name} to {Path(target_file).name}:\n\n"
                    for i, file in enumerate(chain):
                        indent = "  " * i
                        output += f"{indent}→ {Path(file).relative_to(Path.cwd())}\n"

                    return ToolResult(
                        success=True,
                        output=output,
                        metadata={"chain_length": len(chain)}
                    )
                else:
                    return ToolResult(
                        success=False,
                        error=f"No import chain found from {Path(path).name} to {Path(target_file).name}"
                    )

            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown operation: {operation}"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Dependency analysis failed: {str(e)}",
                suggestion="Make sure the file exists and the codebase has been analyzed"
            )


class ReadSymbolTool(Tool):
    """
    Read just a specific function or class from a file.

    For large files, this is MUCH faster than reading the whole file.
    Uses LSP when available for more accurate symbol resolution.
    """

    @property
    def name(self) -> str:
        return "read_symbol"

    @property
    def description(self) -> str:
        return """Read just a specific function or class from a file.

For large files (thousands of lines), this is much faster than read_file.

Instead of reading the entire file:
1. Find where the symbol is defined (using LSP if available, otherwise regex)
2. Read just that section (function/class body)
3. Return only what's needed

Example:
read_symbol(
    path="models.py",
    symbol_name="User",
    symbol_type="class"
)

Returns just the User class definition, not the entire 5000-line file.

Parameters:
- path: File path
- symbol_name: Name of function or class
- symbol_type: "function" or "class"
- use_lsp: Use LSP for more accurate symbol resolution (default: true if available)
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file"
                },
                "symbol_name": {
                    "type": "string",
                    "description": "Name of function or class to read"
                },
                "symbol_type": {
                    "type": "string",
                    "enum": ["function", "class"],
                    "description": "Type of symbol (function or class)"
                },
                "use_lsp": {
                    "type": "boolean",
                    "description": "Use LSP for more accurate resolution (default: true if available)"
                }
            },
            "required": ["path", "symbol_name", "symbol_type"]
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self.validate_params(**kwargs)

        path = kwargs["path"]
        symbol_name = kwargs["symbol_name"]
        symbol_type = kwargs["symbol_type"]
        use_lsp = kwargs.get("use_lsp", True)

        # Try LSP first if enabled
        if use_lsp:
            lsp_result = self._try_lsp_resolution(path, symbol_name, symbol_type)
            if lsp_result:
                return lsp_result

        # Fall back to regex-based resolution
        try:
            content = read_symbol(path, symbol_name, symbol_type)

            return ToolResult(
                success=True,
                output=content,
                metadata={
                    "path": path,
                    "symbol_name": symbol_name,
                    "symbol_type": symbol_type,
                    "method": "regex"
                }
            )

        except ValueError as e:
            return ToolResult(
                success=False,
                error=str(e),
                suggestion=f"Symbol '{symbol_name}' not found. Use analyze_structure to see all symbols in the file."
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to read symbol: {str(e)}"
            )

    def _try_lsp_resolution(self, path: str, symbol_name: str, symbol_type: str) -> ToolResult | None:
        """Try to resolve symbol using LSP for more accuracy."""
        try:
            from vishwa.lsp.server_manager import get_server_manager
            from vishwa.lsp.document_manager import get_document_manager

            server_manager = get_server_manager()
            if not server_manager.is_available(path):
                return None

            doc_manager = get_document_manager()
            if not doc_manager.ensure_open(path):
                return None

            client = server_manager.get_client_for_file(path)
            if not client:
                return None

            # Get document symbols
            abs_path = str(Path(path).resolve())
            symbols = client.document_symbols(abs_path)

            if not symbols:
                return None

            # Find the matching symbol
            target_kind = 5 if symbol_type == "class" else 12  # LSP SymbolKind: Class=5, Function=12
            for sym in symbols:
                sym_name = sym.get("name", "")
                sym_kind = sym.get("kind", 0)

                if sym_name == symbol_name and sym_kind == target_kind:
                    # Found the symbol, extract its range
                    range_data = sym.get("range", sym.get("location", {}).get("range"))
                    if range_data:
                        start_line = range_data["start"]["line"]
                        end_line = range_data["end"]["line"]

                        # Read the symbol content
                        content = self._read_lines(path, start_line, end_line + 1)

                        return ToolResult(
                            success=True,
                            output=content,
                            metadata={
                                "path": path,
                                "symbol_name": symbol_name,
                                "symbol_type": symbol_type,
                                "start_line": start_line + 1,
                                "end_line": end_line + 1,
                                "method": "lsp"
                            }
                        )

            return None  # Symbol not found via LSP, fall back to regex

        except Exception:
            return None  # Fall back to regex on any error

    def _read_lines(self, path: str, start_line: int, end_line: int) -> str:
        """Read specific line range from file."""
        with open(path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i < start_line:
                    continue
                if i >= end_line:
                    break
                lines.append(f"{i + 1:4d}| {line.rstrip()}")

        return '\n'.join(lines)
