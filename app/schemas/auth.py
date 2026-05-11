import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    date_of_birth: date | None = None
    consent_data_storage: bool = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID | None = None
    expires_in: int = 900


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


# --- User Profile ---


class GuardianSchema(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    relationship: str | None = None

    model_config = {"from_attributes": True}


class GuardianCreate(BaseModel):
    name: str
    phone: str
    relationship: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^\+?[1-9]\d{1,14}$", v):
            raise ValueError("Phone must be in E.164 format (e.g. +821012345678)")
        return v


class UserProfileResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    date_of_birth: date | None = None
    consent_data_storage: bool
    guardians: list[GuardianSchema] = []
    created_at: datetime
    session_count: int = 0

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    consent_data_storage: bool | None = None


class DeleteAccountRequest(BaseModel):
    password: str
