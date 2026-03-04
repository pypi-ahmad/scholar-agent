# OPS — Autonomous Research + Report Agent Runbook

> **Evidence convention:** `path/file.py:L10-L25` — all claims verified by reading the referenced lines.

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.x | Tested with venv on Windows (PowerShell) |
| pip | Included with Python |
| Git | To clone the repository |
| Google API Key | Required — app raises `ValueError` without it (`app/utils/llm.py:L18`) |
| Tavily API Key | Optional — mock results used when absent |
| LangSmith API Key | Optional — tracing disabled when absent |

---

## 2. Installation

```powershell
# 1. Clone or navigate to the repository
cd "Autonomous Research + Report Agent"

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Upgrade pip
python -m pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt
```

**What gets installed** (`requirements.txt:L1-L20`):

| Package | Purpose |
|---|---|
| `python-dotenv` | Load `.env` file into environment |
| `pydantic` | Data validation (models, structured outputs) |
| `fastapi` | REST API framework |
| `uvicorn` | ASGI server for FastAPI |
| `streamlit` | Streaming UI |
| `langchain` | LLM orchestration framework |
| `langchain-core` | Core primitives (prompts, runnables) |
| `langchain-google-genai` | Google Gemini integration |
| `langgraph` | Cyclic state-machine graph framework |
| `tavily-python` | Tavily search client (indirect, via langchain-community) |
| `faiss-cpu` | Listed but **not used** — vector store is a mock |
| `tenacity` | Retry library (LangChain dependency) |
| `langsmith` | LangSmith tracing SDK |

---

## 3. Environment Configuration

Copy the template and fill in your keys:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```dotenv
# Required
GOOGLE_API_KEY=your_google_api_key_here

# Optional (mock used if absent or if value matches default)
TAVILY_API_KEY=your_tavily_api_key_here

# Optional — LangSmith distributed tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY=your_langchain_api_key_here
LANGCHAIN_PROJECT="autonomous-research-agent"

# Optional — Server config
PORT=8000
HOST=0.0.0.0
RELOAD=false   # ← set to false in production
```

**Environment variable reference:**

| Variable | Required? | Default | Effect if missing |
|---|---|---|---|
| `GOOGLE_API_KEY` | **YES** | — | `ValueError` raised immediately on first LLM call |
| `TAVILY_API_KEY` | No | — | Mock web search results used |
| `AUTH_MODE` | No | `"required"` | `"required"`: `API_KEY` must be set and every request must supply `X-API-Key` (503 if key unset). `"optional"`: open mode when `API_KEY` is empty (dev convenience) |
| `API_KEY` | Depends on `AUTH_MODE` | `""` | Shared secret matched against the `X-API-Key` request header |
| `PORT` | No | `8000` | Uvicorn listens on 8000 |
| `HOST` | No | `0.0.0.0` | Binds on all interfaces |
| `RELOAD` | No | `"true"` | Hot reload enabled |
| `LANGCHAIN_TRACING_V2` | No | off | LangSmith tracing disabled |
| `LANGCHAIN_ENDPOINT` | No | — | LangSmith ingestion URL |
| `LANGCHAIN_API_KEY` | No | — | LangSmith auth token |
| `LANGCHAIN_PROJECT` | No | — | LangSmith project label |
| `REDIS_URL` | No | `""` | Redis connection URL. When set, enables `RedisCache`; falls back to in-memory on failure. Requires `pip install redis` |
| `VECTOR_DB_PATH` | No | `""` | Filesystem path for a persisted FAISS index. Enables `FAISSVectorStore`; falls back to in-memory on failure |
| `CHROMA_PERSIST_DIR` | No | `""` | Directory for Chroma persistence. Enables `ChromaVectorStore` (takes priority over FAISS). Requires `pip install chromadb` |
| `EMBEDDING_MODEL` | No | `"models/embedding-001"` | Google embedding model name used by FAISS / Chroma backends |

---

## 4. Running the Application

### Option A: API server (programmatic access)

```powershell
python main.py
```

- Starts Uvicorn at `http://{HOST}:{PORT}` (default `http://0.0.0.0:8000`).
- `main.py:L12-L17` reads `PORT`, `HOST`, `RELOAD` from environment.
- Reload is enabled by default (dev mode) — set `RELOAD=false` for production.
- Endpoints: `POST /research`, `GET /health`.
- OpenAPI docs: `http://localhost:8000/docs`.

**Example curl request:**

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the latest advancements in quantum computing?"}'
```

**Expected response time:** 30–120 seconds (LLM API latency).

### Option B: Streamlit UI

```powershell
streamlit run ui/streamlit_app.py
```

- Opens a browser tab at `http://localhost:8501` (Streamlit default).
- Enter your query and click **Start Research**.
- UI streams node-by-node trace as the graph executes.
- Displays final report, score, iteration count, and deduplicated source links.

