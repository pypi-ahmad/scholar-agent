# README Evidence Map

Every major claim in [README.md](../README.md) is backed by a specific file and line reference.
This document serves as a verification artifact — if a claim below cannot be found at the cited location, the README is out of date.

---

## 1. Architecture claims

| Claim | File | Lines | Verified |
| ----- | ---- | ----- | -------- |
| LangGraph-based multi-agent cyclic workflow | [app/graph/builder.py](../app/graph/builder.py) | L1-91 | ✅ `StateGraph(AgentState)` with 5 nodes, conditional edges |
| 5 agent nodes: planner, retriever, synthesizer, critic, refiner | [app/graph/builder.py](../app/graph/builder.py) | L55-63 | ✅ `workflow.add_node(...)` ×5 |
| Parallel fan-out retrieval via Send API | [app/graph/builder.py](../app/graph/builder.py) | L18-28 | ✅ `return [Send("retriever", {...}) for q in plan]` |
| Cyclic refine loop (critic → refiner → critic) | [app/graph/builder.py](../app/graph/builder.py) | L30-46, L82-86 | ✅ `should_refine` routes to `"refiner"` or `END` |
| Thread-safe lazy singleton graph | [app/graph/builder.py](../app/graph/builder.py) | L94-117 | ✅ `threading.Lock()` + double-checked pattern |
| FastAPI REST API | [api/app.py](../api/app.py) | L64-67 | ✅ `app = FastAPI(...)` |
| Streamlit streaming UI | [ui/streamlit_app.py](../ui/streamlit_app.py) | Full file | ✅ `st.title(...)`, `graph.stream(...)` |
| Google Gemini 2.0 Flash LLM | [app/utils/llm.py](../app/utils/llm.py) | L10, L23-26 | ✅ `GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"`, `max_retries=3` |

## 2. Endpoint claims

| Claim | File | Lines | Verified |
| ----- | ---- | ----- | -------- |
| `POST /research` | [api/app.py](../api/app.py) | L125-172 | ✅ `@app.post("/research", ...)` |
| `GET /research/stream` (SSE) | [api/app.py](../api/app.py) | L265-276 | ✅ `@app.get("/research/stream", ...)` returns `EventSourceResponse` |
| `GET /health` | [api/app.py](../api/app.py) | L279-280 | ✅ `@app.get("/health")` returns `{"status": "ok"}` |
| SSE emits `node`, `final`, `error` events | [api/app.py](../api/app.py) | L193-262 | ✅ `yield {"event": "node", ...}`, `yield {"event": "final", ...}`, `yield {"event": "error", ...}` |
| SSE uses threaded `graph.stream()` | [api/app.py](../api/app.py) | L215-229 | ✅ `threading.Thread(target=_run, ...)` with queue |

## 3. Security claims

| Claim | File | Lines | Verified |
| ----- | ---- | ----- | -------- |
| `AUTH_MODE` required/optional | [api/app.py](../api/app.py) | L24-58 | ✅ `_AUTH_MODE = os.getenv("AUTH_MODE", "required")` + conditional logic |
| `AUTH_MODE` defaults to `"required"` | [app/utils/config.py](../app/utils/config.py) | L36 | ✅ `AUTH_MODE: str = os.getenv("AUTH_MODE", "required")` |
| 503 when API_KEY not set in required mode | [api/app.py](../api/app.py) | L43-47 | ✅ `raise HTTPException(status_code=503, ...)` |
| CORS middleware, env-driven, default deny | [api/app.py](../api/app.py) | L72-82 | ✅ `CORS_ALLOW_ORIGINS` split, only added if non-empty |
| Rate limiting via slowapi, default `10/minute` | [api/app.py](../api/app.py) | L88-100 | ✅ `Limiter(...)`, `_rate_limit = os.getenv("RATE_LIMIT", "10/minute")` |
| Input validation: query 1-1000 chars | [api/app.py](../api/app.py) | L111-116 | ✅ `min_length=1, max_length=1000` |
| URL sanitization in Streamlit UI | [ui/streamlit_app.py](../ui/streamlit_app.py) | `_is_safe_url()` | ✅ Blocks non-http, localhost, private IP patterns |
| Safe error messages (no stack traces leaked) | [api/app.py](../api/app.py) | L172 | ✅ `detail="An internal error occurred..."` |

## 4. Configuration claims

