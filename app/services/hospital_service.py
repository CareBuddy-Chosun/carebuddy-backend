"""Hospital search backed by the Naver Local Search API.

LIMITATION: Naver Local Search is keyword-based, NOT coordinate/radius filtered —
results are ranked by Naver relevance, then we sort by distance client-side. True
GPS-radius filtering is not supported by this API. The `radius_km` argument is only
used to populate the response metadata, not to filter results at the source.

LOCATION-AWARENESS: we reverse-geocode the caller's GPS coords to an administrative
region (dong/eup/myeon level) via the Naver Cloud Platform (NCP) Maps reverse
geocoding API and prepend that region to the search keyword (e.g. "역삼동 병원"),
which biases the keyword-based Local Search toward the user's locale. This requires
NCP Maps keys (NAVER_MAPS_KEY_ID / NAVER_MAPS_KEY) — note these are SEPARATE from the
Naver Developers Local Search credentials (NAVER_CLIENT_ID / NAVER_CLIENT_SECRET).
Without the NCP keys, search degrades gracefully to a plain nationwide keyword search.
"""

import math
import re

import httpx

from app.core.config import settings
from app.schemas.hospital import HospitalResponse

NAVER_LOCAL_API_URL = "https://openapi.naver.com/v1/search/local.json"

# NCP Maps reverse geocoding (administrative region lookup from GPS coords).
# NOTE: NCP migrated Maps APIs to the maps.apigw.ntruss.com host; the old
# naveropenapi.apigw.ntruss.com host returns 401 "subscription required".
NCP_REVERSE_GEOCODE_URL = (
    "https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc"
)

# Naver Local Search caps `display` at 5.
NAVER_MAX_DISPLAY = 5

_B_TAG_RE = re.compile(r"</?b>")


async def find_nearby_hospitals(
    latitude: float,
    longitude: float,
    radius_km: float = 10.0,
    limit: int = 5,
    triage_level: str | None = None,
) -> list[HospitalResponse]:
    keyword = "응급실" if (triage_level or "").upper() == "EMERGENCY" else "병원"

    # location-aware: reverse-geocode GPS → region keyword; falls back to plain
    # keyword if NCP keys absent
    region = await reverse_geocode(latitude, longitude)
    query = f"{region} {keyword}" if region else keyword

    params = {
        "query": query,
        "display": NAVER_MAX_DISPLAY,
        "sort": "random",
    }
    headers = {
        "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            NAVER_LOCAL_API_URL, params=params, headers=headers, timeout=10.0
        )
        response.raise_for_status()
        data = response.json()

    hospitals: list[HospitalResponse] = []
    for item in data.get("items", []):
        name = _B_TAG_RE.sub("", item.get("title", "")).strip()
        category = item.get("category", "") or ""
        address = item.get("roadAddress") or item.get("address") or ""
        telephone = item.get("telephone") or None
        link = item.get("link") or ""

        place_lat, place_lng = _naver_to_wgs84(item.get("mapx"), item.get("mapy"))

        if place_lat is not None and place_lng is not None:
            distance_km = round(
                _haversine(latitude, longitude, place_lat, place_lng), 2
            )
        else:
            distance_km = 0.0

        has_emergency_room = "응급" in category or "응급" in name

        hospitals.append(
            HospitalResponse(
                place_id=_place_id(link, address, name),
                name=name,
                address=address,
                distance_km=distance_km,
                phone=telephone,
                has_emergency_room=has_emergency_room,
                specialties=[category] if category else [],
                operating_hours=None,
                latitude=place_lat,
                longitude=place_lng,
                maps_url=link or _naver_map_search_url(name),
            )
        )

    hospitals.sort(key=lambda h: h.distance_km)
    return hospitals[:limit]


async def reverse_geocode(lat: float, lng: float) -> str | None:
    """Reverse-geocode WGS84 coords to an administrative region via NCP Maps.

    Returns a region string biased toward the dong/eup/myeon level (area3) —
    e.g. "역삼동" or "강남구 역삼동". Returns None if the NCP keys are absent or
    the response is empty/unparseable. Never raises.
    """
    if not settings.NAVER_MAPS_KEY_ID or not settings.NAVER_MAPS_KEY:
        return None

    # NCP wants coords as "lng,lat" (x,y order).
    params = {
        "coords": f"{lng},{lat}",
        "output": "json",
        "orders": "admcode,legalcode,addr",
    }
    headers = {
        "X-NCP-APIGW-API-KEY-ID": settings.NAVER_MAPS_KEY_ID,
        "X-NCP-APIGW-API-KEY": settings.NAVER_MAPS_KEY,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                NCP_REVERSE_GEOCODE_URL,
                params=params,
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        for result in data.get("results", []):
            region = result.get("region") or {}
            area2 = ((region.get("area2") or {}).get("name") or "").strip()
            area3 = ((region.get("area3") or {}).get("name") or "").strip()
            if area3:
                return f"{area2} {area3}".strip() if area2 else area3
            if area2:
                return area2
        return None
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


def _naver_to_wgs84(mapx, mapy) -> tuple[float | None, float | None]:
    """Convert Naver local search mapx/mapy to WGS84 (lng, lat) -> (lat, lng).

    Naver local search mapx/mapy are integer strings. We assume WGS84 scaled by
    1e7 (e.g. "1269712017" -> 126.9712017). mapx is longitude, mapy is latitude.

    # TODO: verify coordinate scale against a real Naver response
    """
    try:
        if mapx in (None, "") or mapy in (None, ""):
            return None, None
        lng = int(mapx) / 1e7
        lat = int(mapy) / 1e7
        return lat, lng
    except (ValueError, TypeError):
        return None, None


def _place_id(link: str, address: str, name: str) -> str:
    """Derive a stable id from the item link, falling back to roadAddress+title."""
    if link:
        return re.sub(r"[^a-zA-Z0-9]+", "-", link).strip("-")
    slug = f"{address}-{name}".strip("-")
    return re.sub(r"\s+", "-", slug)


def _naver_map_search_url(name: str) -> str:
    return f"https://map.naver.com/v5/search/{name}"


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(d_lng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
