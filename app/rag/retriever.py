# RAG pipeline — to be implemented in W6-W7
# Placeholder for LangChain + FAISS integration

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings

_vectorstore: FAISS | None = None


def get_vectorstore() -> FAISS | None:
    return _vectorstore


async def retrieve_user_context(user_id: str, query: str, k: int = 3) -> str:
    """Retrieve relevant past session summaries for a user."""
    if _vectorstore is None:
        return ""

    results = _vectorstore.similarity_search(
        query, k=k, filter={"user_id": user_id}
    )
    if not results:
        return ""

    context_parts = [doc.page_content for doc in results]
    return "\n---\n".join(context_parts)


async def index_session_summary(user_id: str, session_id: str, summary: str) -> None:
    """Index a session summary into the vector store."""
    global _vectorstore

    embeddings = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY)
    metadata = {"user_id": user_id, "session_id": session_id}

    if _vectorstore is None:
        _vectorstore = FAISS.from_texts([summary], embeddings, metadatas=[metadata])
    else:
        _vectorstore.add_texts([summary], metadatas=[metadata])
