import pytest
from httpx import AsyncClient


GUARDIAN_URL = "/api/v1/users/me/guardians"


@pytest.mark.asyncio
class TestGuardianCRUD:
    async def test_create_guardian(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            GUARDIAN_URL,
            json={
                "name": "Mom",
                "phone": "+821012345678",
                "relationship": "Mother",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Mom"
        assert data["phone"] == "+821012345678"
        assert data["relationship"] == "Mother"
        assert "id" in data

    async def test_update_guardian(self, authenticated_client: AsyncClient):
        # Create
        create_resp = await authenticated_client.post(
            GUARDIAN_URL,
            json={"name": "Dad", "phone": "+821099999999"},
        )
        guardian_id = create_resp.json()["id"]

        # Update
        resp = await authenticated_client.patch(
            f"{GUARDIAN_URL}/{guardian_id}",
            json={"name": "Father", "phone": "+821088888888"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Father"

    async def test_delete_guardian(self, authenticated_client: AsyncClient):
        create_resp = await authenticated_client.post(
            GUARDIAN_URL,
            json={"name": "Sis", "phone": "+821077777777"},
        )
        guardian_id = create_resp.json()["id"]

        resp = await authenticated_client.delete(f"{GUARDIAN_URL}/{guardian_id}")
        assert resp.status_code == 204

    async def test_delete_nonexistent_guardian(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.delete(
            f"{GUARDIAN_URL}/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_invalid_phone_format(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            GUARDIAN_URL,
            json={"name": "X", "phone": "not-a-phone"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestGuardianLimit:
    async def test_max_two_guardians(self, authenticated_client: AsyncClient):
        # Create first guardian
        resp1 = await authenticated_client.post(
            GUARDIAN_URL,
            json={"name": "G1", "phone": "+821011111111"},
        )
        assert resp1.status_code == 201

        # Create second guardian
        resp2 = await authenticated_client.post(
            GUARDIAN_URL,
            json={"name": "G2", "phone": "+821022222222"},
        )
        assert resp2.status_code == 201

        # Third should fail
        resp3 = await authenticated_client.post(
            GUARDIAN_URL,
            json={"name": "G3", "phone": "+821033333333"},
        )
        assert resp3.status_code == 400
        assert "Maximum" in resp3.json()["detail"]
