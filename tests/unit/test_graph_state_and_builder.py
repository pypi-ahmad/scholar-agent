import app.graph.builder as builder
import app.graph.state as state_mod
from langgraph.graph import END, START


def test_append_to_list_variants():
    assert state_mod.append_to_list([1, 2], [3]) == [1, 2, 3]
    assert state_mod.append_to_list(None, [1]) == [1]
    assert state_mod.append_to_list([1], None) == [1]
    assert state_mod.append_to_list(None, None) == []


def test_update_dict_variants():
    assert state_mod.update_dict({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
    assert state_mod.update_dict(None, {"a": 1}) == {"a": 1}
    assert state_mod.update_dict({"a": 1}, None) == {"a": 1}
    assert state_mod.update_dict({"a": 1}, {"a": 2}) == {"a": 2}


def test_continue_to_retrieve_from_plan(monkeypatch):
    captured = []

    def fake_send(node_name, payload):
        captured.append((node_name, payload))
        return {"node": node_name, "payload": payload}

    monkeypatch.setattr(builder, "Send", fake_send)

    out = builder.continue_to_retrieve({"plan": ["q1", "q2"]})

    assert len(out) == 2
    assert captured == [
        ("retriever", {"sub_query": "q1"}),
        ("retriever", {"sub_query": "q2"}),
    ]


def test_continue_to_retrieve_falls_back_to_query(monkeypatch):
    captured = []

    def fake_send(node_name, payload):
        captured.append((node_name, payload))
        return {"node": node_name, "payload": payload}

    monkeypatch.setattr(builder, "Send", fake_send)

    out = builder.continue_to_retrieve({"plan": [], "query": "root-query"})

    assert len(out) == 1
    assert captured[0] == ("retriever", {"sub_query": "root-query"})


def test_should_refine_boundaries():
    assert builder.should_refine({"score": 0.8, "iteration": 1}) == END
    assert builder.should_refine({"score": 0.9, "iteration": 0}) == END
    assert builder.should_refine({"score": 0.2, "iteration": 3}) == END
    assert builder.should_refine({"score": 0.79, "iteration": 2}) == "refiner"
    assert builder.should_refine({"score": 0.0, "iteration": 0}) == "refiner"


def test_build_graph_wires_expected_nodes_and_edges(monkeypatch):
    class FakeWorkflow:
        def __init__(self, state_schema):
            self.state_schema = state_schema
            self.nodes = []
            self.edges = []
            self.cond_edges = []

        def add_node(self, name, fn):
            self.nodes.append((name, fn))

        def add_edge(self, a, b):
            self.edges.append((a, b))

        def add_conditional_edges(self, node, fn, options):
            self.cond_edges.append((node, fn, options))

        def compile(self):
            return {
                "nodes": self.nodes,
                "edges": self.edges,
                "conditional": self.cond_edges,
            }

    monkeypatch.setattr(builder, "StateGraph", FakeWorkflow)

    compiled = builder.build_graph()

    node_names = [name for name, _ in compiled["nodes"]]
    assert set(node_names) == {
        "planner",
        "retriever",
        "synthesizer",
        "critic",
        "refiner",
    }
    assert (START, "planner") in compiled["edges"]
    assert ("retriever", "synthesizer") in compiled["edges"]
    assert ("synthesizer", "critic") in compiled["edges"]
    assert ("refiner", "critic") in compiled["edges"]

    planner_cond = [item for item in compiled["conditional"] if item[0] == "planner"][0]
    critic_cond = [item for item in compiled["conditional"] if item[0] == "critic"][0]
    assert planner_cond[2] == ["retriever"]
    assert critic_cond[2] == ["refiner", END]


def test_get_compiled_graph_is_lazy_singleton(monkeypatch):
    sentinel = object()
    calls = {"count": 0}

    def fake_build_graph():
        calls["count"] += 1
        return sentinel

    builder._compiled_graph = None
    monkeypatch.setattr(builder, "build_graph", fake_build_graph)

    first = builder.get_compiled_graph()
    second = builder.get_compiled_graph()

    assert first is sentinel
    assert second is sentinel
    assert calls["count"] == 1
