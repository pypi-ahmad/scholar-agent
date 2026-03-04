import asyncio

import pytest
from fastapi import HTTPException

import api.app as api_mod


def test_research_request_model_constructs():
    model = api_mod.ResearchRequest(query="ok")
    assert model.query == "ok"


def test_health_check():
    assert api_mod.health_check() == {"status": "ok"}


def test_perform_research_success(monkeypatch):
    # Both 'critique' and 'metadata' carry distinct payloads so we can prove
    # the response is sourced from the correct state key ('metadata'), not
    # from 'critique'.  A regression to state.get("critique") would fail here.
    critique_payload = {"overall": 0.85}
    metadata_payload = {"trace_id": "t1"}

    class FakeGraph:
        def invoke(self, state):
            return {
                "draft": "final",
                "iteration": 2,
                "score": 0.85,
                "critique": critique_payload,
                "metadata": metadata_payload,
                "history": ["h1"],
            }

    monkeypatch.setattr(api_mod, "get_compiled_graph", lambda: FakeGraph())

    req = api_mod.ResearchRequest(query="test")
    response = asyncio.run(api_mod.perform_research(req))

    assert response.final_report == "final"
    assert response.iterations == 2
    assert response.score == 0.85
    # Positive: metadata must equal the 'metadata' state value
    assert response.metadata == metadata_payload
    # Negative: metadata must NOT be the 'critique' state value
    assert response.metadata != critique_payload
    assert response.history == ["h1"]


def test_perform_research_failure_returns_http_500(monkeypatch):
    class FakeGraph:
        def invoke(self, state):
            raise RuntimeError("boom")

    monkeypatch.setattr(api_mod, "get_compiled_graph", lambda: FakeGraph())

    req = api_mod.ResearchRequest(query="test")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api_mod.perform_research(req))

    assert exc.value.status_code == 500
    assert exc.value.detail == "An internal error occurred. Please try again later."


# ---------------------------------------------------------------------------
# API boundary validation – proves bad input is rejected at the Pydantic
# layer, NOT deep inside the graph.  Works with both real Pydantic and the
# validation-aware conftest stub.
# ---------------------------------------------------------------------------

from pydantic import ValidationError as _PydanticValidationError


def test_request_rejects_missing_query():
    """Empty body / missing 'query' key must raise ValidationError."""
    with pytest.raises(_PydanticValidationError):
        api_mod.ResearchRequest()


def test_request_rejects_null_query():
    """Explicitly null query must not pass into the graph."""
    with pytest.raises(_PydanticValidationError):
        api_mod.ResearchRequest(query=None)


def test_request_rejects_empty_string_query():
    """Empty string must be caught by min_length=1 constraint."""
    with pytest.raises(_PydanticValidationError):
        api_mod.ResearchRequest(query="")


def test_request_rejects_oversized_query():
    """Query exceeding max_length=1000 must be rejected at the boundary."""
    with pytest.raises(_PydanticValidationError):
        api_mod.ResearchRequest(query="x" * 1001)


def test_request_accepts_valid_query():
    """Happy-path: a normal query passes validation cleanly."""
    req = api_mod.ResearchRequest(query="How does photosynthesis work?")
    assert req.query == "How does photosynthesis work?"


def test_request_accepts_max_length_query():
    """Boundary: exactly 1000 characters must be accepted."""
    req = api_mod.ResearchRequest(query="a" * 1000)
    assert len(req.query) == 1000
