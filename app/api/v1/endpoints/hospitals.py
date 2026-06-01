from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.hospital import HospitalSearchResponse, UserLocation
from app.services.hospital_service import find_nearby_hospitals

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("/nearby", response_model=HospitalSearchResponse)
async def nearby_hospitals(
    latitude: float = Query(..., description="User latitude"),
    longitude: float = Query(..., description="User longitude"),
    radius_km: float = Query(10, gt=0, le=50, description="Search radius in km"),
    limit: int = Query(5, ge=1, le=10, description="Max results"),
    triage_level: str | None = Query(None, description="Triage level (e.g. EMERGENCY)"),
    department: str | None = Query(
        None, description="Recommended Korean department keyword (e.g. 신경과)"
    ),
    current_user: User = Depends(get_current_user),
):
    hospitals = await find_nearby_hospitals(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
        triage_level=triage_level,
        department=department,
    )
    return HospitalSearchResponse(
        hospitals=hospitals,
        search_radius_km=radius_km,
        user_location=UserLocation(latitude=latitude, longitude=longitude),
    )
