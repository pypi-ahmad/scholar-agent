import os
import logging
from typing import List, Dict
from langchain_community.tools.tavily_search import TavilySearchResults

logger = logging.getLogger("research_agent.tools.web_search")

# S-04: Maximum query length forwarded to the external Tavily API.
_MAX_QUERY_LEN = 500


def perform_web_search(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """
    Executes a web search using Tavily.
    Returns a list of dicts: [{'source': URL, 'content': text_snippet}].
    If TAVILY_API_KEY is not set, falls back to a mock search for testing.
    """
    # S-04: Strip and truncate user-supplied query before forwarding to the
    #        external Tavily API to limit prompt-injection and SSRF exposure.
    query = query.strip()[:_MAX_QUERY_LEN]
    api_key = os.getenv("TAVILY_API_KEY")
    
    if not api_key or api_key == "your_tavily_api_key_here":
        logger.warning("TAVILY_API_KEY missing or default. Using mock web search.")
        return [
            {
                "source": f"https://mock-search.com/result-1?q={query.replace(' ', '+')}",
                "content": f"Mock result 1 for query: {query}. The quick brown fox jumps over the lazy dog."
            },
            {
                "source": f"https://mock-search.com/result-2?q={query.replace(' ', '+')}",
                "content": f"Mock result 2 for query: {query}. It was the best of times, it was the worst of times."
            }
        ]
        
    try:
        tool = TavilySearchResults(max_results=max_results)
        # The tool returns a list of dicts like: [{'url': '...', 'content': '...'}]
        results = tool.invoke({"query": query})
        
        # Ensure we standardize the keys to 'source' and 'content'
        standardized_results = []
        for r in results:
            standardized_results.append({
                "source": r.get("url", "unknown_source"),
                "content": r.get("content", "")
            })
            
        logger.info(f"Web search for '{query}' returned {len(standardized_results)} results.")
        return standardized_results
        
    except Exception:
        logger.error(f"Error during web search for '{query}'", exc_info=True)
        # Graceful degradation
        return [{
            "source": "error_fallback",
            "content": f"Search failed for '{query}'."
        }]
