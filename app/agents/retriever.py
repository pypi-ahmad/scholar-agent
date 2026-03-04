import logging
import time
from pydantic import BaseModel, Field
from typing import Literal, TypedDict

from app.utils.llm import get_json_llm
from app.utils.prompts import TOOL_ROUTER_PROMPT
from app.tools.web_search import perform_web_search
from app.tools.vector_store import vector_db
from app.tools.cache import global_cache
from app.utils.config import MAX_DOCS_PER_SUBQUERY

logger = logging.getLogger("research_agent.agents.retriever")

class ToolRouterOutput(BaseModel):
    """Structured output for deciding which tool to use."""
    # H-02: Literal type enforces that only the three valid tool names are
    #        accepted.  Any other string from the LLM raises a ValidationError
    #        which is caught in retriever_node and falls back to web_search.
    selected_tool: Literal["web_search", "vector_store", "cache"] = Field(
        description="The chosen tool: 'web_search', 'vector_store', or 'cache'."
    )
    search_query: str = Field(
        description="The highly optimized search query for the selected tool."
    )

class SubQueryState(TypedDict):
    """State for the parallel retriever nodes."""
    sub_query: str

def retriever_node(state: SubQueryState) -> dict:
    """
    Retriever Agent: Routes to the optimal tool and executes retrieval for a sub-query.
    Designed to run in parallel using LangGraph's Send API.
    """
    sub_query = state.get("sub_query", "")
    logger.info(f"--- RETRIEVER AGENT (Sub-query: {sub_query}) ---")
    t0 = time.monotonic()
    
    # 1. Tool Selection (Router logic)
    llm = get_json_llm()
    structured_llm = llm.with_structured_output(ToolRouterOutput)
    chain = TOOL_ROUTER_PROMPT | structured_llm
    
    selected_tool = "web_search"
    search_query = sub_query
    
    try:
        routing_decision = chain.invoke({"sub_question": sub_query})
        selected_tool = routing_decision.selected_tool
        search_query = routing_decision.search_query
        logger.info(f"Router decided on tool: '{selected_tool}' with query: '{search_query}'")
    except Exception as e:
        logger.error(f"Tool routing failed for '{sub_query}': {e}. Defaulting to web_search.")
    
    # 2. Tool Execution
    # C-06: Changed the first two blocks to if/elif so that at most one of
    #        cache/vector_store executes on the initial routing decision.
    #        The final 'if web_search' remains a plain 'if' (not elif) so it
    #        also catches fallbacks mutated by the blocks above.
    # L-07: max_results aligned with perform_web_search default (3).
    documents = []

    if selected_tool == "cache":
        documents = global_cache.get(search_query)
        if not documents:
            logger.info("Cache miss. Falling back to web_search.")
            selected_tool = "web_search"

    elif selected_tool == "vector_store":
        documents = vector_db.similarity_search(search_query)
        if not documents:
            logger.info("Vector store empty. Falling back to web_search.")
            selected_tool = "web_search"

    if selected_tool == "web_search":
        documents = perform_web_search(search_query, max_results=MAX_DOCS_PER_SUBQUERY)

    # Enforce per-sub-query document cap
    documents = documents[:MAX_DOCS_PER_SUBQUERY]

    elapsed = round(time.monotonic() - t0, 3)
    return {
        "documents": documents,
        "history": [f"Retrieved {len(documents)} docs for '{sub_query}' using '{selected_tool}'"],
        "metadata": {
            f"retriever_{sub_query[:40]}_seconds": elapsed,
            f"retriever_{sub_query[:40]}_tool": selected_tool,
            f"retriever_{sub_query[:40]}_doc_count": len(documents),
        },
    }
