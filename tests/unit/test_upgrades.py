"""
Tests for the upgrade features:
- Config / caps
- API auth (X-API-Key)
- Metadata population in agent nodes
- URL sanitization in UI helper
- Caps enforcement in planner, retriever, synthesizer
"""

import asyncio
import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.utils.config as config_mod
import api.app as api_mod


# ── Config module ──────────────────────────────────────────────────────────

class TestConfig:
    def test_default_caps(self):
        assert config_mod.MAX_SUB_QUESTIONS >= 1
        assert config_mod.MAX_DOCS_PER_SUBQUERY >= 1
        assert config_mod.MAX_DOCS_TOTAL >= 1
        assert config_mod.MAX_ITERATIONS >= 1
        assert 0.0 < config_mod.SCORE_THRESHOLD <= 1.0

    def test_int_env_fallback(self):
        assert config_mod._int_env("__NONEXISTENT__", 42) == 42

    def test_int_env_invalid_returns_default(self, monkeypatch):
        monkeypatch.setenv("__TEST_BAD_INT__", "not_a_number")
        assert config_mod._int_env("__TEST_BAD_INT__", 7) == 7


# ── API Auth ───────────────────────────────────────────────────────────────

class TestAPIAuth:
    """Tests for AUTH_MODE × API_KEY interaction."""

    # ── AUTH_MODE = "optional" (legacy / dev convenience) ─────────────────

    def test_optional_open_mode_when_no_key(self, monkeypatch):
        """optional + empty API_KEY → open mode, all requests allowed."""
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "optional")
        monkeypatch.setattr(api_mod, "_API_KEY", "")
        asyncio.run(api_mod._verify_api_key(key=None))

    def test_optional_rejects_wrong_key(self, monkeypatch):
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "optional")
        monkeypatch.setattr(api_mod, "_API_KEY", "secret-123")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(api_mod._verify_api_key(key="wrong-key"))
        assert exc.value.status_code == 401

    def test_optional_rejects_missing_key(self, monkeypatch):
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "optional")
        monkeypatch.setattr(api_mod, "_API_KEY", "secret-123")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(api_mod._verify_api_key(key=None))
        assert exc.value.status_code == 401

    def test_optional_accepts_correct_key(self, monkeypatch):
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "optional")
        monkeypatch.setattr(api_mod, "_API_KEY", "secret-123")
        asyncio.run(api_mod._verify_api_key(key="secret-123"))

    # ── AUTH_MODE = "required" (default / production) ─────────────────────

    def test_required_rejects_when_api_key_not_configured(self, monkeypatch):
        """required + empty API_KEY → 503 server misconfiguration."""
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "required")
        monkeypatch.setattr(api_mod, "_API_KEY", "")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(api_mod._verify_api_key(key=None))
        assert exc.value.status_code == 503

    def test_required_rejects_wrong_key(self, monkeypatch):
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "required")
        monkeypatch.setattr(api_mod, "_API_KEY", "secret-123")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(api_mod._verify_api_key(key="wrong-key"))
        assert exc.value.status_code == 401

    def test_required_rejects_missing_key(self, monkeypatch):
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "required")
        monkeypatch.setattr(api_mod, "_API_KEY", "secret-123")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(api_mod._verify_api_key(key=None))
        assert exc.value.status_code == 401

    def test_required_accepts_correct_key(self, monkeypatch):
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "required")
        monkeypatch.setattr(api_mod, "_API_KEY", "secret-123")
        asyncio.run(api_mod._verify_api_key(key="secret-123"))

    def test_required_503_even_with_key_in_header(self, monkeypatch):
        """Even if the client sends a header, 503 if server has no key."""
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "required")
        monkeypatch.setattr(api_mod, "_API_KEY", "")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(api_mod._verify_api_key(key="anything"))
        assert exc.value.status_code == 503


# ── API metadata in response ───────────────────────────────────────────────

