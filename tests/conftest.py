import sys
import types
from types import SimpleNamespace


def _ensure_pydantic_stub():
    try:
        import pydantic  # noqa: F401
        # Verify it's the real deal, not a leftover stub
        if hasattr(pydantic, "__version__"):
            return
    except Exception:
        pass

    mod = types.ModuleType("pydantic")

    class ValidationError(Exception):
        pass

    class _FieldInfo:
        """Lightweight stand-in for pydantic.fields.FieldInfo."""

        def __init__(self, default=None, **kwargs):
            self.default = default
            self.required = default is ...
            self.min_length = kwargs.get("min_length")
            self.max_length = kwargs.get("max_length")

    def Field(default=None, **kwargs):
        return _FieldInfo(default, **kwargs)

    class BaseModel:
        def __init__(self, **data):
            annotations = getattr(self.__class__, "__annotations__", {})
            for key, type_hint in annotations.items():
                field_info = getattr(self.__class__, key, None)
                is_field = isinstance(field_info, _FieldInfo)

                # --- presence / required check ---
                if key not in data:
                    if is_field and field_info.required:
                        raise ValidationError(
                            f"Field '{key}' is required"
                        )
                    continue

                value = data[key]

                # --- type check (str fields) ---
                if type_hint is str and not isinstance(value, str):
                    raise ValidationError(
                        f"Field '{key}' expects str, got {type(value).__name__}"
                    )

                # --- string length constraints ---
                if is_field and isinstance(value, str):
                    if (
                        field_info.min_length is not None
                        and len(value) < field_info.min_length
                    ):
                        raise ValidationError(
                            f"Field '{key}' length {len(value)} "
                            f"< min_length {field_info.min_length}"
                        )
                    if (
                        field_info.max_length is not None
                        and len(value) > field_info.max_length
                    ):
                        raise ValidationError(
                            f"Field '{key}' length {len(value)} "
                            f"> max_length {field_info.max_length}"
                        )

                setattr(self, key, value)

    mod.BaseModel = BaseModel
    mod.Field = Field
    mod.ValidationError = ValidationError
    sys.modules["pydantic"] = mod


def _ensure_fastapi_stub():
    try:
        import fastapi  # noqa: F401
        return
    except Exception:
        pass

    mod = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class Request:
        """Minimal request stub."""
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def Depends(dep=None):
        """Stub for Depends — just returns the callable for test introspection."""
        return dep

    def Query(default=..., **kwargs):
        """Stub for fastapi.Query — returns default for test introspection."""
        return default

    class FastAPI:
        def __init__(self, *args, **kwargs):
            self.routes = []
            self.state = SimpleNamespace()
            self._middleware = []
            self._exception_handlers = {}

        def post(self, path, response_model=None, dependencies=None):
            def decorator(fn):
                self.routes.append(("POST", path, fn))
                return fn

            return decorator

        def get(self, path, dependencies=None):
            def decorator(fn):
                self.routes.append(("GET", path, fn))
                return fn

            return decorator

        def add_middleware(self, cls, **kwargs):
            self._middleware.append((cls, kwargs))

        def exception_handler(self, exc_class):
            def decorator(fn):
                self._exception_handlers[exc_class] = fn
                return fn
            return decorator

    mod.FastAPI = FastAPI
    mod.HTTPException = HTTPException
    mod.Request = Request
    mod.Depends = Depends
    mod.Query = Query
    sys.modules["fastapi"] = mod

    # --- fastapi.security stub ---
    security_mod = types.ModuleType("fastapi.security")

    class APIKeyHeader:
        def __init__(self, **kwargs):
            self.name = kwargs.get("name", "")
            self.auto_error = kwargs.get("auto_error", True)

    security_mod.APIKeyHeader = APIKeyHeader
    mod.security = security_mod
    sys.modules["fastapi.security"] = security_mod

    # --- fastapi.middleware.cors stub ---
    middleware_mod = types.ModuleType("fastapi.middleware")
    cors_mod = types.ModuleType("fastapi.middleware.cors")

    class CORSMiddleware:
        def __init__(self, app, **kwargs):
            pass

    cors_mod.CORSMiddleware = CORSMiddleware
    middleware_mod.cors = cors_mod
    mod.middleware = middleware_mod
    sys.modules["fastapi.middleware"] = middleware_mod
    sys.modules["fastapi.middleware.cors"] = cors_mod


