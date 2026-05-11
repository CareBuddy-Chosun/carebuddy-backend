import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# --- Message ---


class MessageSchema(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    input_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Triage ---


class TriageResultSchema(BaseModel):
    level: str
    explanation: str | None = None
    next_steps: list[str] = []
    disclaimer: str = (
        "This is not a medical diagnosis. CareBuddy is a triage assistance tool only. "
        "Always consult a qualified healthcare professional for medical advice."
    )
    emergency_keywords_detected: list[str] = []


# --- Session ---


class LocationSchema(BaseModel):
    latitude: float
    longitude: float


class SessionCreateRequest(BaseModel):
    initial_message: str | None = None
    location: LocationSchema | None = None


class SessionResponse(BaseModel):
    id: uuid.UUID
    status: str = "active"
    triage_level: str | None = None
    triage_explanation: str | None = None
    primary_symptom_tag: str | None = None
    summary: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    messages: list[MessageSchema] = []
    context_injected: bool = False

    model_config = {"from_attributes": True}


class SessionSummary(BaseModel):
    id: uuid.UUID
    status: str
    primary_symptom_tag: str | None = None
    triage_level: str | None = None
    started_at: datetime | None = None
    duration_seconds: int | None = None

    model_config = {"from_attributes": True}


class PaginationSchema(BaseModel):
    page: int
    per_page: int
    total_count: int
    total_pages: int


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
    pagination: PaginationSchema


# --- Chat ---


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    message: str
    input_type: str | None = "text"
    audio_duration_seconds: float | None = None


class ChatMessageRequest(BaseModel):
    content: str
    input_type: str | None = "text"
    audio_duration_seconds: float | None = None


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    message_id: uuid.UUID | None = None
    reply: str
    tts_text: str | None = None
    quick_reply_options: list[str] | None = None
    triage_result: TriageResultSchema | None = None
    is_emergency: bool = False
    session_complete: bool = False
    timestamp: datetime | None = None
