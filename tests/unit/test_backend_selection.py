"""
Unit tests for data-backend factory / selection logic.

All tests are hermetic — no Redis server, no FAISS index, no Chroma DB
required.  Concrete backends are monkeypatched or intentionally allowed
to fail so the factory's fallback logic is exercised.
"""

import os

import pytest

import app.tools.cache as cache_mod
import app.tools.vector_store as vs_mod


# ── Cache interface conformance ──────────────────────────────────────────────


class TestInMemoryCache:
    """Verify InMemoryCache satisfies CacheBackend contract."""

    def test_isinstance(self):
        cache = cache_mod.InMemoryCache()
        assert isinstance(cache, cache_mod.CacheBackend)

    def test_get_hit_returns_list(self):
        cache = cache_mod.InMemoryCache()
        result = cache.get("what is the capital of france?")
        assert len(result) == 1
        assert result[0]["source"].startswith("cache:")

    def test_get_miss_returns_empty_list(self):
        cache = cache_mod.InMemoryCache()
        assert cache.get("no match anywhere") == []

    def test_set_and_get(self):
        cache = cache_mod.InMemoryCache()
        cache.set("my_key", "my_value")
        # InMemoryCache.get does substring matching — exact key should hit.
        assert cache.store.get("my_key") == "my_value"

    def test_delete(self):
        cache = cache_mod.InMemoryCache()
        cache.set("del_key", "val")
        cache.delete("del_key")
        assert "del_key" not in cache.store


class TestRedisCacheInterface:
    """RedisCache class exists and inherits CacheBackend."""

    def test_is_subclass(self):
        assert issubclass(cache_mod.RedisCache, cache_mod.CacheBackend)


# ── Cache factory ────────────────────────────────────────────────────────────


