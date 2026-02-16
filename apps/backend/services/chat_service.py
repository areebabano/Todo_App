"""ChatKit Store and Server implementation backed by SQLModel.

Provides:
- ``TodoStore`` — A ``chatkit.store.Store`` subclass that persists threads
  (conversations) and items (messages) in the Neon PostgreSQL database.
- ``TodoChatKitServer`` — A ``chatkit.server.ChatKitServer`` subclass whose
  ``respond`` method orchestrates the AI agent and streams events back.
"""

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter
from sqlmodel import Session, select, col

from chatkit.server import ChatKitServer
from chatkit.store import NotFoundError, Store
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageContentPartAdded,
    AssistantMessageContentPartDone,
    AssistantMessageContentPartTextDelta,
    AssistantMessageItem,
    Page,
    ThreadItem,
    ThreadItemAddedEvent,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    ThreadUpdatedEvent,
    UserMessageItem,
)

from apps.backend.agents.todo_agent import process_chat_message
from db.models.conversation_model import Conversation
from db.models.message_model import Message
from db.session import engine

logger = logging.getLogger(__name__)

# Pydantic adapter for serializing/deserializing ThreadItem (discriminated union)
_thread_item_adapter = TypeAdapter(ThreadItem)


# ---------------------------------------------------------------------------
# Store implementation
# ---------------------------------------------------------------------------