**Note:** The Streamlit UI invokes the graph directly (not via the API). It must have access to all the same environment variables.

---

## 5. Running Tests

### Configuration

`pytest.ini:L1-L4`

```ini
[pytest]
testpaths = tests/unit tests/integration
python_files = test_*.py
addopts = -q --disable-warnings
```

### Run all tests

```powershell
python -m pytest tests/unit tests/integration -q
```

### Run only unit tests

```powershell
python -m pytest tests/unit -q
```

### Run only integration tests

```powershell
python -m pytest tests/integration -q
```

### Run with verbose output

```powershell
python -m pytest tests/unit tests/integration -vv
```

### Run a specific test file

```powershell
python -m pytest tests/unit/test_api_app.py -vv
```

### Expected output

```
34 passed in 0.34s
```

Last verified run: 2026-03-01 — 34 passed, 0 failed (`TEST_REPORT.md:L51-L55`).

### Test architecture

| Suite | Location | Mechanism | Dependencies on external services |
|---|---|---|---|
| Unit | `tests/unit/` | Monkeypatching; pure Python | None — all LLM/API calls mocked |
| Integration (workflow) | `tests/integration/test_graph_workflow.py` | Monkeypatched node functions in real graph | None |
| Integration (smoke) | `tests/integration/test_import_smoke.py` | `importlib.import_module` on 14 modules | Requires all packages installed |

**`conftest.py`** (`tests/conftest.py:L1-L285`): Provides pure-stdlib stubs for `pydantic`, `fastapi`, `langchain_core`, `langchain_google_genai`, `langchain_community`, and `langgraph` — ensuring tests run without the real packages if needed (useful in constrained CI).

---

## 6. Stopping the Application

### API server

```powershell
Ctrl+C
```

Uvicorn handles `SIGINT` gracefully.

### Streamlit UI

```powershell
Ctrl+C
```

in the terminal where `streamlit run` was launched.

---

## 7. Deployment Notes

### Current state

There is **no Docker, Kubernetes, Terraform, or CI/CD pipeline** in this repository. Deployment must be handled manually or by adding infrastructure configuration.

### Minimum production checklist

| Step | Action | Why |
|---|---|---|
| Set `RELOAD=false` | `RELOAD=false` in `.env` | `main.py:L14` — uvicorn file watcher adds latency and is unsafe in prod |
| Set `HOST=127.0.0.1` | `HOST=127.0.0.1` in `.env` | Default `0.0.0.0` exposes on all interfaces |
| Protect `GOOGLE_API_KEY` | Use secrets manager or env injection | Never commit to source control |
| Add auth layer | Implement middleware or gateway auth | No auth on any endpoint currently |
| Add rate limiting | Add `slowapi` or gateway throttling | Repeated `/research` calls exhaust Gemini quota |
| Disable OpenAPI in prod | `app = FastAPI(docs_url=None, redoc_url=None)` | Avoid exposing schema to untrusted clients |
| Add CORS config | `from fastapi.middleware.cors import CORSMiddleware` | Required for any browser-based client |
| Replace mock stores | Implement real `VectorStoreWrapper` and `QueryCache` | Current implementations are in-memory mocks |

### Recommended containerization skeleton

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0
ENV PORT=8000
ENV RELOAD=false
EXPOSE 8000
CMD ["python", "main.py"]
```

---

## 8. Observability

### Logging

- All logs go to `sys.stdout` in format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
  (`app/utils/logger.py:L17`)
- Logger hierarchy: `research_agent` → `research_agent.api`, `research_agent.graph.builder`, `research_agent.agents.*`, `research_agent.tools.*`
- Level: `INFO` (all nodes log entry, key decisions, and errors)

### LangSmith tracing (optional)

Enable by setting:

```dotenv
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=autonomous-research-agent
```

LangChain auto-instruments all `invoke()` calls. View traces at [smith.langchain.com](https://smith.langchain.com).

### What is NOT instrumented

- No Prometheus metrics
- No distributed trace propagation (e.g., OpenTelemetry)
- No Sentry or error tracking
- No `/metrics` endpoint

---

## 9. Common Issues

| Issue | Cause | Fix |
|---|---|---|
| `ValueError: GOOGLE_API_KEY environment variable is not set` | `GOOGLE_API_KEY` not in env | Set `GOOGLE_API_KEY` in `.env` and restart |
| Mock web search results returned | `TAVILY_API_KEY` missing or set to default placeholder | Set real `TAVILY_API_KEY` in `.env` |
| `POST /research` times out | LLM latency > client timeout | Increase client timeout; graph takes 30–120s |
| Tests import errors | Dependencies not installed | Run `pip install -r requirements.txt` in venv |
| Streamlit page crashes mid-stream | Unhandled exception in graph node | Check terminal logs; add exception handling in UI |
| `RELOAD=true` warning in production | Default value used | Explicitly set `RELOAD=false` in `.env` |
