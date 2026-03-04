# CLEANUP PLAN — Autonomous Research + Report Agent

> **Evidence convention:** `path/file.py:L10-L25` — all claims verified by reading the referenced lines.  
> **Audit date:** 2026-03-04

---

## 1. Overview

This document identifies legacy code, dead code, incorrect defaults, missing infrastructure, and technical debt in the repository. Each item includes evidence, risk assessment, and a staged removal/improvement plan.

**Cleanup urgency levels:**

| Level | Meaning |
|---|---|
| 🔴 HIGH | Blocks production use or creates active security/correctness risk |
| 🟡 MEDIUM | Degrades developer experience, performance, or operational safety |
| 🟢 LOW | Cosmetic, minor, or future-state improvement |

---

## 2. Legacy / Dead / Stub Code

### 2.1 — Mock Vector Store (production blocker)

| Property | Value |
|---|---|
| **Candidate** | `app/tools/vector_store.py` — entire file |
| **Why legacy** | `VectorStoreWrapper` uses a 3-document hardcoded Python list with keyword matching. It is not a real vector store. `faiss-cpu` is in `requirements.txt` but never imported anywhere in the codebase. |
| **Evidence** | `app/tools/vector_store.py:L14-L21` (hard-coded docs); `requirements.txt:L14` (`faiss-cpu` listed); no `import faiss` anywhere in codebase |
| **Risk** | 🔴 HIGH — silently returns irrelevant documents for real research queries |

**Safe removal / replacement steps:**

