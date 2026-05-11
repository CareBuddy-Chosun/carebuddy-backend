import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestUserProfile:
    async def test_get_profile(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/users/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"
        assert data["consent_data_storage"] is False
        assert data["session_count"] == 0
        assert isinstance(data["guardians"], list)

    async def test_update_full_name(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.patch(
            "/api/v1/users/me",
            json={"full_name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    async def test_toggle_consent(self, authenticated_client: AsyncClient):
        # Enable consent
        resp = await authenticated_client.patch(
            "/api/v1/users/me",
            json={"consent_data_storage": True},
        )
        assert resp.status_code == 200
        assert resp.json()["consent_data_storage"] is True

        # Disable consent
        resp = await authenticated_client.patch(
            "/api/v1/users/me",
            json={"consent_data_storage": False},
        )
        assert resp.status_code == 200
        assert resp.json()["consent_data_storage"] is False

    async def test_get_profile_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.get("/api/v1/users/me")
        assert resp.status_code == 403  # HTTPBearer returns 403 when no creds


@pytest.mark.asyncio
class TestDeleteAccount:
    async def test_delete_account_success(self, async_client: AsyncClient):
        # Register a fresh user
        reg = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "delete@example.com",
                "password": "SecurePass1",
                "full_name": "Delete User",
            },
        )
        token = reg.json()["access_token"]
        async_client.headers["Authorization"] = f"Bearer {token}"

        resp = await async_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"password": "SecurePass1"},
        )
        assert resp.status_code == 204

        # Login should fail
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "delete@example.com", "password": "SecurePass1"},
        )
        assert resp.status_code == 401

    async def test_delete_account_wrong_password(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.request(
            "DELETE",
            "/api/v1/users/me",
            json={"password": "WrongPass1"},
        )
        assert resp.status_code == 403
