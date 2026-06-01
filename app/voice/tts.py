import io

import edge_tts


async def synthesize_speech(
    text: str, voice: str = "ko-KR-SunHiNeural", speed: float | None = None
) -> bytes:
    """Convert text to speech using Microsoft Edge TTS (free).

    Available Korean voices:
      - ko-KR-SunHiNeural  (female, default)
      - ko-KR-InJoonNeural (male)
    English voices:
      - en-US-JennyNeural   (female)
      - en-US-GuyNeural     (male)

    `speed` is a multiplier (1.0 = normal). It is mapped to edge-tts's
    percentage `rate` (e.g. 1.2 -> "+20%", 0.8 -> "-20%").
    """
    kwargs = {}
    if speed is not None and speed > 0 and speed != 1.0:
        percent = round((speed - 1.0) * 100)
        kwargs["rate"] = f"{percent:+d}%"

    communicate = edge_tts.Communicate(text, voice, **kwargs)
    audio_buffer = io.BytesIO()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])

    return audio_buffer.getvalue()
