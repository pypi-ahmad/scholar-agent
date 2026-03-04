"""
Vector-store abstraction layer with pluggable backends.

Backends:
    InMemoryVectorStore  — default; keyword matching (original behaviour)
    FAISSVectorStore     — enabled when VECTOR_DB_PATH is set; uses faiss-cpu
    ChromaVectorStore    — enabled when CHROMA_PERSIST_DIR is set; uses chromadb

Factory:
    get_vector_store() → selects backend by environment; falls back to
    InMemoryVectorStore.

Agents must use the factory or the module-level singleton ``vector_db``.
"""

import abc
import logging
import os
from typing import Dict, List

logger = logging.getLogger("research_agent.tools.vector_store")


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------
class VectorStoreBackend(abc.ABC):
    """Minimal vector-store contract expected by the retriever agent."""

    @abc.abstractmethod
    def add_documents(self, docs: List[Dict[str, str]]) -> None:
        """Ingest *docs* (each with ``"source"`` and ``"content"`` keys)."""

    @abc.abstractmethod
    def similarity_search(self, query: str, k: int = 2) -> List[Dict[str, str]]:
        """Return up to *k* documents most relevant to *query*."""


# ---------------------------------------------------------------------------
# In-memory fallback (original behaviour)
# ---------------------------------------------------------------------------
class InMemoryVectorStore(VectorStoreBackend):
    """
    In-memory mock vector store with keyword matching.

    Ships with three hard-coded sample documents.  Suitable as the
    default when no external vector DB is configured.
    """

    def __init__(self) -> None:
        self.mock_db: List[Dict[str, str]] = [
            {
                "source": "internal_doc_1.pdf",
                "content": "The company Q3 revenue grew by 15% due to new AI product launches.",
            },
            {
                "source": "internal_doc_2.pdf",
                "content": "Our new cloud infrastructure costs decreased by 20% in 2023.",
            },
            {
                "source": "policy_manual.txt",
                "content": "Remote work policy: Employees may work from anywhere up to 4 weeks a year.",
            },
        ]

    def add_documents(self, docs: List[Dict[str, str]]) -> None:
        self.mock_db.extend(docs)

    def similarity_search(self, query: str, k: int = 2) -> List[Dict[str, str]]:
        """Simulates a vector DB similarity search via keyword matching."""
        logger.info(f"Vector search executed for query: '{query}'")

        # Simple keyword matching for the mock instead of actual embeddings.
        # L-05: threshold > 2 so short-but-meaningful technical terms pass.
        results = []
        for doc in self.mock_db:
            if any(
                word.lower() in doc["content"].lower()
                for word in query.split()
                if len(word) > 2
            ):
                results.append(doc)

        # If nothing matches, return the first k docs as a fallback.
        if not results:
            results = self.mock_db[:k]

        return results[:k]


# ---------------------------------------------------------------------------
# FAISS backend
# ---------------------------------------------------------------------------
class FAISSVectorStore(VectorStoreBackend):
    """
    FAISS-backed vector store persisted to ``VECTOR_DB_PATH``.

    Requires ``faiss-cpu`` (already in requirements.txt) **and** an
    embeddings provider (``langchain-google-genai`` by default).
    """

    def __init__(
        self, persist_path: str, embedding_model: str = "models/embedding-001"
    ) -> None:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from langchain_community.vectorstores import FAISS as _FAISS

        self._FAISS = _FAISS
        self._persist_path = persist_path
        self._embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model)

        if os.path.exists(persist_path):
            self._store = _FAISS.load_local(
                persist_path,
                self._embeddings,
                allow_dangerous_deserialization=True,
            )
            logger.info("FAISS index loaded from %s", persist_path)
        else:
            self._store = None
            logger.info(
                "FAISS index will be created at %s on first add_documents()",
                persist_path,
            )

    def add_documents(self, docs: List[Dict[str, str]]) -> None:
        from langchain_core.documents import Document

        lc_docs = [
            Document(
                page_content=d["content"],
                metadata={"source": d.get("source", "")},
            )
            for d in docs
        ]
        if self._store is None:
            self._store = self._FAISS.from_documents(lc_docs, self._embeddings)
        else:
            self._store.add_documents(lc_docs)
        self._store.save_local(self._persist_path)

    def similarity_search(self, query: str, k: int = 2) -> List[Dict[str, str]]:
        if self._store is None:
            logger.warning("FAISS index is empty — returning no results")
            return []
        results = self._store.similarity_search(query, k=k)
        return [
            {"source": doc.metadata.get("source", ""), "content": doc.page_content}
            for doc in results
        ]


# ---------------------------------------------------------------------------
# Chroma backend
# ---------------------------------------------------------------------------
class ChromaVectorStore(VectorStoreBackend):
    """
    Chroma-backed vector store persisted to ``CHROMA_PERSIST_DIR``.

    Requires ``chromadb`` package (``pip install chromadb``).
    """

    def __init__(
        self, persist_dir: str, embedding_model: str = "models/embedding-001"
    ) -> None:
        import chromadb  # noqa: F401 — verifies package availability

        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from langchain_community.vectorstores import Chroma as _Chroma

        self._embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model)
        self._store = _Chroma(
            persist_directory=persist_dir,
            embedding_function=self._embeddings,
            collection_name="research_docs",
        )
        logger.info("Chroma vector store initialised at %s", persist_dir)

    def add_documents(self, docs: List[Dict[str, str]]) -> None:
        from langchain_core.documents import Document

        lc_docs = [
            Document(
                page_content=d["content"],
                metadata={"source": d.get("source", "")},
            )
            for d in docs
        ]
        self._store.add_documents(lc_docs)

    def similarity_search(self, query: str, k: int = 2) -> List[Dict[str, str]]:
        results = self._store.similarity_search(query, k=k)
        return [
            {"source": doc.metadata.get("source", ""), "content": doc.page_content}
            for doc in results
        ]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_vector_store() -> VectorStoreBackend:
    """Return a vector-store backend chosen by environment variables.

    Priority:
        1. ``CHROMA_PERSIST_DIR`` → :class:`ChromaVectorStore`
        2. ``VECTOR_DB_PATH``     → :class:`FAISSVectorStore`
        3. fallback               → :class:`InMemoryVectorStore`

    The ``EMBEDDING_MODEL`` env var (default ``models/embedding-001``)
    controls the Google embedding model used by FAISS / Chroma.
    """
    embedding_model = os.getenv("EMBEDDING_MODEL", "models/embedding-001")

    chroma_dir = os.getenv("CHROMA_PERSIST_DIR", "")
    if chroma_dir:
        try:
            return ChromaVectorStore(chroma_dir, embedding_model)
        except Exception as exc:
            logger.warning("Chroma unavailable (%s), trying next backend", exc)

    faiss_path = os.getenv("VECTOR_DB_PATH", "")
    if faiss_path:
        try:
            return FAISSVectorStore(faiss_path, embedding_model)
        except Exception as exc:
            logger.warning(
                "FAISS unavailable (%s), falling back to InMemoryVectorStore",
                exc,
            )

    return InMemoryVectorStore()


# ---------------------------------------------------------------------------
# Module-level singleton — agents import this name
# ---------------------------------------------------------------------------
vector_db: VectorStoreBackend = get_vector_store()

# Backward-compat alias so existing code referencing VectorStoreWrapper still works.
VectorStoreWrapper = InMemoryVectorStore
