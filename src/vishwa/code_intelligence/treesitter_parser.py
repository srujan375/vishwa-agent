"""
Tree-sitter based code parsing for multi-language structure extraction.

Extracts definitions (classes, functions, methods), references (calls),
and inheritance relationships from source files using tree-sitter grammars.

This is the lowest layer of the repo map feature. It takes a single file
and returns structured data about what's defined and referenced in it.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass(frozen=True)
class SymbolDefinition:
    """
    A defined symbol (class, function, method) in a source file.

    TODO: This dataclass is complete. No changes needed.

    Examples:
        SymbolDefinition(
            name="validate_email",
            qualified_name="src/models/user.py::User.validate_email",
            kind="method",
            file_path="src/models/user.py",
            line=42,
            signature="def validate_email(self) -> bool",
            parent_class="User",
            bases=(),
        )
    """
    name: str                              # e.g., "User", "validate_email"
    qualified_name: str                    # e.g., "src/models/user.py::User.validate_email"
    kind: str                              # "class", "function", "method"
    file_path: str                         # Relative path from project root
    line: int                              # 1-based line number
    signature: str                         # e.g., "def login(self, user: User) -> Token"
    parent_class: Optional[str] = None     # Enclosing class name, if this is a method
    bases: tuple = ()                      # Base classes (for class definitions only)


@dataclass(frozen=True)
class SymbolReference:
    """
    A reference (call site) to a symbol from another location.

    TODO: This dataclass is complete. No changes needed.

    Example: If function `login()` calls `validate_email()`, that call is a SymbolReference
    with name="validate_email" and context_symbol="login".
    """
    name: str                              # Referenced symbol name
    file_path: str                         # File containing the reference
    line: int                              # Line of the reference
    context_symbol: Optional[str] = None   # Enclosing function/class making the call


@dataclass
class FileParseResult:
    """
    Complete parse result for a single file.

    TODO: This dataclass is complete. No changes needed.
    """
    file_path: str
    language: str
    definitions: list = field(default_factory=list)   # list[SymbolDefinition]
    references: list = field(default_factory=list)     # list[SymbolReference]
    imports: list = field(default_factory=list)         # list[str]
    mtime: float = 0.0                                 # File modification time at parse time


# =============================================================================
# LANGUAGE CONFIGURATION
# =============================================================================

# TODO [A]: Map file extensions to tree-sitter language names.
# This tells the parser which grammar to load for each file type.
# Example: {".py": "python", ".js": "javascript", ".ts": "typescript", ...}
EXTENSION_TO_LANGUAGE: dict = {
    # Fill in mappings for: .py, .js, .jsx, .ts, .tsx, .go, .rs, .java, .c, .cpp, .h, .hpp
}

# TODO [B]: Map language names to their tree-sitter pip package names.
# Example: {"python": "tree_sitter_python", "javascript": "tree_sitter_javascript", ...}
# These packages are imported dynamically via importlib.import_module()
LANGUAGE_TO_MODULE: dict = {
    # Fill in mappings for each language
}


# =============================================================================
# PARSER CLASS
# =============================================================================

class TreeSitterParser:
    """
    Multi-language parser using tree-sitter grammars.

    Loads grammars lazily on first use per language. Extracts:
    - Class definitions with inheritance
    - Function/method definitions with full signatures
    - Call-site references (function A calls function B)
    - Import statements

    Usage:
        parser = TreeSitterParser()
        result = parser.parse_file("src/models/user.py", project_root="/path/to/project")
        for defn in result.definitions:
            print(f"{defn.kind}: {defn.signature} at line {defn.line}")
    """

    def __init__(self) -> None:
        # TODO [C]: Initialize two caches (dicts):
        # self._parsers: dict[str, Parser] — cached tree-sitter Parser instances per language
        # self._languages: dict[str, Language] — cached Language objects per language
        pass

    def parse_file(self, file_path: str, project_root: str) -> FileParseResult:
        """
        Parse a single file and extract all definitions and references.

        TODO [D]: Implement this method. Steps:
        1. Determine language from file extension using EXTENSION_TO_LANGUAGE
        2. If language not supported, raise RuntimeError
        3. Read the file contents as bytes (tree-sitter works with bytes)
        4. Get or create a tree-sitter Parser for this language (call _get_parser)
        5. Parse the source: tree = parser.parse(source_bytes)
        6. Call the appropriate extraction method based on language:
           - "python" -> _extract_python(tree, source_bytes, relative_path)
           - "javascript"/"typescript" -> _extract_javascript(tree, source_bytes, relative_path)
           - etc. (add more as you implement them)
        7. Extract imports separately
        8. Get file mtime from os.path.getmtime()
        9. Return a FileParseResult with all the data

        Args:
            file_path: Absolute path to the file
            project_root: Absolute path to project root (for computing relative paths)

        Returns:
            FileParseResult with definitions, references, imports
        """
        raise NotImplementedError("Implement parse_file")

    def _get_parser(self, language: str):
        """
        Lazily load and cache a tree-sitter Parser for the given language.

        TODO [E]: Implement this method. Steps:
        1. Check if language is already in self._parsers cache, return if so
        2. Call _load_language(language) to get the Language object
        3. Create a new tree_sitter.Parser()
        4. Set the parser's language: parser.language = language_obj
        5. Cache both the parser and language, return the parser

        The tree-sitter API (v0.23+):
            import tree_sitter
            parser = tree_sitter.Parser()
            parser.language = language_obj  # Language object from grammar package
        """
        raise NotImplementedError("Implement _get_parser")

    def _load_language(self, language: str):
        """
        Load a tree-sitter Language from the corresponding pip package.

        TODO [F]: Implement this method. Steps:
        1. Look up the module name from LANGUAGE_TO_MODULE
        2. Use importlib.import_module(module_name) to import it
        3. Call tree_sitter.Language(module.language()) to create the Language
        4. Return it

        Example for Python:
            import tree_sitter_python
            lang = tree_sitter.Language(tree_sitter_python.language())

        Raise RuntimeError if the language isn't in LANGUAGE_TO_MODULE or import fails.
        """
        raise NotImplementedError("Implement _load_language")

    # =========================================================================
    # PYTHON EXTRACTION
    # =========================================================================

    def _extract_python(self, tree, source: bytes, file_path: str):
        """
        Extract definitions and references from a Python AST.

        TODO [G]: Implement this. This is the most important extraction method.

        For DEFINITIONS, walk the tree looking for these node types:
        - "class_definition": Extract class name, base classes, line number
          - Build signature like: "class User(BaseModel):"
          - Set kind="class", bases=(base class names)
          - Then look inside the class body for "function_definition" nodes (methods)
            - These get kind="method" and parent_class=class_name

        - "function_definition" (top-level, not inside a class): Extract name, params, return type
          - Build signature like: "def validate_email(self) -> bool"
          - Set kind="function"

        For REFERENCES, walk the tree looking for:
        - "call" nodes: Extract the function name being called
          - Simple calls: `validate()` -> name="validate"
          - Attribute calls: `user.validate()` -> name="validate"
          - Determine the context_symbol (which function/class contains this call)

        How to walk a tree-sitter tree:
            cursor = tree.walk()
            # Use cursor.goto_first_child(), cursor.goto_next_sibling(), cursor.goto_parent()
            # Or use tree.root_node and recursively visit node.children
            # Each node has: node.type, node.text (bytes), node.start_point (row, col)

        How to get text from a node:
            node.text.decode('utf-8')  # node.text is bytes

        How to get line number:
            node.start_point[0] + 1  # start_point is (row, col), 0-indexed

        Returns:
            Tuple of (list[SymbolDefinition], list[SymbolReference])
        """
        raise NotImplementedError("Implement _extract_python")

    # =========================================================================
    # JAVASCRIPT / TYPESCRIPT EXTRACTION
    # =========================================================================

    def _extract_javascript(self, tree, source: bytes, file_path: str):
        """
        Extract definitions and references from JavaScript/TypeScript AST.

        TODO [H]: Implement this (can do after Python works).

        Similar to Python but look for these node types:
        - "class_declaration": name, heritage (extends), body
        - "function_declaration": name, parameters, return type (TS)
        - "method_definition": name, parameters (inside class body)
        - "arrow_function" assigned to const/let: treat as function definition
        - "call_expression": function calls (references)

        Returns:
            Tuple of (list[SymbolDefinition], list[SymbolReference])
        """
        raise NotImplementedError("Implement _extract_javascript")

    # =========================================================================
    # ADD MORE LANGUAGES HERE
    # =========================================================================

    # TODO [I]: Add extraction methods for Go, Rust, Java, C/C++ as needed.
    # Each follows the same pattern: walk tree, find definitions and calls.
    # Start with Python, then JS/TS, then add others incrementally.
    #
    # Go: function_declaration, method_declaration, type_declaration (struct/interface)
    # Rust: function_item, impl_item, struct_item, enum_item, trait_item
    # Java: class_declaration, method_declaration
    # C/C++: function_definition, struct_specifier, class_specifier (C++)

    # =========================================================================
    # IMPORT EXTRACTION
    # =========================================================================

    def _extract_imports_python(self, tree, source: bytes) -> list:
        """
        Extract Python import statements from the AST.

        TODO [J]: Walk the tree looking for:
        - "import_statement": e.g., `import os` -> "os"
        - "import_from_statement": e.g., `from pathlib import Path` -> "pathlib.Path"

        Return a list of import strings.
        """
        raise NotImplementedError("Implement _extract_imports_python")
