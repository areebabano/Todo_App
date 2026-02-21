"""Streaming chat service that bypasses ChatKit protocol.

Provides a simple SSE-based streaming interface that reuses the existing
``process_chat_message()`` agent and the Conversation/Message DB models.
"""

import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import uuid4

from sqlmodel import Session, select, col

from apps.backend.agents.todo_agent import process_chat_message
from db.models.conversation_model import Conversation
from db.models.message_model import Message
from db.session import engine

logger = logging.getLogger(__name__)


def _generate_title(text: str) -> str:
    """Generate a short conversation title from the first user message."""
    text = text.strip()
    if not text:
        return "New conversation"
    for prefix in ("please ", "can you ", "could you ", "i want to ", "i'd like to "):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
            break
    text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
    if len(text) > 50:
        text = text[:50].rsplit(" ", 1)[0] + "..."
    return text


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_chat_response(
    message: str,
    owner_user_id: str,
    conversation_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Process a user message and yield SSE event strings.

    SSE event types:
      - conversation_id: sent first with the conversation ID
      - text_delta: incremental text from the assistant
      - tool_call: agent invoked an MCP tool
      - tool_output: MCP tool returned a result
      - done: final assembled response
      - error: something went wrong
    """
    # --- Resolve or create conversation ---
    with Session(engine) as session:
        if conversation_id:
            conv = session.get(Conversation, conversation_id)
            if not conv or conv.owner_user_id != owner_user_id:
                yield _sse_event("error", {"content": "Conversation not found"})
                return
        else:
            # Archive existing active conversations
            stmt = select(Conversation).where(
                Conversation.owner_user_id == owner_user_id,
                Conversation.is_active == True,  # noqa: E712
            )
            for ac in session.exec(stmt).all():
                ac.is_active = False
                session.add(ac)

            conv = Conversation(
                id=uuid4(),
                owner_user_id=owner_user_id,
                title=_generate_title(message),
                is_active=True,
            )
            session.add(conv)
            session.commit()
            session.refresh(conv)

        conv_id = str(conv.id)

    yield _sse_event("conversation_id", {"conversation_id": conv_id})

    # --- Save user message ---
    user_msg_id = str(uuid4())
    with Session(engine) as session:
        session.add(Message(
            id=user_msg_id,
            conversation_id=conv_id,
            role="user",
            content=message,
        ))
        # Touch conversation timestamp
        conv = session.get(Conversation, conv_id)
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            session.add(conv)
        session.commit()

    # --- Load conversation history ---
    with Session(engine) as session:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(col(Message.created_at).asc())
            .limit(50)
        )
        msgs = session.exec(stmt).all()

    conversation_history = []
    for m in msgs:
        if str(m.id) == user_msg_id:
            continue  # skip the message we just saved; it will be appended by the agent
        conversation_history.append({"role": m.role, "content": m.content})

    # --- Stream AI response ---
    full_response = ""
    try:
        async for event in process_chat_message(
            user_message=message,
            conversation_history=conversation_history,
            owner_user_id=owner_user_id,
        ):
            event_type = event.get("type")

            if event_type == "text_delta":
                delta = event.get("content", "")
                full_response += delta
                yield _sse_event("text_delta", {"content": delta})

            elif event_type == "tool_call":
                yield _sse_event("tool_call", {
                    "name": event.get("name"),
                    "arguments": event.get("arguments"),
                })

            elif event_type == "tool_output":
                yield _sse_event("tool_output", {
                    "name": event.get("name"),
                    "output": event.get("output"),
                })

            elif event_type == "done":
                done_content = event.get("content", "")
                if done_content and not full_response:
                    full_response = done_content

            elif event_type == "error":
                full_response = event.get("content", "Sorry, something went wrong.")
                yield _sse_event("error", {"content": full_response})

    except Exception as exc:
        logger.exception("Streaming chat error: %s", exc)
        error_str = str(exc)
        if "402" in error_str:
            full_response = (
                "The AI service API key has reached its spending limit. "
                "The chatbot is running in offline mode — you can still use basic commands like "
                "\"Add task [title]\", \"Show my tasks\", \"Complete [task name]\", etc."
            )
        elif "429" in error_str:
            full_response = (
                "The AI service is currently rate-limited. Please wait a moment and try again."
            )
        else:
            full_response = full_response or (
                "I'm having trouble connecting to the AI service right now. "
                "Try a simple command like \"Show my tasks\" or \"Add task [title]\"."
            )
        yield _sse_event("error", {"content": full_response})

    if not full_response:
        full_response = "I'm sorry, I couldn't process that request. Please try again."

    yield _sse_event("done", {"content": full_response})

    # --- Save assistant message ---
    with Session(engine) as session:
        session.add(Message(
            id=str(uuid4()),
            conversation_id=conv_id,
            role="assistant",
            content=full_response,
        ))
        conv = session.get(Conversation, conv_id)
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            session.add(conv)
        session.commit()


def get_conversations(owner_user_id: str) -> list[dict]:
    """List all conversations for a user, newest first."""
    with Session(engine) as session:
        stmt = (
            select(Conversation)
            .where(Conversation.owner_user_id == owner_user_id)
            .order_by(col(Conversation.updated_at).desc())
        )
        convs = session.exec(stmt).all()
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in convs
    ]


def get_messages(conversation_id: str, owner_user_id: str) -> list[dict] | None:
    """Load messages for a conversation. Returns None if not found/unauthorized."""
    with Session(engine) as session:
        conv = session.get(Conversation, conversation_id)
        if not conv or conv.owner_user_id != owner_user_id:
            return None

        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(col(Message.created_at).asc())
        )
        msgs = session.exec(stmt).all()

    return [
        {
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in msgs
    ]
