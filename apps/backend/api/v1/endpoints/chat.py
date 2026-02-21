"""Chat endpoints with SSE streaming.

Provides a simple streaming chat API that replaces the ChatKit protocol.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from apps.backend.api.v1.schemas.chat import ChatMessageRequest
from apps.backend.core.security import verify_session_token
from apps.backend.services.chat_stream_service import (
    stream_chat_response,
    get_conversations,
    get_messages,
)

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/stream")
async def chat_stream(
    body: ChatMessageRequest,
    current_user_id: str = Depends(verify_session_token),
):
    """Stream a chat response as Server-Sent Events."""
    return StreamingResponse(
        stream_chat_response(
            message=body.message,
            owner_user_id=current_user_id,
            conversation_id=body.conversation_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations")
async def list_conversations(
    current_user_id: str = Depends(verify_session_token),
):
    """List all conversations for the authenticated user."""
    return get_conversations(current_user_id)


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    current_user_id: str = Depends(verify_session_token),
):
    """Load messages for a specific conversation."""
    result = get_messages(conversation_id, current_user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result
