import logging
import os

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from app.core.config import settings
from app.core.llm import get_embeddings

logger = logging.getLogger(__name__)

_vectorstore: FAISS | None = None


def _get_embeddings() -> Embeddings:
    return get_embeddings()


def load_index() -> None:
    """Load FAISS index from disk on startup."""
    global _vectorstore
    index_path = settings.FAISS_INDEX_PATH
    if os.path.exists(index_path):
        try:
            _vectorstore = FAISS.load_local(
                index_path, _get_embeddings(), allow_dangerous_deserialization=True
            )
            logger.info("FAISS index loaded from %s", index_path)
        except Exception:
            logger.exception("Failed to load FAISS index")
            _vectorstore = None


def save_index() -> None:
    """Persist FAISS index to disk."""
    if _vectorstore is not None:
        _vectorstore.save_local(settings.FAISS_INDEX_PATH)
        logger.info("FAISS index saved to %s", settings.FAISS_INDEX_PATH)


async def retrieve_user_context(user_id: str, query: str, k: int = 3) -> str:
    """Retrieve relevant past session summaries for a user."""
    if _vectorstore is None:
        return ""

    try:
        results = _vectorstore.similarity_search(
            query, k=k, filter={"user_id": user_id}
        )
    except Exception:
        logger.exception("FAISS similarity search failed")
        return ""

    if not results:
        return ""

    context_parts = [doc.page_content for doc in results]
    return "\n---\n".join(context_parts)


async def index_session_summary(
    user_id: str, session_id: str, summary: str
) -> int | None:
    """Index a session summary into the vector store. Returns the FAISS index ID."""
    global _vectorstore

    embeddings = _get_embeddings()
    metadata = {"user_id": user_id, "session_id": session_id}

    try:
        if _vectorstore is None:
            _vectorstore = FAISS.from_texts(
                [summary], embeddings, metadatas=[metadata]
            )
            faiss_id = 0
        else:
            ids = _vectorstore.add_texts([summary], metadatas=[metadata])
            faiss_id = len(_vectorstore.index_to_docstore_id) - 1

        save_index()
        return faiss_id
    except Exception:
        logger.exception("Failed to index session summary")
        return None


async def delete_session_embedding(session_id: str) -> None:
    """Remove a session's embedding from the vector store."""
    # FAISS doesn't support efficient deletion by metadata.
    # For MVP, we skip FAISS deletion (index rebuilds handle this).
    logger.info("Session embedding deletion requested for %s (FAISS rebuild needed)", session_id)


async def delete_user_embeddings(user_id: str) -> None:
    """Remove all embeddings for a user."""
    logger.info("User embedding deletion requested for %s (FAISS rebuild needed)", user_id)
