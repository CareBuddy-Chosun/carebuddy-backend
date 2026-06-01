import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.voice.tts import synthesize_speech

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Transcribe audio to text.

    NOTE: Requires a valid OpenAI API key (Ollama does not support Whisper).
    The mobile app uses on-device STT instead of this endpoint.
    """
    if settings.OPENAI_BASE_URL and "localhost" in settings.OPENAI_BASE_URL:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="서버 STT는 현재 지원되지 않습니다. 모바일 앱의 온디바이스 STT를 사용해 주세요.",
        )

    from app.voice.stt import transcribe_audio

    if audio.content_type not in ("audio/webm", "audio/mp4", "audio/mpeg", "audio/wav"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported audio format",
        )
    audio_bytes = await audio.read()
    text = await transcribe_audio(audio_bytes, filename=audio.filename or "audio.webm")
    return {"text": text}


class TTSRequest(BaseModel):
    text: str
    voice: str = "ko-KR-SunHiNeural"


@router.post("/synthesize")
async def synthesize(
    data: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        audio_bytes = await synthesize_speech(data.text, voice=data.voice)
    except Exception as e:
        logger.error("TTS synthesis failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="음성 합성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        )
    return Response(content=audio_bytes, media_type="audio/mpeg")