1. Implement a real `VectorStoreWrapper` that connects to FAISS, Chroma, or Pinecone.
2. Preserve the `similarity_search(query: str, k: int = 2) -> List[Dict[str, str]]` interface — `retriever.py` imports `vector_db` and calls `.similarity_search()`.
3. Keep `vector_db = VectorStoreWrapper()` singleton pattern.
4. Once real implementation is in place, remove `mock_db` list (`vector_store.py:L14-L21`).
5. Remove `# noqa` comment `L-05` in its current form if the logic is replaced.
6. Remove `faiss-cpu` from `requirements.txt` if using a different backend (e.g., Chroma doesn't need it).

---

### 2.2 — Hard-coded Query Cache (production blocker)

| Property | Value |
|---|---|
| **Candidate** | `app/tools/cache.py:L10-L18` — `QueryCache.store` dict |
| **Why legacy** | Contains only 3 trivial factoid entries (`capital of france`, `romeo and juliet`, `2+2`). Not useful for any real research query. Cache is process-local; cleared on every restart. |
| **Evidence** | `app/tools/cache.py:L10-L18` |
| **Risk** | 🔴 HIGH — will almost never match real queries; cache tool selection is misleading |

**Safe removal / replacement steps:**

1. Replace `self.store = {…}` with connection to a persistent cache (Redis, DynamoDB, Firestore, etc.).
2. Update `get(query: str)` to query the real backend.
3. Preserve the return type `List[Dict[str, str]]` — callers expect `[{"source": str, "content": str}]`.
4. Add TTL-based expiry to the real cache.
5. The `global_cache = QueryCache()` singleton pattern is fine to keep.

---

### 2.3 — `faiss-cpu` in `requirements.txt` (unused dependency)

| Property | Value |
|---|---|
| **Candidate** | `requirements.txt:L14` — `faiss-cpu` |
| **Why legacy** | `faiss-cpu` is listed with comment `L-02` (note about replacing `faiss-gpu`) but is never imported by any module in the repo. The vector store is a pure mock. |
| **Evidence** | `requirements.txt:L14`; zero `import faiss` anywhere in codebase (confirmed by audit) |
| **Risk** | 🟡 MEDIUM — adds ~300MB install overhead and a binary build dependency for no benefit |

**Safe removal steps:**

1. Remove `faiss-cpu` from `requirements.txt`.
2. Add it back only when implementing a real FAISS-backed vector store.
3. PR: single-line change — low risk.

---

### 2.4 — `metadata` state channel always empty

| Property | Value |
|---|---|
| **Candidate** | `app/graph/state.py:L42` — `metadata` field; `api/app.py:L44` |
| **Why dead** | The `metadata` field has a `update_dict` reducer and is returned in `ResearchResponse`, but no agent node ever writes to it. It is initialized as `{}` and passed through unchanged. |
| **Evidence** | `app/graph/state.py:L42`; `api/app.py:L44`; grepping all agents — none set `"metadata"` in return dict |
| **Risk** | 🟢 LOW — not harmful; wasted infrastructure |

**Options:**

- **Option A (keep, populate):** Add metadata-producing instrumentation (request ID, timing, token counts) — this is mentioned as a future improvement in `README.md:L296`.
- **Option B (remove):** Remove `metadata` from `AgentState`, `ResearchResponse`, and initial state dict in API/UI.

Recommended: **Option A** — wire real telemetry (execution time per node, total LLM token usage).

---

### 2.5 — `operator` import removed (already fixed, confirm cleanup)

| Property | Value |
|---|---|
| **Candidate** | `app/graph/state.py:L1` — comment `L-01` |
| **Why** | Comment notes `operator` was imported but never referenced — already removed |
| **Evidence** | `app/graph/state.py:L1-L2` — comment confirms fix was applied |
| **Risk** | 🟢 LOW — already fixed; confirm no other unused imports remain |

**Action:** Remove the `L-01` comment if desired — it's informational, not code.

---

## 3. Security / Configuration Defaults

### 3.1 — `RELOAD=true` default (production hazard)

| Property | Value |
|---|---|
| **Candidate** | `main.py:L14` |
| **Why** | `RELOAD` defaults to `"true"` when env var is unset. Uvicorn hot-reload is a development convenience but inappropriate for production — it adds latency, spawns file watchers, and can cause issues with worker state. |
| **Evidence** | `main.py:L14`: `reload_enabled = os.getenv("RELOAD", "true").lower() == "true"` |
| **Risk** | 🟡 MEDIUM — deploying to production without setting `RELOAD=false` is a silent operational issue |

**Safe fix:**

```python
# Change default from "true" to "false"
reload_enabled = os.getenv("RELOAD", "false").lower() == "true"
```

Alternatively add an `if` guard warning if `RELOAD=true` and `HOST != "127.0.0.1"`.

---

### 3.2 — `HOST=0.0.0.0` default

| Property | Value |
|---|---|
| **Candidate** | `main.py:L13` |
| **Why** | Default bind host `0.0.0.0` exposes the API on all network interfaces immediately after `python main.py`. A developer running locally may inadvertently expose the unauthenticated API to the LAN. |
| **Evidence** | `main.py:L13`: `host = os.getenv("HOST", "0.0.0.0")` |
| **Risk** | 🟡 MEDIUM — combined with no auth, exposes all endpoints on the network |

**Safe fix:** Change default to `127.0.0.1`:

```python
host = os.getenv("HOST", "127.0.0.1")
```

Production deployments can override via `HOST=0.0.0.0` in their environment.

---

### 3.3 — No CORS configuration

| Property | Value |
|---|---|
| **Candidate** | `api/app.py` — absent |
| **Why** | `CORSMiddleware` is not configured. Any browser-based client attempting to call `POST /research` from a different origin will be blocked by the browser's same-origin policy. |
| **Evidence** | No `CORSMiddleware` import or `app.add_middleware` call in `api/app.py` |
| **Risk** | 🟡 MEDIUM — blocks browser clients; 🔴 HIGH if wildcard CORS added without auth |

**Safe fix:**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit default, add real origins
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)
```

Never use `allow_origins=["*"]` without authentication.

---

### 3.4 — No authentication on any endpoint

| Property | Value |
|---|---|
| **Candidate** | `api/app.py:L36`, `api/app.py:L83` |
| **Why** | Both `POST /research` and `GET /health` have zero authentication. Any caller can invoke the graph without credentials. |
| **Evidence** | `api/app.py:L36` — no `Depends(...)` on `perform_research`; `README.md:L182` acknowledges this |
| **Risk** | 🔴 HIGH — if exposed to the internet, anyone can exhaust Gemini API quota and Tavily credits |

**Options:**
- API key header (`X-API-Key`) — simple, stateless.
- OAuth2 Bearer tokens — for user-facing deployments.
- Network-level controls (VPN, firewall) — for internal tools.

Minimum viable fix:

```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(key: str = Security(api_key_header)):
    if key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Forbidden")
```

---

## 4. Missing Infrastructure

### 4.1 — No CI/CD pipeline

| Property | Value |
|---|---|
| **Missing** | `.github/workflows/`, `Jenkinsfile`, `azure-pipelines.yml`, or equivalent |
| **Risk** | 🔴 HIGH per org policy (CI required for code reviews and coverage enforcement) |

**Recommended `main.yml` skeleton:**

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/unit tests/integration -q
      - run: python -m pytest tests/integration/test_import_smoke.py -v
```

---

### 4.2 — No Dockerfile

| Property | Value |
|---|---|
| **Missing** | `Dockerfile`, `docker-compose.yml` |
| **Risk** | 🟡 MEDIUM — deployment is manual; environment reproducibility not guaranteed |

See `OPS.md` Section 7 for a minimal `Dockerfile` skeleton.

---

### 4.3 — No `.gitignore`

| Property | Value |
|---|---|
| **Missing** | `.gitignore` |
| **Risk** | 🔴 HIGH — `.env` (containing `GOOGLE_API_KEY`) may be accidentally committed to version control |

