import httpx

from app.core.config import settings

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


async def synthesize_speech(text: str) -> bytes:
    """Convert text to speech using ElevenLabs API."""
    url = f"{ELEVENLABS_URL}/{settings.ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=15.0)
        response.raise_for_status()
        return response.content
