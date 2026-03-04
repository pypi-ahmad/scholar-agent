from types import SimpleNamespace

import pytest

import app.agents.critic as critic_mod
import app.agents.planner as planner_mod
import app.agents.refiner as refiner_mod
import app.agents.retriever as retriever_mod
import app.agents.synthesizer as synth_mod


class PromptPipe:
    def __init__(self, chain):
        self.chain = chain

    def __or__(self, other):
        return self.chain


class Chain:
    def __init__(self, invoke_result=None, exc=None):
        self.invoke_result = invoke_result
        self.exc = exc

    def invoke(self, payload):
        if self.exc:
            raise self.exc
        return self.invoke_result


def test_plan_node_success(monkeypatch):
    chain = Chain(invoke_result=planner_mod.PlanOutput(sub_questions=["a", "b"]))
    monkeypatch.setattr(planner_mod, "PLANNER_PROMPT", PromptPipe(chain))

    class FakeLLM:
        def with_structured_output(self, schema):
            return object()

    monkeypatch.setattr(planner_mod, "get_json_llm", lambda: FakeLLM())

    out = planner_mod.plan_node({"query": "root", "current_step": 0})
    assert out["plan"] == ["a", "b"]
    assert out["current_step"] == 1


def test_plan_node_failure_fallback(monkeypatch):
    monkeypatch.setattr(planner_mod, "PLANNER_PROMPT", PromptPipe(Chain(exc=RuntimeError("down"))))

    class FakeLLM:
        def with_structured_output(self, schema):
            return object()

    monkeypatch.setattr(planner_mod, "get_json_llm", lambda: FakeLLM())

    out = planner_mod.plan_node({"query": "root", "current_step": 0})
    assert out["plan"] == ["root"]


def test_tool_router_output_validation():
    retriever_mod.ToolRouterOutput(selected_tool="cache", search_query="q")


def test_retriever_cache_hit(monkeypatch):
    route = retriever_mod.ToolRouterOutput(selected_tool="cache", search_query="q")
    monkeypatch.setattr(retriever_mod, "TOOL_ROUTER_PROMPT", PromptPipe(Chain(invoke_result=route)))

    class FakeLLM:
        def with_structured_output(self, schema):
            return object()

    monkeypatch.setattr(retriever_mod, "get_json_llm", lambda: FakeLLM())
    monkeypatch.setattr(retriever_mod, "global_cache", SimpleNamespace(get=lambda q: [{"source": "cache:x", "content": "y"}]))

    out = retriever_mod.retriever_node({"sub_query": "q"})
    assert len(out["documents"]) == 1


def test_retriever_cache_miss_falls_back_to_web(monkeypatch):
    route = retriever_mod.ToolRouterOutput(selected_tool="cache", search_query="q")
    monkeypatch.setattr(retriever_mod, "TOOL_ROUTER_PROMPT", PromptPipe(Chain(invoke_result=route)))

    class FakeLLM:
        def with_structured_output(self, schema):
            return object()

    monkeypatch.setattr(retriever_mod, "get_json_llm", lambda: FakeLLM())
    monkeypatch.setattr(retriever_mod, "global_cache", SimpleNamespace(get=lambda q: []))
    monkeypatch.setattr(retriever_mod, "perform_web_search", lambda q, max_results=3: [{"source": "web", "content": "c"}])

    out = retriever_mod.retriever_node({"sub_query": "q"})
    assert out["documents"][0]["source"] == "web"


def test_synthesizer_no_docs_success(monkeypatch):
    monkeypatch.setattr(synth_mod, "SYNTHESIZER_PROMPT", PromptPipe(Chain(invoke_result=SimpleNamespace(content="draft"))))
    monkeypatch.setattr(synth_mod, "get_llm", lambda temperature=0.3: object())

    out = synth_mod.synthesizer_node({"query": "q", "documents": [], "current_step": 0, "iteration": 0})
    assert out["draft"] == "draft"
    assert out["iteration"] == 1


def test_synthesizer_failure_fallback(monkeypatch):
    monkeypatch.setattr(synth_mod, "SYNTHESIZER_PROMPT", PromptPipe(Chain(exc=RuntimeError("down"))))
    monkeypatch.setattr(synth_mod, "get_llm", lambda temperature=0.3: object())

    out = synth_mod.synthesizer_node({"query": "q", "documents": [], "current_step": 0, "iteration": 0})
    assert "Failed to synthesize" in out["draft"]


def test_critique_output_validation():
    critic_mod.CritiqueOutput(factuality=0.5, completeness=0.5, clarity=0.5, feedback="ok")


def test_critic_node_missing_draft():
    out = critic_mod.critic_node({"query": "q", "draft": ""})
    assert out["score"] == 0.0


def test_critic_node_success(monkeypatch):
    critique = critic_mod.CritiqueOutput(factuality=0.9, completeness=0.6, clarity=0.6, feedback="ok")
    monkeypatch.setattr(critic_mod, "CRITIC_PROMPT", PromptPipe(Chain(invoke_result=critique)))

    class FakeLLM:
        def with_structured_output(self, schema):
            return object()

    monkeypatch.setattr(critic_mod, "get_json_llm", lambda temperature=0.1: FakeLLM())

    out = critic_mod.critic_node({"query": "q", "draft": "d", "current_step": 0})
    assert out["score"] == round((0.9 + 0.6 + 0.6) / 3.0, 2)


def test_refiner_skips_when_missing_input():
    out = refiner_mod.refiner_node({"query": "q", "draft": "", "critique": {}})
    assert "draft" not in out


def test_refiner_success(monkeypatch):
    monkeypatch.setattr(refiner_mod, "REFINER_PROMPT", PromptPipe(Chain(invoke_result=SimpleNamespace(content="refined"))))
    monkeypatch.setattr(refiner_mod, "get_llm", lambda temperature=0.4: object())

    out = refiner_mod.refiner_node(
        {
            "query": "q",
            "draft": "orig",
            "critique": {"factuality": 0.5, "completeness": 0.5, "clarity": 0.5, "feedback": "improve"},
            "current_step": 1,
            "iteration": 1,
        }
    )
    assert out["draft"] == "refined"
    assert out["current_step"] == 2
    assert "iteration" not in out
