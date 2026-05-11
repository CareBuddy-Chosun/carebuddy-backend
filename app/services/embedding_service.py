import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.embedding import Embedding
from app.models.session import Session
from app.rag.retriever import index_session_summary

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_VERSION = "text-embedding-ada-002"


async def generate_session_embedding(session_id: uuid.UUID) -> None:
    """Background task: generate and index embedding for a completed session."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Session)
            .where(Session.id == session_id)
            .options(selectinload(Session.messages))
        )
        session = result.scalar_one_or_none()
        if not session or not session.messages:
            return

        # Build transcript summary
        transcript_parts = []
        for msg in session.messages:
            prefix = "User" if msg.role == "user" else "CareBuddy"
            transcript_parts.append(f"{prefix}: {msg.content}")
        transcript = "\n".join(transcript_parts)

        summary = transcript[:2000]  # Cap for embedding

        faiss_id = await index_session_summary(
            str(session.user_id), str(session.id), summary
        )

        if faiss_id is not None:
            embedding = Embedding(
                session_id=session.id,
                user_id=session.user_id,
                faiss_index_id=faiss_id,
                model_version=EMBEDDING_MODEL_VERSION,
                embedding_text_preview=summary[:200],
            )
            db.add(embedding)
            await db.commit()
            logger.info("Embedding created for session %s", session_id)