class TodoStore(Store[str]):
    """ChatKit ``Store`` backed by Conversation and Message SQLModel tables.

    The generic context type is ``str`` representing the authenticated
    ``owner_user_id``.  Every store operation receives this context so
    that data isolation is enforced.
    """

    # -- Thread operations -------------------------------------------------

    async def load_thread(self, thread_id: str, context: str) -> ThreadMetadata:
        with Session(engine) as session:
            conv = session.get(Conversation, thread_id)
        if not conv or conv.owner_user_id != context:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self._conv_to_metadata(conv)

    async def save_thread(self, thread: ThreadMetadata, context: str) -> None:
        with Session(engine) as session:
            conv = session.get(Conversation, thread.id)
            if conv:
                conv.title = thread.title
                conv.updated_at = datetime.utcnow()
            else:
                # Archive any existing active conversations for this user
                # so only the new one is active
                stmt = select(Conversation).where(
                    Conversation.owner_user_id == context,
                    Conversation.is_active == True,  # noqa: E712
                )
                active_convs = session.exec(stmt).all()
                for ac in active_convs:
                    ac.is_active = False
                    session.add(ac)

                conv = Conversation(
                    id=thread.id,
                    owner_user_id=context,
                    title=thread.title,
                    is_active=True,
                    created_at=thread.created_at,
                    updated_at=datetime.utcnow(),
                )
            session.add(conv)
            session.commit()

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: str,
    ) -> Page[ThreadMetadata]:
        with Session(engine) as session:
            stmt = select(Conversation).where(
                Conversation.owner_user_id == context,
            )
            if order == "desc":
                stmt = stmt.order_by(col(Conversation.created_at).desc())
            else:
                stmt = stmt.order_by(col(Conversation.created_at).asc())

            if after:
                # Cursor-based pagination: skip past the 'after' thread
                ref = session.get(Conversation, after)
                if ref:
                    if order == "desc":
                        stmt = stmt.where(Conversation.created_at < ref.created_at)
                    else:
                        stmt = stmt.where(Conversation.created_at > ref.created_at)

            convs = session.exec(stmt.limit(limit + 1)).all()

        has_more = len(convs) > limit
        data = convs[:limit]
        return Page(
            data=[self._conv_to_metadata(c) for c in data],
            has_more=has_more,
            after=str(data[-1].id) if data and has_more else None,
        )

    async def delete_thread(self, thread_id: str, context: str) -> None:
        with Session(engine) as session:
            conv = session.get(Conversation, thread_id)
            if not conv or conv.owner_user_id != context:
                raise NotFoundError(f"Thread {thread_id} not found")
            # Messages cascade-delete via FK
            session.delete(conv)
            session.commit()

    # -- Item operations ---------------------------------------------------

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: str,
    ) -> Page[ThreadItem]:
        with Session(engine) as session:
            stmt = select(Message).where(Message.conversation_id == thread_id)

            if order == "desc":
                stmt = stmt.order_by(col(Message.created_at).desc())
            else:
                stmt = stmt.order_by(col(Message.created_at).asc())

            if after:
                ref = session.get(Message, after)
                if ref:
                    if order == "desc":
                        stmt = stmt.where(Message.created_at < ref.created_at)
                    else:
                        stmt = stmt.where(Message.created_at > ref.created_at)

            msgs = session.exec(stmt.limit(limit + 1)).all()

        has_more = len(msgs) > limit
        data = msgs[:limit]
        items = [self._msg_to_thread_item(m, thread_id) for m in data]
        return Page(
            data=items,
            has_more=has_more,
            after=str(data[-1].id) if data and has_more else None,
        )

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: str
    ) -> None:
        with Session(engine) as session:
            msg = self._thread_item_to_msg(item, thread_id)
            session.add(msg)
            # Update conversation timestamp
            conv = session.get(Conversation, thread_id)
            if conv:
                conv.updated_at = datetime.utcnow()
                session.add(conv)
            session.commit()

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: str
    ) -> None:
        with Session(engine) as session:
            existing = session.get(Message, item.id)
            if existing:
                existing.content = self._extract_content(item)
                existing.tool_calls = self._extract_tool_calls(item)
                session.add(existing)
            else:
                msg = self._thread_item_to_msg(item, thread_id)
                session.add(msg)
            session.commit()

    async def load_item(
        self, thread_id: str, item_id: str, context: str
    ) -> ThreadItem:
        with Session(engine) as session:
            msg = session.get(Message, item_id)
        if not msg or str(msg.conversation_id) != thread_id:
            raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")
        return self._msg_to_thread_item(msg, thread_id)

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: str
    ) -> None:
        with Session(engine) as session:
            msg = session.get(Message, item_id)
            if msg and str(msg.conversation_id) == thread_id:
                session.delete(msg)
                session.commit()

    # -- Attachment operations (minimal — not using attachments) ------------

    async def save_attachment(self, attachment: Any, context: str) -> None:
        pass  # Attachments not supported in this implementation

    async def load_attachment(self, attachment_id: str, context: str) -> Any:
        raise NotFoundError(f"Attachment {attachment_id} not found")

    async def delete_attachment(self, attachment_id: str, context: str) -> None:
        pass  # Attachments not supported

    # -- ID generation -----------------------------------------------------

    def generate_thread_id(self, context: str) -> str:
        return str(uuid4())

    def generate_item_id(
        self, item_type: str, thread: ThreadMetadata, context: str
    ) -> str:
        return str(uuid4())

    # -- Internal helpers --------------------------------------------------

    @staticmethod
    def _conv_to_metadata(conv: Conversation) -> ThreadMetadata:
        return ThreadMetadata(
            id=str(conv.id),
            title=conv.title,
            created_at=conv.created_at,
        )

    @staticmethod
    def _msg_to_thread_item(msg: Message, thread_id: str) -> ThreadItem:
        """Convert a DB Message to a ChatKit ThreadItem."""
        base = {
            "id": str(msg.id),
            "thread_id": str(thread_id),
            "created_at": msg.created_at,
        }

        if msg.role == "user":
            return UserMessageItem(
                **base,
                content=[{"type": "input_text", "text": msg.content}],
                inference_options={},
            )
        else:
            # Assistant message
            return AssistantMessageItem(
                **base,
                content=[
                    AssistantMessageContent(text=msg.content),
                ],
            )

    @staticmethod
    def _thread_item_to_msg(item: ThreadItem, thread_id: str) -> Message:
        """Convert a ChatKit ThreadItem to a DB Message for persistence."""
        content = TodoStore._extract_content(item)
        role = "user" if isinstance(item, UserMessageItem) else "assistant"
        tool_calls = TodoStore._extract_tool_calls(item)

        return Message(
            id=item.id,
            conversation_id=thread_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            created_at=item.created_at,
        )

    @staticmethod
    def _extract_content(item: ThreadItem) -> str:
        """Extract text content from a ThreadItem."""
        if isinstance(item, UserMessageItem):
            parts = []
            for c in item.content:
                if hasattr(c, "text"):
                    parts.append(c.text)
            return " ".join(parts) if parts else ""
        elif isinstance(item, AssistantMessageItem):
            parts = []
            for c in item.content:
                if hasattr(c, "text"):
                    parts.append(c.text)
            return " ".join(parts) if parts else ""
        else:
            # For hidden context, widget, etc. — store as JSON
            return getattr(item, "content", "") or ""

    @staticmethod
    def _extract_tool_calls(item: ThreadItem) -> dict[str, Any] | None:
        """Extract tool_calls metadata if present."""
        # We store the full item JSON for non-message types
        if not isinstance(item, (UserMessageItem, AssistantMessageItem)):
            try:
                return {"_raw_type": item.type, "_raw": item.model_dump(mode="json")}
            except Exception:
                return None
        return None


# ---------------------------------------------------------------------------
# ChatKit Server implementation
# ---------------------------------------------------------------------------


