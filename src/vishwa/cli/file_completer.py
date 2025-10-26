"""
File path autocomplete for @ mentions in Vishwa.

This module provides fuzzy file path completion when users type @ in the interactive prompt.
"""

import os
from pathlib import Path
from typing import Iterable, List
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class FileCompleter(Completer):
    """
    Autocompletes file paths when user types @ in the prompt.

    Provides fuzzy matching on file names and shows relative paths from workspace root.
    """

    def __init__(self, workspace_root: Path, max_suggestions: int = 10):
        """
        Initialize the file completer.

        Args:
            workspace_root: Root directory to search for files
            max_suggestions: Maximum number of suggestions to show
        """
        self.workspace_root = Path(workspace_root)
        self.max_suggestions = max_suggestions
        self._file_cache: List[Path] = []
        self._cache_files()

    def _cache_files(self) -> None:
        """
        Cache all files in workspace for fast lookups.

        Excludes common directories like .git, node_modules, __pycache__, etc.
        """
        excluded_dirs = {
            '.git', '.vscode', '.idea', 'node_modules', '__pycache__',
            'venv', '.venv', 'env', '.env', 'dist', 'build', '.pytest_cache',
            '.mypy_cache', '.tox', 'eggs', '.eggs', '*.egg-info'
        }

        self._file_cache = []

        try:
            for root, dirs, files in os.walk(self.workspace_root):
                # Remove excluded directories from search
                dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith('.')]

                root_path = Path(root)
                for file in files:
                    # Skip hidden files and common artifacts
                    if file.startswith('.') or file.endswith(('.pyc', '.pyo')):
                        continue

                    file_path = root_path / file
                    self._file_cache.append(file_path)
        except Exception:
            # If caching fails, continue with empty cache
            pass

    def _fuzzy_match(self, query: str, filepath: Path) -> bool:
        """
        Check if query fuzzy matches the file path.

        Args:
            query: User's search query
            filepath: File path to check against

        Returns:
            True if query matches the file path
        """
        if not query:
            return True

        query_lower = query.lower()

        # Get relative path from workspace
        try:
            rel_path = filepath.relative_to(self.workspace_root)
            path_str = str(rel_path).replace('\\', '/')
        except ValueError:
            path_str = str(filepath)

        path_lower = path_str.lower()

        # Simple fuzzy matching:
        # 1. Exact substring match
        if query_lower in path_lower:
            return True

        # 2. Match on filename only
        filename = filepath.name.lower()
        if query_lower in filename:
            return True

        # 3. Character-by-character fuzzy match
        # e.g., "fcom" matches "file_completer.py"
        query_idx = 0
        for char in path_lower:
            if query_idx < len(query_lower) and char == query_lower[query_idx]:
                query_idx += 1

        return query_idx == len(query_lower)

    def _get_match_priority(self, query: str, filepath: Path) -> int:
        """
        Get priority score for a match (lower is better).

        Args:
            query: User's search query
            filepath: File path

        Returns:
            Priority score (0 = best match)
        """
        try:
            rel_path = filepath.relative_to(self.workspace_root)
            path_str = str(rel_path).replace('\\', '/')
        except ValueError:
            path_str = str(filepath)

        query_lower = query.lower()
        path_lower = path_str.lower()
        filename_lower = filepath.name.lower()

        # Priority levels:
        # 0: Exact filename match
        if filename_lower == query_lower:
            return 0

        # 1: Filename starts with query
        if filename_lower.startswith(query_lower):
            return 1

        # 2: Path starts with query
        if path_lower.startswith(query_lower):
            return 2

        # 3: Exact substring in filename
        if query_lower in filename_lower:
            return 3

        # 4: Exact substring in path
        if query_lower in path_lower:
            return 4

        # 5: Fuzzy match
        return 5

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """
        Generate file path completions for @ mentions.

        Args:
            document: Current prompt document
            complete_event: Completion event

        Yields:
            Completion objects for matching files
        """
        text_before_cursor = document.text_before_cursor

        # Check if we're in an @ mention
        if '@' not in text_before_cursor:
            return

        # Find the last @ symbol
        last_at = text_before_cursor.rfind('@')

        # Get the query after @
        query = text_before_cursor[last_at + 1:]

        # If there's a space after @, don't complete
        if ' ' in query:
            return

        # Find matching files
        matches = []
        for filepath in self._file_cache:
            if self._fuzzy_match(query, filepath):
                priority = self._get_match_priority(query, filepath)
                matches.append((priority, filepath))

        # Sort by priority, then alphabetically
        matches.sort(key=lambda x: (x[0], str(x[1])))

        # Limit to max suggestions
        matches = matches[:self.max_suggestions]

        # Generate completions
        for _, filepath in matches:
            try:
                rel_path = filepath.relative_to(self.workspace_root)
                display_path = str(rel_path).replace('\\', '/')
            except ValueError:
                display_path = str(filepath)

            # The text to insert is the path
            completion_text = display_path

            # Calculate start position (after @)
            start_position = -len(query)

            yield Completion(
                text=completion_text,
                start_position=start_position,
                display=display_path,
                display_meta=f"📄 {filepath.suffix or 'file'}",
            )

    def refresh_cache(self) -> None:
        """Refresh the file cache to pick up new/deleted files."""
        self._cache_files()
