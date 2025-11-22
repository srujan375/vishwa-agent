"""
Caching layer for autocomplete suggestions.

Caches suggestions based on file path, cursor position, and surrounding context.
"""

from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from hashlib import md5
import time


@dataclass
class CachedSuggestion:
    """A cached autocomplete suggestion."""
    suggestion: str
    timestamp: float
    hits: int = 0


class SuggestionCache:
    """
    Cache for autocomplete suggestions.

    Uses file path + cursor position + context hash as key.
    Invalidates cache entries after timeout or when file changes.
    """

    def __init__(self, max_size: int = 100, ttl: int = 300):
        """
        Initialize suggestion cache.

        Args:
            max_size: Maximum number of cached suggestions
            ttl: Time-to-live in seconds (default: 5 minutes)
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, CachedSuggestion] = {}
        self._file_versions: Dict[str, str] = {}  # Track file content hashes

    def _make_key(
        self,
        file_path: str,
        cursor_line: int,
        cursor_char: int,
        context: str
    ) -> str:
        """
        Create cache key from file path, position, and context.

        Args:
            file_path: Path to file
            cursor_line: Line number
            cursor_char: Character position
            context: Surrounding code context

        Returns:
            Cache key string
        """
        # Create hash of context to keep key size reasonable
        context_hash = md5(context.encode()).hexdigest()[:16]
        return f"{file_path}:{cursor_line}:{cursor_char}:{context_hash}"

    def _make_file_version_key(self, file_path: str, content: str) -> str:
        """
        Create version key for file content.

        Args:
            file_path: Path to file
            content: File content

        Returns:
            Content hash
        """
        return md5(content.encode()).hexdigest()

    def get(
        self,
        file_path: str,
        cursor_line: int,
        cursor_char: int,
        context: str,
        file_content: str
    ) -> Optional[str]:
        """
        Get cached suggestion if available.

        Args:
            file_path: Path to file
            cursor_line: Line number
            cursor_char: Character position
            context: Surrounding code context
            file_content: Current file content

        Returns:
            Cached suggestion or None
        """
        # Check if file has changed
        current_version = self._make_file_version_key(file_path, file_content)
        cached_version = self._file_versions.get(file_path)

        if cached_version and cached_version != current_version:
            # File changed, invalidate all cache entries for this file
            self._invalidate_file(file_path)
            self._file_versions[file_path] = current_version
            return None

        # Update file version
        self._file_versions[file_path] = current_version

        # Try to get from cache
        key = self._make_key(file_path, cursor_line, cursor_char, context)
        cached = self._cache.get(key)

        if not cached:
            return None

        # Check if expired
        if time.time() - cached.timestamp > self.ttl:
            del self._cache[key]
            return None

        # Update hit count
        cached.hits += 1

        return cached.suggestion

    def put(
        self,
        file_path: str,
        cursor_line: int,
        cursor_char: int,
        context: str,
        file_content: str,
        suggestion: str
    ):
        """
        Store suggestion in cache.

        Args:
            file_path: Path to file
            cursor_line: Line number
            cursor_char: Character position
            context: Surrounding code context
            file_content: Current file content
            suggestion: Suggestion to cache
        """
        # Update file version
        current_version = self._make_file_version_key(file_path, file_content)
        self._file_versions[file_path] = current_version

        # Evict old entries if cache is full
        if len(self._cache) >= self.max_size:
            self._evict_lru()

        # Store suggestion
        key = self._make_key(file_path, cursor_line, cursor_char, context)
        self._cache[key] = CachedSuggestion(
            suggestion=suggestion,
            timestamp=time.time(),
            hits=0
        )

    def _invalidate_file(self, file_path: str):
        """
        Invalidate all cache entries for a file.

        Args:
            file_path: Path to file
        """
        # Remove all keys starting with file_path
        keys_to_remove = [
            key for key in self._cache.keys()
            if key.startswith(f"{file_path}:")
        ]
        for key in keys_to_remove:
            del self._cache[key]

    def _evict_lru(self):
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find oldest entry (lowest timestamp)
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].timestamp
        )
        del self._cache[oldest_key]

    def clear(self):
        """Clear all cached suggestions."""
        self._cache.clear()
        self._file_versions.clear()

    def get_stats(self) -> Dict[str, any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_hits = sum(cached.hits for cached in self._cache.values())
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'total_hits': total_hits,
            'files_tracked': len(self._file_versions)
        }