class TestAPIMetadata:
    def test_response_includes_request_id_and_elapsed(self, monkeypatch):
        class FakeGraph:
            def invoke(self, state):
                return {
                    "draft": "report",
                    "iteration": 1,
                    "score": 0.9,
                    "critique": {},
                    "metadata": state.get("metadata", {}),
                    "history": [],
                }

        monkeypatch.setattr(api_mod, "get_compiled_graph", lambda: FakeGraph())
        req = api_mod.ResearchRequest(query="test")
        resp = asyncio.run(api_mod.perform_research(req))

        assert "request_id" in resp.metadata
        assert "elapsed_seconds" in resp.metadata
        assert resp.metadata["elapsed_seconds"] >= 0


# ── Caps in planner ────────────────────────────────────────────────────────

class TestPlannerCaps:
    def test_plan_is_capped(self, monkeypatch):
        import app.agents.planner as planner_mod

        many_qs = [f"q{i}" for i in range(20)]
        chain_result = planner_mod.PlanOutput(sub_questions=many_qs)

        class PromptPipe:
            def __init__(self, chain):
                self.chain = chain

            def __or__(self, other):
                return self.chain

        class Chain:
            def invoke(self, payload):
                return chain_result

        monkeypatch.setattr(planner_mod, "PLANNER_PROMPT", PromptPipe(Chain()))

        class FakeLLM:
            def with_structured_output(self, schema):
                return object()

        monkeypatch.setattr(planner_mod, "get_json_llm", lambda: FakeLLM())
        monkeypatch.setattr(planner_mod, "MAX_SUB_QUESTIONS", 4)

        out = planner_mod.plan_node({"query": "root", "current_step": 0})
        assert len(out["plan"]) == 4


# ── Caps in retriever ──────────────────────────────────────────────────────

class TestRetrieverCaps:
    def test_documents_capped_per_subquery(self, monkeypatch):
        import app.agents.retriever as retriever_mod

        route = retriever_mod.ToolRouterOutput(selected_tool="web_search", search_query="q")

        class PromptPipe:
            def __init__(self, chain):
                self.chain = chain
            def __or__(self, other):
                return self.chain

        class Chain:
            def invoke(self, payload):
                return route

        monkeypatch.setattr(retriever_mod, "TOOL_ROUTER_PROMPT", PromptPipe(Chain()))

        class FakeLLM:
            def with_structured_output(self, schema):
                return object()

        monkeypatch.setattr(retriever_mod, "get_json_llm", lambda: FakeLLM())
        # Return 10 docs from web search
        monkeypatch.setattr(
            retriever_mod,
            "perform_web_search",
            lambda q, max_results=5: [{"source": f"s{i}", "content": f"c{i}"} for i in range(10)],
        )
        monkeypatch.setattr(retriever_mod, "MAX_DOCS_PER_SUBQUERY", 3)

        out = retriever_mod.retriever_node({"sub_query": "q"})
        assert len(out["documents"]) == 3


# ── Metadata in agent outputs ──────────────────────────────────────────────