class TestCacheFactory:
    def test_defaults_to_in_memory(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        cache = cache_mod.get_cache()
        assert isinstance(cache, cache_mod.InMemoryCache)

    def test_selects_redis_when_url_set(self, monkeypatch):
        """If REDIS_URL is set and the backend initialises, factory returns it."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        class _FakeRedis(cache_mod.CacheBackend):
            def __init__(self, url):
                self.url = url

            def get(self, key):
                return None

            def set(self, key, value, ttl=None):
                pass

            def delete(self, key):
                pass

        monkeypatch.setattr(cache_mod, "RedisCache", _FakeRedis)
        cache = cache_mod.get_cache()
        assert isinstance(cache, _FakeRedis)
        assert cache.url == "redis://localhost:6379"

    def test_falls_back_when_redis_unavailable(self, monkeypatch):
        """If RedisCache raises during init, factory falls back silently."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        def _broken(url):
            raise ConnectionError("server not reachable")

        monkeypatch.setattr(cache_mod, "RedisCache", _broken)
        cache = cache_mod.get_cache()
        assert isinstance(cache, cache_mod.InMemoryCache)

    def test_global_cache_is_cache_backend(self):
        """Module-level singleton satisfies the abstract interface."""
        assert isinstance(cache_mod.global_cache, cache_mod.CacheBackend)


# ── Backward compat alias ───────────────────────────────────────────────────


class TestCacheBackwardCompat:
    def test_query_cache_alias(self):
        assert cache_mod.QueryCache is cache_mod.InMemoryCache


# ── VectorStore interface conformance ────────────────────────────────────────


class TestInMemoryVectorStore:
    """Verify InMemoryVectorStore satisfies VectorStoreBackend contract."""

    def test_isinstance(self):
        vs = vs_mod.InMemoryVectorStore()
        assert isinstance(vs, vs_mod.VectorStoreBackend)

    def test_similarity_search_keyword_hit(self):
        vs = vs_mod.InMemoryVectorStore()
        results = vs.similarity_search("revenue ai", k=2)
        assert len(results) >= 1

    def test_similarity_search_fallback(self):
        vs = vs_mod.InMemoryVectorStore()
        results = vs.similarity_search("zzzzz qqqqq", k=2)
        assert len(results) == 2

    def test_add_documents(self):
        vs = vs_mod.InMemoryVectorStore()
        before = len(vs.mock_db)
        vs.add_documents([{"source": "new.pdf", "content": "new content"}])
        assert len(vs.mock_db) == before + 1


class TestFAISSVectorStoreInterface:
    def test_is_subclass(self):
        assert issubclass(vs_mod.FAISSVectorStore, vs_mod.VectorStoreBackend)


class TestChromaVectorStoreInterface:
    def test_is_subclass(self):
        assert issubclass(vs_mod.ChromaVectorStore, vs_mod.VectorStoreBackend)


# ── VectorStore factory ─────────────────────────────────────────────────────


class TestVectorStoreFactory:
    def test_defaults_to_in_memory(self, monkeypatch):
        monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)
        monkeypatch.delenv("VECTOR_DB_PATH", raising=False)
        vs = vs_mod.get_vector_store()
        assert isinstance(vs, vs_mod.InMemoryVectorStore)

    def test_selects_chroma_when_dir_set(self, monkeypatch):
        monkeypatch.setenv("CHROMA_PERSIST_DIR", "/tmp/chroma")
        monkeypatch.delenv("VECTOR_DB_PATH", raising=False)

        class _FakeChroma(vs_mod.VectorStoreBackend):
            def __init__(self, d, em):
                self.dir = d

            def add_documents(self, docs):
                pass

            def similarity_search(self, query, k=2):
                return []

        monkeypatch.setattr(vs_mod, "ChromaVectorStore", _FakeChroma)
        vs = vs_mod.get_vector_store()
        assert isinstance(vs, _FakeChroma)
        assert vs.dir == "/tmp/chroma"

    def test_selects_faiss_when_path_set(self, monkeypatch):
        monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)
        monkeypatch.setenv("VECTOR_DB_PATH", "/tmp/faiss")

        class _FakeFAISS(vs_mod.VectorStoreBackend):
            def __init__(self, p, em):
                self.path = p

            def add_documents(self, docs):
                pass

            def similarity_search(self, query, k=2):
                return []

        monkeypatch.setattr(vs_mod, "FAISSVectorStore", _FakeFAISS)
        vs = vs_mod.get_vector_store()
        assert isinstance(vs, _FakeFAISS)
        assert vs.path == "/tmp/faiss"

    def test_chroma_has_priority_over_faiss(self, monkeypatch):
        """When both env vars are set, Chroma wins."""
        monkeypatch.setenv("CHROMA_PERSIST_DIR", "/tmp/chroma")
        monkeypatch.setenv("VECTOR_DB_PATH", "/tmp/faiss")

        class _FakeChroma(vs_mod.VectorStoreBackend):
            def __init__(self, d, em):
                pass

            def add_documents(self, docs):
                pass

            def similarity_search(self, query, k=2):
                return []

        monkeypatch.setattr(vs_mod, "ChromaVectorStore", _FakeChroma)
        vs = vs_mod.get_vector_store()
        assert isinstance(vs, _FakeChroma)

    def test_falls_back_when_chroma_unavailable(self, monkeypatch):
        monkeypatch.setenv("CHROMA_PERSIST_DIR", "/tmp/chroma")
        monkeypatch.delenv("VECTOR_DB_PATH", raising=False)

        def _broken(d, em):
            raise ImportError("chromadb not installed")

        monkeypatch.setattr(vs_mod, "ChromaVectorStore", _broken)
        vs = vs_mod.get_vector_store()
        assert isinstance(vs, vs_mod.InMemoryVectorStore)

    def test_falls_back_when_faiss_unavailable(self, monkeypatch):
        monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)
        monkeypatch.setenv("VECTOR_DB_PATH", "/tmp/faiss")

        def _broken(p, em):
            raise ImportError("faiss not installed")

        monkeypatch.setattr(vs_mod, "FAISSVectorStore", _broken)
        vs = vs_mod.get_vector_store()
        assert isinstance(vs, vs_mod.InMemoryVectorStore)

    def test_embedding_model_env_var(self, monkeypatch):
        """EMBEDDING_MODEL env var is forwarded to the backend constructor."""
        monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)
        monkeypatch.setenv("VECTOR_DB_PATH", "/tmp/faiss")
        monkeypatch.setenv("EMBEDDING_MODEL", "custom-model")

        captured = {}

        class _FakeFAISS(vs_mod.VectorStoreBackend):
            def __init__(self, p, em):
                captured["model"] = em

            def add_documents(self, docs):
                pass

            def similarity_search(self, query, k=2):
                return []

        monkeypatch.setattr(vs_mod, "FAISSVectorStore", _FakeFAISS)
        vs_mod.get_vector_store()
        assert captured["model"] == "custom-model"

    def test_vector_db_singleton_is_backend(self):
        """Module-level singleton satisfies the abstract interface."""
        assert isinstance(vs_mod.vector_db, vs_mod.VectorStoreBackend)


# ── Backward compat alias ───────────────────────────────────────────────────


class TestVectorStoreBackwardCompat:
    def test_wrapper_alias(self):
        assert vs_mod.VectorStoreWrapper is vs_mod.InMemoryVectorStore
