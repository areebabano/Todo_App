"""Conversation model for AI chatbot sessions.

Represents a chat session between an authenticated user and the AI assistant.
Each user can have multiple conversations, but only one is active at a time.
When a user starts a new conversation, the previous active one is archived.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class Conversation(SQLModel, table=True):
    """A chat conversation thread owned by a single user.

    Attributes:
        id: Unique identifier (UUID, auto-generated).
        owner_user_id: The ID of the user who owns this conversation.
        title: Auto-generated summary title (set after first assistant response).
        is_active: Whether this is the user's current active conversation.
            A user can have at most one active conversation at a time.
        created_at: Timestamp when the conversation was started.
        updated_at: Timestamp of the last activity in this conversation.
    """

    __tablename__ = "conversations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_user_id: str = Field(nullable=False, index=True)
    title: Optional[str] = Field(default=None, max_length=200)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index(
            "ix_conversation_owner_active",
            "owner_user_id",
            "is_active",
        ),
    )
