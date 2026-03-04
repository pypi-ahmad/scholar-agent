# Changelog — Upgrades

All notable changes from the upgrade/bughunt pass.

## [1.2.0] — 2026-03-04

### Features
- **SSE streaming endpoint**: `GET /research/stream?query=…` returns `text/event-stream` via `sse-starlette`
  - Streams `node` events (one per graph node execution) with `{request_id, node, payload, timestamp}`
  - Streams a `final` event with `{request_id, report, metadata}` on completion
  - Streams an `error` event with `{request_id, message}` on failure, then closes
  - Respects `X-API-Key` auth and rate limiting (same as `/research`)

### Tests
- 8 new unit tests for SSE endpoint: response type, event structure, error handling, auth, `_safe_json` helper
- Enhanced conftest `CompiledGraph.stream` stub to yield per-node dicts (matches real LangGraph)
- Added `sse_starlette` stub to conftest

---

## [1.1.0] — 2026-03-04

### Security
- **API authentication**: `X-API-Key` header auth gated by `API_KEY` env var (open mode when unset)
- **CORS middleware**: `CORSMiddleware` controlled by `CORS_ALLOW_ORIGINS` env var; default deny-all
- **Rate limiting**: `slowapi` integration on `/research`; configurable via `RATE_LIMIT` env (default `10/minute`)
- **URL sanitization**: Streamlit source links validated — blocks non-http, loopback, and private IPs

### Reliability
- **Sub-question cap**: Planner output capped at `MAX_SUB_QUESTIONS` (default 6)
- **Per-subquery doc cap**: Retriever capped at `MAX_DOCS_PER_SUBQUERY` (default 5)
- **Total doc cap**: Synthesizer input capped at `MAX_DOCS_TOTAL` (default 30) post-dedup
- **Configurable thresholds**: `MAX_ITERATIONS` and `SCORE_THRESHOLD` moved to env-driven config
- **Error boundary**: Streamlit graph streaming wrapped in try/except → `st.error()` on failure

### Observability
- **Request tracing**: UUID `request_id` injected into state at API entry and returned in metadata
- **Execution timing**: `elapsed_seconds` measured per-request; per-node `*_seconds` in metadata
- **Node metadata**: Every agent node now writes timing and node-specific metrics to the `metadata` state field

### Infrastructure
- **Centralised config**: New `app/utils/config.py` — single source of truth for all caps and thresholds
- **Dependencies**: Added `slowapi` and `sse-starlette` to `requirements.txt`

### Tests
- **28 new unit tests** covering: auth, caps, metadata, URL sanitization, config, builder thresholds
- **Upgraded conftest stubs**: Added stubs for `slowapi`, `streamlit`, `dotenv`, `fastapi.security`, `CORSMiddleware`
- **Zero regressions**: All 79 tests (62 unit + 17 integration) pass