**Minimum `.gitignore`:**

```
.env
.venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
```

---

### 4.4 — No rate limiting

| Property | Value |
|---|---|
| **Missing** | Rate limiting middleware |
| **Risk** | 🔴 HIGH — each `/research` call triggers multiple Gemini + Tavily API calls; unthrottled access exhausts quotas |

**Recommended fix:** Add `slowapi`:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/research")
@limiter.limit("5/minute")
async def perform_research(request: Request, body: ResearchRequest):
    ...
```

---

## 5. Staged Cleanup PRs

### PR 1 — Security baseline (do first)

| Item | File(s) | Change |
|---|---|---|
| Add `.gitignore` | new file | Prevent `.env` commits |
| Change `RELOAD` default | `main.py:L14` | `"true"` → `"false"` |
| Change `HOST` default | `main.py:L13` | `"0.0.0.0"` → `"127.0.0.1"` |

**Risk:** Low — no logic changes.

---

### PR 2 — Remove dead dependency

| Item | File(s) | Change |
|---|---|---|
| Remove `faiss-cpu` | `requirements.txt:L14` | Delete line |

**Risk:** Very low — no code uses it.

---

### PR 3 — Real vector store

| Item | File(s) | Change |
|---|---|---|
| Implement real `VectorStoreWrapper` | `app/tools/vector_store.py` | Replace mock with Chroma/FAISS/Pinecone |
| Update `requirements.txt` | `requirements.txt` | Add chosen vector DB client |
| Update unit tests | `tests/unit/test_tools_and_utils.py` | Test against real similarity behavior |

**Risk:** Medium — interface preserved; test coverage required.

---

### PR 4 — Real cache backend

| Item | File(s) | Change |
|---|---|---|
| Implement real `QueryCache` | `app/tools/cache.py` | Replace dict with Redis/DynamoDB/etc. |
| Add TTL expiry | `app/tools/cache.py` | Time-bound cache entries |
| Update tests | `tests/unit/test_tools_and_utils.py` | Mock the real backend in unit tests |

**Risk:** Medium — interface preserved.

---

### PR 5 — API hardening

| Item | File(s) | Change |
|---|---|---|
| Add CORS middleware | `api/app.py` | `CORSMiddleware` with explicit origins |
| Add authentication | `api/app.py` | API key header or OAuth2 |
| Add rate limiting | `api/app.py` + `requirements.txt` | `slowapi` or similar |
| Disable OpenAPI in prod | `api/app.py` | env-conditional `docs_url=None` |

**Risk:** Medium — requires new env vars; test updates for auth.

---

### PR 6 — CI/CD pipeline

| Item | File(s) | Change |
|---|---|---|
| GitHub Actions workflow | `.github/workflows/ci.yml` | build, test, lint, coverage check |
| Coverage enforcement | `pytest.ini` or workflow | `--cov` + `--cov-fail-under=80` |
| Dockerfile | `Dockerfile` | Containerize API for deployment |

**Risk:** Low — infrastructure only, no app logic changes.

---

### PR 7 — Populate `metadata` field

| Item | File(s) | Change |
|---|---|---|
| Add request timing | `api/app.py` | Pre/post `asyncio.to_thread` timing → inject into `metadata` |
| Add token counts | `app/agents/*.py` | LangChain `AIMessage.usage_metadata` → `metadata` |
| Add request ID | `api/app.py` | UUID per request → `metadata` |

**Risk:** Low — adds data; existing callers get a richer `metadata` object.

---

## 6. Summary Table

| # | Candidate | Severity | Type | PR |
|---|---|---|---|---|
| 2.1 | Mock `VectorStoreWrapper` | 🔴 HIGH | Production blocker | PR 3 |
| 2.2 | Hard-coded `QueryCache` | 🔴 HIGH | Production blocker | PR 4 |
| 2.3 | `faiss-cpu` unused | 🟡 MEDIUM | Dead dependency | PR 2 |
| 2.4 | `metadata` always empty | 🟢 LOW | Dead infrastructure | PR 7 |
| 3.1 | `RELOAD=true` default | 🟡 MEDIUM | Config default | PR 1 |
| 3.2 | `HOST=0.0.0.0` default | 🟡 MEDIUM | Config default | PR 1 |
| 3.3 | No CORS config | 🟡 MEDIUM | Missing security | PR 5 |
| 3.4 | No authentication | 🔴 HIGH | Missing security | PR 5 |
| 4.1 | No CI/CD pipeline | 🔴 HIGH | Missing infra | PR 6 |
| 4.2 | No Dockerfile | 🟡 MEDIUM | Missing infra | PR 6 |
| 4.3 | No `.gitignore` | 🔴 HIGH | Missing security | PR 1 |
| 4.4 | No rate limiting | 🔴 HIGH | Missing security | PR 5 |
