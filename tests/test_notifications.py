from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestGuardianNotification:
    async def _setup_emergency_session(
        self, client: AsyncClient
    ) -> str:
        """Create a session and trigger emergency to get EMERGENCY triage."""
        create_resp = await client.post("/api/v1/sessions")
        session_id = create_resp.json()["id"]

        await client.post(
            f"/api/v1/sessions/{session_id}/messages",
            json={"content": "I have severe chest pain and can't breathe"},
        )
        return session_id

    @patch("app.services.notification_service.send_guardian_sms", new_callable=AsyncMock)
    async def test_notify_guardians_success(
        self, mock_sms, authenticated_client: AsyncClient
    ):
        mock_sms.return_value = True

        # Add a guardian first
        await authenticated_client.post(
            "/api/v1/users/me/guardians",
            json={"name": "Mom", "phone": "+821012345678"},
        )

        session_id = await self._setup_emergency_session(authenticated_client)

        resp = await authenticated_client.post(
            f"/api/v1/sessions/{session_id}/notify-guardians"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["notifications"]) == 1

    async def test_notify_non_emergency_fails(
        self, authenticated_client: AsyncClient
    ):
        # Create a normal session (no messages = still active, no triage)
        create_resp = await authenticated_client.post("/api/v1/sessions")
        session_id = create_resp.json()["id"]

        resp = await authenticated_client.post(
            f"/api/v1/sessions/{session_id}/notify-guardians"
        )
        assert resp.status_code == 400

    async def test_notify_no_guardians(self, authenticated_client: AsyncClient):
        session_id = await self._setup_emergency_session(authenticated_client)

        resp = await authenticated_client.post(
            f"/api/v1/sessions/{session_id}/notify-guardians"
        )
        assert resp.status_code == 400
        assert "No guardians" in resp.json()["detail"]

    async def test_notify_nonexistent_session(self, authenticated_client: AsyncClient):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await authenticated_client.post(
            f"/api/v1/sessions/{fake_id}/notify-guardians"
        )
        assert resp.status_code == 404
