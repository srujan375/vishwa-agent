"""
Smart Cache System - Cache results of expensive operations.

This cache system stores results of repeated operations like:
- File reads
- Directory listings
- Grep searches
- Structure analysis

Caches are automatically invalidated when files are modified.
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from vishwa.utils.logger import logger


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    data: Any
    created_at: float
    access_count: int = 0
    last_accessed: float = 0
    file_hash: Optional[str] = None  # Hash of source file if applicable


class SmartCache:
    """
    Smart cache with automatic invalidation and LRU eviction.
    
    Features:
    - File-based caching with automatic invalidation
    - LRU eviction when cache limit reached
    - Time-based expiration
    - Operation-based cache keys
    """

    def __init__(self, cache_dir: str = ".vishwa_cache", max_size_mb: int = 100):
        """
        Initialize smart cache.
        
        Args:
            cache_dir: Directory for cache files
            max_size_mb: Maximum cache size in MB
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        # In-memory index for fast lookups
        self.index: Dict[str, CacheEntry] = {}
        
        # Load existing cache
        self._load_cache_index()
        
        # Cleanup expired entries periodically
        self._cleanup_expired()

    def _load_cache_index(self) -> None:
        """Load cache index from disk"""
        index_file = self.cache_dir / "index.json"
        
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    data = json.load(f)
                    
                for key, entry_data in data.items():
                    entry = CacheEntry(**entry_data)
                    self.index[key] = entry
                    
                logger.debug("cache", f"Loaded {len(self.index)} cache entries")
                
            except Exception as e:
                logger.error("cache", f"Failed to load cache index: {e}")
                self.index = {}

    def _save_cache_index(self) -> None:
        """Save cache index to disk"""
        index_file = self.cache_dir / "index.json"
        
        try:
            # Convert to serializable format
            data = {}
            for key, entry in self.index.items():
                data[key] = asdict(entry)
                
            with open(index_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error("cache", f"Failed to save cache index: {e}")

    def _cleanup_expired(self) -> None:
        """Remove expired entries"""
        now = time.time()
        expired_keys = []
        
        for key, entry in self.index.items():
            # Remove entries older than 24 hours
            if now - entry.created_at > 24 * 3600:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_entry(key)
        
        if expired_keys:
            logger.debug("cache", f"Cleaned up {len(expired_keys)} expired entries")

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for key"""
        # Hash the key to avoid filesystem issues
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    def _calculate_file_hash(self, file_path: Union[str, Path]) -> Optional[str]:
        """Calculate hash of a file's content and mtime"""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
                
            stat = path.stat()
            
            # Combine mtime and size for hash
            hash_input = f"{stat.st_mtime}:{stat.st_size}"
            return hashlib.md5(hash_input.encode()).hexdigest()
            
        except Exception:
            return None

    def _remove_entry(self, key: str) -> None:
        """Remove a cache entry"""
        cache_path = self._get_cache_path(key)
        
        try:
            if cache_path.exists():
                cache_path.unlink()
        except Exception:
            pass
            
        if key in self.index:
            del self.index[key]

    def get(self, key: str, file_path: Optional[Union[str, Path]] = None) -> Optional[Any]:
        """
        Get cached value.
        
        Args:
            key: Cache key
            file_path: Optional file path to check for staleness
            
        Returns:
            Cached value or None if not found/stale
        """
        entry = self.index.get(key)
        
        if not entry:
            return None
        
        # Check file staleness
        if file_path and entry.file_hash:
            current_hash = self._calculate_file_hash(file_path)
            if current_hash != entry.file_hash:
                # File has changed, invalidate cache
                self._remove_entry(key)
                return None
        
        # Update access statistics
        entry.access_count += 1
        entry.last_accessed = time.time()
        
        # Load data from cache file
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
                
            logger.debug("cache", f"Cache hit for key: {key}")
            return data
            
        except Exception as e:
            logger.error("cache", f"Failed to load cache entry {key}: {e}")
            self._remove_entry(key)
            return None

    def set(
        self,
        key: str,
        data: Any,
        file_path: Optional[Union[str, Path]] = None,
        ttl: Optional[int] = None
    ) -> None:
        """
        Set cached value.
        
        Args:
            key: Cache key
            data: Value to cache
            file_path: Optional file path to track for invalidation
            ttl: Time to live in seconds (default: 24h)
        """
        # Calculate file hash if file path provided
        file_hash = None
        if file_path:
            file_hash = self._calculate_file_hash(file_path)
        
        # Check cache size and evict if needed
        self._evict_if_needed()
        
        # Create cache entry
        entry = CacheEntry(
            data=data,
            created_at=time.time(),
            file_hash=file_hash
        )
        
        # Save to index
        self.index[key] = entry
        
        # Save data to cache file
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug("cache", f"Cached key: {key}")
            
        except Exception as e:
            logger.error("cache", f"Failed to cache {key}: {e}")
            self._remove_entry(key)

    def _evict_if_needed(self) -> None:
        """Evict least recently used entries if cache is full"""
        current_size = self._calculate_cache_size()
        
        if current_size < self.max_size_bytes:
            return
        
        # Sort by access count (LRU) and access time
        entries = [
            (entry.access_count, entry.last_accessed, key)
            for key, entry in self.index.items()
        ]
        
        entries.sort(key=lambda x: (x[0], x[1]))  # Sort by access count, then time
        
        # Evict 20% of entries
        evict_count = max(1, len(entries) // 5)
        
        for _, _, key in entries[:evict_count]:
            self._remove_entry(key)
            logger.debug("cache", f"Evicted cache entry: {key}")
        
        self._save_cache_index()

    def _calculate_cache_size(self) -> int:
        """Calculate current cache size in bytes"""
        total_size = 0
        
        for entry in self.index.values():
            cache_path = self._get_cache_path(entry.created_at)  # Use created_at as proxy for hash
            if cache_path.exists():
                total_size += cache_path.stat().st_size
        
        # Add index size
        index_file = self.cache_dir / "index.json"
        if index_file.exists():
            total_size += index_file.stat().st_size
        
        return total_size

    def invalidate(self, file_path: Optional[Union[str, Path]] = None) -> None:
        """
        Invalidate cache entries.
        
        Args:
            file_path: If provided, invalidate entries related to this file
                      If None, invalidate all cache
        """
        if file_path:
            # Invalidate entries related to specific file
            file_path_str = str(file_path)
            keys_to_remove = []
            
            for key in list(self.index.keys()):
                entry = self.index[key]
                if entry.file_hash:
                    # This is a heuristic - invalidate if key contains file path
                    if file_path_str in key:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._remove_entry(key)
            
            logger.debug("cache", f"Invalidated {len(keys_to_remove)} entries for {file_path}")
            
        else:
            # Invalidate all cache
            for key in list(self.index.keys()):
                self._remove_entry(key)
            
            logger.debug("cache", "Invalidated all cache entries")

    def clear(self) -> None:
        """Clear all cache"""
        for key in list(self.index.keys()):
            self._remove_entry(key)
        
        logger.info("cache", "Cleared all cache")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_size = self._calculate_cache_size()
        
        stats = {
            "entries": len(self.index),
            "size_mb": total_size / (1024 * 1024),
            "max_size_mb": self.max_size_bytes / (1024 * 1024),
            "hit_rate": 0  # TODO: Track hit rate
        }
        
        return stats


# Global cache instance
_global_cache: Optional[SmartCache] = None


def get_cache() -> SmartCache:
    """Get global cache instance"""
    global _global_cache
    
    if _global_cache is None:
        _global_cache = SmartCache()
    
    return _global_cache


def cache_key(operation: str, **kwargs) -> str:
    """Generate cache key from operation and parameters"""
    # Create sorted key-value pairs
    items = sorted(kwargs.items())
    key_str = f"{operation}:" + ":".join(f"{k}={v}" for k, v in items)
    
    return key_str


def cached_operation(
    operation: str,
    ttl: Optional[int] = None,
    key_func: Optional[callable] = None
):
    """
    Decorator for caching function results.
    
    Args:
        operation: Operation name for cache key
        ttl: Time to live in seconds
        key_func: Optional function to generate cache key from args
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = cache_key(operation, args=str(args), kwargs=str(sorted(kwargs.items())))
            
            # Try to get from cache
            result = cache.get(key)
            
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


class FileReadCache:
    """Specialized cache for file reads with smart invalidation"""
    
    def __init__(self):
        self.cache = get_cache()
    
    def get_file_content(self, file_path: Union[str, Path]) -> Optional[Tuple[str, float]]:
        """
        Get cached file content and mtime.
        
        Returns:
            Tuple of (content, mtime) or None if not cached/stale
        """
        key = f"file_read:{file_path}"
        cached = self.cache.get(key, file_path=file_path)
        
        if cached:
            return cached["content"], cached["mtime"]
        
        return None
    
    def set_file_content(
        self,
        file_path: Union[str, Path],
        content: str,
        mtime: float
    ) -> None:
        """Cache file content"""
        key = f"file_read:{file_path}"
        
        self.cache.set(
            key,
            {"content": content, "mtime": mtime},
            file_path=file_path
        )
    
    def invalidate_file(self, file_path: Union[str, Path]) -> None:
        """Invalidate cache for specific file"""
        key = f"file_read:{file_path}"
        
        # Remove from cache
        cache_entry = self.cache.index.get(key)
        if cache_entry:
            cache_path = self.cache._get_cache_path(key)
            try:
                if cache_path.exists():
                    cache_path.unlink()
            except Exception:
                pass
            del self.cache.index[key]
            self.cache._save_cache_index()


# Invalidate file cache when files are modified
_file_modification_times: Dict[str, float] = {}


def track_file_modification(file_path: Union[str, Path]) -> None:
    """Track that a file has been modified"""
    path_str = str(file_path)
    _file_modification_times[path_str] = time.time()
    
    # Invalidate cache
    cache = get_cache()
    cache.invalidate(file_path)


def was_file_modified_since(
    file_path: Union[str, Path],
    timestamp: float
) -> bool:
    """Check if file has been modified since timestamp"""
    path_str = str(file_path)
    
    # Check modification time
    try:
        mtime = os.path.getmtime(file_path)
        if mtime > timestamp:
            return True
    except OSError:
        pass
    
    # Check if we tracked a modification
    if path_str in _file_modification_times:
        return _file_modification_times[path_str] > timestamp
    
    return False