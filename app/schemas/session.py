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


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    message_id: uuid.UUID | None = None
    reply: str
    tts_text: str | None = None
    quick_reply_options: list[str] | None = None
    triage_result: dict | None = None
    is_emergency: bool = False
    session_complete: bool = False
    timestamp: str | None = None
