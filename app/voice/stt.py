"""STT module — currently unused.

The mobile app uses on-device STT (Flutter speech_to_text plugin, free).
This server-side endpoint is kept as a placeholder for future web client support.
It requires a valid OpenAI API key with Whisper access to function.
"""

import io

import openai

from app.core.config import settings

client = openai.AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
)


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio bytes to text using OpenAI Whisper.

    NOTE: This requires a valid OpenAI API key (not Ollama).
    Ollama does not support the Whisper transcription API.
    The mobile app uses on-device STT instead.
    """
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename

    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="ko",
    )
    return transcript.text
