import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "SecurePass1",
                "full_name": "New User",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] is not None
        assert data["expires_in"] == 900

    async def test_register_duplicate_email(self, async_client: AsyncClient):
        payload = {
            "email": "dup@example.com",
            "password": "SecurePass1",
            "full_name": "Dup User",
        }
        await async_client.post("/api/v1/auth/register", json=payload)
        resp = await async_client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_register_weak_password_short(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={"email": "a@b.com", "password": "Ab1", "full_name": "X"},
        )
        assert resp.status_code == 422

    async def test_register_weak_password_no_uppercase(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={"email": "a@b.com", "password": "lowercase1", "full_name": "X"},
        )
        assert resp.status_code == 422

    async def test_register_weak_password_no_digit(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={"email": "a@b.com", "password": "NoDigitHere", "full_name": "X"},
        )
        assert resp.status_code == 422

    async def test_register_with_consent(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "consent@example.com",
                "password": "SecurePass1",
                "full_name": "Consent User",
                "consent_data_storage": True,
            },
        )
        assert resp.status_code == 201


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, async_client: AsyncClient):
        await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "SecurePass1",
                "full_name": "Login User",
            },
        )
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "SecurePass1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user_id"] is not None

    async def test_login_invalid_password(self, async_client: AsyncClient):
        await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "loginfail@example.com",
                "password": "SecurePass1",
                "full_name": "Fail User",
            },
        )
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "loginfail@example.com", "password": "WrongPass1"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "Whatever1"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestRefreshToken:
    async def test_refresh_rotates_token(self, async_client: AsyncClient):
        reg = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@example.com",
                "password": "SecurePass1",
                "full_name": "Refresh User",
            },
        )
        refresh_token = reg.json()["refresh_token"]

        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["refresh_token"] != refresh_token  # rotated

    async def test_refresh_old_token_revoked(self, async_client: AsyncClient):
        reg = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "revoke@example.com",
                "password": "SecurePass1",
                "full_name": "Revoke User",
            },
        )
        old_token = reg.json()["refresh_token"]

        # Use the token once (rotates it)
        await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_token},
        )

        # Try using the old token again — should fail
        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_token},
        )
        assert resp.status_code == 401

    async def test_refresh_invalid_token(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestLogout:
    async def test_logout_revokes_refresh(self, async_client: AsyncClient):
        reg = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "logout@example.com",
                "password": "SecurePass1",
                "full_name": "Logout User",
            },
        )
        tokens = reg.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        async_client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await async_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 204

        # Refresh should fail after logout
        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 401
