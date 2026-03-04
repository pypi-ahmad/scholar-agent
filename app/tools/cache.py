"""
Cache abstraction layer with pluggable backends.

Backends:
    InMemoryCache  — default; keyword-substring matching (original behaviour)
    RedisCache     — enabled when REDIS_URL env var is set; requires ``redis``

Factory:
    get_cache() → selects backend by environment; falls back to InMemoryCache.

Agents must use the factory or the module-level singleton ``global_cache``.
"""

import abc
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("research_agent.tools.cache")


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------
class CacheBackend(abc.ABC):
    """Minimal cache contract expected by the retriever agent."""

    @abc.abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Return cached value for *key*, or a falsy value on miss."""

    @abc.abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store *value* under *key*, with an optional TTL in seconds."""

    @abc.abstractmethod
    def delete(self, key: str) -> None:
        """Remove *key* from the cache (no-op if absent)."""


# ---------------------------------------------------------------------------
# In-memory fallback (original behaviour)
# ---------------------------------------------------------------------------
class InMemoryCache(CacheBackend):
    """
    Simple in-memory cache with case-insensitive substring matching.

    Ships with three hard-coded entries for demonstration.  Suitable as the
    default when no external cache backend is configured.
    """

    def __init__(self) -> None:
        self.store: Dict[str, Any] = {
            "what is the capital of france": "The capital of France is Paris.",
            "who wrote romeo and juliet": "William Shakespeare wrote Romeo and Juliet.",
            "what is 2+2": "2+2 is 4.",
        }

    def get(self, key: str) -> List[Dict[str, str]]:
        """Retrieve a cached answer if it exists (substring match)."""
        key_lower = key.strip().lower().replace("?", "")
        for k, v in self.store.items():
            if k in key_lower or key_lower in k:
                logger.info(f"Cache hit for query: '{key}'")
                return [{"source": f"cache:{k}", "content": v}]
        logger.info(f"Cache miss for query: '{key}'")
        return []

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.store[key.strip().lower()] = value

    def delete(self, key: str) -> None:
        self.store.pop(key.strip().lower(), None)


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------
class RedisCache(CacheBackend):
    """
    Redis-backed cache.  Activated when ``REDIS_URL`` is set.

    Requires the ``redis`` package (``pip install redis``).
    Values are JSON-serialised before storage so compound objects
    (lists, dicts) round-trip cleanly.
    """

    def __init__(self, url: str) -> None:
        import redis  # deferred so the package is optional

        self._client = redis.from_url(url, decode_responses=True)
        # Verify connectivity eagerly so the factory can fall back.
        self._client.ping()
        logger.info("Redis cache connected: %s", url)

    def get(self, key: str) -> Optional[Any]:
        raw = self._client.get(key)
        if raw is None:
            logger.info("Cache miss for key: '%s'", key)
            return None
        logger.info("Cache hit for key: '%s'", key)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        serialised = json.dumps(value) if not isinstance(value, str) else value
        if ttl:
            self._client.setex(key, ttl, serialised)
        else:
            self._client.set(key, serialised)

    def delete(self, key: str) -> None:
        self._client.delete(key)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_cache() -> CacheBackend:
    """Return a cache backend chosen by environment variables.

    * ``REDIS_URL`` set → :class:`RedisCache`
    * otherwise → :class:`InMemoryCache`

    If Redis is requested but unavailable (package missing or server
    unreachable) the factory logs a warning and falls back silently.
    """
    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            return RedisCache(redis_url)
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s), falling back to InMemoryCache", exc
            )
    return InMemoryCache()


# ---------------------------------------------------------------------------
# Module-level singleton — agents import this name
# ---------------------------------------------------------------------------
global_cache: CacheBackend = get_cache()

# Backward-compat alias so existing code referencing QueryCache still works.
QueryCache = InMemoryCache
