"""Chat endpoint that bridges FastAPI with the ChatKit protocol.

Accepts raw ChatKit requests, authenticates the user via Better Auth
session token, and delegates to ``TodoChatKitServer.process()``.
Streaming responses are returned as Server-Sent Events.
"""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from apps.backend.core.security import verify_session_token

router = APIRouter(prefix="/chat", tags=["Chat"])

# Lazy-initialized server instance (set by main.py on startup)
_chatkit_server = None


def set_chatkit_server(server) -> None:
    """Called during app startup to inject the ChatKit server instance."""
    global _chatkit_server
    _chatkit_server = server


def _get_server():
    if _chatkit_server is None:
        raise RuntimeError("ChatKit server not initialized")
    return _chatkit_server


@router.post("")
@router.post("/")
async def chat_handler(
    request: Request,
    current_user_id: str = Depends(verify_session_token),
):
    """Handle all ChatKit protocol requests.

    The ChatKit SDK sends JSON requests to a single endpoint. The server
    parses the request type internally and routes to the correct handler
    (create thread, add message, list threads, etc.).
    """
    body = await request.body()
    server = _get_server()
    result = await server.process(body, context=current_user_id)

    # StreamingResult → SSE response
    if hasattr(result, "json_events"):
        return StreamingResponse(
            result,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # NonStreamingResult → JSON response
    return Response(
        content=result.json,
        media_type="application/json",
    )
