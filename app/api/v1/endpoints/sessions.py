import uuid
from datetime import datetime, timezone

import openai
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.session import Message, Session
from app.models.user import User
from app.schemas.session import ChatResponse, MessageRequest, SessionResponse
from app.triage.engine import (
    TriageResult,
    build_triage_messages,
    check_emergency_keywords,
    parse_triage_result,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

llm_client = openai.AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
)


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = Session(user_id=current_user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse(
        id=session.id,
        status="active",
        started_at=session.created_at,
        messages=[],
    )


@router.post("/{session_id}/messages", response_model=ChatResponse)
async def send_message(
    session_id: uuid.UUID,
    data: MessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id, Session.user_id == current_user.id)
        .options(selectinload(Session.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Emergency keyword check
    is_emergency = check_emergency_keywords(data.content)
    if is_emergency:
        reply = (
            "This sounds like a medical emergency. "
            "Please call 119 or go to the nearest emergency room immediately. "
            "I am not a medical professional. This is not a diagnosis. "
            "TRIAGE: EMERGENCY"
        )
        triage_result = TriageResult.EMERGENCY
    else:
        history = [
            {"role": msg.role, "content": msg.content} for msg in session.messages
        ]
        messages = build_triage_messages(history, data.content)
        response = await llm_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            max_tokens=300,
            temperature=0.3,
        )
        reply = response.choices[0].message.content
        triage_result = parse_triage_result(reply)

    # Persist messages
    user_msg = Message(session_id=session.id, role="user", content=data.content)
    assistant_msg = Message(session_id=session.id, role="assistant", content=reply)
    db.add(user_msg)
    db.add(assistant_msg)

    session_complete = False
    triage_dict = None
    if triage_result:
        session.triage_result = triage_result.value
        session_complete = True
        session.ended_at = datetime.now(timezone.utc)
        triage_dict = {
            "level": triage_result.value.upper(),
            "explanation": None,
            "next_steps": [],
            "disclaimer": (
                "This is not a medical diagnosis. CareBuddy is a triage "
                "assistance tool only. Always consult a qualified healthcare "
                "professional for medical advice."
            ),
        }

    await db.commit()

    return ChatResponse(
        session_id=session.id,
        message_id=assistant_msg.id,
        reply=reply,
        tts_text=reply,
        triage_result=triage_dict,
        is_emergency=triage_result == TriageResult.EMERGENCY,
        session_complete=session_complete,
        timestamp=assistant_msg.created_at.isoformat() if assistant_msg.created_at else None,
    )


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session)
        .where(Session.user_id == current_user.id)
        .options(selectinload(Session.messages))
        .order_by(Session.created_at.desc())
    )
    sessions = result.scalars().all()
    return [
        SessionResponse(
            id=s.id,
            status="completed" if s.ended_at else "active",
            triage_level=s.triage_result.upper() if s.triage_result else None,
            summary=s.summary,
            started_at=s.created_at,
            completed_at=s.ended_at,
            messages=[],
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id, Session.user_id == current_user.id)
        .options(selectinload(Session.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return SessionResponse(
        id=session.id,
        status="completed" if session.ended_at else "active",
        triage_level=session.triage_result.upper() if session.triage_result else None,
        summary=session.summary,
        started_at=session.created_at,
        completed_at=session.ended_at,
        messages=[],
    )
