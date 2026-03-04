# API — Autonomous Research + Report Agent

> **Evidence convention:** `path/file.py:L10-L25` — all claims verified by reading the referenced lines.

---

## 1. API Overview

The REST API is implemented using **FastAPI** and served by **Uvicorn**.

- **Application module:** `api/app.py`
- **Server entrypoint:** `main.py`
- **Base URL (default):** `http://0.0.0.0:8000`
- **API version:** `1.0.0` (`api/app.py:L13`)
- **Auto-generated docs:** `/docs` (Swagger UI), `/redoc` (ReDoc) — FastAPI defaults, no code required.

---

## 2. Endpoint Summary

| Method | Path | Handler | Auth | Input | Output | Status codes |
|---|---|---|---|---|---|---|
| `POST` | `/research` | `perform_research` | None | `ResearchRequest` JSON | `ResearchResponse` JSON | 200, 422, 500 |
| `GET` | `/health` | `health_check` | None | None | `{"status": "ok"}` | 200 |

---

## 3. `POST /research`

**Handler:** `perform_research` — `api/app.py:L36-L80`

### Purpose

Executes the full multi-agent LangGraph workflow for a given research query. Returns the final report, quality score, iteration count, execution history, and metadata.

### Request

**Content-Type:** `application/json`

**Schema:** `ResearchRequest` (`api/app.py:L18-L27`)

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `query` | `string` | Yes | `min_length=1`, `max_length=1000` | The research question to investigate |

**Example:**
```json
{
  "query": "What are the latest advancements in quantum computing?"
}
```

### Response

**Content-Type:** `application/json`

**Schema:** `ResearchResponse` (`api/app.py:L29-L34`)

| Field | Type | Description |
|---|---|---|
| `final_report` | `string` | The final synthesized (and optionally refined) research report with inline citations |
| `iterations` | `integer` | Number of synthesis passes completed (max 3) |
| `score` | `float` | Final quality score from critic: average of factuality, completeness, clarity ∈ [0.0, 1.0] |
| `metadata` | `object` | Auxiliary metadata dictionary (currently always `{}` — no node populates it) |
| `history` | `array[string]` | Ordered execution trace: one entry per node per pass |

**Example:**
```json
{
  "final_report": "## Quantum Computing Advancements\n\n...[cited report]...",
  "iterations": 2,
  "score": 0.87,
  "metadata": {},
  "history": [
    "API Received Query: What are the latest...",
    "Planner broke down the query into 3 sub-questions.",
    "Retrieved 3 docs for 'quantum error correction' using 'web_search'",
    "Synthesized initial draft using 6 unique documents.",
    "Critic evaluated draft: overall score 0.65.",
    "Refiner applied feedback and updated draft.",
    "Critic evaluated draft: overall score 0.87."
  ]
}
```

### Error responses

| HTTP Status | When | Response body |
|---|---|---|
| `422 Unprocessable Entity` | Query fails Pydantic validation (missing, empty, >1000 chars) | FastAPI validation error detail |
| `500 Internal Server Error` | Any exception during graph execution | `{"detail": "An internal error occurred. Please try again later."}` |

**Security note:** Internal exceptions are logged server-side with full stack trace (`api/app.py:L73-L74`) but only a generic message is returned to the caller (`api/app.py:L75-L79`), preventing leakage of API keys, file paths, or internal state.

### Side effects

- Triggers LLM calls to Google Gemini (2+ calls to router per sub-question, 1 each for planner, synthesizer, critic, refiner).
- May trigger Tavily API calls for web search.
- Appends to LangSmith trace if `LANGCHAIN_TRACING_V2=true`.
- No database writes. No persistent side effects.

### Performance characteristics

- Graph execution is synchronous and runs in a `asyncio.to_thread` worker (`api/app.py:L59-L62`).
- Typical execution time: **30–120 seconds** depending on Gemini latency and number of sub-questions.
- The event loop remains free to serve `/health` and other requests during execution.

---

## 4. `GET /health`

**Handler:** `health_check` — `api/app.py:L83-L84`

### Purpose

Liveness probe. Returns immediately without touching the graph or any external service.

### Request

No body. No parameters.

### Response

```json
{"status": "ok"}
```

**HTTP 200** always (unless the process is dead).

---

## 5. Request Validation Rules

All validation enforced by Pydantic before the handler function is called.

| Rule | Field | Constraint | Location | Error on violation |
|---|---|---|---|---|
| Required field | `query` | Field is mandatory | `api/app.py:L20` | 422 |
| Non-empty | `query` | `min_length=1` | `api/app.py:L22` | 422 |
| Length cap | `query` | `max_length=1000` | `api/app.py:L23` | 422 |
| Type | `query` | must be `string` | Pydantic inferred | 422 |

---

## 6. FastAPI Application Configuration

`api/app.py:L11-L15`

```python
app = FastAPI(
    title="Autonomous Research + Report Agent API",
    description="Multi-agent cyclic reasoning system powered by LangGraph.",
    version="1.0.0"
)
```

**Not configured:**
- CORS (`CORSMiddleware`) — not present; cross-origin browser requests will be blocked by default.
- Authentication middleware — no auth on any endpoint.
- Rate limiting — not implemented.
- Request ID / tracing headers — not implemented.
- Response compression — FastAPI default (none).

---

## 7. OpenAPI Schema

FastAPI auto-generates OpenAPI 3.x schema. Accessible at:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **Raw JSON:** `http://localhost:8000/openapi.json`

---

## 8. API Security Assessment

| Control | Status | Notes |
|---|---|---|
| Input validation | ✅ Present | Pydantic min/max_length on `query` |
| Error detail sanitization | ✅ Present | Generic 500 message to callers |
| Authentication | ❌ Missing | No API keys, tokens, or session auth |
| Authorization | ❌ Missing | All endpoints publicly accessible |
| Rate limiting | ❌ Missing | No throttling; DoS vector via repeated `/research` calls |
| CORS policy | ❌ Missing | No `CORSMiddleware` |
| HTTPS enforcement | Unknown | Depends on deployment; not configured in code |
| Request size limit | ⚠️ Partial | Only `query` field capped; overall body size not constrained beyond Uvicorn defaults |

---

## 9. Streamlit UI (non-REST interface)

The Streamlit UI (`ui/streamlit_app.py`) is a **separate process** that directly invokes the graph — it does not call the FastAPI endpoint.

**Key differences from API path:**

| Aspect | API (`api/app.py`) | UI (`ui/streamlit_app.py`) |
|---|---|---|
| Invocation | `graph.invoke()` (blocking, thread pool) | `graph.stream()` (iterator, same thread) |
| Output format | JSON response | Live Streamlit widgets |
| Input validation | Pydantic `ResearchRequest` | `if not query.strip():` check only |
| Error display | HTTP 500 JSON | No explicit error UI — would crash Streamlit page |
| State persistence | None (per-request) | `st.session_state` (per browser session) |
