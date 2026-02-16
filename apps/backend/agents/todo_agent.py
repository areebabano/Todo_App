"""Todo Assistant agent powered by the OpenAI Agents SDK.

Defines the agent configuration (system prompt, model, MCP servers) and
the ``process_chat_message`` async generator that streams AI responses
back to the caller.

Architecture
------------
ChatKit Server  -->  process_chat_message()
                         |
                         v
                     Agent + Runner.run_streamed()
                         |
                         v
                     MCP Server (create_task, list_tasks, ...)
                         |
                         v
                     TaskService  -->  PostgreSQL
"""

import logging
import os
from typing import Any, AsyncGenerator

from agents import Agent, Runner
from agents.items import TResponseInputItem
from agents.mcp import MCPServerStreamableHttp
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a friendly, concise task management assistant called "Todo Assistant".

**Capabilities** (use the MCP tools provided):
- Create new tasks
- List tasks (all, active, or completed)
- Update task titles and descriptions
- Mark tasks as complete or incomplete
- Delete tasks

**Behaviour rules**:
1. Always confirm actions by including the task title in your response.
2. Before deleting a task, ask the user to confirm.
3. If a request is ambiguous (e.g. multiple tasks match), ask which one.
4. If the user asks something unrelated to task management, politely \
redirect them: "I'm a task management assistant — I can help you \
create, view, update, or complete tasks."
5. When listing many tasks, summarise or paginate (show 10 at a time).
6. Keep responses short and conversational.

**Multi-turn context rules**:
7. Track context from earlier messages in this conversation. When the \
user says "it", "that task", "the first one", "the last one", etc., \
resolve the reference using the most recent relevant context (e.g. \
a task just created, or a position in a previously listed set of tasks).
8. If you listed tasks earlier, remember their order. "The first one" \
means the first task in the most recent listing. "The second one" means \
the second, etc.
9. If context is truly unclear and you cannot resolve a reference, ask \
the user to clarify which task they mean.

**Important**: The current user's ID is provided in the conversation. \
Always pass it as the ``owner_user_id`` parameter when calling any tool.
"""

# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def _get_mcp_server_url() -> str:
    """Build the MCP server URL from environment configuration."""
    port = os.getenv("BACKEND_PORT", "8000")
    return f"http://localhost:{port}/mcp"


def create_agent() -> Agent:
    """Create and return a configured Todo Assistant agent.

    The agent is wired to the MCP server via Streamable HTTP transport
    and uses the model specified by the ``OPENAI_MODEL`` env var
    (defaults to ``gpt-4o``).
    """
    mcp_server = MCPServerStreamableHttp(
        params={"url": _get_mcp_server_url()},
        name="Todo Tools",
    )

    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    return Agent(
        name="Todo Assistant",
        instructions=SYSTEM_PROMPT,
        model=model,
        mcp_servers=[mcp_server],
    )


# ---------------------------------------------------------------------------
# Chat message processor (streaming)
# ---------------------------------------------------------------------------


async def process_chat_message(
    user_message: str,
    conversation_history: list[dict[str, Any]],
    owner_user_id: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Process a user chat message and yield streaming response events.

    This is the main entry-point called by the ChatKit server's
    ``respond`` method.  It:

    1. Truncates the conversation history to the configured context
       window.
    2. Appends a system-level note with the ``owner_user_id`` so the
       agent can pass it to MCP tools.
    3. Runs the agent with ``Runner.run_streamed()``.
    4. Yields dicts describing each streaming event (text deltas, tool
       calls, completion).

    Args:
        user_message: The latest message from the user.
        conversation_history: Previous messages in SDK-compatible format
            (list of dicts with ``role`` and ``content`` keys).
        owner_user_id: Authenticated user ID, injected into the agent
            context so MCP tools can enforce data isolation.

    Yields:
        Dicts with a ``type`` key and associated payload:
        - ``{"type": "text_delta", "content": "..."}``
        - ``{"type": "tool_call", "name": "...", "arguments": "..."}``
        - ``{"type": "tool_output", "name": "...", "output": "..."}``
        - ``{"type": "done", "content": "..."}``
        - ``{"type": "error", "content": "..."}``
    """
    context_window = int(os.getenv("CHATBOT_CONTEXT_WINDOW", "20"))

    # -- Build input messages ------------------------------------------
    input_messages: list[TResponseInputItem] = []

    # Inject owner_user_id as a developer/system note the agent can see
    input_messages.append(
        {
            "role": "user",
            "content": (
                f"[system note — do not display to the user] "
                f"The current user's owner_user_id is: {owner_user_id}"
            ),
        }
    )

    # Truncate history to context window (most recent messages)
    truncated = conversation_history[-context_window:]
    for msg in truncated:
        input_messages.append(
            {
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            }
        )

    # Append the new user message
    input_messages.append({"role": "user", "content": user_message})

    # -- Run the agent with streaming ---------------------------------
    agent = create_agent()

    try:
        async with agent.mcp_servers[0] as _mcp_conn:
            result = Runner.run_streamed(agent, input=input_messages)

            full_response = ""

            async for event in result.stream_events():
                if isinstance(event, RawResponsesStreamEvent):
                    data = event.data
                    # Text deltas from the model
                    if hasattr(data, "delta") and isinstance(data.delta, str):
                        full_response += data.delta
                        yield {"type": "text_delta", "content": data.delta}

                elif isinstance(event, RunItemStreamEvent):
                    if event.name == "tool_called":
                        item = event.item
                        yield {
                            "type": "tool_call",
                            "name": getattr(item, "name", "unknown"),
                            "arguments": getattr(item, "arguments", ""),
                        }
                    elif event.name == "tool_output":
                        item = event.item
                        yield {
                            "type": "tool_output",
                            "name": getattr(item, "name", "unknown"),
                            "output": getattr(item, "output", ""),
                        }
                    elif event.name == "message_output_created":
                        # Final assembled message — extract text
                        item = event.item
                        raw_item = getattr(item, "raw_item", None)
                        if raw_item and hasattr(raw_item, "content"):
                            for part in raw_item.content:
                                if hasattr(part, "text"):
                                    full_response = part.text

            yield {"type": "done", "content": full_response}

    except Exception as exc:
        logger.exception("Agent processing error: %s", exc)
        error_msg = (
            "I'm sorry, I'm having trouble processing your request "
            "right now. Please try again in a moment."
        )
        yield {"type": "error", "content": error_msg}