class TodoChatKitServer(ChatKitServer[str]):
    """ChatKit server that delegates AI responses to the Todo Agent.

    The context type ``str`` is the authenticated ``owner_user_id``.
    """

    @staticmethod
    def _generate_title_from_message(user_text: str) -> str:
        """Generate a short conversation title from the first user message.

        Truncates to ~50 chars at a word boundary. This is a simple
        heuristic — no LLM call needed for a title.
        """
        text = user_text.strip()
        if not text:
            return "New conversation"
        # Remove leading "please", "can you", etc. for a cleaner title
        for prefix in ("please ", "can you ", "could you ", "i want to ", "i'd like to "):
            if text.lower().startswith(prefix):
                text = text[len(prefix):]
                break
        # Capitalize first letter
        text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
        # Truncate at word boundary
        if len(text) > 50:
            text = text[:50].rsplit(" ", 1)[0] + "..."
        return text

    async def _maybe_set_title(
        self, thread: ThreadMetadata, user_text: str, context: str
    ) -> bool:
        """Set the conversation title if it hasn't been set yet.

        Returns True if a title was generated, False otherwise.
        """
        if thread.title:
            return False
        title = self._generate_title_from_message(user_text)
        thread.title = title
        # Persist to DB
        with Session(engine) as session:
            conv = session.get(Conversation, thread.id)
            if conv and not conv.title:
                conv.title = title
                conv.updated_at = datetime.utcnow()
                session.add(conv)
                session.commit()
        return True

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: str,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Process user message through the AI agent and stream response events."""
        # Extract the user's text from the incoming message
        user_text = ""
        if input_user_message:
            for part in input_user_message.content:
                if hasattr(part, "text"):
                    user_text += part.text

        # Auto-generate conversation title from the first user message
        title_was_set = await self._maybe_set_title(thread, user_text, context)

        if not user_text.strip():
            # Empty message — yield a helpful prompt
            item_id = self.store.generate_item_id("message", thread, context)
            assistant_item = AssistantMessageItem(
                id=item_id,
                thread_id=thread.id,
                created_at=datetime.utcnow(),
                content=[
                    AssistantMessageContent(
                        text="It looks like you sent an empty message. How can I help you with your tasks?"
                    )
                ],
            )
            yield ThreadItemDoneEvent(item=assistant_item)
            return

        # Load conversation history from the store for context
        history_page = await self.store.load_thread_items(
            thread.id, after=None, limit=50, order="asc", context=context
        )

        conversation_history = []
        for item in history_page.data:
            if isinstance(item, UserMessageItem):
                text = " ".join(
                    getattr(c, "text", "") for c in item.content
                )
                conversation_history.append({"role": "user", "content": text})
            elif isinstance(item, AssistantMessageItem):
                text = " ".join(
                    getattr(c, "text", "") for c in item.content
                )
                conversation_history.append({"role": "assistant", "content": text})

        # Stream response from the AI agent
        item_id = self.store.generate_item_id("message", thread, context)
        full_text = ""
        tool_calls_metadata = []
        started = False

        async for event in process_chat_message(
            user_message=user_text,
            conversation_history=conversation_history,
            owner_user_id=context,
        ):
            event_type = event.get("type")

            if event_type == "text_delta":
                delta = event.get("content", "")
                if not started:
                    # Emit the initial item-added event
                    started = True
                    assistant_item = AssistantMessageItem(
                        id=item_id,
                        thread_id=thread.id,
                        created_at=datetime.utcnow(),
                        content=[AssistantMessageContent(text="")],
                    )
                    yield ThreadItemAddedEvent(item=assistant_item)
                    yield AssistantMessageContentPartAdded(
                        content_index=0,
                        content=AssistantMessageContent(text=""),
                    )

                full_text += delta
                yield AssistantMessageContentPartTextDelta(
                    content_index=0,
                    delta=delta,
                )

            elif event_type == "tool_call":
                tool_calls_metadata.append({
                    "name": event.get("name"),
                    "arguments": event.get("arguments"),
                })

            elif event_type == "tool_output":
                tool_calls_metadata.append({
                    "name": event.get("name"),
                    "output": event.get("output"),
                })

            elif event_type == "done":
                # Use the final assembled content if available
                done_content = event.get("content", "")
                if done_content and not full_text:
                    full_text = done_content

            elif event_type == "error":
                full_text = event.get("content", "Sorry, something went wrong.")

        # Ensure we emit at least one complete message
        if not started and full_text:
            assistant_item = AssistantMessageItem(
                id=item_id,
                thread_id=thread.id,
                created_at=datetime.utcnow(),
                content=[AssistantMessageContent(text=full_text)],
            )
            yield ThreadItemDoneEvent(item=assistant_item)
        elif started:
            # Emit the content-part-done and item-done events
            yield AssistantMessageContentPartDone(
                content_index=0,
                content=AssistantMessageContent(text=full_text),
            )
            final_item = AssistantMessageItem(
                id=item_id,
                thread_id=thread.id,
                created_at=datetime.utcnow(),
                content=[AssistantMessageContent(text=full_text)],
            )
            yield ThreadItemDoneEvent(item=final_item)
        else:
            # No response at all — yield a fallback
            assistant_item = AssistantMessageItem(
                id=item_id,
                thread_id=thread.id,
                created_at=datetime.utcnow(),
                content=[
                    AssistantMessageContent(
                        text="I'm sorry, I couldn't process that request. Please try again."
                    )
                ],
            )
            yield ThreadItemDoneEvent(item=assistant_item)

        # Notify the client of the new title if it was just generated
        if title_was_set and thread.title:
            yield ThreadUpdatedEvent(thread=thread)
