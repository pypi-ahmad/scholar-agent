import logging
import threading
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send

from app.graph.state import AgentState
from app.agents.planner import plan_node
from app.agents.retriever import retriever_node
from app.agents.synthesizer import synthesizer_node
from app.agents.critic import critic_node
from app.agents.refiner import refiner_node
from app.utils.config import MAX_ITERATIONS, SCORE_THRESHOLD

logger = logging.getLogger("research_agent.graph.builder")

def continue_to_retrieve(state: AgentState):
    """
    Fan-out function: Maps the generated sub-questions to parallel retriever nodes.
    """
    plan = state.get("plan", [])
    if not plan:
        logger.warning("No plan generated. Falling back to default query.")
        plan = [state.get("query", "Default query fallback")]
        
    logger.info(f"Fanning out to {len(plan)} parallel retriever nodes.")
    # Send each sub-query to its own instance of the retriever node
    return [Send("retriever", {"sub_query": q}) for q in plan]

def should_refine(state: AgentState):
    """
    Conditional edge logic: Decides whether to refine the draft or finish.
    """
    score = state.get("score", 0.0)
    iteration = state.get("iteration", 0)
    
    logger.info(f"Evaluating routing: Score={score}, Iteration={iteration}")
    
    if score >= SCORE_THRESHOLD:
        logger.info(f"Draft score meets threshold (>= {SCORE_THRESHOLD}). Ending flow.")
        return END
    if iteration >= MAX_ITERATIONS:
        logger.info(f"Max iterations ({MAX_ITERATIONS}) reached. Ending flow.")
        return END
        
    logger.info("Draft score below threshold. Routing to refiner.")
    return "refiner"

def build_graph():
    """Builds and compiles the Multi-Agent LangGraph."""
    logger.info("Building the LangGraph orchestration...")
    
    # Initialize the graph with the Advanced State Schema
    workflow = StateGraph(AgentState)
    
    # Add all agent nodes
    workflow.add_node("planner", plan_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("refiner", refiner_node)
    
    # 1. Start execution at the planner
    workflow.add_edge(START, "planner")
    
    # 2. Planner fans out to parallel retrievers
    workflow.add_conditional_edges(
        "planner", 
        continue_to_retrieve, 
        ["retriever"]
    )
    
    # 3. All parallel retrievers fan-in to the synthesizer
    workflow.add_edge("retriever", "synthesizer")
    
    # 4. Synthesizer passes the draft to the critic
    workflow.add_edge("synthesizer", "critic")
    
    # 5. Critic evaluates and loops conditionally
    workflow.add_conditional_edges(
        "critic",
        should_refine,
        ["refiner", END]
    )
    
    # 6. Refiner passes improved draft back to critic
    workflow.add_edge("refiner", "critic")
    
    # Compile the state machine
    app_graph = workflow.compile()
    logger.info("LangGraph compiled successfully.")

    return app_graph


_compiled_graph = None
_compiled_graph_lock = threading.Lock()


def get_compiled_graph():
    """H-04: Lazy initialiser — compiles the graph on first call only.

    Keeping build_graph() out of module-level scope means:
    - Importing builder in tests does NOT trigger a full graph compilation.
    - Test doubles can be injected before the first call.
    - Import errors surface at the call site, not at import time.
    """
    global _compiled_graph
    if _compiled_graph is None:
        with _compiled_graph_lock:
            if _compiled_graph is None:
                _compiled_graph = build_graph()
    return _compiled_graph
