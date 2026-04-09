import uuid

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
from app.schemas.session import ChatRequest, ChatResponse, SessionResponse
from app.triage.engine import (
    TriageResult,
    build_triage_messages,
    check_emergency_keywords,
    parse_triage_result,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

llm_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = Session(user_id=current_user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session)
        .where(Session.id == data.session_id, Session.user_id == current_user.id)
        .options(selectinload(Session.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Emergency keyword check
    is_emergency = check_emergency_keywords(data.message)
    if is_emergency:
        reply = (
            "This sounds like a medical emergency. "
            "Please call 911 or go to the nearest emergency room immediately. "
            "I am not a medical professional. This is not a diagnosis. "
            "TRIAGE: EMERGENCY"
        )
        triage_result = TriageResult.EMERGENCY
    else:
        history = [
            {"role": msg.role, "content": msg.content} for msg in session.messages
        ]
        messages = build_triage_messages(history, data.message)
        response = await llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.3,
        )
        reply = response.choices[0].message.content
        triage_result = parse_triage_result(reply)

    # Persist messages
    db.add(Message(session_id=session.id, role="user", content=data.message))
    db.add(Message(session_id=session.id, role="assistant", content=reply))

    if triage_result:
        session.triage_result = triage_result.value

    await db.commit()

    return ChatResponse(
        session_id=session.id,
        reply=reply,
        triage_result=triage_result.value if triage_result else None,
        is_emergency=triage_result == TriageResult.EMERGENCY,
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
    return result.scalars().all()


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
    return session
