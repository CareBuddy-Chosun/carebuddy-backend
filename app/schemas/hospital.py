from pydantic import BaseModel


class HospitalResponse(BaseModel):
    place_id: str
    name: str
    address: str
    distance_km: float
    phone: str | None
    specialty: str | None
    maps_url: str
