import os

import pytest

import app.tools.cache as cache_mod
import app.tools.vector_store as vector_mod
import app.tools.web_search as web_mod
import app.utils.llm as llm_mod
import app.utils.logger as logger_mod


def test_setup_logger_reuses_existing_handlers():
    name = "pytest.logger.reuse"
    logger = logger_mod.setup_logger(name)
    count_before = len(logger.handlers)
    logger2 = logger_mod.setup_logger(name)
    count_after = len(logger2.handlers)
    assert count_before == count_after


def test_get_llm_raises_when_google_api_key_missing(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ValueError):
        llm_mod.get_llm()


def test_get_llm_constructs_chat_model(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    captured = {}

    class FakeChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_mod, "ChatGoogleGenerativeAI", FakeChat)
    model = llm_mod.get_llm(model_name="gemini-2.0-flash", temperature=0.6)

    assert isinstance(model, FakeChat)
    assert captured["model"] == "gemini-2.0-flash"
    assert captured["temperature"] == 0.6
    assert captured["google_api_key"] == "fake-key"
    assert captured["max_retries"] == 3


def test_get_json_llm_delegates_to_get_llm(monkeypatch):
    sentinel = object()

    def fake_get_llm(model_name, temperature):
        assert model_name == "m"
        assert temperature == 0.1
        return sentinel

    monkeypatch.setattr(llm_mod, "get_llm", fake_get_llm)
    out = llm_mod.get_json_llm(model_name="m", temperature=0.1)
    assert out is sentinel


def test_query_cache_hit_and_miss():
    cache = cache_mod.QueryCache()
    hit = cache.get("what is the capital of france?")
    miss = cache.get("this query should miss cache")

    assert len(hit) == 1
    assert hit[0]["source"].startswith("cache:")
    assert miss == []


def test_vector_store_similarity_and_fallback():
    vdb = vector_mod.VectorStoreWrapper()

    matched = vdb.similarity_search("revenue ai", k=2)
    fallback = vdb.similarity_search("zzzzz qqqqq", k=2)

    assert len(matched) >= 1
    assert len(fallback) == 2


def test_web_search_uses_mock_when_key_missing(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    out = web_mod.perform_web_search("query")
    assert len(out) == 2
    assert "mock-search.com" in out[0]["source"]


def test_web_search_uses_tavily_when_key_present(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "real-key")

    class FakeTavily:
        def __init__(self, max_results):
            self.max_results = max_results

        def invoke(self, payload):
            assert payload["query"] == "hello"
            return [{"url": "http://src", "content": "body"}]

    monkeypatch.setattr(web_mod, "TavilySearchResults", FakeTavily)
    out = web_mod.perform_web_search("hello", max_results=4)

    assert out == [{"source": "http://src", "content": "body"}]


def test_web_search_exception_returns_error_fallback(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "real-key")

    class FakeTavily:
        def __init__(self, max_results):
            pass

        def invoke(self, payload):
            raise RuntimeError("rate limited")

    monkeypatch.setattr(web_mod, "TavilySearchResults", FakeTavily)
    out = web_mod.perform_web_search("hello")

    assert len(out) == 1
    assert out[0]["source"] == "error_fallback"
    assert out[0]["content"] == "Search failed for 'hello'."
