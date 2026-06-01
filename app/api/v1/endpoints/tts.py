import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.voice.tts import synthesize_speech

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["tts"])

DEFAULT_VOICE = "ko-KR-SunHiNeural"


class TTSRequest(BaseModel):
    text: str
    voice_id: str | None = None
    speed: float | None = None


@router.post("/synthesize")
async def synthesize(
    data: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    voice = data.voice_id or DEFAULT_VOICE
    try:
        audio_bytes = await synthesize_speech(data.text, voice=voice, speed=data.speed)
    except Exception as e:
        logger.error("TTS synthesis failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="음성 합성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        )
    return Response(content=audio_bytes, media_type="audio/mpeg")
