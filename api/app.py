import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.graph.builder import get_compiled_graph

logger = logging.getLogger("research_agent.api")

# ---------------------------------------------------------------------------
# Security: API-key authentication
# ---------------------------------------------------------------------------
_AUTH_MODE = os.getenv("AUTH_MODE", "required").strip().lower()
_API_KEY = os.getenv("API_KEY", "")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_api_key(key: str = Depends(_api_key_header)):
    """Enforce API-key authentication based on AUTH_MODE.

    AUTH_MODE="required" (default):
        API_KEY *must* be configured server-side.  If it isn't, reject with
        503 so the operator notices immediately.  Every request must include
        a matching X-API-Key header (401 on mismatch / missing).

    AUTH_MODE="optional":
        If API_KEY is empty the endpoint is open (dev convenience).
        If API_KEY is set, requests must still present a matching header.
    """
    if _AUTH_MODE == "required":
        if not _API_KEY:
            raise HTTPException(
                status_code=503,
                detail="Server misconfiguration: API_KEY is not set while AUTH_MODE is 'required'.",
            )
        if key != _API_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing API key.")
        return

    # AUTH_MODE == "optional" (or any other value treated as optional)
    if not _API_KEY:
        return  # open mode – no key configured
    if key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Autonomous Research + Report Agent API",
    description="Multi-agent cyclic reasoning system powered by LangGraph.",
    version="1.1.0",
)

# ---------------------------------------------------------------------------
# CORS – configurable via env var, default deny-all
# ---------------------------------------------------------------------------
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if o.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ---------------------------------------------------------------------------
# Rate-limiting (best-effort: works in-process; override via env)
# ---------------------------------------------------------------------------
try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    _rate_limit = os.getenv("RATE_LIMIT", "10/minute")
    limiter = Limiter(key_func=get_remote_address, default_limits=[_rate_limit])
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        from starlette.responses import JSONResponse
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})

except Exception:
    # slowapi not installed – run without rate-limiting
    limiter = None
    logger.warning("slowapi not installed; rate-limiting disabled.")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class ResearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The main user query to research.",
    )


class ResearchResponse(BaseModel):
    final_report: str
    iterations: int
    score: float
    metadata: Dict[str, Any]
    history: List[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/research", response_model=ResearchResponse, dependencies=[Depends(_verify_api_key)])
async def perform_research(request: ResearchRequest):
    """
    Executes the multi-agent cyclic LangGraph to produce a well-cited research report.
    """
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] Received API request for query: '{request.query}'")

    initial_state = {
        "query": request.query,
        "plan": [],
        "current_step": 0,
        "documents": [],
        "draft": "",
        "critique": {},
        "score": 0.0,
        "iteration": 0,
        "history": [f"API Received Query: {request.query}"],
        "metadata": {"request_id": request_id},
    }

    try:
        t0 = time.monotonic()
        logger.info(f"[{request_id}] Starting graph execution...")
        final_state = await asyncio.to_thread(
            get_compiled_graph().invoke, initial_state
        )
        elapsed = round(time.monotonic() - t0, 2)
        logger.info(f"[{request_id}] Graph execution completed in {elapsed}s.")

        # Inject timing into metadata
        meta = final_state.get("metadata", {})
        meta["elapsed_seconds"] = elapsed
        meta["request_id"] = request_id

        return ResearchResponse(
            final_report=final_state.get("draft", "Error generating draft."),
            iterations=final_state.get("iteration", 0),
            score=final_state.get("score", 0.0),
            metadata=meta,
            history=final_state.get("history", []),
        )

    except Exception:
        logger.error(f"[{request_id}] Graph execution failed", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        )


# ---------------------------------------------------------------------------
# SSE streaming endpoint
# ---------------------------------------------------------------------------
def _safe_json(obj: Any) -> Any:
    """Convert non-serialisable objects to strings so json.dumps never fails."""
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json(v) for v in obj]
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


async def _stream_graph(request_id: str, query: str):
    """Async generator that yields SSE-formatted dicts from the graph stream."""
    initial_state = {
        "query": query,
        "plan": [],
        "current_step": 0,
        "documents": [],
        "draft": "",
        "critique": {},
        "score": 0.0,
        "iteration": 0,
        "history": [f"SSE Received Query: {query}"],
        "metadata": {"request_id": request_id},
    }

    try:
        t0 = time.monotonic()
        graph = get_compiled_graph()

        # graph.stream() is synchronous — run in a thread so we don't block
        # the event loop between yields.
        import queue
        import threading

        q: queue.Queue = queue.Queue()
        _SENTINEL = object()

        def _run():
            try:
                for chunk in graph.stream(initial_state):
                    q.put(chunk)
            except Exception as exc:
                q.put(exc)
            finally:
                q.put(_SENTINEL)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        final_state = dict(initial_state)

        while True:
            # Use asyncio-friendly polling so the event loop stays responsive
            item = await asyncio.to_thread(q.get)
            if item is _SENTINEL:
                break
            if isinstance(item, Exception):
                raise item

            for node_name, state_update in item.items():
                # Track state locally for the final event
                for key in ("draft", "score", "iteration"):
                    if key in state_update:
                        final_state[key] = state_update[key]
                if "metadata" in state_update and isinstance(state_update["metadata"], dict):
                    final_state.setdefault("metadata", {}).update(state_update["metadata"])

                payload = _safe_json(state_update)
                yield {
                    "event": "node",
                    "data": json.dumps({
                        "request_id": request_id,
                        "node": node_name,
                        "payload": payload,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }),
                }

        elapsed = round(time.monotonic() - t0, 2)
        meta = final_state.get("metadata", {})
        meta["elapsed_seconds"] = elapsed
        meta["request_id"] = request_id

        yield {
            "event": "final",
            "data": json.dumps(_safe_json({
                "request_id": request_id,
                "report": final_state.get("draft", ""),
                "metadata": meta,
            })),
        }

    except Exception:
        logger.error(f"[{request_id}] SSE stream failed", exc_info=True)
        yield {
            "event": "error",
            "data": json.dumps({
                "request_id": request_id,
                "message": "An internal error occurred during streaming.",
            }),
        }


@app.get("/research/stream", dependencies=[Depends(_verify_api_key)])
async def stream_research(
    query: str = Query(..., min_length=1, max_length=1000, description="Research query"),
):
    """SSE endpoint — streams node-by-node updates from the LangGraph execution."""
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] SSE stream requested for query: '{query}'")
    return EventSourceResponse(_stream_graph(request_id, query))


@app.get("/health")
def health_check():
    return {"status": "ok"}