| Claim | File | Lines | Verified |
| ----- | ---- | ----- | -------- |
| All caps in centralised config | [app/utils/config.py](../app/utils/config.py) | L1-39 | ✅ Single file, all `os.getenv()` with defaults |
| `MAX_SUB_QUESTIONS` default 6 | [app/utils/config.py](../app/utils/config.py) | L23 | ✅ `_int_env("MAX_SUB_QUESTIONS", 6)` |
| `MAX_DOCS_PER_SUBQUERY` default 5 | [app/utils/config.py](../app/utils/config.py) | L24 | ✅ `_int_env("MAX_DOCS_PER_SUBQUERY", 5)` |
| `MAX_DOCS_TOTAL` default 30 | [app/utils/config.py](../app/utils/config.py) | L25 | ✅ `_int_env("MAX_DOCS_TOTAL", 30)` |
| `MAX_ITERATIONS` default 3 | [app/utils/config.py](../app/utils/config.py) | L26 | ✅ `_int_env("MAX_ITERATIONS", 3)` |
| `SCORE_THRESHOLD` default 0.8 | [app/utils/config.py](../app/utils/config.py) | L27 | ✅ `float(os.getenv("SCORE_THRESHOLD", "0.8"))` |
| `REDIS_URL` enables RedisCache | [app/tools/cache.py](../app/tools/cache.py) | `get_cache()` factory | ✅ Checks `REDIS_URL`, falls back to InMemoryCache |
| `VECTOR_DB_PATH` enables FAISSVectorStore | [app/tools/vector_store.py](../app/tools/vector_store.py) | `get_vector_store()` factory | ✅ Chroma > FAISS > InMemory priority |
| `CHROMA_PERSIST_DIR` enables ChromaVectorStore | [app/tools/vector_store.py](../app/tools/vector_store.py) | `get_vector_store()` factory | ✅ Checks `CHROMA_PERSIST_DIR` first |
| `EMBEDDING_MODEL` default `models/embedding-001` | [app/utils/config.py](../app/utils/config.py) | L33 | ✅ |
| In-memory fallback when no backend configured | [app/tools/cache.py](../app/tools/cache.py), [app/tools/vector_store.py](../app/tools/vector_store.py) | factory functions | ✅ Both default to InMemory variants |

## 5. Data backend claims

| Claim | File | Lines | Verified |
| ----- | ---- | ----- | -------- |
| `CacheBackend` ABC with get/set/delete | [app/tools/cache.py](../app/tools/cache.py) | ABC class | ✅ `@abstractmethod` ×3 |
| `InMemoryCache` with substring match | [app/tools/cache.py](../app/tools/cache.py) | class | ✅ 3 demo entries, substring key matching |
| `RedisCache` with JSON serialization | [app/tools/cache.py](../app/tools/cache.py) | class | ✅ `json.dumps`/`json.loads`, deferred `import redis` |
| `VectorStoreBackend` ABC | [app/tools/vector_store.py](../app/tools/vector_store.py) | ABC class | ✅ `add_documents`, `similarity_search` abstract methods |
| `InMemoryVectorStore` keyword match | [app/tools/vector_store.py](../app/tools/vector_store.py) | class | ✅ 3 demo docs, keyword-based similarity |
| `FAISSVectorStore` with persistence | [app/tools/vector_store.py](../app/tools/vector_store.py) | class | ✅ `faiss.write_index`/`faiss.read_index` |
| `ChromaVectorStore` with persistence | [app/tools/vector_store.py](../app/tools/vector_store.py) | class | ✅ `chromadb.PersistentClient` |
| Factory priority: Chroma > FAISS > InMemory | [app/tools/vector_store.py](../app/tools/vector_store.py) | `get_vector_store()` | ✅ if/elif chain |

## 6. Agent behaviour claims

| Claim | File | Lines | Verified |
| ----- | ---- | ----- | -------- |
| Planner caps sub-questions at `MAX_SUB_QUESTIONS` | [app/agents/planner.py](../app/agents/planner.py) | plan_node | ✅ `plan[:MAX_SUB_QUESTIONS]` |
| Retriever routes: cache → vector_store → web_search | [app/agents/retriever.py](../app/agents/retriever.py) | retriever_node | ✅ if/elif chain |
| Retriever caps at `MAX_DOCS_PER_SUBQUERY` | [app/agents/retriever.py](../app/agents/retriever.py) | retriever_node | ✅ `docs[:MAX_DOCS_PER_SUBQUERY]` |
| Synthesizer deduplicates documents | [app/agents/synthesizer.py](../app/agents/synthesizer.py) | synthesizer_node | ✅ Dedup by (source, content) |
| Synthesizer caps at `MAX_DOCS_TOTAL` | [app/agents/synthesizer.py](../app/agents/synthesizer.py) | synthesizer_node | ✅ `docs[:MAX_DOCS_TOTAL]` |
| Synthesizer increments iteration | [app/agents/synthesizer.py](../app/agents/synthesizer.py) | synthesizer_node | ✅ `iteration + 1` |
| Critic scores 3 axes (factuality/completeness/clarity) | [app/agents/critic.py](../app/agents/critic.py) | CritiqueOutput | ✅ 3 float fields with ge=0.0, le=1.0 |
| Refiner does NOT increment iteration | [app/agents/refiner.py](../app/agents/refiner.py) | refiner_node | ✅ Only returns draft, no iteration change |
| All agents emit metadata with timing | [app/agents/planner.py](../app/agents/planner.py), etc. | metadata dict | ✅ `*_seconds` keys in metadata |

