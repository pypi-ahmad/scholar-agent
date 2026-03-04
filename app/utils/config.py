"""
Centralised caps and configuration loaded from environment variables.

Every constant has a sensible hard-coded default so the app works out
of the box without a .env file.
"""

import os


def _int_env(name: str, default: int) -> int:
    """Read an int from the environment, falling back to *default*."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# --- Graph execution caps ---------------------------------------------------
MAX_SUB_QUESTIONS: int = _int_env("MAX_SUB_QUESTIONS", 6)
MAX_DOCS_PER_SUBQUERY: int = _int_env("MAX_DOCS_PER_SUBQUERY", 5)
MAX_DOCS_TOTAL: int = _int_env("MAX_DOCS_TOTAL", 30)
MAX_ITERATIONS: int = _int_env("MAX_ITERATIONS", 3)
SCORE_THRESHOLD: float = float(os.getenv("SCORE_THRESHOLD", "0.8"))

# --- Data backends -----------------------------------------------------------
REDIS_URL: str = os.getenv("REDIS_URL", "")
VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", "")
CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "models/embedding-001")

# --- API / Security ---------------------------------------------------------
AUTH_MODE: str = os.getenv("AUTH_MODE", "required").strip().lower()
API_KEY: str = os.getenv("API_KEY", "")
CORS_ALLOW_ORIGINS: str = os.getenv("CORS_ALLOW_ORIGINS", "")
RATE_LIMIT: str = os.getenv("RATE_LIMIT", "10/minute")
