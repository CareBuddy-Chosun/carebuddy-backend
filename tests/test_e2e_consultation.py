"""End-to-end consultation flow tests."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


SESSIONS_URL = "/api/v1/sessions"


@pytest.mark.asyncio
class TestFullConsultationFlow:
    @patch("app.services.session_service.llm_client")
    @patch("app.services.session_service.retrieve_user_context", new_callable=AsyncMock)
    async def test_multi_turn_conversation(
        self, mock_rag, mock_llm, authenticated_client: AsyncClient
    ):
        """Register → Create session → Multi-turn chat → Triage result."""
        mock_rag.return_value = ""

        # Turn 1: ask follow-up question (no triage yet)
        mock_choice_1 = AsyncMock()
        mock_choice_1.message.content = "Where exactly is the pain?"

        # Turn 2: provide triage
        mock_choice_2 = AsyncMock()
        mock_choice_2.message.content = (
            "Based on your description, this sounds like tension headache.\n"
            "TRIAGE: HOME_CARE\n"
            "EXPLANATION: Mild tension headache without alarming symptoms\n"
            "NEXT_STEPS: Rest, Take OTC pain reliever, Monitor for 48 hours"
        )

        mock_response_1 = AsyncMock()
        mock_response_1.choices = [mock_choice_1]
        mock_response_2 = AsyncMock()
        mock_response_2.choices = [mock_choice_2]

        mock_llm.chat.completions.create = AsyncMock(
            side_effect=[mock_response_1, mock_response_2]
        )

        # Create session
        create_resp = await authenticated_client.post(SESSIONS_URL)
        assert create_resp.status_code == 201
        session_id = create_resp.json()["id"]

        # Turn 1
        resp1 = await authenticated_client.post(
            f"{SESSIONS_URL}/{session_id}/messages",
            json={"content": "I have a headache"},
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["session_complete"] is False
        assert data1["triage_result"] is None

        # Turn 2
        resp2 = await authenticated_client.post(
            f"{SESSIONS_URL}/{session_id}/messages",
            json={"content": "It's at the temples, mild throbbing"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["session_complete"] is True
        assert data2["triage_result"]["level"] == "HOME_CARE"
        assert len(data2["triage_result"]["next_steps"]) == 3

        # Verify session is marked completed
        get_resp = await authenticated_client.get(
            f"{SESSIONS_URL}/{session_id}"
        )
        assert get_resp.json()["status"] == "completed"


@pytest.mark.asyncio
class TestEmergencyFlow:
    async def test_emergency_immediate_triage(
        self, authenticated_client: AsyncClient
    ):
        """Emergency keyword → immediate EMERGENCY triage without LLM call."""
        create_resp = await authenticated_client.post(SESSIONS_URL)
        session_id = create_resp.json()["id"]

        resp = await authenticated_client.post(
            f"{SESSIONS_URL}/{session_id}/messages",
            json={"content": "My father is unconscious and not breathing"},
        )
        data = resp.json()
        assert data["is_emergency"] is True
        assert data["session_complete"] is True
        assert data["triage_result"]["level"] == "EMERGENCY"
        assert "911" in data["reply"]
        assert len(data["triage_result"]["emergency_keywords_detected"]) >= 2

    async def test_completed_session_rejects_messages(
        self, authenticated_client: AsyncClient
    ):
        """After emergency triage, session is completed — no more messages."""
        create_resp = await authenticated_client.post(SESSIONS_URL)
        session_id = create_resp.json()["id"]

        # Trigger emergency
        await authenticated_client.post(
            f"{SESSIONS_URL}/{session_id}/messages",
            json={"content": "chest pain severe"},
        )

        # Try another message
        resp = await authenticated_client.post(
            f"{SESSIONS_URL}/{session_id}/messages",
            json={"content": "can you help more?"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestGDPRFlow:
    async def test_session_deletion(self, authenticated_client: AsyncClient):
        """Create session with messages → delete → verify gone."""
        create_resp = await authenticated_client.post(SESSIONS_URL)
        session_id = create_resp.json()["id"]

        # Add emergency message (auto-completes)
        await authenticated_client.post(
            f"{SESSIONS_URL}/{session_id}/messages",
            json={"content": "chest pain"},
        )

        # Delete
        del_resp = await authenticated_client.delete(
            f"{SESSIONS_URL}/{session_id}"
        )
        assert del_resp.status_code == 204

        # Verify gone
        get_resp = await authenticated_client.get(
            f"{SESSIONS_URL}/{session_id}"
        )
        assert get_resp.status_code == 404

    async def test_account_deletion_cascades(self, async_client: AsyncClient):
        """Register → create session → delete account → verify all data gone."""
        # Register
        reg_resp = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "gdpr@example.com",
                "password": "SecurePass1",
                "full_name": "GDPR User",
            },
        )
        token = reg_resp.json()["access_token"]
        async_client.headers["Authorization"] = f"Bearer {token}"

        # Create session
        await async_client.post(SESSIONS_URL)

        # Delete account
        del_resp = await async_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"password": "SecurePass1"},
        )
        assert del_resp.status_code == 204

        # Cannot login
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "gdpr@example.com", "password": "SecurePass1"},
        )
        assert login_resp.status_code == 401
