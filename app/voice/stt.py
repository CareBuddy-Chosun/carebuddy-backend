"""Provider-agnostic Speech-to-Text.

Switch STT backend by setting STT_PROVIDER in .env:
  - "openai"  → OpenAI Whisper API
  - "google"  → Google Gemini multimodal (audio → text)
"""

import base64
import io
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class TranscriptionResult:
    text: str
    confidence: float | None = None
    language: str = "en"
    duration_seconds: float | None = None


async def transcribe_audio(
    audio_bytes: bytes, filename: str = "audio.webm"
) -> TranscriptionResult:
    """Transcribe audio bytes to text using the configured STT provider."""
    provider = settings.STT_PROVIDER.lower()

    if provider == "openai":
        return await _transcribe_openai(audio_bytes, filename)
    if provider == "google":
        return await _transcribe_google(audio_bytes, filename)

    raise ValueError(f"Unsupported STT_PROVIDER: {provider}")


async def _transcribe_openai(audio_bytes: bytes, filename: str) -> TranscriptionResult:
    """OpenAI Whisper STT."""
    import openai

    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename

    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="en",
        response_format="verbose_json",
    )

    return TranscriptionResult(
        text=transcript.text,
        language=getattr(transcript, "language", "en"),
        duration_seconds=getattr(transcript, "duration", None),
    )


async def _transcribe_google(audio_bytes: bytes, filename: str) -> TranscriptionResult:
    """Google Gemini multimodal audio transcription."""
    from google import genai

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    # Determine MIME type from filename extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    mime_map = {
        "webm": "audio/webm",
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "m4a": "audio/mp4",
    }
    mime_type = mime_map.get(ext, "audio/webm")

    audio_part = {
        "inline_data": {
            "mime_type": mime_type,
            "data": base64.b64encode(audio_bytes).decode(),
        }
    }

    response = await client.aio.models.generate_content(
        model=settings.LLM_MODEL or "gemini-2.0-flash",
        contents=[
            audio_part,
            "Transcribe this audio to text. Return only the transcription, nothing else.",
        ],
    )

    return TranscriptionResult(
        text=response.text.strip(),
        language="en",
    )
