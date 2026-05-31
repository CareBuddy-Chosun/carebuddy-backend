import io

import edge_tts


async def synthesize_speech(text: str, voice: str = "ko-KR-SunHiNeural") -> bytes:
    """Convert text to speech using Microsoft Edge TTS (free).

    Available Korean voices:
      - ko-KR-SunHiNeural  (female, default)
      - ko-KR-InJoonNeural (male)
    English voices:
      - en-US-JennyNeural   (female)
      - en-US-GuyNeural     (male)
    """
    communicate = edge_tts.Communicate(text, voice)
    audio_buffer = io.BytesIO()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])

    return audio_buffer.getvalue()
