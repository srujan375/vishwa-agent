"""
Repository Map - concise codebase overview for LLM system prompts.

Parses the codebase using tree-sitter, builds a symbol graph with call
relationships, ranks symbols by importance using PageRank, and generates
a text representation that fits within a token budget.

This is the main orchestrator. It ties together:
- TreeSitterParser (parsing individual files)
- RepoMapCache (avoiding redundant re-parsing)
- PageRank (ranking symbols by importance)
- Text formatting (producing the concise map)

The generated map is injected into the agent's system prompt so it knows
the codebase architecture before taking any action.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from vishwa.code_intelligence.treesitter_parser import (
    TreeSitterParser,
    SymbolDefinition,
    SymbolReference,
    FileParseResult,
    EXTENSION_TO_LANGUAGE,
)
from vishwa.code_intelligence.repo_map_cache import RepoMapCache


# =============================================================================
# SYMBOL GRAPH NODE
# =============================================================================

@dataclass
class SymbolNode:
    """
    Node in the symbol graph. Wraps a SymbolDefinition with call edges and rank.

    TODO: This dataclass is complete. No changes needed.
    """
    definition: SymbolDefinition
    outgoing_calls: set = field(default_factory=set)   # qualified_names this symbol calls
    incoming_calls: set = field(default_factory=set)    # qualified_names that call this symbol
    rank: float = 0.0                                   # PageRank score


# =============================================================================
# DEFAULT CONFIGURATION
# =============================================================================

# Directories/patterns to always exclude from scanning
DEFAULT_EXCLUDES = [
    "**/venv/**", "**/.venv/**", "**/node_modules/**",
    "**/__pycache__/**", "**/dist/**", "**/build/**",
    "**/.git/**", "**/env/**", "**/.tox/**", "**/htmlcov/**",
    "**/*.egg-info/**",
]

# Source file extensions to include
DEFAULT_EXTENSIONS = [
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs", ".java", ".c", ".cpp", ".h", ".hpp",
]

# Rough estimate: 1 token ~= 4 characters (consistent with ContextManager)
CHARS_PER_TOKEN = 4

# Maximum number of files to parse (safety limit for huge repos)
MAX_FILES = 1000


# =============================================================================
# MAIN REPO MAP CLASS
# =============================================================================

class RepoMap:
    """
    Generates a concise repository map for LLM context.

    Usage:
        repo_map = RepoMap(project_root="/path/to/project")
        text = repo_map.generate(token_budget=3000)

    The output looks like:
        ===REPOSITORY MAP===
        src/models/user.py:
        | class User(BaseModel):
        |   def __init__(self, name: str, email: str)
        |   def validate_email(self) -> bool
        |
        src/services/auth.py:
        | class AuthService:
        |   def login(self, user: User) -> Token
        |   ...calls: User.validate_email, TokenStore.revoke
        |
        (23 files, 156 symbols total | showing top 45 by importance)
    """

    def __init__(
        self,
        project_root: str,
        token_budget: int = 3000,
        extensions: Optional[list] = None,
        exclude_patterns: Optional[list] = None,
    ) -> None:
        """
        TODO [A]: Store all parameters as instance variables.
        Also create:
        - self._parser = TreeSitterParser()
        - self._cache = RepoMapCache()
        - self._symbol_graph: dict[str, SymbolNode] = {}  (qualified_name -> SymbolNode)
        - self._file_results: dict[str, FileParseResult] = {}  (file_path -> results)
        """
        raise NotImplementedError("Implement __init__")

    def generate(self, context_files: Optional[list] = None) -> str:
        """
        Generate the repository map text.

        TODO [B]: Implement this. This is the main entry point. Steps:
        1. Call _discover_files() to find all source files
        2. Call _parse_all(files) to parse them (uses cache)
        3. Call _build_symbol_graph() to create nodes and edges
        4. Call _run_pagerank(context_files) to rank symbols
        5. Call _select_symbols() to pick top symbols within budget
        6. Call _format_map(selected) to produce the text
        7. Return the text

        If no files found or no definitions extracted, return a helpful message.

        Args:
            context_files: Files currently in the conversation. Symbols in these
                          files get a PageRank boost (personalized PageRank).
        """
        raise NotImplementedError("Implement generate")

    def refresh(self, changed_files: Optional[list] = None) -> str:
        """
        Incrementally update the map after file changes.

        TODO [C]: Implement this. Steps:
        1. If changed_files provided, invalidate those in cache
        2. If not, cache will auto-detect stale files via mtime
        3. Call generate() again (it will only re-parse stale files)
        """
        raise NotImplementedError("Implement refresh")

    # =========================================================================
    # FILE DISCOVERY
    # =========================================================================

    def _discover_files(self) -> list:
        """
        Find all source files in the project, respecting exclude patterns.

        TODO [D]: Implement this. Steps:
        1. Walk self._project_root using os.walk() or Path.rglob()
        2. For each file, check if its extension is in self._extensions
        3. Check if the path matches any self._exclude_patterns (use fnmatch or pathlib.match)
        4. Optionally respect .gitignore using gitpython (already a dependency):
           - from git import Repo
           - repo = Repo(self._project_root)
           - Skip files where repo.ignored(file_path) is True
           - Wrap in try/except for non-git directories
        5. Cap at MAX_FILES (1000) to prevent issues with huge repos
        6. Return list of absolute file paths

        Hint: Look at how search.py handles DEFAULT_EXCLUDES for reference.
        """
        raise NotImplementedError("Implement _discover_files")

    # =========================================================================
    # PARSING
    # =========================================================================

    def _parse_all(self, file_paths: list) -> None:
        """
        Parse files using tree-sitter, leveraging cache for unchanged files.

        TODO [E]: Implement this. Steps:
        1. Call self._cache.get_stale_files(file_paths) to find which need parsing
        2. For each stale file:
           a. Call self._parser.parse_file(file_path, self._project_root)
           b. Store result in self._cache via self._cache.put()
           c. If parsing fails (RuntimeError), log warning and skip file
        3. For all files (cached + freshly parsed), store in self._file_results
        """
        raise NotImplementedError("Implement _parse_all")

    # =========================================================================
    # SYMBOL GRAPH
    # =========================================================================

    def _build_symbol_graph(self) -> None:
        """
        Build the symbol graph from all FileParseResults.

        TODO [F]: Implement this. Steps:
        1. Clear self._symbol_graph
        2. For each FileParseResult in self._file_results.values():
           a. For each definition, create a SymbolNode and add to graph
              Key = definition.qualified_name
        3. For each FileParseResult:
           a. For each reference, try to resolve it to a definition
              using _resolve_reference()
           b. If resolved, add edges:
              - caller's outgoing_calls.add(resolved_qualified_name)
              - callee's incoming_calls.add(caller_qualified_name)
              Where "caller" is the context_symbol of the reference
        """
        raise NotImplementedError("Implement _build_symbol_graph")

    def _resolve_reference(self, ref: SymbolReference) -> Optional[str]:
        """
        Attempt to resolve a SymbolReference to a SymbolDefinition's qualified_name.

        TODO [G]: Implement this. Resolution strategy (try in order):
        1. Same-file match: Look for a definition with name=ref.name in the same file
        2. Imported match: Check if ref.name appears in the file's imports,
           then find the definition in the imported module
        3. Global match: Search all definitions across the project for ref.name
           (may produce false positives for common names — prefer same-file matches)

        Return the qualified_name of the best match, or None if unresolvable.
        """
        raise NotImplementedError("Implement _resolve_reference")

    # =========================================================================
    # PAGERANK
    # =========================================================================

    def _run_pagerank(
        self,
        context_files: Optional[list] = None,
        damping: float = 0.85,
        iterations: int = 50,
    ) -> None:
        """
        Run PageRank on the symbol graph to rank symbols by importance.

        TODO [H]: Implement this. This is the algorithm that decides which symbols
        appear in the map. Steps:

        1. Get all nodes from self._symbol_graph
        2. Build a personalization vector:
           - For each node, if its file_path is in context_files, give weight 3.0
           - Otherwise give weight 1.0
           - Normalize so all weights sum to 1.0
        3. Initialize each node's rank to its personalization weight
        4. Iterate `iterations` times:
           For each node:
             incoming_rank = sum of (caller.rank / len(caller.outgoing_calls))
                             for each caller in node.incoming_calls
             new_rank = (1 - damping) * personalization[node] + damping * incoming_rank
        5. Set each node.rank to its final computed rank

        This is standard PageRank with personalization. No external library needed —
        the graph is small enough (hundreds to low thousands of nodes) for a naive
        implementation to converge in <10ms.

        The key insight: symbols that are CALLED by many other symbols rank higher.
        If context_files are provided, symbols in those files get boosted, making
        the map more relevant to the current task.
        """
        raise NotImplementedError("Implement _run_pagerank")

    # =========================================================================
    # SYMBOL SELECTION
    # =========================================================================

    def _select_symbols(self) -> list:
        """
        Select symbols to include in the map, fitting within token_budget.

        TODO [I]: Implement this. Steps:
        1. Sort all SymbolNodes by rank (descending)
        2. Greedily add symbols, estimating each symbol's token cost:
           - A class definition line: ~15-25 tokens
           - A method/function line: ~10-20 tokens
           - The "...calls:" line: ~10-30 tokens
           Use _estimate_tokens(signature_text) for accuracy
        3. Stop when adding the next symbol would exceed self._token_budget
        4. Ensure at least one symbol per file that has definitions
           (so every file appears in the map, even if just the top-ranked symbol)

        Returns:
            List of SymbolNode objects to include in the map.
        """
        raise NotImplementedError("Implement _select_symbols")

    # =========================================================================
    # TEXT FORMATTING
    # =========================================================================

    def _format_map(self, selected: list) -> str:
        """
        Format selected symbols into the concise text representation.

        TODO [J]: Implement this. Steps:
        1. Group selected symbols by file_path
        2. Sort files by the highest-ranked symbol they contain (descending)
        3. For each file, format as:
           ```
           src/models/user.py:
           | class User(BaseModel):
           |   def __init__(self, name: str, email: str)
           |   def validate_email(self) -> bool
           |   ...calls: TokenStore.revoke, EmailValidator.check
           |
           ```
           - Classes first, then standalone functions
           - Methods indented under their parent class
           - "...calls:" line shows notable outgoing calls to OTHER files
             (skip self-calls within the same class)
        4. Add a footer line:
           "(45 files, 312 symbols total | showing top 60 by importance)"
        5. Wrap everything in "===REPOSITORY MAP===" header

        Returns:
            The formatted map string.
        """
        raise NotImplementedError("Implement _format_map")

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        TODO [K]: Simple — return len(text) // CHARS_PER_TOKEN
        This is consistent with how ContextManager estimates tokens.
        """
        return len(text) // CHARS_PER_TOKEN
