import httpx

from app.core.config import settings

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


async def synthesize_speech(
    text: str,
    voice_id: str | None = None,
    speed: float | None = None,
) -> bytes:
    """Convert text to speech using ElevenLabs API."""
    vid = voice_id or settings.ELEVENLABS_VOICE_ID
    url = f"{ELEVENLABS_URL}/{vid}"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    voice_settings = {"stability": 0.5, "similarity_boost": 0.75}
    if speed is not None:
        voice_settings["speed"] = max(0.5, min(2.0, speed))

    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2",
        "voice_settings": voice_settings,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=15.0)
        response.raise_for_status()
        return response.content
