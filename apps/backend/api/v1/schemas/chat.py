"""Chat request/response schemas for the streaming chat API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Incoming chat message from the user."""

    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(
        default=None,
        description="Existing conversation ID to continue. If omitted, a new conversation is created.",
    )


class MessageResponse(BaseModel):
    """A single chat message."""

    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime


class ConversationResponse(BaseModel):
    """A chat conversation summary."""

    id: str
    title: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
