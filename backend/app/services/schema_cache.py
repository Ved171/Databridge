"""
app/services/schema_cache.py
────────────────────────────
TTL in-memory cache for connector schemas and user permissions.

Replaces the per-call schema fetch in _get_accessible_connectors_with_schema
which was hitting the database every single time a tool was called.

Design:
  - Cache key: (user_id, cache_type) -> e.g. ("user-123", "connectors_with_schema")
  - TTL: 5 minutes (configurable)
  - Invalidation: Cleared automatically on TTL expiry OR manually via clear_cache()
  - Thread-safe: Uses simple Dict[str, CacheEntry] with timestamps
"""
from __future__ import annotations

import time
import json
import logging
from typing import Any, Dict, Optional, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry with TTL metadata."""
    data: Any
    created_at: float = field(default_factory=time.monotonic)
    ttl_seconds: int = 300
    
    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL."""
        elapsed = time.monotonic() - self.created_at
        return elapsed > self.ttl_seconds
    
    def age_seconds(self) -> float:
        """How many seconds old is this entry?"""
        return time.monotonic() - self.created_at


class SchemaCache:
    """
    In-memory TTL cache for schemas and permissions.
    
    Thread-safe for read-heavy workloads; uses monotonic time for expiry checks.
    """
    
    def __init__(self, default_ttl_seconds: int = 300):
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl_seconds
    
    def _make_key(self, user_id: str, data_type: str) -> str:
        """Normalize cache keys."""
        return f"{user_id}:{data_type}"
    
    def get(self, user_id: str, data_type: str) -> Optional[Any]:
        """
        Retrieve cached data if it exists and hasn't expired.
        
        Args:
            user_id: The user ID.
            data_type: Type of data (e.g., "connectors_with_schema", "permissions").
            
        Returns:
            The cached data, or None if missing/expired.
        """
        key = self._make_key(user_id, data_type)
        entry = self._cache.get(key)
        
        if entry is None:
            return None
        
        if entry.is_expired():
            logger.debug(f"Cache expired for {key} after {entry.age_seconds():.1f}s")
            del self._cache[key]
            return None
        
        return entry.data
    
    def set(self, user_id: str, data_type: str, data: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Store data in the cache with optional TTL override.
        
        Args:
            user_id: The user ID.
            data_type: Type of data.
            data: The data to cache.
            ttl_seconds: Optional TTL override (defaults to self._default_ttl).
        """
        key = self._make_key(user_id, data_type)
        ttl = ttl_seconds or self._default_ttl
        self._cache[key] = CacheEntry(data=data, ttl_seconds=ttl)
        logger.debug(f"Cached {key} with TTL {ttl}s")
    
    def clear_for_user(self, user_id: str, data_type: Optional[str] = None) -> None:
        """
        Clear cache for a specific user, optionally filtered by data_type.
        
        Args:
            user_id: The user ID.
            data_type: If provided, only clear this data type; otherwise clear all types for the user.
        """
        if data_type:
            key = self._make_key(user_id, data_type)
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cleared cache entry: {key}")
        else:
            # Clear all entries for this user
            prefix = f"{user_id}:"
            keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._cache[k]
            logger.debug(f"Cleared {len(keys_to_delete)} cache entries for user {user_id}")
    
    def clear_all(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
        logger.info("Cache cleared entirely")
    
    def stats(self) -> Dict[str, Any]:
        """
        Return cache statistics for monitoring/debugging.
        
        Returns:
            Dict with entry count, sizes, expiry status, etc.
        """
        now = time.monotonic()
        entries = []
        for key, entry in self._cache.items():
            entries.append({
                "key": key,
                "age_seconds": entry.age_seconds(),
                "ttl_seconds": entry.ttl_seconds,
                "expired": entry.is_expired(),
                "data_size_bytes": len(str(entry.data).encode("utf-8")),
            })
        
        return {
            "total_entries": len(self._cache),
            "entries": entries,
            "total_memory_mb": sum(e["data_size_bytes"] for e in entries) / (1024 * 1024),
        }


# Global cache instance
_cache = SchemaCache(default_ttl_seconds=300)


def get_cache() -> SchemaCache:
    """Get the global cache instance."""
    return _cache


async def get_or_fetch_connectors_schema(
    user_id: str,
    fetch_fn,  # async callable: () -> List[Dict]
) -> List[Dict]:
    """
    Wrapper: Try cache first; if miss, call fetch_fn and cache result.
    
    Args:
        user_id: The user ID.
        fetch_fn: Async callable that returns the schema data.
        
    Returns:
        The schema data (from cache or freshly fetched).
    """
    cache = get_cache()
    
    # Try cache first
    cached = cache.get(user_id, "connectors_with_schema")
    if cached is not None:
        logger.debug(f"Cache HIT for user {user_id}")
        return cached
    
    # Cache miss: fetch fresh data
    logger.debug(f"Cache MISS for user {user_id}, fetching...")
    data = await fetch_fn()
    cache.set(user_id, "connectors_with_schema", data)
    return data


def invalidate_connector_schema(user_id: Optional[str] = None) -> None:
    """
    Invalidate schema cache (called when sync_schema.py runs or admin updates connectors).
    
    Args:
        user_id: If provided, only invalidate for this user; otherwise invalidate globally.
    """
    cache = get_cache()
    if user_id:
        cache.clear_for_user(user_id, "connectors_with_schema")
    else:
        cache.clear_all()
        logger.info("Schema cache invalidated globally")