class TestAgentMetadata:
    def test_planner_emits_metadata(self, monkeypatch):
        import app.agents.planner as planner_mod

        chain_result = planner_mod.PlanOutput(sub_questions=["a"])

        class PromptPipe:
            def __init__(self, chain):
                self.chain = chain
            def __or__(self, other):
                return self.chain

        class Chain:
            def invoke(self, payload):
                return chain_result

        monkeypatch.setattr(planner_mod, "PLANNER_PROMPT", PromptPipe(Chain()))

        class FakeLLM:
            def with_structured_output(self, schema):
                return object()

        monkeypatch.setattr(planner_mod, "get_json_llm", lambda: FakeLLM())

        out = planner_mod.plan_node({"query": "x", "current_step": 0})
        assert "metadata" in out
        assert "planner_seconds" in out["metadata"]

    def test_critic_emits_metadata(self, monkeypatch):
        import app.agents.critic as critic_mod

        critique = critic_mod.CritiqueOutput(
            factuality=0.9, completeness=0.8, clarity=0.7, feedback="ok"
        )

        class PromptPipe:
            def __init__(self, chain):
                self.chain = chain
            def __or__(self, other):
                return self.chain

        class Chain:
            def invoke(self, payload):
                return critique

        monkeypatch.setattr(critic_mod, "CRITIC_PROMPT", PromptPipe(Chain()))

        class FakeLLM:
            def with_structured_output(self, schema):
                return object()

        monkeypatch.setattr(critic_mod, "get_json_llm", lambda temperature=0.1: FakeLLM())

        out = critic_mod.critic_node({"query": "q", "draft": "d", "current_step": 0})
        assert "metadata" in out
        assert "critic_seconds" in out["metadata"]
        assert "critic_score" in out["metadata"]

    def test_synthesizer_emits_metadata(self, monkeypatch):
        import app.agents.synthesizer as synth_mod

        class PromptPipe:
            def __init__(self, chain):
                self.chain = chain
            def __or__(self, other):
                return self.chain

        class Chain:
            def invoke(self, payload):
                return SimpleNamespace(content="draft")

        monkeypatch.setattr(synth_mod, "SYNTHESIZER_PROMPT", PromptPipe(Chain()))
        monkeypatch.setattr(synth_mod, "get_llm", lambda temperature=0.3: object())

        out = synth_mod.synthesizer_node(
            {"query": "q", "documents": [], "current_step": 0, "iteration": 0}
        )
        assert "metadata" in out
        assert "synthesizer_seconds" in out["metadata"]

    def test_refiner_emits_metadata(self, monkeypatch):
        import app.agents.refiner as refiner_mod

        class PromptPipe:
            def __init__(self, chain):
                self.chain = chain
            def __or__(self, other):
                return self.chain

        class Chain:
            def invoke(self, payload):
                return SimpleNamespace(content="refined")

        monkeypatch.setattr(refiner_mod, "REFINER_PROMPT", PromptPipe(Chain()))
        monkeypatch.setattr(refiner_mod, "get_llm", lambda temperature=0.4: object())

        out = refiner_mod.refiner_node(
            {
                "query": "q",
                "draft": "orig",
                "critique": {"factuality": 0.5, "completeness": 0.5, "clarity": 0.5, "feedback": "fix"},
                "current_step": 1,
                "iteration": 1,
            }
        )
        assert "metadata" in out
        assert "refiner_seconds" in out["metadata"]


# ── URL sanitization ──────────────────────────────────────────────────────

class TestURLSanitization:
    """Tests the _is_safe_url helper extracted from the Streamlit UI."""

    @pytest.fixture(autouse=True)
    def _import_helper(self):
        # Import the function from ui module
        import importlib
        import ui.streamlit_app as ui_mod
        self._is_safe_url = ui_mod._is_safe_url

    def test_allows_https_url(self):
        assert self._is_safe_url("https://example.com/article") is True

    def test_allows_http_url(self):
        assert self._is_safe_url("http://example.com") is True

    def test_blocks_localhost(self):
        assert self._is_safe_url("http://localhost:8080/secret") is False

    def test_blocks_127_0_0_1(self):
        assert self._is_safe_url("http://127.0.0.1/admin") is False

    def test_blocks_private_10_range(self):
        assert self._is_safe_url("http://10.0.0.1/internal") is False

    def test_blocks_private_192_168_range(self):
        assert self._is_safe_url("http://192.168.1.1/router") is False

    def test_blocks_ftp_scheme(self):
        assert self._is_safe_url("ftp://files.example.com/data") is False

    def test_blocks_file_scheme(self):
        assert self._is_safe_url("file:///etc/passwd") is False

    def test_handles_garbage_gracefully(self):
        # Should not crash
        result = self._is_safe_url("")
        assert result is False


# ── Builder uses config thresholds ─────────────────────────────────────────

class TestBuilderThresholds:
    def test_should_refine_uses_config_threshold(self, monkeypatch):
        import app.graph.builder as builder
        from langgraph.graph import END

        # Tighten the threshold
        monkeypatch.setattr(builder, "SCORE_THRESHOLD", 0.95)
        monkeypatch.setattr(builder, "MAX_ITERATIONS", 5)

        # 0.9 is below the new threshold — should refine
        assert builder.should_refine({"score": 0.9, "iteration": 1}) == "refiner"
        # 0.95 meets threshold — should end
        assert builder.should_refine({"score": 0.95, "iteration": 1}) == END
        # Iteration cap still works
        assert builder.should_refine({"score": 0.5, "iteration": 5}) == END


