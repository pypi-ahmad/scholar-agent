import logging
import time
from app.utils.llm import get_llm
from app.utils.prompts import REFINER_PROMPT
from app.graph.state import AgentState

logger = logging.getLogger("research_agent.agents.refiner")

def refiner_node(state: AgentState) -> dict:
    """
    Refiner Agent: Improves the draft report based on the critique feedback.
    Maintains existing citations and corrects factual/structural issues.
    """
    logger.info("--- REFINER AGENT ---")
    t0 = time.monotonic()
    query = state.get("query")
    draft = state.get("draft")
    critique_dict = state.get("critique", {})
    
    if not draft or not critique_dict:
        logger.warning("Refiner missing draft or critique. Returning state unmodified.")
        return {
            "history": ["Refiner skipped: Missing draft or critique."]
        }
        
    # 1. Format critique for the prompt
    critique_text = (
        f"Factuality Score: {critique_dict.get('factuality', 'N/A')}\n"
        f"Completeness Score: {critique_dict.get('completeness', 'N/A')}\n"
        f"Clarity Score: {critique_dict.get('clarity', 'N/A')}\n"
        f"Feedback: {critique_dict.get('feedback', 'No feedback provided.')}"
    )
    
    logger.info("Refining draft based on critique feedback.")
    
    # 2. Invoke LLM Refiner
    llm = get_llm(temperature=0.4) # A bit of creativity allowed to restructure
    chain = REFINER_PROMPT | llm
    
    try:
        result = chain.invoke({
            "query": query, 
            "draft": draft, 
            "critique": critique_text
        })
        refined_draft = result.content
        logger.info("Draft successfully refined.")
    except Exception as e:
        logger.error(f"Refiner failed: {str(e)}")
        # Fallback to the original draft if it fails
        refined_draft = draft

    # Return state updates
    # C-05: Removed 'iteration' increment from the refiner.
    #        Only the synthesizer owns the iteration counter (one synthesis pass
    #        = one iteration).  Previously the refiner also incremented, causing
    #        the loop to exhaust after only 2 refinements instead of 3.
    elapsed = round(time.monotonic() - t0, 3)
    return {
        "draft": refined_draft,
        "history": ["Refiner applied feedback and updated draft."],
        "current_step": state.get("current_step", 0) + 1,
        "metadata": {"refiner_seconds": elapsed},
    }
