"""Medical-knowledge RAG retriever.

Lazily loads a FAISS index (built by scripts/ingest_medical.py) and exposes a
similarity-search helper used to inject medical context into the triage prompt.
The index is loaded once and cached. If the index is missing or any error
occurs, retrieval degrades gracefully to an empty list so chat never crashes.
"""

import logging
import os

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings

logger = logging.getLogger(__name__)

_vectorstore: FAISS | None = None
_load_attempted = False
_embeddings: OpenAIEmbeddings | None = None


def _get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_base=settings.OPENAI_BASE_URL,
            openai_api_key=settings.OPENAI_API_KEY,
            check_embedding_ctx_length=False,
        )
    return _embeddings


def _get_vectorstore() -> FAISS | None:
    """Load the FAISS index once; return None if unavailable."""
    global _vectorstore, _load_attempted
    if _vectorstore is not None:
        return _vectorstore
    if _load_attempted:
        return _vectorstore

    _load_attempted = True
    index_path = settings.FAISS_INDEX_PATH
    if not os.path.isdir(index_path):
        logger.warning(
            "Medical FAISS index not found at %s; retrieval disabled.", index_path
        )
        return None
    try:
        _vectorstore = FAISS.load_local(
            index_path,
            _get_embeddings(),
            allow_dangerous_deserialization=True,
        )
        logger.info("Loaded medical FAISS index from %s", index_path)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to load medical FAISS index from %s", index_path)
        _vectorstore = None
    return _vectorstore


# Cap each retrieved snippet so the RAG context kept small — long MedQuAD answers
# bloat the LLM prompt and slow inference with little triage benefit.
_MAX_SNIPPET_CHARS = 400


async def retrieve_medical_context(
    query: str, k: int = 3, max_chars: int = _MAX_SNIPPET_CHARS
) -> list[str]:
    """Return the top-k retrieved medical snippets (page_content) for a query.

    Each snippet is truncated to ``max_chars`` to keep the triage prompt small.
    Returns [] if the index is missing or any error occurs.
    """
    if not query or not query.strip():
        return []
    vs = _get_vectorstore()
    if vs is None:
        return []
    try:
        results = vs.similarity_search(query, k=k)
        return [doc.page_content[:max_chars].strip() for doc in results]
    except Exception:  # noqa: BLE001
        logger.exception("Medical retrieval failed for query: %r", query)
        return []
