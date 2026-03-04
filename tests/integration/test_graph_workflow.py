import app.graph.builder as builder


def _initial_state(query="root"):
    return {
        "query": query,
        "plan": [],
        "current_step": 0,
        "documents": [],
        "draft": "",
        "critique": {},
        "score": 0.0,
        "iteration": 0,
        "history": [],
        "metadata": {},
    }


def test_workflow_parallel_retrieval_and_end(monkeypatch):
    calls = {"retriever": []}

    def planner_node(state):
        return {"plan": ["q1", "q2"], "history": ["planned"], "current_step": state.get("current_step", 0) + 1}

    def retriever_node(state):
        sq = state["sub_query"]
        calls["retriever"].append(sq)
        return {"documents": [{"source": sq, "content": f"doc-{sq}"}], "history": [f"retrieved-{sq}"]}

    def synthesizer_node(state):
        assert len(state.get("documents", [])) == 2
        return {
            "draft": "draft-v1",
            "iteration": state.get("iteration", 0) + 1,
            "history": ["synthesized"],
            "current_step": state.get("current_step", 0) + 1,
        }

    def critic_node(state):
        return {
            "score": 0.9,
            "critique": {"overall": 0.9},
            "history": ["critic-ok"],
            "current_step": state.get("current_step", 0) + 1,
        }

    def refiner_node(state):
        raise AssertionError("refiner should not run when critic score >= 0.8")

    monkeypatch.setattr(builder, "plan_node", planner_node)
    monkeypatch.setattr(builder, "retriever_node", retriever_node)
    monkeypatch.setattr(builder, "synthesizer_node", synthesizer_node)
    monkeypatch.setattr(builder, "critic_node", critic_node)
    monkeypatch.setattr(builder, "refiner_node", refiner_node)

    graph = builder.build_graph()
    final_state = graph.invoke(_initial_state())

    assert sorted(calls["retriever"]) == ["q1", "q2"]
    assert final_state["score"] == 0.9
    assert final_state["iteration"] == 1
    assert len(final_state["documents"]) == 2


def test_workflow_refinement_loop_then_end(monkeypatch):
    calls = {"critic": 0, "refiner": 0}

    def planner_node(state):
        return {"plan": ["q1"], "history": ["planned"], "current_step": state.get("current_step", 0) + 1}

    def retriever_node(state):
        return {"documents": [{"source": "q1", "content": "doc"}], "history": ["retrieved"]}

    def synthesizer_node(state):
        return {
            "draft": "draft-v1",
            "iteration": state.get("iteration", 0) + 1,
            "history": ["synthesized"],
            "current_step": state.get("current_step", 0) + 1,
        }

    def critic_node(state):
        calls["critic"] += 1
        if calls["critic"] == 1:
            return {
                "score": 0.5,
                "critique": {"overall": 0.5, "feedback": "improve"},
                "history": ["critic-low"],
                "current_step": state.get("current_step", 0) + 1,
            }
        return {
            "score": 0.85,
            "critique": {"overall": 0.85, "feedback": "ok"},
            "history": ["critic-high"],
            "current_step": state.get("current_step", 0) + 1,
        }

    def refiner_node(state):
        calls["refiner"] += 1
        return {
            "draft": "draft-v2",
            "history": ["refined"],
            "current_step": state.get("current_step", 0) + 1,
        }

    monkeypatch.setattr(builder, "plan_node", planner_node)
    monkeypatch.setattr(builder, "retriever_node", retriever_node)
    monkeypatch.setattr(builder, "synthesizer_node", synthesizer_node)
    monkeypatch.setattr(builder, "critic_node", critic_node)
    monkeypatch.setattr(builder, "refiner_node", refiner_node)

    graph = builder.build_graph()
    final_state = graph.invoke(_initial_state())

    assert calls["critic"] == 2
    assert calls["refiner"] == 1
    assert final_state["draft"] == "draft-v2"
    assert final_state["score"] == 0.85
