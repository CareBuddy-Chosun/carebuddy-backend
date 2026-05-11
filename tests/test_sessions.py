from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

SESSIONS_URL = "/api/v1/sessions"


@pytest.mark.asyncio
class TestSessionCreate:
    async def test_create_session(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(SESSIONS_URL)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "active"
        assert "id" in data

    async def test_create_session_with_location(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            SESSIONS_URL,
            json={"location": {"latitude": 37.5665, "longitude": 126.978}},
        )
        assert resp.status_code == 201


@pytest.mark.asyncio
class TestSessionList:
    async def test_list_sessions_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(SESSIONS_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["pagination"]["total_count"] == 0

    async def test_list_sessions_with_data(self, authenticated_client: AsyncClient):
        # Create 3 sessions
        for _ in range(3):
            await authenticated_client.post(SESSIONS_URL)

        resp = await authenticated_client.get(SESSIONS_URL)
        data = resp.json()
        assert len(data["sessions"]) == 3
        assert data["pagination"]["total_count"] == 3

    async def test_list_sessions_pagination(self, authenticated_client: AsyncClient):
        for _ in range(5):
            await authenticated_client.post(SESSIONS_URL)

        resp = await authenticated_client.get(f"{SESSIONS_URL}?page=1&per_page=2")
        data = resp.json()
        assert len(data["sessions"]) == 2
        assert data["pagination"]["total_pages"] == 3


@pytest.mark.asyncio
class TestSessionGet:
    async def test_get_session(self, authenticated_client: AsyncClient):
        create_resp = await authenticated_client.post(SESSIONS_URL)
        session_id = create_resp.json()["id"]

        resp = await authenticated_client.get(f"{SESSIONS_URL}/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == session_id

    async def test_get_nonexistent_session(self, authenticated_client: AsyncClient):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await authenticated_client.get(f"{SESSIONS_URL}/{fake_id}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestSessionDelete:
    async def test_delete_session(self, authenticated_client: AsyncClient):
        create_resp = await authenticated_client.post(SESSIONS_URL)
        session_id = create_resp.json()["id"]

        resp = await authenticated_client.delete(f"{SESSIONS_URL}/{session_id}")
        assert resp.status_code == 204

        # Should be gone
        resp = await authenticated_client.get(f"{SESSIONS_URL}/{session_id}")
        assert resp.status_code == 404

    async def test_delete_nonexistent_session(self, authenticated_client: AsyncClient):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await authenticated_client.delete(f"{SESSIONS_URL}/{fake_id}")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestSendMessage:
    @patch("app.services.session_service.llm_client")
    @patch("app.services.session_service.retrieve_user_context", new_callable=AsyncMock)
    async def test_send_message_normal(
        self, mock_rag, mock_llm, authenticated_client: AsyncClient
    ):
        mock_rag.return_value = ""
        # Mock LLM response (no triage)
        mock_choice = AsyncMock()
        mock_choice.message.content = "Can you tell me more about your headache?"
        mock_response = AsyncMock()
        mock_response.choices = [mock_choice]
        mock_llm.chat.completions.create = AsyncMock(return_value=mock_response)

        # Create session
        create_resp = await authenticated_client.post(SESSIONS_URL)
        session_id = create_resp.json()["id"]

        # Send message via SRS canonical endpoint
        resp = await authenticated_client.post(
            f"{SESSIONS_URL}/{session_id}/messages",
            json={"content": "I have a headache"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] is not None
        assert data["session_complete"] is False

    async def test_send_message_emergency_keywords(
        self, authenticated_client: AsyncClient
    ):
        create_resp = await authenticated_client.post(SESSIONS_URL)
        session_id = create_resp.json()["id"]

        resp = await authenticated_client.post(
            f"{SESSIONS_URL}/{session_id}/messages",
            json={"content": "I have severe chest pain and can't breathe"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_emergency"] is True
        assert data["session_complete"] is True
        assert data["triage_result"]["level"] == "EMERGENCY"

    async def test_send_message_to_nonexistent_session(
        self, authenticated_client: AsyncClient
    ):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await authenticated_client.post(
            f"{SESSIONS_URL}/{fake_id}/messages",
            json={"content": "hello"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestBackwardCompatChat:
    async def test_chat_endpoint_emergency(self, authenticated_client: AsyncClient):
        create_resp = await authenticated_client.post(SESSIONS_URL)
        session_id = create_resp.json()["id"]

        resp = await authenticated_client.post(
            f"{SESSIONS_URL}/chat",
            json={
                "session_id": session_id,
                "message": "I'm having a heart attack",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_emergency"] is True
