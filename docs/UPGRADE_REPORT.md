# UPGRADE REPORT — Autonomous Research + Report Agent

> **Generated:** 2026-03-04
> **Scope:** Security baseline, caps enforcement, metadata/observability, error handling, test coverage

---

## 1  Issue Ledger

| # | Sev | Category | Issue | File(s) | Fix Applied |
|---|-----|----------|-------|---------|-------------|
| U-01 | P0 | Security | No authentication on `/research` endpoint | `api/app.py` | Added `X-API-Key` header auth via `API_KEY` env var; open mode when unset |
| U-02 | P0 | Security | No CORS policy — any origin allowed by default | `api/app.py` | Added `CORSMiddleware` gated by `CORS_ALLOW_ORIGINS` env var (default deny) |
| U-03 | P1 | Security | No rate limiting on expensive `/research` | `api/app.py` | Added `slowapi` limiter (`RATE_LIMIT` env, default 10/min) |
| U-04 | P1 | Security | Source URLs rendered as clickable links without validation (SSRF) | `ui/streamlit_app.py` | Added `_is_safe_url()` — blocks non-http, localhost, private IPs |
| U-05 | P1 | Reliability | No cap on sub-questions — LLM can generate unlimited fan-out | `app/agents/planner.py` | Enforced `MAX_SUB_QUESTIONS` (default 6) from config |
| U-06 | P1 | Reliability | No cap on docs per sub-query | `app/agents/retriever.py` | Enforced `MAX_DOCS_PER_SUBQUERY` (default 5) from config |
| U-07 | P1 | Reliability | No cap on total docs in synthesizer context window | `app/agents/synthesizer.py` | Enforced `MAX_DOCS_TOTAL` (default 30) post-dedup |
| U-08 | P1 | Reliability | Iteration/score thresholds hardcoded in builder | `app/graph/builder.py` | Moved to `MAX_ITERATIONS` / `SCORE_THRESHOLD` via config |
| U-09 | P1 | UX | No try/except around Streamlit graph streaming | `ui/streamlit_app.py` | Wrapped in try/except → `st.error()` + `st.stop()` |
| U-10 | P2 | Observability | `metadata` dict never populated by any node | All agents | Every node now writes timing + node-specific metrics to `metadata` |
| U-11 | P2 | Observability | No request tracing ID | `api/app.py` | `request_id` (UUID) injected into initial state + final response |
| U-12 | P2 | Observability | No execution timing | `api/app.py` | `elapsed_seconds` measured and returned in metadata |
| U-13 | P2 | Infra | Missing `slowapi`, `sse-starlette` in requirements | `requirements.txt` | Added both packages |
| U-14 | P2 | Config | All caps/thresholds scattered as magic numbers | — | Created `app/utils/config.py` — single source of truth |
| U-15 | P2 | Feature | SSE streaming endpoint missing — `sse-starlette` in deps but not wired | `api/app.py` | Added `GET /research/stream?query=…` with `EventSourceResponse`; streams `node`/`final`/`error` events |

---

## 2  Files Changed

| File | Change Type | Lines Δ |
|------|------------|---------|
| `api/app.py` | **Rewritten** | +75 (auth, CORS, rate limit, request_id, timing) |
| `app/utils/config.py` | **New** | +35 (caps, thresholds, env loader) |
| `app/agents/planner.py` | Modified | +8 (time import, cap, metadata) |
| `app/agents/retriever.py` | Modified | +12 (time, cap, metadata) |
| `app/agents/synthesizer.py` | Modified | +10 (time, doc cap, metadata) |
| `app/agents/critic.py` | Modified | +6 (time, metadata) |
| `app/agents/refiner.py` | Modified | +6 (time, metadata) |
| `app/graph/builder.py` | Modified | +3 (config imports for thresholds) |
| `ui/streamlit_app.py` | Modified | +25 (URL sanitization, try/except) |
| `requirements.txt` | Modified | +4 (slowapi, sse-starlette) |
| `tests/conftest.py` | Modified | +85 (stubs: slowapi, streamlit, dotenv, fastapi.security, CORSMiddleware) |
| `tests/unit/test_upgrades.py` | **New** | +270 (28 new test cases) |

---

## 3  New Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `API_KEY` | `""` (open mode) | `X-API-Key` header value; empty = no auth |
| `CORS_ALLOW_ORIGINS` | `""` (deny all) | Comma-separated allowed origins |
| `RATE_LIMIT` | `10/minute` | slowapi rate limit string |
| `MAX_SUB_QUESTIONS` | `6` | Cap on planner sub-questions |
| `MAX_DOCS_PER_SUBQUERY` | `5` | Cap on docs returned per retriever call |
| `MAX_DOCS_TOTAL` | `30` | Cap on unique docs fed to synthesizer |
| `MAX_ITERATIONS` | `3` | Max refine→critic loops before forced end |
| `SCORE_THRESHOLD` | `0.8` | Critic score that triggers early end |

---

## 4  Test Results

```
tests/unit/       → 62 passed  (28 new)
tests/integration → 17 passed  (0 regressions)
─────────────────────────────────
TOTAL               79 passed   0 failed
```

### New Test Coverage

| Test Class | Tests | What's Covered |
|------------|-------|----------------|
| `TestConfig` | 3 | Default values, env fallback, invalid int |
| `TestAPIAuth` | 4 | Open mode, wrong key, missing key, correct key |
| `TestAPIMetadata` | 1 | request_id + elapsed_seconds in response |
| `TestPlannerCaps` | 1 | Sub-question list truncated to cap |
| `TestRetrieverCaps` | 1 | Documents truncated to per-subquery cap |
| `TestAgentMetadata` | 4 | Planner, critic, synthesizer, refiner emit metadata |
| `TestURLSanitization` | 9 | https, http, localhost, 127.0.0.1, 10.x, 192.168.x, ftp, file, empty |
| `TestBuilderThresholds` | 1 | Configurable score threshold + iteration cap |

---

## 5  Architecture Notes

### Config module (`app/utils/config.py`)
Single import point for all caps and security settings. Every constant reads from `os.getenv()` with a sensible default. Modules import individual constants — no global config object to mock.

### Authentication flow
`api/app.py` uses FastAPI `Depends()`:
1. If `API_KEY` env is empty → open mode, no check.
2. Otherwise, `X-API-Key` header must match exactly → 401 on mismatch.

### Metadata flow
Each agent node measures wall-clock time via `time.monotonic()` and writes to the `metadata` dict entry in state. The `update_dict` reducer in `AgentState` merges all nodes' metadata into a single flat dict. The API endpoint additionally writes `request_id` and `elapsed_seconds`.

### URL sanitization
`ui/streamlit_app.py._is_safe_url()` blocks:
- Non-http(s) schemes (file://, ftp://, etc.)
- Loopback addresses (localhost, 127.0.0.1, ::1)
- Private IP ranges (10.x, 192.168.x, 172.x)

---

## 6  Remaining Backlog (Not Addressed)

| Item | Priority | Rationale for deferral |
|------|----------|----------------------|
| Real vector store (FAISS/Chroma) replacing mock | P2 | Needs design decision on embedding model |
| Real cache (Redis) replacing in-memory dict | P2 | Needs infra provisioning |
| Structured logging (JSON) | P3 | Current StreamHandler is adequate for dev |
| CI pipeline (GitHub Actions) | P2 | Needs repo admin access |
| Docker / docker-compose | P2 | Needs deployment strategy decision |
