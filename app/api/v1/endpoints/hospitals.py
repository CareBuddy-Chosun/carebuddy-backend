from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.hospital import HospitalResponse
from app.services.hospital_service import find_nearby_hospitals

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("", response_model=list[HospitalResponse])
async def nearby_hospitals(
    lat: float = Query(..., description="User latitude"),
    lng: float = Query(..., description="User longitude"),
    radius_m: int = Query(5000, ge=500, le=20000, description="Search radius in meters"),
    current_user: User = Depends(get_current_user),
):
    return await find_nearby_hospitals(lat, lng, radius_m)
