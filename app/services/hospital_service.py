import httpx

from app.core.config import settings
from app.schemas.hospital import HospitalResponse

PLACES_API_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


async def find_nearby_hospitals(
    lat: float, lng: float, radius_m: int = 5000
) -> list[HospitalResponse]:
    params = {
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "type": "hospital",
        "key": settings.GOOGLE_MAPS_API_KEY,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(PLACES_API_URL, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

    hospitals = []
    for place in data.get("results", [])[:10]:
        location = place["geometry"]["location"]
        distance_km = _haversine(lat, lng, location["lat"], location["lng"])
        hospitals.append(
            HospitalResponse(
                place_id=place["place_id"],
                name=place["name"],
                address=place.get("vicinity", ""),
                distance_km=round(distance_km, 2),
                phone=place.get("formatted_phone_number"),
                specialty=None,
                maps_url=f"https://www.google.com/maps/place/?q=place_id:{place['place_id']}",
            )
        )

    return sorted(hospitals, key=lambda h: h.distance_km)


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math

    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(d_lng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
