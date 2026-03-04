# FLOWS — Autonomous Research + Report Agent

> **Evidence convention:** `path/file.py:L10-L25` — all claims verified by reading the referenced lines.

---

## 1. Runtime Flow Overview

The system has **two runtime paths** that invoke the same underlying LangGraph:

| Path | Entrypoint | Invocation mode | Output |
|---|---|---|---|
| API | `main.py` → `api/app.py` | `graph.invoke()` in `asyncio.to_thread` | JSON `ResearchResponse` |
| UI | `ui/streamlit_app.py` | `graph.stream()` in Streamlit event loop | Node-by-node streaming display |

Both paths initialize an identical `AgentState` dict and pass it to the same compiled graph singleton.

---

## 2. API Request Flow

### Step-by-step

```
User HTTP Client
  │
  │  POST /research {"query": "..."}
  ▼
FastAPI (api/app.py:L36)
  │
  │  ResearchRequest Pydantic validation
  │    ├─ min_length=1         (api/app.py:L22)
  │    └─ max_length=1000      (api/app.py:L23)
  │
  │  Build initial AgentState  (api/app.py:L42-L54)
  │    query, plan=[], documents=[], draft="", score=0.0, iteration=0 ...
  │
  │  asyncio.to_thread(graph.invoke, initial_state)  (api/app.py:L59-L62)
  │    ← runs synchronous LangGraph in a thread pool worker
  │
  ├─► [GRAPH EXECUTION — see Section 4]
  │
  │  Extract final_state fields
  │    final_report = final_state["draft"]
  │    iterations   = final_state["iteration"]
  │    score        = final_state["score"]
  │    metadata     = final_state["metadata"]
  │    history      = final_state["history"]
  │
  │  Return ResearchResponse JSON  (api/app.py:L64-L71)
  │
  └─► HTTP 200 {"final_report": "...", "iterations": N, "score": F, ...}

On any exception:
  └─► logger.error(..., exc_info=True)    (api/app.py:L73-L74)
  └─► HTTP 500 {"detail": "An internal error occurred..."}  (api/app.py:L75-L79)
```

---

## 3. Streamlit UI Flow

```
User (browser)
  │
  │  Enters query in text_input
  │  Clicks "Start Research"
  ▼
streamlit_app.py (ui/streamlit_app.py:L29-L34)
  │
  │  Validate non-empty query
  │  Initialize st.session_state["current_state"]  (L43-L56)
  │
  │  for output in get_compiled_graph().stream(current_state):  (L58)
  │      for node_name, state_update in output.items():
  │          ├─ Update local current_state tracking
  │          ├─ Display: "🟢 Node executed: {node_name}"
  │          ├─ Display: latest history event
  │          └─ Node-specific expanders:
  │               planner    → show plan sub-questions
  │               retriever  → show document count
  │               synthesizer → show draft snapshot
  │               critic      → show score + critique JSON
  │
  │  After streaming completes:
  │    Display final report markdown
  │    Display score + iteration metrics
  │    Display deduplicated source links
  └─► User sees complete research report
```

---

## 4. LangGraph Execution Flow (core)

This is the graph that both API and UI invoke.

### Node execution sequence

```mermaid
sequenceDiagram
    participant Graph as "LangGraph\nbuilder.py"
    participant Planner as "plan_node\nplanner.py"
    participant Router as "continue_to_retrieve\nbuilder.py:L15"
    participant R1 as "retriever_node\n(sub_query=q1)"
    participant R2 as "retriever_node\n(sub_query=q2)"
    participant Synth as "synthesizer_node\nsynth.py"
    participant Critic as "critic_node\ncritic.py"
    participant Route2 as "should_refine\nbuilder.py:L29"
    participant Refiner as "refiner_node\nrefiner.py"

    Graph->>Planner: plan_node(state)
    Note over Planner: LLM: PlanOutput<br/>→ ["q1","q2",...]
    Planner-->>Graph: {plan: [...], current_step+1}

    Graph->>Router: continue_to_retrieve(state)
    Router-->>Graph: [Send("retriever",{q1}), Send("retriever",{q2})]

    par Parallel fan-out (LangGraph Send)
        Graph->>R1: retriever_node({sub_query:"q1"})
        Note over R1: LLM routes tool<br/>executes cache/vector/web
        R1-->>Graph: {documents:[...], history:[...]}
    and
        Graph->>R2: retriever_node({sub_query:"q2"})
        Note over R2: LLM routes tool<br/>fallback chain if needed
        R2-->>Graph: {documents:[...], history:[...]}
    end

    Note over Graph: append_to_list reducer merges<br/>documents from R1 + R2

    Graph->>Synth: synthesizer_node(state)
    Note over Synth: De-dup documents<br/>LLM: draft with citations<br/>iteration += 1
    Synth-->>Graph: {draft:"...", iteration:1, current_step+1}

    Graph->>Critic: critic_node(state)
    Note over Critic: LLM: CritiqueOutput<br/>overall = avg(F+C+Cl)
    Critic-->>Graph: {score:0.65, critique:{...}, current_step+1}

    Graph->>Route2: should_refine(state)
    Route2-->>Graph: "refiner" (score 0.65 < 0.8, iter 1 < 3)

    Graph->>Refiner: refiner_node(state)
    Note over Refiner: LLM: apply critique feedback<br/>NO iteration increment
    Refiner-->>Graph: {draft:"improved...", current_step+1}

    Graph->>Critic: critic_node(state)
    Note over Critic: Re-evaluate improved draft
    Critic-->>Graph: {score:0.87, critique:{...}}

    Graph->>Route2: should_refine(state)
    Route2-->>Graph: END (score 0.87 >= 0.8)

    Graph-->>API/UI: final_state
```

