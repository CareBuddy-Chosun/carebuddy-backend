from pydantic import BaseModel


class HospitalResponse(BaseModel):
    place_id: str
    name: str
    address: str
    distance_km: float
    phone: str | None = None
    has_emergency_room: bool = False
    specialties: list[str] = []
    operating_hours: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    maps_url: str


class HospitalSearchResponse(BaseModel):
    hospitals: list[HospitalResponse]
    search_radius_km: float
    user_location: dict
