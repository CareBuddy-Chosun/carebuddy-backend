import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MessageSchema(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    input_type: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: uuid.UUID
    status: str = "active"
    triage_level: str | None = None
    triage_explanation: str | None = None
    summary: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    messages: list[MessageSchema] = []

    model_config = {"from_attributes": True}


class MessageRequest(BaseModel):
    content: str
    input_type: str = "text"
    # Optional UI language toggle ("ko"/"en"). When omitted the backend
    # auto-detects from the message content.
    language: str | None = None


class TriageResultSchema(BaseModel):
    level: Literal["EMERGENCY", "VISIT_HOSPITAL", "HOME_CARE"]
    explanation: str | None = None
    next_steps: list[str] = []
    disclaimer: str = (
        "이것은 의료 진단이 아닙니다. CareBuddy는 분류 보조 도구일 뿐입니다. "
        "반드시 전문 의료인의 진료를 받으세요."
    )
    emergency_keywords_detected: list[str] = []
    # Recommended Korean medical department (e.g. "신경과") used as a nearby-
    # hospital search keyword. None for emergencies (use ER search instead).
    recommended_department: str | None = None


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    message_id: uuid.UUID | None = None
    reply: str
    tts_text: str | None = None
    quick_reply_options: list[str] | None = None
    triage_result: TriageResultSchema | None = None
    is_emergency: bool = False
    session_complete: bool = False
    timestamp: str | None = None