# ── SSE streaming endpoint ─────────────────────────────────────────────────

class TestSSEStream:
    """Tests for GET /research/stream."""

    def _fake_graph(self):
        """Return a graph stub whose .stream() yields per-node dicts."""

        class _Graph:
            def stream(self, state):
                yield {"planner": {"plan": ["q1"], "current_step": 1}}
                yield {"retriever": {"documents": [{"source": "s", "content": "c"}]}}
                yield {"synthesizer": {"draft": "report", "iteration": 1}}
                yield {"critic": {"score": 0.9, "critique": {"overall": 0.9}}}

            def invoke(self, state):
                return {}

        return _Graph()

    @staticmethod
    def _collect_events(async_gen):
        """Drain an async generator of SSE dicts into a plain list."""
        async def _drain():
            items = []
            async for item in async_gen:
                items.append(item)
            return items
        return asyncio.run(_drain())

    def test_stream_returns_event_source_response(self, monkeypatch):
        monkeypatch.setattr(api_mod, "get_compiled_graph", lambda: self._fake_graph())
        resp = asyncio.run(api_mod.stream_research(query="hello"))
        # EventSourceResponse wraps our async generator
        assert resp.status_code == 200

    def test_stream_yields_node_and_final_events(self, monkeypatch):
        import json as _json

        monkeypatch.setattr(api_mod, "get_compiled_graph", lambda: self._fake_graph())

        # Collect events directly from the async generator
        events = self._collect_events(api_mod._stream_graph("test-id", "hello"))
        event_types = [e["event"] for e in events]

        # Must contain at least one "node" event and exactly one "final" event
        assert "node" in event_types
        assert event_types.count("final") == 1

        # Each node event must carry expected keys
        for ev in events:
            payload = _json.loads(ev["data"])
            assert "request_id" in payload
            if ev["event"] == "node":
                assert "node" in payload
                assert "payload" in payload
                assert "timestamp" in payload
            elif ev["event"] == "final":
                assert "report" in payload
                assert "metadata" in payload

    def test_stream_error_event_on_failure(self, monkeypatch):
        import json as _json

        class _BrokenGraph:
            def stream(self, state):
                raise RuntimeError("boom")

        monkeypatch.setattr(api_mod, "get_compiled_graph", lambda: _BrokenGraph())

        events = self._collect_events(api_mod._stream_graph("err-id", "fail"))
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        payload = _json.loads(error_events[0]["data"])
        assert "message" in payload
        assert payload["request_id"] == "err-id"

    def test_stream_auth_rejects_wrong_key(self, monkeypatch):
        """Auth on /research/stream is wired via the same _verify_api_key dep."""
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "optional")
        monkeypatch.setattr(api_mod, "_API_KEY", "secret-abc")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(api_mod._verify_api_key(key="wrong"))
        assert exc.value.status_code == 401

    def test_stream_auth_open_mode(self, monkeypatch):
        monkeypatch.setattr(api_mod, "_AUTH_MODE", "optional")
        monkeypatch.setattr(api_mod, "_API_KEY", "")
        # Should NOT raise
        asyncio.run(api_mod._verify_api_key(key=None))


# ── _safe_json helper ──────────────────────────────────────────────────────

class TestSafeJson:
    def test_safe_json_passes_primitives(self):
        assert api_mod._safe_json(42) == 42
        assert api_mod._safe_json("hello") == "hello"

    def test_safe_json_converts_non_serialisable(self):
        result = api_mod._safe_json(object())
        assert isinstance(result, str)

    def test_safe_json_recurses_dicts_and_lists(self):
        inp = {"key": [object(), 1]}
        out = api_mod._safe_json(inp)
        assert isinstance(out["key"][0], str)
        assert out["key"][1] == 1
