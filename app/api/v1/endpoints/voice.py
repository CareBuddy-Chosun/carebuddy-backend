from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models.user import User
from app.voice.stt import transcribe_audio
from app.voice.tts import synthesize_speech

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
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


@router.post("/synthesize")
async def synthesize(
    data: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    audio_bytes = await synthesize_speech(data.text)
    return Response(content=audio_bytes, media_type="audio/mpeg")
