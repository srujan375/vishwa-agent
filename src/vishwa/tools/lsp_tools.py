"""
LSP-based code intelligence tools.

Provides precise go-to-definition, find-references, and hover documentation
by leveraging Language Server Protocol servers.
"""

from typing import Any, Dict, Optional
from pathlib import Path

from vishwa.tools.base import Tool, ToolResult


class GoToDefinitionTool(Tool):
    """
    Navigate to where a symbol is defined.

    Uses LSP textDocument/definition to find the exact location
    where a function, class, variable, or import is defined.
    """

    @property
    def name(self) -> str:
        return "goto_definition"

    @property
    def description(self) -> str:
        return """Find where a symbol is defined using Language Server Protocol.

Given a file and position (line/column), returns the location where that symbol
is defined. Works with functions, classes, variables, imports, and more.

MUCH more precise than grep for finding definitions.

Supported languages: Python (pyright), TypeScript/JavaScript, Go, Rust, C/C++

Example:
goto_definition(
    file_path="src/auth.py",
    line=45,
    character=12
)

Returns the file path, line number, and a preview of the definition.

Use this when you need to:
- Understand what a function/class does
- Find the source of an imported symbol
- Navigate to type definitions
- Trace through code dependencies

Note: Line and character are 0-indexed (first line is 0, first column is 0).
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file containing the symbol",
                },
                "line": {
                    "type": "integer",
                    "description": "Line number (0-indexed)",
                },
                "character": {
                    "type": "integer",
                    "description": "Character offset in line (0-indexed)",
                },
            },
            "required": ["file_path", "line", "character"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self.validate_params(**kwargs)

        file_path = kwargs["file_path"]
        line = kwargs["line"]
        character = kwargs["character"]

        try:
            # Import here to avoid circular imports
            from vishwa.lsp.server_manager import get_server_manager
            from vishwa.lsp.document_manager import get_document_manager

            # Ensure document is open
            doc_manager = get_document_manager()
            if not doc_manager.ensure_open(file_path):
                return ToolResult(
                    success=False,
                    error=f"No LSP server available for {file_path}",
                    suggestion="Install the appropriate language server (e.g., pip install pyright for Python)",
                )

            # Get client and find definition
            server_manager = get_server_manager()
            client = server_manager.get_client_for_file(file_path)

            if client is None:
                return ToolResult(success=False, error="LSP client not available")

            location = client.goto_definition(
                str(Path(file_path).resolve()), line, character
            )

            if location is None:
                return ToolResult(
                    success=True,
                    output="No definition found at this position",
                    metadata={"found": False},
                )

            # Format output with preview
            def_path = location.to_file_path()
            def_line = location.range.start.line

            output = "Definition found:\n"
            output += f"  File: {self._relative_path(def_path)}\n"
            output += f"  Line: {def_line + 1}\n"  # Convert to 1-indexed for display

            # Read preview lines
            preview = self._get_preview(def_path, def_line)
            if preview:
                output += f"\n  Preview:\n{preview}"

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "found": True,
                    "file": def_path,
                    "line": def_line,
                    "character": location.range.start.character,
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to find definition: {str(e)}")

    def _get_preview(self, file_path: str, line: int, context: int = 3) -> str:
        """Get a preview of the definition location."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            start = max(0, line)
            end = min(len(lines), line + context)

            preview_lines = []
            for i in range(start, end):
                prefix = f"  {i + 1}| "
                preview_lines.append(f"{prefix}{lines[i].rstrip()}")

            return "\n".join(preview_lines)
        except:
            return ""

    def _relative_path(self, path: str) -> str:
        """Convert to relative path if possible."""
        try:
            return str(Path(path).relative_to(Path.cwd()))
        except ValueError:
            return path


