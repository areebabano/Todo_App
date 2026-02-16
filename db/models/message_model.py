"""Message model for individual chat messages within a conversation.

Each message belongs to a conversation and is either from the user or the
AI assistant. Messages are ordered chronologically by created_at within
their parent conversation. Assistant messages may include metadata about
MCP tool invocations in the tool_calls JSON field.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, Index, Text
from sqlmodel import Field, SQLModel


class Message(SQLModel, table=True):
    """An individual message within a conversation.

    Attributes:
        id: Unique identifier (UUID, auto-generated).
        conversation_id: FK reference to the parent Conversation.
            Cascade-deletes when the conversation is removed.
        role: Message sender role — either "user" or "assistant".
        content: The text content of the message.
        tool_calls: Optional JSON metadata recording which MCP tools were
            invoked during this assistant response (tool name, arguments,
            result summary).
        created_at: Timestamp when the message was sent/received.
    """

    __tablename__ = "messages"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(
        foreign_key="conversations.id",
        nullable=False,
        index=True,
    )
    role: str = Field(nullable=False, max_length=20)
    content: str = Field(sa_column=Column(Text, nullable=False))
    tool_calls: Optional[dict[str, Any]] = Field(default=None, sa_type=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index(
            "ix_message_conversation_created",
            "conversation_id",
            "created_at",
        ),
    )
