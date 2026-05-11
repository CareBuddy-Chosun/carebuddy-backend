import uuid
from datetime import datetime, timezone
from math import ceil

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.llm import get_chat_llm
from app.models.session import Message, Session
from app.models.user import User
from app.schemas.session import (
    ChatMessageRequest,
    ChatResponse,
    PaginationSchema,
    SessionCreateRequest,
    SessionListResponse,
    SessionSummary,
    TriageResultSchema,
)
from app.rag.retriever import retrieve_user_context
from app.utils.sanitize import sanitize_llm_input
from app.triage.engine import (
    DISCLAIMER_TEXT,
    TriageLevel,
    build_triage_messages,
    check_emergency_keywords,
    clean_reply_for_tts,
    extract_quick_reply_options,
    parse_triage_result,
)

_CONTEXT_PREFIX = "Relevant context from past sessions:\n"


def _to_langchain_messages(messages: list[dict]) -> list:
    """Convert OpenAI-style dicts to LangChain message objects."""
    mapping = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
    return [mapping.get(m["role"], HumanMessage)(content=m["content"]) for m in messages]


async def create_session(
    db: AsyncSession, user: User, data: SessionCreateRequest | None = None
) -> Session:
    session = Session(
        user_id=user.id,
        status="active",
        location_lat=data.location.latitude if data and data.location else None,
        location_lng=data.location.longitude if data and data.location else None,
    )
    db.add(session)
    await db.commit()
    # Eager-load messages so SessionResponse serialization works without lazy IO
    result = await db.execute(
        select(Session)
        .where(Session.id == session.id)
        .options(selectinload(Session.messages))
    )
    return result.scalar_one()


async def process_message(
    db: AsyncSession,
    session: Session,
    content: str,
    input_type: str | None = "text",
    audio_duration_seconds: float | None = None,
) -> ChatResponse:
    # Sanitize user input
    content = sanitize_llm_input(content)

    # Emergency keyword check
    matched_keywords = check_emergency_keywords(content)
    is_emergency = len(matched_keywords) > 0

    if is_emergency:
        reply = (
            "This sounds like a medical emergency. "
            "Please call 911 or go to the nearest emergency room immediately. "
            "I am not a medical professional. This is not a diagnosis."
        )
        triage_data = {
            "level": TriageLevel.EMERGENCY.value,
            "explanation": "Emergency keywords detected in your message.",
            "next_steps": ["Call 911 immediately", "Go to the nearest emergency room"],
        }
        quick_reply_options = ["Call 911", "Find nearest hospital", "Notify guardian"]
    else:
        history = [
            {"role": msg.role, "content": msg.content} for msg in session.messages
        ]
        # RAG: inject context on first user message
        if len(history) == 0:
            rag_context = await retrieve_user_context(str(session.user_id), content)
            if rag_context:
                history.insert(0, {
                    "role": "system",
                    "content": _CONTEXT_PREFIX + rag_context,
                })
        messages = build_triage_messages(history, content)
        lc_messages = _to_langchain_messages(messages)
        llm = get_chat_llm()
        response = await llm.ainvoke(lc_messages)
        reply = response.content
        triage_data = parse_triage_result(reply)
        quick_reply_options = extract_quick_reply_options(reply)

    # Persist messages
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=content,
        input_type=input_type,
        audio_duration_seconds=audio_duration_seconds,
    )
    assistant_msg = Message(
        session_id=session.id,
        role="assistant",
        content=reply,
    )
    db.add(user_msg)
    db.add(assistant_msg)

    # Update session if triage result produced
    session_complete = False
    triage_result_schema = None

    if triage_data:
        session.triage_level = triage_data["level"]
        session.triage_explanation = triage_data.get("explanation")
        session.triage_next_steps = triage_data.get("next_steps", [])
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
        if session.started_at:
            started = session.started_at
            completed = session.completed_at
            # Ensure both are tz-aware for subtraction (SQLite may strip tz)
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            session.duration_seconds = int(
                (completed - started).total_seconds()
            )
        session_complete = True

        triage_result_schema = TriageResultSchema(
            level=triage_data["level"],
            explanation=triage_data.get("explanation"),
            next_steps=triage_data.get("next_steps", []),
            disclaimer=DISCLAIMER_TEXT,
            emergency_keywords_detected=matched_keywords,
        )

    if matched_keywords:
        session.emergency_keywords = matched_keywords

    await db.commit()
    await db.refresh(assistant_msg)

    return ChatResponse(
        session_id=session.id,
        message_id=assistant_msg.id,
        reply=reply,
        tts_text=clean_reply_for_tts(reply),
        quick_reply_options=quick_reply_options,
        triage_result=triage_result_schema,
        is_emergency=is_emergency,
        session_complete=session_complete,
        timestamp=assistant_msg.created_at,
    )


async def get_session_with_messages(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> Session | None:
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id, Session.user_id == user_id)
        .options(selectinload(Session.messages))
    )
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    per_page: int = 20,
    sort: str = "started_at_desc",
) -> SessionListResponse:
    # Count total
    count_result = await db.execute(
        select(func.count()).where(Session.user_id == user_id)
    )
    total_count = count_result.scalar()

    # Sort
    order_col = Session.started_at.desc()
    if sort == "started_at_asc":
        order_col = Session.started_at.asc()

    # Query
    offset = (page - 1) * per_page
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(order_col)
        .offset(offset)
        .limit(per_page)
    )
    sessions = result.scalars().all()

    return SessionListResponse(
        sessions=[
            SessionSummary(
                id=s.id,
                status=s.status,
                primary_symptom_tag=s.primary_symptom_tag,
                triage_level=s.triage_level,
                started_at=s.started_at,
                duration_seconds=s.duration_seconds,
            )
            for s in sessions
        ],
        pagination=PaginationSchema(
            page=page,
            per_page=per_page,
            total_count=total_count,
            total_pages=ceil(total_count / per_page) if total_count > 0 else 0,
        ),
    )


async def delete_session(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> bool:
    session = await get_session_with_messages(db, user_id, session_id)
    if not session:
        return False
    await db.delete(session)
    await db.commit()
    return True
