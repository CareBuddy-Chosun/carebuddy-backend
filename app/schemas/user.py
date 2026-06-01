import uuid
from datetime import date, datetime

from pydantic import BaseModel


class GuardianResponse(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    relationship: str | None = None


class GuardianCreateRequest(BaseModel):
    name: str
    phone: str
    relationship: str | None = None


class GuardianUpdateRequest(BaseModel):
    name: str
    phone: str
    relationship: str | None = None


class UserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    date_of_birth: date | None = None
    consent_data_storage: bool = False
    guardians: list[GuardianResponse] = []
    created_at: datetime
    session_count: int = 0


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    consent_data_storage: bool | None = None


class NotificationItem(BaseModel):
    guardian_name: str
    phone: str
    status: str


class NotifyGuardiansResponse(BaseModel):
    notifications: list[NotificationItem] = []