class FindReferencesTool(Tool):
    """
    Find all usages of a symbol across the codebase.

    Uses LSP textDocument/references to find everywhere
    a symbol is used.
    """

    @property
    def name(self) -> str:
        return "find_references"

    @property
    def description(self) -> str:
        return """Find all references to a symbol using Language Server Protocol.

Given a file and position, finds all places where that symbol is used.
Much more accurate than grep because it understands code semantically.

Supported languages: Python (pyright), TypeScript/JavaScript, Go, Rust, C/C++

Example:
find_references(
    file_path="src/models/user.py",
    line=23,
    character=6
)

Returns a list of all files and line numbers where the symbol is used.

Use this to:
- Understand impact of changing a function/class
- Find all callers of a function
- See all usages before refactoring
- Navigate to related code

Note: Line and character are 0-indexed.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file containing the symbol",
                },
                "line": {
                    "type": "integer",
                    "description": "Line number (0-indexed)",
                },
                "character": {
                    "type": "integer",
                    "description": "Character offset in line (0-indexed)",
                },
                "include_declaration": {
                    "type": "boolean",
                    "description": "Include the definition itself (default: true)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of references to return (default: 50)",
                },
            },
            "required": ["file_path", "line", "character"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self.validate_params(**kwargs)

        file_path = kwargs["file_path"]
        line = kwargs["line"]
        character = kwargs["character"]
        include_declaration = kwargs.get("include_declaration", True)
        max_results = kwargs.get("max_results", 50)

        try:
            from vishwa.lsp.server_manager import get_server_manager
            from vishwa.lsp.document_manager import get_document_manager

            # Ensure document is open
            doc_manager = get_document_manager()
            if not doc_manager.ensure_open(file_path):
                return ToolResult(
                    success=False, error=f"No LSP server available for {file_path}"
                )

            # Get client and find references
            server_manager = get_server_manager()
            client = server_manager.get_client_for_file(file_path)

            if client is None:
                return ToolResult(success=False, error="LSP client not available")

            locations = client.find_references(
                str(Path(file_path).resolve()), line, character, include_declaration
            )

            if not locations:
                return ToolResult(
                    success=True, output="No references found", metadata={"count": 0}
                )

            # Format output
            total_count = len(locations)
            locations = locations[:max_results]

            output = f"Found {total_count} references:\n\n"

            for loc in locations:
                ref_path = self._relative_path(loc.to_file_path())
                ref_line = loc.range.start.line + 1  # 1-indexed for display

                # Get the line content
                line_content = self._get_line(loc.to_file_path(), loc.range.start.line)

                output += f"{ref_path}:{ref_line}\n"
                if line_content:
                    output += f"  {ref_line}| {line_content.strip()}\n"
                output += "\n"

            if total_count > max_results:
                output += f"... and {total_count - max_results} more references\n"

            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "count": total_count,
                    "locations": [
                        {"file": loc.to_file_path(), "line": loc.range.start.line}
                        for loc in locations
                    ],
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to find references: {str(e)}")

    def _get_line(self, file_path: str, line: int) -> str:
        """Get a specific line from a file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for i, content in enumerate(f):
                    if i == line:
                        return content
        except:
            pass
        return ""

    def _relative_path(self, path: str) -> str:
        try:
            return str(Path(path).relative_to(Path.cwd()))
        except ValueError:
            return path


class HoverTool(Tool):
    """
    Get documentation and type information for a symbol.

    Uses LSP textDocument/hover to get rich documentation.
    """

    @property
    def name(self) -> str:
        return "hover_info"

    @property
    def description(self) -> str:
        return """Get documentation and type information for a symbol.

Uses Language Server Protocol to show what a symbol is -
its type signature, docstring, and other relevant information.

Supported languages: Python (pyright), TypeScript/JavaScript, Go, Rust, C/C++

Example:
hover_info(
    file_path="src/utils.py",
    line=15,
    character=8
)

Returns the type signature and documentation for the symbol at that position.

Use this to:
- Quickly understand what a function does
- See type signatures without opening files
- Read docstrings inline
- Verify function arguments

Note: Line and character are 0-indexed.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file",
                },
                "line": {
                    "type": "integer",
                    "description": "Line number (0-indexed)",
                },
                "character": {
                    "type": "integer",
                    "description": "Character offset in line (0-indexed)",
                },
            },
            "required": ["file_path", "line", "character"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self.validate_params(**kwargs)

        file_path = kwargs["file_path"]
        line = kwargs["line"]
        character = kwargs["character"]

        try:
            from vishwa.lsp.server_manager import get_server_manager
            from vishwa.lsp.document_manager import get_document_manager

            # Ensure document is open
            doc_manager = get_document_manager()
            if not doc_manager.ensure_open(file_path):
                return ToolResult(
                    success=False, error=f"No LSP server available for {file_path}"
                )

            # Get client and hover info
            server_manager = get_server_manager()
            client = server_manager.get_client_for_file(file_path)

            if client is None:
                return ToolResult(success=False, error="LSP client not available")

            hover_content = client.hover(
                str(Path(file_path).resolve()), line, character
            )

            if hover_content is None:
                return ToolResult(
                    success=True,
                    output="No hover information available at this position",
                    metadata={"found": False},
                )

            return ToolResult(
                success=True, output=hover_content, metadata={"found": True}
            )

        except Exception as e:
            return ToolResult(
                success=False, error=f"Failed to get hover information: {str(e)}"
            )


class LSPStatusTool(Tool):
    """
    Check status of LSP servers and available languages.
    """

    @property
    def name(self) -> str:
        return "lsp_status"

    @property
    def description(self) -> str:
        return """Check the status of Language Server Protocol servers.

Shows which language servers are available, running, and configured.
Useful for diagnosing LSP issues.

Example:
lsp_status()

Returns a list of all configured language servers and their status.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs: Any) -> ToolResult:
        from vishwa.lsp.config import get_lsp_config
        from vishwa.lsp.server_manager import get_server_manager

        config = get_lsp_config()
        server_manager = get_server_manager()

        available = config.list_available_servers()
        running = server_manager.get_running_servers()
        all_servers = config.list_all_servers()

        output = "LSP Server Status:\n\n"

        for language, is_available in available.items():
            server_config = all_servers.get(language)
            cmd = " ".join(server_config.command) if server_config else "N/A"

            if language in running and running[language]:
                status = "RUNNING"
            elif is_available:
                status = "AVAILABLE"
            else:
                status = "NOT INSTALLED"

            output += f"  {language}: {status}\n"
            output += f"    Command: {cmd}\n"

        output += "\nInstallation hints:\n"
        for language in available:
            if not available[language]:
                hint = config.get_install_hint(language)
                output += f"  {language}: {hint}\n"

        return ToolResult(
            success=True,
            output=output,
            metadata={"available": available, "running": running},
        )
