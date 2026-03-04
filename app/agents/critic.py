import logging
import time
from pydantic import BaseModel, Field

from app.utils.llm import get_json_llm
from app.utils.prompts import CRITIC_PROMPT
from app.graph.state import AgentState

logger = logging.getLogger("research_agent.agents.critic")

class CritiqueOutput(BaseModel):
    """Structured output for the Critic Agent."""
    # H-01: Added ge/le constraints so Pydantic rejects out-of-range LLM values
    #        (e.g. 1.5 or -0.1) before they corrupt the routing threshold.
    factuality: float = Field(
        ge=0.0, le=1.0,
        description="Score between 0.0 and 1.0. How fact-based and accurately cited the draft is."
    )
    completeness: float = Field(
        ge=0.0, le=1.0,
        description="Score between 0.0 and 1.0. How thoroughly the query is answered."
    )
    clarity: float = Field(
        ge=0.0, le=1.0,
        description="Score between 0.0 and 1.0. How readable and structured the report is."
    )
    feedback: str = Field(
        description="Specific, actionable suggestions for improving the draft if scores are below 1.0."
    )

def critic_node(state: AgentState) -> dict:
    """
    Critic Agent: Evaluates the draft report based on multi-metric scoring.
    """
    logger.info("--- CRITIC AGENT ---")
    t0 = time.monotonic()
    query = state.get("query")
    draft = state.get("draft")
    
    if not draft:
        logger.error("No draft provided to the Critic Agent.")
        return {
            "score": 0.0,
            "critique": {"error": "Missing draft."},
            "history": ["Critic failed: Missing draft."]
        }
    
    # 1. Invoke structured LLM critic
    llm = get_json_llm(temperature=0.1) # low temp for strict evaluation
    structured_llm = llm.with_structured_output(CritiqueOutput)
    chain = CRITIC_PROMPT | structured_llm
    
    try:
        critique_result = chain.invoke({"query": query, "draft": draft})
        
        # 2. Compute overall score
        overall_score = round(
            (critique_result.factuality + critique_result.completeness + critique_result.clarity) / 3.0, 
            2
        )
        logger.info(f"Critique Output: Score {overall_score} (F:{critique_result.factuality}, C:{critique_result.completeness}, Cl:{critique_result.clarity})")
        
        critique_dict = {
            "factuality": critique_result.factuality,
            "completeness": critique_result.completeness,
            "clarity": critique_result.clarity,
            "overall": overall_score,
            "feedback": critique_result.feedback
        }
        
    except Exception:
        logger.error("Critic Agent failed", exc_info=True)
        overall_score = 0.5
        critique_dict = {
            "overall": overall_score,
            "feedback": "Critic failed to evaluate properly.",
            "factuality": 0.0,
            "completeness": 0.0,
            "clarity": 0.0
        }

    # Return state updates
    elapsed = round(time.monotonic() - t0, 3)
    return {
        "critique": critique_dict,
        "score": overall_score,
        "history": [f"Critic evaluated draft: overall score {overall_score}."],
        "current_step": state.get("current_step", 0) + 1,
        "metadata": {"critic_seconds": elapsed, "critic_score": overall_score},
    }
