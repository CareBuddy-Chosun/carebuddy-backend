import uuid
from datetime import datetime, timezone

import openai
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.guardian import Guardian
from app.models.session import Message, Session
from app.models.user import User
from app.medical.retriever import retrieve_top_condition
from app.schemas.session import (
    ChatResponse,
    MessageRequest,
    MessageSchema,
    SessionResponse,
    TriageResultSchema,
)
from app.schemas.user import NotificationItem, NotifyGuardiansResponse
from app.triage.engine import (
    REQUIRED_SLOTS,
    TriageResult,
    ask_directive,
    assess_conversation,
    build_triage_messages,
    check_emergency_keywords,
    clean_reply,
    closing_directive,
    closing_fallback,
    detect_language,
    fallback_question,
    first_missing_slot,
    format_conversation,
    recommend_care,
    translate_to_english,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

llm_client = openai.AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
)

TRIAGE_GUIDANCE = {
    "ko": {
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
    },
    "en": {
        TriageResult.EMERGENCY: {
            "explanation": "This appears to be an emergency.",
            "next_steps": [
                "Call emergency services (911/119) immediately.",
                "Go to the nearest emergency room.",
                "Notify your guardian.",
            ],
        },
        TriageResult.VISIT_HOSPITAL: {
            "explanation": "A hospital visit within 24 hours is recommended.",
            "next_steps": [
                "Visit a nearby hospital or clinic.",
                "Go to the emergency room if symptoms worsen.",
            ],
        },
        TriageResult.HOME_CARE: {
            "explanation": "You may monitor your condition at home.",
            "next_steps": [
                "Get plenty of rest.",
                "Stay well hydrated.",
                "Visit a hospital if symptoms persist or worsen.",
            ],
        },
    },
}

# Non-diagnostic disclaimer (FR-014) — language-aware.
DISCLAIMER = {
    "ko": (
        "이것은 의료 진단이 아닙니다. CareBuddy는 분류 보조 도구일 뿐입니다. "
        "반드시 전문 의료인의 진료를 받으세요."
    ),
    "en": (
        "This is not a medical diagnosis. CareBuddy is a triage assistance tool "
        "only. Always consult a qualified healthcare professional."
    ),
}

EMERGENCY_REPLY = {
    "ko": (
        "의료 응급 상황으로 보입니다. "
        "즉시 119에 전화하거나 가까운 응급실로 가세요. "
        "저는 의료 전문가가 아니며, 이것은 진단이 아닙니다. "
        "TRIAGE: EMERGENCY"
    ),
    "en": (
        "This appears to be a medical emergency. "
        "Call emergency services (911/119) or go to the nearest emergency room "
        "immediately. I am not a medical professional, and this is not a diagnosis. "
        "TRIAGE: EMERGENCY"
    ),
}


# Safety valve: finalize a triage after this many user turns even if the model
# never self-reports all required slots, so a conversation can't loop forever.
MAX_TURNS_BEFORE_TRIAGE = 8

