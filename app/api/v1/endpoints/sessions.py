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
from app.models.guardian import Guardian
from app.models.session import Message, Session
from app.models.user import User
from app.schemas.session import (
    ChatResponse,
    MessageRequest,
    SessionResponse,
    TriageResultSchema,
)
from app.schemas.user import NotificationItem, NotifyGuardiansResponse
from app.triage.engine import (
    TriageResult,
    build_triage_messages,
    check_emergency_keywords,
    clean_reply,
    parse_triage_result,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

llm_client = openai.AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
)

TRIAGE_GUIDANCE = {
    TriageResult.EMERGENCY: {
        "explanation": "응급 상황으로 판단됩니다.",
        "next_steps": [
            "즉시 119에 전화하세요.",
            "가까운 응급실로 이동하세요.",
            "보호자에게 알리세요.",
        ],
    },
    TriageResult.VISIT_HOSPITAL: {
        "explanation": "24시간 이내에 병원 방문이 권장됩니다.",
        "next_steps": [
            "가까운 병원이나 의원을 방문하세요.",
            "증상이 악화되면 응급실로 가세요.",
        ],
    },
    TriageResult.HOME_CARE: {
        "explanation": "가정에서 경과를 관찰하셔도 됩니다.",
        "next_steps": [
            "충분한 휴식을 취하세요.",
            "수분을 충분히 섭취하세요.",
            "증상이 지속되거나 악화되면 병원을 방문하세요.",
        ],
    },
}


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
            "의료 응급 상황으로 보입니다. "
            "즉시 119에 전화하거나 가까운 응급실로 가세요. "
            "저는 의료 전문가가 아니며, 이것은 진단이 아닙니다. "
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
        reply = response.choices[0].message.content or ""
        triage_result = parse_triage_result(reply)

    # Strip the machine-readable TRIAGE tag so it never reaches the user / TTS.
    reply = clean_reply(reply)

    # Persist messages
    user_msg = Message(session_id=session.id, role="user", content=data.content)
    assistant_msg = Message(session_id=session.id, role="assistant", content=reply)
    db.add(user_msg)
    db.add(assistant_msg)

    session_complete = False
    triage_schema = None
    if triage_result:
        session.triage_result = triage_result.value
        session_complete = True
        session.ended_at = datetime.now(timezone.utc)
        guidance = TRIAGE_GUIDANCE[triage_result]
        triage_schema = TriageResultSchema(
            level=triage_result.value.upper(),
            explanation=guidance["explanation"],
            next_steps=guidance["next_steps"],
        )

    await db.commit()

    return ChatResponse(
        session_id=session.id,
        message_id=assistant_msg.id,
        reply=reply,
        tts_text=reply,
        triage_result=triage_schema,
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


async def _get_owned_session(
    db: AsyncSession, session_id: uuid.UUID, current_user: User
) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your session"
        )
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, session_id, current_user)
    await db.delete(session)
    await db.commit()


@router.post("/{session_id}/notify-guardians", response_model=NotifyGuardiansResponse)
async def notify_guardians(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_session(db, session_id, current_user)

    guardians_result = await db.execute(
        select(Guardian)
        .where(Guardian.user_id == current_user.id)
        .order_by(Guardian.created_at)
    )
    guardians = guardians_result.scalars().all()

    # No real SMS provider (e.g. Twilio) configured yet -> stub the delivery.
    notifications = [
        NotificationItem(
            guardian_name=guardian.name,
            phone=guardian.phone,
            status="stubbed",
        )
        for guardian in guardians
    ]
    return NotifyGuardiansResponse(notifications=notifications)
