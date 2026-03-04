from typing import TypedDict, List, Dict, Any, Annotated
# L-01: 'operator' was imported but never referenced — removed.

def append_to_list(left: List[Any], right: List[Any]) -> List[Any]:
    """Helper to safely merge lists in LangGraph."""
    if not left:
        left = []
    if not right:
        right = []
    return left + right

def update_dict(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to safely update dictionaries in LangGraph."""
    if not left:
        left = {}
    if not right:
        right = {}
    merged = left.copy()
    merged.update(right)
    return merged

class AgentState(TypedDict):
    """
    Advanced State for the Multi-Agent Research System.
    Includes explicit tracking of documents, execution history, and metrics.
    """
    query: str
    plan: List[str]  # Sub-queries
    current_step: int
    
    # Using Annotated to specify that parallel execution should append to the list
    documents: Annotated[List[Dict[str, str]], append_to_list] 
    
    draft: str
    critique: Dict[str, Any]  # structured metrics (factuality, completeness, clarity, overall, feedback)
    score: float
    iteration: int
    
    # Traceability and metrics
    history: Annotated[List[str], append_to_list]
    metadata: Annotated[Dict[str, Any], update_dict]
