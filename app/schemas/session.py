import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MessageSchema(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: uuid.UUID
    triage_result: str | None
    summary: str | None
    created_at: datetime
    ended_at: datetime | None
    messages: list[MessageSchema] = []

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    message: str


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    reply: str
    triage_result: str | None = None
    is_emergency: bool = False
