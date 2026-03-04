import logging
import time
from app.utils.llm import get_llm
from app.utils.prompts import SYNTHESIZER_PROMPT
from app.utils.config import MAX_DOCS_TOTAL
from app.graph.state import AgentState

logger = logging.getLogger("research_agent.agents.synthesizer")

def synthesizer_node(state: AgentState) -> dict:
    """
    Synthesizer Agent: Generates the initial drafted report.
    It combines all retrieved documents into context, enforcing strict citations.
    """
    logger.info("--- SYNTHESIZER AGENT ---")
    t0 = time.monotonic()
    query = state.get("query")
    documents = state.get("documents", [])
    
    # 1. Format context for prompt
    # C-03: unique_docs initialised here so it is always bound regardless of which
    #        branch executes; prevents NameError on log/return lines below.
    unique_docs = []
    if not documents:
        formatted_docs = "No documents found."
        logger.warning("Synthesizer running without retrieved documents.")
    else:
        # De-duplicate documents based on exact source+content match
        seen = set()
        for doc in documents:
            sig = (doc.get("source"), doc.get("content"))
            if sig not in seen:
                seen.add(sig)
                unique_docs.append(doc)
                
        # Enforce total document cap after dedup
        unique_docs = unique_docs[:MAX_DOCS_TOTAL]

        formatted_docs = "\n\n".join(
            [f"Source: [{doc.get('source')}]\nContent: {doc.get('content')}" for doc in unique_docs]
        )
        
    logger.info(f"Synthesizing report using {len(unique_docs) if documents else 0} unique document snippets.")
    
    # 2. Invoke LLM Synthesizer
    llm = get_llm(temperature=0.3)  # Slightly higher temperature for generation, but constrained by context
    chain = SYNTHESIZER_PROMPT | llm
    
    try:
        result = chain.invoke({"query": query, "documents": formatted_docs})
        draft = result.content
        logger.info("Draft synthesis completed.")
    except Exception as e:
        logger.error(f"Synthesizer failed: {str(e)}")
        draft = "Failed to synthesize report due to an internal error."

    # Return state updates
    elapsed = round(time.monotonic() - t0, 3)
    return {
        "draft": draft,
        "history": [f"Synthesized initial draft using {len(unique_docs) if documents else 0} unique documents."],
        "current_step": state.get("current_step", 0) + 1,
        "iteration": state.get("iteration", 0) + 1,  # Increment iteration counter for cyclic loop
        "metadata": {
            "synthesizer_seconds": elapsed,
            "unique_doc_count": len(unique_docs) if documents else 0,
        },
    }
