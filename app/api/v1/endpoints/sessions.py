import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.session import (
    ChatMessageRequest,
    ChatRequest,
    ChatResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
)
from app.services.session_service import (
    create_session,
    delete_session,
    get_session_with_messages,
    list_sessions,
    process_message,
)
from app.triage.engine import check_emergency_keywords
from app.voice.stt import transcribe_audio

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_new_session(
    data: SessionCreateRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await create_session(db, current_user, data)
    return session


# SRS canonical endpoint
@router.post("/{session_id}/messages", response_model=ChatResponse)
async def send_message(
    session_id: uuid.UUID,
    data: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_with_messages(db, current_user.id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not active"
        )
    return await process_message(
        db, session, data.content, data.input_type, data.audio_duration_seconds
    )


# Backward-compatible endpoint for Flutter client
@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_with_messages(db, current_user.id, data.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not active"
        )
    return await process_message(
        db, session, data.message, data.input_type, data.audio_duration_seconds
    )


@router.get("", response_model=SessionListResponse)
async def list_user_sessions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    sort: str = Query("started_at_desc"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_sessions(db, current_user.id, page, per_page, sort)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_with_messages(db, current_user.id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return session


@router.post("/{session_id}/audio")
async def upload_session_audio(
    session_id: uuid.UUID,
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload audio for STT transcription within a session context."""
    session = await get_session_with_messages(db, current_user.id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    if audio.content_type not in (
        "audio/webm", "audio/mp4", "audio/mpeg", "audio/wav",
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported audio format",
        )
    audio_bytes = await audio.read()
    result = await transcribe_audio(audio_bytes, filename=audio.filename or "audio.webm")
    matched_keywords = check_emergency_keywords(result.text)
    return {
        "transcription": result.text,
        "confidence": result.confidence,
        "language_detected": result.language,
        "duration_seconds": result.duration_seconds,
        "emergency_keywords_detected": matched_keywords,
    }


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_session(db, current_user.id, session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