def _ensure_langchain_stubs():
    try:
        import langchain_core.prompts  # noqa: F401
    except Exception:
        lc_core = types.ModuleType("langchain_core")
        prompts = types.ModuleType("langchain_core.prompts")

        class _PromptTemplate:
            def __or__(self, other):
                return other

        class ChatPromptTemplate:
            @classmethod
            def from_messages(cls, messages):
                return _PromptTemplate()

        prompts.ChatPromptTemplate = ChatPromptTemplate
        lc_core.prompts = prompts
        sys.modules["langchain_core"] = lc_core
        sys.modules["langchain_core.prompts"] = prompts

    try:
        import langchain_google_genai  # noqa: F401
    except Exception:
        lcg = types.ModuleType("langchain_google_genai")

        class ChatGoogleGenerativeAI:
            def __init__(self, *args, **kwargs):
                self.kwargs = kwargs

            def with_structured_output(self, schema):
                return self

            def invoke(self, payload):
                return SimpleNamespace(content="")

        lcg.ChatGoogleGenerativeAI = ChatGoogleGenerativeAI
        sys.modules["langchain_google_genai"] = lcg

    try:
        import langchain_community.tools.tavily_search  # noqa: F401
    except Exception:
        lcc = types.ModuleType("langchain_community")
        tools = types.ModuleType("langchain_community.tools")
        tavily = types.ModuleType("langchain_community.tools.tavily_search")

        class TavilySearchResults:
            def __init__(self, max_results=3):
                self.max_results = max_results

            def invoke(self, payload):
                return []

        tavily.TavilySearchResults = TavilySearchResults
        tools.tavily_search = tavily
        lcc.tools = tools
        sys.modules["langchain_community"] = lcc
        sys.modules["langchain_community.tools"] = tools
        sys.modules["langchain_community.tools.tavily_search"] = tavily


def _ensure_langgraph_stubs():
    try:
        import langgraph.graph  # noqa: F401
        import langgraph.constants  # noqa: F401
        return
    except Exception:
        pass

    lg = types.ModuleType("langgraph")
    graph_mod = types.ModuleType("langgraph.graph")
    constants_mod = types.ModuleType("langgraph.constants")

    START = "__start__"
    END = "__end__"

    class Send:
        def __init__(self, node, arg):
            self.node = node
            self.arg = arg

    class CompiledGraph:
        def __init__(self, nodes, edges, cond_edges):
            self.nodes = nodes
            self.edges = edges
            self.cond_edges = cond_edges

        def _merge(self, state, update):
            for key, value in (update or {}).items():
                if key in {"documents", "history"} and isinstance(value, list):
                    state[key] = (state.get(key) or []) + value
                elif key in {"metadata", "critique"} and isinstance(value, dict):
                    merged = dict(state.get(key) or {})
                    merged.update(value)
                    state[key] = merged
                else:
                    state[key] = value

        def invoke(self, initial_state):
            state = dict(initial_state)
            planner = self.nodes["planner"]
            retriever = self.nodes["retriever"]
            synthesizer = self.nodes["synthesizer"]
            critic = self.nodes["critic"]
            refiner = self.nodes["refiner"]
            planner_cond = self.cond_edges["planner"]
            critic_cond = self.cond_edges["critic"]

            self._merge(state, planner(state))
            sends = planner_cond(state)
            for send in sends:
                payload = send.arg if hasattr(send, "arg") else send.get("payload", {})
                self._merge(state, retriever(payload))

            self._merge(state, synthesizer(state))
            self._merge(state, critic(state))

            while True:
                route = critic_cond(state)
                if route == END:
                    return state
                self._merge(state, refiner(state))
                self._merge(state, critic(state))

        def stream(self, initial_state):
            """Yield per-node dicts like real LangGraph, then a synthetic __end__."""
            state = dict(initial_state)
            planner = self.nodes["planner"]
            retriever = self.nodes["retriever"]
            synthesizer = self.nodes["synthesizer"]
            critic = self.nodes["critic"]
            refiner = self.nodes["refiner"]
            planner_cond = self.cond_edges["planner"]
            critic_cond = self.cond_edges["critic"]

            p_update = planner(state)
            self._merge(state, p_update)
            yield {"planner": p_update}

            sends = planner_cond(state)
            for send in sends:
                payload = send.arg if hasattr(send, "arg") else send.get("payload", {})
                r_update = retriever(payload)
                self._merge(state, r_update)
                yield {"retriever": r_update}

            s_update = synthesizer(state)
            self._merge(state, s_update)
            yield {"synthesizer": s_update}

            c_update = critic(state)
            self._merge(state, c_update)
            yield {"critic": c_update}

            while True:
                route = critic_cond(state)
                if route == END:
                    return
                ref_update = refiner(state)
                self._merge(state, ref_update)
                yield {"refiner": ref_update}
                c_update2 = critic(state)
                self._merge(state, c_update2)
                yield {"critic": c_update2}

    class StateGraph:
        def __init__(self, state_schema):
            self.state_schema = state_schema
            self.nodes = {}
            self.edges = []
            self.cond_edges = {}

        def add_node(self, name, fn):
            self.nodes[name] = fn

        def add_edge(self, a, b):
            self.edges.append((a, b))

        def add_conditional_edges(self, node, fn, options):
            self.cond_edges[node] = fn

        def compile(self):
            return CompiledGraph(self.nodes, self.edges, self.cond_edges)

    graph_mod.StateGraph = StateGraph
    graph_mod.START = START
    graph_mod.END = END
    constants_mod.Send = Send

    lg.graph = graph_mod
    lg.constants = constants_mod

    sys.modules["langgraph"] = lg
    sys.modules["langgraph.graph"] = graph_mod
    sys.modules["langgraph.constants"] = constants_mod