## 7. Testing claims

| Claim | File | Lines | Verified |
| ----- | ---- | ----- | -------- |
| 118 hermetic tests | [tests/](../tests/) | All test files | ✅ Sum: 12+10+7+9+37+26+2+15 = 118 |
| Pure-stdlib stubs (no real deps in tests) | [tests/conftest.py](../tests/conftest.py) | L1-421 | ✅ ~421 lines of fakes for pydantic, fastapi, langchain, etc. |
| No external services required for tests | [tests/conftest.py](../tests/conftest.py) | sys.modules stubs | ✅ All heavy deps replaced before import |
| pytest config: unit + integration paths | [pytest.ini](../pytest.ini) | L1-4 | ✅ `testpaths = tests/unit tests/integration` |

## 8. Infrastructure / entry point claims

| Claim | File | Lines | Verified |
| ----- | ---- | ----- | -------- |
| `main.py` is Uvicorn entry point | [main.py](../main.py) | L12-17 | ✅ `uvicorn.run("api.app:app", ...)` |
| `PORT` / `HOST` / `RELOAD` from env | [main.py](../main.py) | L12-15 | ✅ `os.getenv("PORT", 8000)`, etc. |
| `load_dotenv()` runs before app imports | [main.py](../main.py) | L3-6 | ✅ `load_dotenv()` at line 6, imports after |
| Tavily web search with mock fallback | [app/tools/web_search.py](../app/tools/web_search.py) | L23-33 | ✅ Try Tavily, except → mock results |
| Query length truncation (500 chars) | [app/tools/web_search.py](../app/tools/web_search.py) | `_MAX_QUERY_LEN` | ✅ `query[:_MAX_QUERY_LEN]` |
| 5 ChatPromptTemplates | [app/utils/prompts.py](../app/utils/prompts.py) | Full file | ✅ PLANNER, TOOL_ROUTER, SYNTHESIZER, CRITIC, REFINER |
| Logger to stdout | [app/utils/logger.py](../app/utils/logger.py) | L1-27 | ✅ `StreamHandler(sys.stdout)` |

---

## Files scanned (coverage proof)

Total production files: **18**

| # | File | Lines |
| - | ---- | ----- |
| 1 | [main.py](../main.py) | 18 |
| 2 | [api/app.py](../api/app.py) | 301 |
| 3 | [ui/streamlit_app.py](../ui/streamlit_app.py) | ~155 |
| 4 | [app/graph/state.py](../app/graph/state.py) | 43 |
| 5 | [app/graph/builder.py](../app/graph/builder.py) | 117 |
| 6 | [app/agents/planner.py](../app/agents/planner.py) | ~55 |
| 7 | [app/agents/retriever.py](../app/agents/retriever.py) | ~95 |
| 8 | [app/agents/synthesizer.py](../app/agents/synthesizer.py) | ~68 |
| 9 | [app/agents/critic.py](../app/agents/critic.py) | ~90 |
| 10 | [app/agents/refiner.py](../app/agents/refiner.py) | ~61 |
| 11 | [app/tools/cache.py](../app/tools/cache.py) | ~160 |
| 12 | [app/tools/vector_store.py](../app/tools/vector_store.py) | ~250 |
| 13 | [app/tools/web_search.py](../app/tools/web_search.py) | ~60 |
| 14 | [app/utils/config.py](../app/utils/config.py) | 39 |
| 15 | [app/utils/llm.py](../app/utils/llm.py) | 35 |
| 16 | [app/utils/prompts.py](../app/utils/prompts.py) | ~80 |
| 17 | [app/utils/logger.py](../app/utils/logger.py) | 27 |
| 18 | [.env.example](../.env.example) | 46 |

Total test files: **8**

| # | File | Tests |
| - | ---- | ----- |
| 1 | [tests/conftest.py](../tests/conftest.py) | — (stub layer) |
| 2 | [tests/unit/test_agents_nodes.py](../tests/unit/test_agents_nodes.py) | 12 |
| 3 | [tests/unit/test_api_app.py](../tests/unit/test_api_app.py) | 10 |
| 4 | [tests/unit/test_graph_state_and_builder.py](../tests/unit/test_graph_state_and_builder.py) | 7 |
| 5 | [tests/unit/test_tools_and_utils.py](../tests/unit/test_tools_and_utils.py) | 9 |
| 6 | [tests/unit/test_upgrades.py](../tests/unit/test_upgrades.py) | 37 |
| 7 | [tests/unit/test_backend_selection.py](../tests/unit/test_backend_selection.py) | 26 |
| 8 | [tests/integration/test_graph_workflow.py](../tests/integration/test_graph_workflow.py) | 2 |
| 9 | [tests/integration/test_import_smoke.py](../tests/integration/test_import_smoke.py) | 15 |

Config files: [pytest.ini](../pytest.ini), [requirements.txt](../requirements.txt), [.gitignore](../.gitignore)

**Skipped files:** None. All source, test, config, and doc files were read.
