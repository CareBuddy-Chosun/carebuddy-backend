from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSTT:
    @patch("app.api.v1.endpoints.sessions.transcribe_audio", new_callable=AsyncMock)
    async def test_audio_upload(self, mock_stt, authenticated_client: AsyncClient):
        from app.voice.stt import TranscriptionResult

        mock_stt.return_value = TranscriptionResult(
            text="I have a headache",
            confidence=0.95,
            language="en",
            duration_seconds=3.5,
        )

        # Create session
        resp = await authenticated_client.post("/api/v1/sessions")
        session_id = resp.json()["id"]

        # Upload audio
        resp = await authenticated_client.post(
            f"/api/v1/sessions/{session_id}/audio",
            files={"audio": ("test.wav", b"fake-audio-data", "audio/wav")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["transcription"] == "I have a headache"
        assert data["confidence"] == 0.95
        assert data["duration_seconds"] == 3.5
        assert data["emergency_keywords_detected"] == []

    @patch("app.api.v1.endpoints.sessions.transcribe_audio", new_callable=AsyncMock)
    async def test_audio_emergency_detection(
        self, mock_stt, authenticated_client: AsyncClient
    ):
        from app.voice.stt import TranscriptionResult

        mock_stt.return_value = TranscriptionResult(
            text="I can't breathe and have chest pain",
            confidence=0.9,
            language="en",
            duration_seconds=2.0,
        )

        resp = await authenticated_client.post("/api/v1/sessions")
        session_id = resp.json()["id"]

        resp = await authenticated_client.post(
            f"/api/v1/sessions/{session_id}/audio",
            files={"audio": ("test.wav", b"fake-audio", "audio/wav")},
        )
        data = resp.json()
        assert len(data["emergency_keywords_detected"]) > 0

    async def test_audio_unsupported_format(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post("/api/v1/sessions")
        session_id = resp.json()["id"]

        resp = await authenticated_client.post(
            f"/api/v1/sessions/{session_id}/audio",
            files={"audio": ("test.txt", b"not audio", "text/plain")},
        )
        assert resp.status_code == 415


@pytest.mark.asyncio
class TestTTS:
    @patch("app.api.v1.endpoints.voice.synthesize_speech", new_callable=AsyncMock)
    async def test_tts_synthesize(self, mock_tts, authenticated_client: AsyncClient):
        mock_tts.return_value = b"fake-audio-bytes"

        resp = await authenticated_client.post(
            "/api/v1/voice/synthesize",
            json={"text": "Hello, how are you feeling?"},
        )
        assert resp.status_code == 200

    async def test_tts_text_too_long(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/api/v1/voice/synthesize",
            json={"text": "x" * 501},
        )
        assert resp.status_code == 422