---

## 5. Retriever Tool Routing Flow

Each `retriever_node` instance executes this decision tree:

```mermaid
flowchart TD
    SQ["sub_query input"] --> RLLM["LLM Router\nToolRouterOutput\nbuilder.py:L40-L52"]
    RLLM -->|selected_tool| ROUTE{Tool?}

    ROUTE -->|cache| CACHE["global_cache.get(search_query)\ncache.py:L23-L29"]
    CACHE -->|hit: docs returned| DONE["return documents"]
    CACHE -->|miss: empty list| WEB

    ROUTE -->|vector_store| VEC["vector_db.similarity_search(query)\nvector_store.py:L26-L38"]
    VEC -->|docs returned| DONE
    VEC -->|empty: no match| WEB

    ROUTE -->|web_search| WEB["perform_web_search(query)\nweb_search.py:L13-L59"]
    ROUTE -->|router error| WEB

    WEB -->|TAVILY_API_KEY set & valid| TAV["TavilySearchResults.invoke\nstandardize url→source"]
    WEB -->|key missing/default| MOCK["Mock results × 2\nweb_search.py:L26-L33"]
    TAV -->|Tavily exception| ERRFB["error_fallback doc\nweb_search.py:L55-L59"]
    TAV -->|success| DONE
    MOCK --> DONE
    ERRFB --> DONE
```

---

## 6. Critic → Refiner Loop Detail

```mermaid
flowchart TD
    CR["critic_node\noutputs score + critique"]
    SR{"should_refine?\nbuilder.py:L29-L51"}
    REF["refiner_node\napply critique feedback\nNO iteration increment"]
    END([END])

    CR --> SR
    SR -->|"score >= 0.8"| END
    SR -->|"iteration >= 3"| END
    SR -->|"score < 0.8\nAND iteration < 3"| REF
    REF -->|updated draft| CR
```

**Key design facts:**
- `iteration` is incremented **only in `synthesizer_node`** (`app/agents/synthesizer.py:L54`).
- `refiner_node` does NOT increment `iteration` (`app/agents/refiner.py:L57`, comment `C-05`).
- Therefore: `iteration` counts synthesis passes, not total critic/refine cycles.
- Maximum critic calls = `iteration` passes + number of refinement rounds per pass.
- Hard stop: `iteration >= 3` in `should_refine` prevents infinite loops.

---

## 7. State Merge Flow (parallel fan-out safety)

```mermaid
flowchart LR
    subgraph "Parallel Retriever Executions"
        R1["retriever 1\nreturns {documents: [d1], history: [h1]}"]
        R2["retriever 2\nreturns {documents: [d2], history: [h2]}"]
        R3["retriever N\nreturns {documents: [dN], history: [hN]}"]
    end

    subgraph "LangGraph State Reducer"
        AL["append_to_list reducer\nstate.py:L7-L12\ndocuments: [d1,d2,...,dN]\nhistory: [h1,h2,...,hN]"]
    end

    subgraph "Synthesizer Input"
        SYNTH["synthesizer_node receives\ndocuments = all merged\nde-duplication by (source,content)"]
    end

    R1 --> AL
    R2 --> AL
    R3 --> AL
    AL --> SYNTH
```

The `append_to_list(left, right)` reducer (`app/graph/state.py:L7-L12`) handles `None` on either side and simply concatenates, making parallel writes from `N` retrievers safe regardless of order.
