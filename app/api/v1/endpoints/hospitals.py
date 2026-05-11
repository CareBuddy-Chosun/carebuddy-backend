from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.hospital import HospitalResponse, HospitalSearchResponse
from app.services.hospital_service import find_nearby_hospitals

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


# SRS canonical endpoint
@router.get("/nearby", response_model=HospitalSearchResponse)
async def nearby_hospitals_srs(
    latitude: float = Query(...),
    longitude: float = Query(...),
    triage_level: str = Query("VISIT_HOSPITAL"),
    radius_km: float = Query(10.0, ge=0.5, le=50.0),
    limit: int = Query(5, ge=1, le=10),
    current_user: User = Depends(get_current_user),
):
    hospitals = await find_nearby_hospitals(
        latitude, longitude, radius_km, triage_level, limit
    )
    return HospitalSearchResponse(
        hospitals=hospitals,
        search_radius_km=radius_km,
        user_location={"latitude": latitude, "longitude": longitude},
    )


# Backward-compatible endpoint for Flutter client
@router.get("", response_model=list[HospitalResponse])
async def nearby_hospitals_compat(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(5000, ge=500, le=20000),
    current_user: User = Depends(get_current_user),
):
    radius_km = radius_m / 1000
    return await find_nearby_hospitals(lat, lng, radius_km, "VISIT_HOSPITAL", 10)