def _ensure_sse_starlette_stub():
    """Stub sse_starlette so api.app can import EventSourceResponse."""
    try:
        import sse_starlette  # noqa: F401
        return
    except Exception:
        pass

    mod = types.ModuleType("sse_starlette")
    sse_mod = types.ModuleType("sse_starlette.sse")

    class EventSourceResponse:
        """Minimal stub — captures the generator for test inspection."""
        def __init__(self, content=None, media_type=None, **kwargs):
            # Materialise the async generator into a list so tests can inspect
            import asyncio

            async def _drain(agen):
                items = []
                async for item in agen:
                    items.append(item)
                return items

            if content is not None and hasattr(content, "__aiter__"):
                # Handle both top-level and nested event-loop contexts
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    # Already inside an event loop (e.g. asyncio.run) — create
                    # a new loop in a thread to avoid "loop already running".
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        self._events = pool.submit(
                            asyncio.run, _drain(content)
                        ).result()
                else:
                    self._events = asyncio.run(_drain(content))
            else:
                self._events = []
            self.media_type = media_type or "text/event-stream"
            self.status_code = 200
            self.body = self._events  # alias for easy assertion

    sse_mod.EventSourceResponse = EventSourceResponse
    mod.sse = sse_mod
    mod.EventSourceResponse = EventSourceResponse  # top-level alias
    sys.modules["sse_starlette"] = mod
    sys.modules["sse_starlette.sse"] = sse_mod


def _ensure_slowapi_stub():
    """Stub slowapi so api.app can import it without the real package."""
    try:
        import slowapi  # noqa: F401
        return
    except Exception:
        pass

    mod = types.ModuleType("slowapi")
    errors_mod = types.ModuleType("slowapi.errors")
    util_mod = types.ModuleType("slowapi.util")

    class RateLimitExceeded(Exception):
        pass

    class Limiter:
        def __init__(self, **kwargs):
            pass

        def limit(self, limit_string):
            def decorator(fn):
                return fn
            return decorator

    def get_remote_address(request=None):
        return "127.0.0.1"

    mod.Limiter = Limiter
    errors_mod.RateLimitExceeded = RateLimitExceeded
    util_mod.get_remote_address = get_remote_address

    mod.errors = errors_mod
    mod.util = util_mod

    sys.modules["slowapi"] = mod
    sys.modules["slowapi.errors"] = errors_mod
    sys.modules["slowapi.util"] = util_mod


def _ensure_streamlit_stub():
    """Minimal streamlit stub so ui.streamlit_app can be imported in tests."""
    try:
        import streamlit  # noqa: F401
        return
    except Exception:
        pass

    mod = types.ModuleType("streamlit")

    def _noop(*args, **kwargs):
        pass

    class _NoopContext:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    mod.set_page_config = _noop
    mod.title = _noop
    mod.markdown = _noop
    mod.text_input = lambda *a, **kw: ""
    mod.button = lambda *a, **kw: False
    mod.warning = _noop
    mod.write = _noop
    mod.subheader = _noop
    mod.info = _noop
    mod.json = _noop
    mod.error = _noop
    mod.stop = _noop
    mod.columns = lambda n: [SimpleNamespace(metric=_noop)] * n
    mod.container = lambda: _NoopContext()
    mod.expander = lambda *a, **kw: _NoopContext()
    mod.empty = lambda: SimpleNamespace(text=_noop, markdown=_noop)
    mod.session_state = {}

    sys.modules["streamlit"] = mod


def _ensure_dotenv_stub():
    """Stub python-dotenv if not installed."""
    try:
        import dotenv  # noqa: F401
        return
    except Exception:
        pass

    mod = types.ModuleType("dotenv")
    mod.load_dotenv = lambda *a, **kw: None
    sys.modules["dotenv"] = mod


def pytest_configure(config):
    _ensure_pydantic_stub()
    _ensure_fastapi_stub()
    _ensure_sse_starlette_stub()
    _ensure_slowapi_stub()
    _ensure_streamlit_stub()
    _ensure_dotenv_stub()
    _ensure_langchain_stubs()
    _ensure_langgraph_stubs()
