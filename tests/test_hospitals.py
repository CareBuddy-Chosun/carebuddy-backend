from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

GOOGLE_PLACES_RESPONSE = {
    "results": [
        {
            "place_id": "place_1",
            "name": "Seoul Hospital",
            "vicinity": "123 Gangnam-daero",
            "geometry": {"location": {"lat": 37.5, "lng": 127.0}},
            "types": ["hospital", "health"],
            "opening_hours": {"open_now": True},
        },
        {
            "place_id": "place_2",
            "name": "Emergency Center",
            "vicinity": "456 Teheran-ro",
            "geometry": {"location": {"lat": 37.51, "lng": 127.01}},
            "types": ["hospital", "emergency"],
            "opening_hours": {"open_now": True},
        },
    ]
}


def _make_mock_client():
    mock_response = MagicMock()
    mock_response.json.return_value = GOOGLE_PLACES_RESPONSE
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
class TestHospitalSearch:
    @patch("app.services.hospital_service.httpx.AsyncClient")
    async def test_nearby_hospitals_srs(
        self, mock_client_cls, authenticated_client: AsyncClient
    ):
        mock_client_cls.return_value = _make_mock_client()

        resp = await authenticated_client.get(
            "/api/v1/hospitals/nearby",
            params={
                "latitude": 37.5,
                "longitude": 127.0,
                "triage_level": "VISIT_HOSPITAL",
                "radius_km": 5.0,
                "limit": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "hospitals" in data
        assert data["search_radius_km"] == 5.0

    @patch("app.services.hospital_service.httpx.AsyncClient")
    async def test_nearby_hospitals_compat(
        self, mock_client_cls, authenticated_client: AsyncClient
    ):
        mock_client_cls.return_value = _make_mock_client()

        resp = await authenticated_client.get(
            "/api/v1/hospitals",
            params={"lat": 37.5, "lng": 127.0},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @patch("app.services.hospital_service.httpx.AsyncClient")
    async def test_limit_param(
        self, mock_client_cls, authenticated_client: AsyncClient
    ):
        mock_client_cls.return_value = _make_mock_client()

        resp = await authenticated_client.get(
            "/api/v1/hospitals/nearby",
            params={
                "latitude": 37.5,
                "longitude": 127.0,
                "limit": 1,
            },
        )
        data = resp.json()
        assert len(data["hospitals"]) <= 1