# Non-diagnostic reference shown with the final triage: the closest matching
# condition from the medical DB (the user opted to show this as reference info).
REFERENCE_INFO = {
    "ko": (
        "참고용 관련 정보: 입력하신 증상은 '{condition}'와(과) 관련이 있을 수 있습니다. "
        "이는 진단이 아니며 참고용입니다. '{department}' 진료가 가능한 가까운 병원을 "
        "찾아보시길 권장합니다."
    ),
    "en": (
        "For reference: your symptoms may be related to '{condition}'. "
        "This is not a diagnosis. Consider visiting a nearby '{department}' clinic."
    ),
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

    # Resolve the reply language: explicit toggle wins, else auto-detect.
    lang = data.language or detect_language(data.content)
    if lang not in ("ko", "en"):
        lang = "ko"

    # Emergency keyword check
    is_emergency = check_emergency_keywords(data.content)
    if is_emergency:
        reply = clean_reply(EMERGENCY_REPLY[lang])
        triage_result = TriageResult.EMERGENCY
    else:
        history = [
            {"role": msg.role, "content": msg.content} for msg in session.messages
        ]

        # 1) Assess what the patient has provided so far (structured pass). This
        #    is reliable about slot completeness; the conversational model is
        #    not. We assess BEFORE replying so the SYSTEM drives the next turn.
        conversation_text = format_conversation(history, data.content)
        assessment = await assess_conversation(
            llm_client, settings.LLM_MODEL, conversation_text
        )
        slots = (
            assessment["slots"]
            if assessment
            else {slot: False for slot in REQUIRED_SLOTS}
        )
        user_turns = sum(1 for m in session.messages if m.role == "user") + 1
        missing = first_missing_slot(slots)
        finalize = missing is None or user_turns >= MAX_TURNS_BEFORE_TRIAGE

        # 2) Drive the reply: ask about the first missing slot, or (when all
        #    slots are filled / cap reached) give a brief close-out. The dialogue
        #    stays in the user's own language so wording is read exactly.
        if finalize:
            triage_result = (assessment or {}).get("triage") or TriageResult.VISIT_HOSPITAL
            directive = closing_directive(lang)
            fallback = closing_fallback(lang)
        else:
            triage_result = None
            directive = ask_directive(lang, missing)
            fallback = fallback_question(lang, missing)

        messages = build_triage_messages(
            history, data.content, language=lang, directive=directive
        )
        response = await llm_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            max_tokens=300,
            temperature=0.3,
        )
        reply = clean_reply(response.choices[0].message.content or "")
        # Never show an empty bubble — fall back to the templated line.
        if not reply:
            reply = fallback

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
        guidance = TRIAGE_GUIDANCE[lang][triage_result]
        explanation = guidance["explanation"]
        recommended_department = None

        # Search the medical DB with the full symptom picture and surface the
        # closest matching condition + a recommended department (non-diagnostic).
        if triage_result != TriageResult.EMERGENCY:
            symptom_texts = [m.content for m in session.messages if m.role == "user"]
            symptom_texts.append(data.content)
            summary = " ".join(symptom_texts).strip()
            summary_en = (
                await translate_to_english(llm_client, settings.LLM_MODEL, summary)
                if lang == "ko"
                else summary
            )
            condition = await retrieve_top_condition(summary_en)
            if condition:
                # Localize the condition name + pick a Korean department to
                # search nearby clinics for.
                care = await recommend_care(
                    llm_client, settings.LLM_MODEL, condition, summary
                )
                if care:
                    recommended_department = care["department"]
                    display_condition = (
                        care["condition_ko"] if lang == "ko" else condition
                    )
                else:
                    display_condition = condition
                explanation = explanation + "\n\n" + REFERENCE_INFO[lang].format(
                    condition=display_condition,
                    department=recommended_department or "",
                )

        triage_schema = TriageResultSchema(
            level=triage_result.value.upper(),
            explanation=explanation,
            next_steps=guidance["next_steps"],
            disclaimer=DISCLAIMER[lang],
            recommended_department=recommended_department,
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


@router.get("")
async def list_sessions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("started_at_desc"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated session summaries: {sessions: [...], pagination: {...}}."""
    base = select(Session).where(Session.user_id == current_user.id)

    total_count = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    order = (
        Session.created_at.asc()
        if sort == "started_at_asc"
        else Session.created_at.desc()
    )
    result = await db.execute(
        base.order_by(order).offset((page - 1) * per_page).limit(per_page)
    )
    sessions = result.scalars().all()

    total_pages = (total_count + per_page - 1) // per_page if total_count else 1

    def _duration(s: Session) -> int | None:
        if s.ended_at and s.created_at:
            return int((s.ended_at - s.created_at).total_seconds())
        return None

    return {
        "sessions": [
            {
                "id": str(s.id),
                "status": "completed" if s.ended_at else "active",
                "primary_symptom_tag": None,
                "triage_level": s.triage_result.upper() if s.triage_result else None,
                "started_at": s.created_at.isoformat() if s.created_at else None,
                "duration_seconds": _duration(s),
            }
            for s in sessions
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    }


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
    ordered = sorted(session.messages, key=lambda m: m.created_at)
    return SessionResponse(
        id=session.id,
        status="completed" if session.ended_at else "active",
        triage_level=session.triage_result.upper() if session.triage_result else None,
        summary=session.summary,
        started_at=session.created_at,
        completed_at=session.ended_at,
        messages=[
            MessageSchema(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in ordered
        ],
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
