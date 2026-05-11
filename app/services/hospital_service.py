import math
import random

import httpx

from app.core.config import settings
from app.schemas.hospital import HospitalResponse

PLACES_API_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


# ── Mock data for testing without API key ────────────────────────────────────

_MOCK_HOSPITALS = [
    {
        "name": "Seoul National University Hospital",
        "address": "101 Daehak-ro, Jongno-gu, Seoul",
        "phone": "+82-2-2072-2114",
        "has_er": True,
        "specialties": ["Emergency", "Internal Medicine", "Surgery"],
        "hours": "Open 24h",
    },
    {
        "name": "Severance Hospital",
        "address": "50-1 Yonsei-ro, Seodaemun-gu, Seoul",
        "phone": "+82-2-2228-5800",
        "has_er": True,
        "specialties": ["Emergency", "Cardiology", "Neurology"],
        "hours": "Open 24h",
    },
    {
        "name": "Samsung Medical Center",
        "address": "81 Irwon-ro, Gangnam-gu, Seoul",
        "phone": "+82-2-3410-2114",
        "has_er": True,
        "specialties": ["Emergency", "Oncology", "Orthopedics"],
        "hours": "Open 24h",
    },
    {
        "name": "Asan Medical Center",
        "address": "88 Olympic-ro 43-gil, Songpa-gu, Seoul",
        "phone": "+82-2-3010-3114",
        "has_er": True,
        "specialties": ["Emergency", "Transplant", "Pediatrics"],
        "hours": "Open 24h",
    },
    {
        "name": "Gangnam Good Morning Clinic",
        "address": "423 Teheran-ro, Gangnam-gu, Seoul",
        "phone": "+82-2-555-1234",
        "has_er": False,
        "specialties": ["Family Medicine", "ENT"],
        "hours": "Mon-Fri 9AM-6PM",
    },
    {
        "name": "Jongno Public Health Center",
        "address": "19 Samil-daero 30-gil, Jongno-gu, Seoul",
        "phone": "+82-2-731-8200",
        "has_er": False,
        "specialties": ["General Practice", "Vaccination"],
        "hours": "Mon-Fri 9AM-6PM",
    },
]


def _generate_mock_hospitals(
    lat: float, lng: float, triage_level: str, limit: int
) -> list[HospitalResponse]:
    """Return realistic mock hospital data near the given coordinates."""
    results = []
    for i, h in enumerate(_MOCK_HOSPITALS):
        if triage_level == "EMERGENCY" and not h["has_er"]:
            continue
        # Scatter hospitals around the user's location
        offset_lat = random.uniform(-0.02, 0.02)
        offset_lng = random.uniform(-0.02, 0.02)
        h_lat = lat + offset_lat
        h_lng = lng + offset_lng
        distance = _haversine(lat, lng, h_lat, h_lng)

        results.append(
            HospitalResponse(
                place_id=f"mock_place_{i}",
                name=h["name"],
                address=h["address"],
                distance_km=round(distance, 2),
                phone=h["phone"],
                has_emergency_room=h["has_er"],
                specialties=h["specialties"],
                operating_hours=h["hours"],
                latitude=round(h_lat, 6),
                longitude=round(h_lng, 6),
                maps_url=f"https://www.google.com/maps/search/{h['name'].replace(' ', '+')}",
            )
        )

    results.sort(key=lambda r: r.distance_km)
    return results[:limit]


# ── Main entry point ─────────────────────────────────────────────────────────

async def find_nearby_hospitals(
    lat: float,
    lng: float,
    radius_km: float = 10.0,
    triage_level: str = "VISIT_HOSPITAL",
    limit: int = 5,
) -> list[HospitalResponse]:
    # Use mock data when no Google Maps API key is configured
    if not settings.GOOGLE_MAPS_API_KEY or settings.GOOGLE_MAPS_API_KEY.startswith("your-"):
        return _generate_mock_hospitals(lat, lng, triage_level, limit)

    radius_m = int(radius_km * 1000)

    params = {
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "type": "hospital",
        "key": settings.GOOGLE_MAPS_API_KEY,
    }
    if triage_level == "EMERGENCY":
        params["keyword"] = "emergency"

    async with httpx.AsyncClient() as client:
        response = await client.get(PLACES_API_URL, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

    hospitals = []
    for place in data.get("results", []):
        location = place["geometry"]["location"]
        distance_km = _haversine(lat, lng, location["lat"], location["lng"])
        place_types = place.get("types", [])
        has_er = "emergency" in " ".join(place_types).lower()

        hours_text = None
        opening_hours = place.get("opening_hours")
        if opening_hours:
            hours_text = "Open now" if opening_hours.get("open_now") else "Closed"

        hospitals.append(
            HospitalResponse(
                place_id=place["place_id"],
                name=place["name"],
                address=place.get("vicinity", ""),
                distance_km=round(distance_km, 2),
                phone=place.get("formatted_phone_number"),
                has_emergency_room=has_er,
                specialties=[],
                operating_hours=hours_text,
                latitude=location["lat"],
                longitude=location["lng"],
                maps_url=f"https://www.google.com/maps/place/?q=place_id:{place['place_id']}",
            )
        )

    hospitals.sort(key=lambda h: h.distance_km)
    return hospitals[:limit]


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(d_lng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
