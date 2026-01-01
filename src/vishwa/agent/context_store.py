"""
Session-scoped context store for sharing data between agents.

This module provides a transparent caching layer that all agents share within
a session, enabling efficient context sharing without duplicate searches.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedFile:
    """Cached file content with metadata."""

    content: str
    mtime: float
    size: int


@dataclass
class ContextStore:
    """
    Session-scoped context store for sharing data between agents.

    This store provides transparent caching for file reads, searches, and glob
    operations. It tracks modified files and can provide aggregated context
    for code review.

    Usage:
        store = ContextStore()

        # File operations (called by ReadFileTool)
        content = store.get_file("/path/to/file.py")
        if content is None:
            content = read_file_from_disk(path)
            store.store_file(path, content)

        # Search operations (called by GrepTool)
        results = store.get_search("pattern", "/path", "flags")
        if results is None:
            results = run_grep(pattern, path, flags)
            store.store_search(pattern, path, results, flags)

        # Invalidation (called by write tools)
        store.invalidate("/path/to/modified/file.py")
    """

    # File content cache: path -> CachedFile
    file_cache: dict[str, CachedFile] = field(default_factory=dict)

    # Search results cache: (pattern, path, flags) -> results
    search_cache: dict[tuple[str, str, str], list[Any]] = field(default_factory=dict)

    # Glob results cache: (pattern, path) -> file_list
    glob_cache: dict[tuple[str, str], list[str]] = field(default_factory=dict)

    # Paths modified this session
    modified_files: set[str] = field(default_factory=set)

    # Original content before modifications (for diff generation)
    original_contents: dict[str, str] = field(default_factory=dict)

    # --- File Operations ---

    def get_file(self, path: str) -> str | None:
        """
        Get cached file content if available and not stale.

        Args:
            path: Absolute path to the file

        Returns:
            File content if cached and fresh, None otherwise
        """
        path = os.path.abspath(path)

        if path not in self.file_cache:
            return None

        cached = self.file_cache[path]

        # Check if file has changed externally
        if self._is_stale(path, cached):
            del self.file_cache[path]
            return None

        return cached.content

    def store_file(self, path: str, content: str) -> None:
        """
        Store file content in cache.

        Args:
            path: Absolute path to the file
            content: File content to cache
        """
        path = os.path.abspath(path)

        try:
            stat = os.stat(path)
            self.file_cache[path] = CachedFile(
                content=content,
                mtime=stat.st_mtime,
                size=stat.st_size,
            )
        except OSError:
            # File doesn't exist or can't be stat'd, store without metadata
            self.file_cache[path] = CachedFile(
                content=content,
                mtime=0,
                size=len(content),
            )

    # --- Search Operations ---

    def get_search(
        self, pattern: str, path: str, flags: str = ""
    ) -> list[Any] | None:
        """
        Get cached search results if available.

        Args:
            pattern: Search pattern (regex)
            path: Search path
            flags: Search flags (e.g., "-i" for case insensitive)

        Returns:
            Cached search results or None
        """
        key = (pattern, os.path.abspath(path), flags)
        return self.search_cache.get(key)

    def store_search(
        self, pattern: str, path: str, results: list[Any], flags: str = ""
    ) -> None:
        """
        Store search results in cache.

        Args:
            pattern: Search pattern (regex)
            path: Search path
            results: Search results to cache
            flags: Search flags
        """
        key = (pattern, os.path.abspath(path), flags)
        self.search_cache[key] = results

    # --- Glob Operations ---

    def get_glob(self, pattern: str, path: str) -> list[str] | None:
        """
        Get cached glob results if available.

        Args:
            pattern: Glob pattern
            path: Base path for glob

        Returns:
            Cached file list or None
        """
        key = (pattern, os.path.abspath(path))
        return self.glob_cache.get(key)

    def store_glob(self, pattern: str, path: str, files: list[str]) -> None:
        """
        Store glob results in cache.

        Args:
            pattern: Glob pattern
            path: Base path for glob
            files: List of matching files
        """
        key = (pattern, os.path.abspath(path))
        self.glob_cache[key] = files

    # --- Modification Tracking ---

    def mark_modified(self, path: str, original_content: str | None = None) -> None:
        """
        Mark a file as modified in this session.

        Args:
            path: Path to the modified file
            original_content: Original content before modification (optional)
        """
        path = os.path.abspath(path)
        self.modified_files.add(path)

        # Store original content if provided and not already stored
        if original_content is not None and path not in self.original_contents:
            self.original_contents[path] = original_content

    def get_modified_files(self) -> set[str]:
        """Get set of all files modified in this session."""
        return self.modified_files.copy()

    def get_original_content(self, path: str) -> str | None:
        """Get original content of a file before modification."""
        return self.original_contents.get(os.path.abspath(path))

    # --- Invalidation ---

    def invalidate(self, path: str) -> None:
        """
        Invalidate cache entries for a modified file.

        This should be called after any file modification (str_replace,
        write_file, multi_edit).

        Args:
            path: Path to the modified file
        """
        path = os.path.abspath(path)

        # Store original content before invalidation if we have it cached
        if path in self.file_cache and path not in self.original_contents:
            self.original_contents[path] = self.file_cache[path].content

        # Remove from file cache
        self.file_cache.pop(path, None)

        # Mark as modified
        self.modified_files.add(path)

        # Invalidate search results that might include this file
        self._invalidate_searches_for_path(path)

        # Invalidate glob results that might include this file
        self._invalidate_globs_for_path(path)

    def invalidate_all(self) -> None:
        """Clear all caches. Useful for testing or session reset."""
        self.file_cache.clear()
        self.search_cache.clear()
        self.glob_cache.clear()
        # Note: Don't clear modified_files or original_contents

    # --- Context Aggregation for Review ---

    def get_context_for_review(self) -> dict[str, Any]:
        """
        Get aggregated context for the code review sub-agent.

        Returns:
            Dictionary containing:
            - modified_files: Set of modified file paths
            - file_contents: Dict of path -> current content
            - original_contents: Dict of path -> original content
            - imports: Dict of path -> list of imported modules
        """
        file_contents: dict[str, str] = {}
        imports: dict[str, list[str]] = {}

        for path in self.modified_files:
            # Get current content (from cache or disk)
            content = self.get_file(path)
            if content is None and os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        content = f.read()
                    self.store_file(path, content)
                except (OSError, UnicodeDecodeError):
                    continue

            if content:
                file_contents[path] = content

                # Extract imports for Python files
                if path.endswith(".py"):
                    imports[path] = self._extract_imports(content)

        return {
            "modified_files": self.modified_files.copy(),
            "file_contents": file_contents,
            "original_contents": {
                p: c for p, c in self.original_contents.items() if p in self.modified_files
            },
            "imports": imports,
        }

    # --- Private Helpers ---

    def _is_stale(self, path: str, cached: CachedFile) -> bool:
        """Check if cached file is stale (file changed on disk)."""
        try:
            stat = os.stat(path)
            return stat.st_mtime != cached.mtime or stat.st_size != cached.size
        except OSError:
            # File doesn't exist anymore
            return True

    def _invalidate_searches_for_path(self, path: str) -> None:
        """Remove search cache entries that might include the given path."""
        path_dir = os.path.dirname(path)
        keys_to_remove = [
            key for key in self.search_cache if path.startswith(key[1]) or key[1].startswith(path_dir)
        ]
        for key in keys_to_remove:
            del self.search_cache[key]

    def _invalidate_globs_for_path(self, path: str) -> None:
        """Remove glob cache entries that might include the given path."""
        path_dir = os.path.dirname(path)
        keys_to_remove = [
            key for key in self.glob_cache if path.startswith(key[1]) or key[1].startswith(path_dir)
        ]
        for key in keys_to_remove:
            del self.glob_cache[key]

    def _extract_imports(self, content: str) -> list[str]:
        """Extract import statements from Python code."""
        imports = []

        # Match 'import x' and 'from x import y'
        import_pattern = re.compile(
            r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE
        )

        for match in import_pattern.finditer(content):
            module = match.group(1) or match.group(2)
            if module:
                imports.append(module)

        return imports
