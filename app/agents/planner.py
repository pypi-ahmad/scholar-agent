import logging
import time
from pydantic import BaseModel, Field
from typing import List

from app.utils.llm import get_json_llm
from app.utils.prompts import PLANNER_PROMPT
from app.utils.config import MAX_SUB_QUESTIONS
from app.graph.state import AgentState

logger = logging.getLogger("research_agent.agents.planner")

class PlanOutput(BaseModel):
    """Structured output for the Planner."""
    sub_questions: List[str] = Field(
        description="A list of specific, actionable sub-questions to research in parallel."
    )

def plan_node(state: AgentState) -> dict:
    """
    Planner Node: Takes the main query and breaks it down into sub-questions.
    """
    logger.info("--- PLANNER AGENT ---")
    t0 = time.monotonic()
    query = str(state.get("query", "")).strip()
    
    # Instantiate LLM and force JSON output matching the Pydantic schema
    llm = get_json_llm()
    structured_llm = llm.with_structured_output(PlanOutput)
    
    chain = PLANNER_PROMPT | structured_llm
    
    try:
        result = chain.invoke({"query": query})
        plan = result.sub_questions[:MAX_SUB_QUESTIONS]
        logger.info(f"Planner generated {len(plan)} sub-questions (cap={MAX_SUB_QUESTIONS}).")
    except Exception as e:
        logger.error(f"Planner failed: {str(e)}")
        # Graceful fallback: just use the main query as the only sub-question
        plan = [query] if query else [""]

    # Return state updates
    elapsed = round(time.monotonic() - t0, 3)
    return {
        "plan": plan,
        "history": [f"Planner broke down the query into {len(plan)} sub-questions."],
        "current_step": state.get("current_step", 0) + 1,
        "metadata": {"planner_seconds": elapsed, "sub_question_count": len(plan)},
    }
