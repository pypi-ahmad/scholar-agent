"""
Import smoke test — validates that all production modules can be imported
with real dependencies (no conftest stubs).

This test catches the failure mode where CI tests pass with module stubs
but production crashes on a missing or broken dependency.

Run separately from the hermetic unit suite:
    python -m pytest tests/integration/test_import_smoke.py -v
"""

import importlib

import pytest

# Every production module that must be importable at runtime.
_PRODUCTION_MODULES = [
    "app.graph.state",
    "app.graph.builder",
    "app.agents.planner",
    "app.agents.retriever",
    "app.agents.synthesizer",
    "app.agents.critic",
    "app.agents.refiner",
    "app.tools.cache",
    "app.tools.vector_store",
    "app.tools.web_search",
    "app.utils.llm",
    "app.utils.prompts",
    "app.utils.logger",
    "api.app",
]


@pytest.mark.parametrize("module_path", _PRODUCTION_MODULES)
def test_production_module_imports(module_path: str):
    """Each production module must import without error."""
    mod = importlib.import_module(module_path)
    assert mod is not None


def test_build_graph_returns_compiled():
    """The graph builder must produce a compilable graph object."""
    from app.graph.builder import build_graph

    graph = build_graph()
    assert graph is not None
