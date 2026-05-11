from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, field_validator

from app.api.deps import get_current_user
from app.models.user import User
from app.voice.stt import transcribe_audio
from app.voice.tts import synthesize_speech

router = APIRouter(tags=["voice"])


# --- STT ---


@router.post("/voice/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if audio.content_type not in (
        "audio/webm", "audio/mp4", "audio/mpeg", "audio/wav",
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported audio format",
        )
    audio_bytes = await audio.read()
    result = await transcribe_audio(audio_bytes, filename=audio.filename or "audio.webm")
    return {
        "text": result.text,
        "confidence": result.confidence,
        "language_detected": result.language,
        "duration_seconds": result.duration_seconds,
    }


# --- TTS ---


class TTSRequest(BaseModel):
    text: str
    voice_id: str | None = None
    speed: float | None = None

    @field_validator("text")
    @classmethod
    def validate_text_length(cls, v: str) -> str:
        if len(v) > 500:
            raise ValueError("Text must not exceed 500 characters")
        return v


@router.post("/voice/synthesize")
async def synthesize_voice(
    data: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    audio_bytes = await synthesize_speech(data.text, data.voice_id, data.speed)
    return Response(content=audio_bytes, media_type="audio/mpeg")


# SRS canonical path
@router.post("/tts/synthesize")
async def synthesize_tts(
    data: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    audio_bytes = await synthesize_speech(data.text, data.voice_id, data.speed)
    return Response(content=audio_bytes, media_type="audio/mpeg")
