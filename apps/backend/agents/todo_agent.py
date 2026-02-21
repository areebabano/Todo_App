"""Todo Assistant agent powered by the OpenAI Agents SDK.

Defines the agent configuration (system prompt, model, MCP servers) and
the ``process_chat_message`` async generator that streams AI responses
back to the caller.

Uses OpenRouter as the LLM provider (free models with tool calling support).
Includes multi-model fallback and a direct command parser as ultimate
fallback when all LLM providers are unavailable.

Architecture
------------
Chat Service  -->  process_chat_message()
                       |
                       v
                   Agent + Runner.run_streamed()
                       |  (fallback: direct command parser)
                       v
                   MCP Server (create_task, list_tasks, ...)
                       |
                       v
                   TaskService  -->  PostgreSQL
"""

import json
import logging
import os
import re
from typing import Any, AsyncGenerator, Optional

from openai import AsyncOpenAI

from agents import Agent, ModelSettings, Runner
from agents.items import TResponseInputItem
from agents.mcp import MCPServerStreamableHttp
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a friendly, helpful task management assistant called "Todo Assistant".

**Capabilities** (use the MCP tools provided):
- Create new tasks (with title and optional description)
- List tasks (all, active, or completed)
- Update task titles and descriptions
- Mark tasks as complete or incomplete
- Delete tasks

**Response formatting rules** (VERY IMPORTANT):
1. NEVER output raw JSON, tool arguments, IDs, or technical data in your response.
2. Always respond in natural, conversational language.
3. When confirming an action, include the task title and relevant details.
4. When a task is created, confirm with: the title, description (if any), \
and a friendly message.
5. When listing tasks, format them as a clean numbered list with status \
indicators (e.g. checkmarks for completed tasks).
6. Include helpful context like task counts and descriptions.
7. Use markdown formatting: **bold** for task titles, bullet points for lists.

**Behaviour rules**:
8. Before deleting a task, ask the user to confirm.
9. If a request is ambiguous (e.g. multiple tasks match), ask which one.
10. If the user asks something unrelated to task management, politely \
redirect them.
11. Keep responses conversational but informative.

**Multi-turn context rules**:
12. Track context from earlier messages in this conversation. When the \
user says "it", "that task", "the first one", "the last one", etc., \
resolve the reference using the most recent relevant context.
13. If you listed tasks earlier, remember their order.
14. If context is truly unclear, ask the user to clarify.

**Important**: The current user's ID is provided in the conversation. \
Always pass it as the ``owner_user_id`` parameter when calling any tool. \
NEVER show the user's ID, owner_user_id, or any internal IDs in your response.
"""

# ---------------------------------------------------------------------------
# OpenRouter client + model with fallback
# ---------------------------------------------------------------------------

# Free models on OpenRouter that support tool calling (ordered by preference)
FALLBACK_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-30b-a3b:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "google/gemma-3-27b-it:free",
]

# Max retries per model before moving to next fallback
_MAX_RETRIES_PER_MODEL = 2

# Keys that indicate raw tool-call JSON leaked into text output
_TOOL_ARG_KEYS = {"owner_user_id", "task_id", "status_filter", "title", "description"}


def _is_leaked_json(text: str) -> bool:
    """Return True if *text* looks like raw JSON tool-call arguments.

    Some free models emit tool arguments as plain text instead of proper
    function calls.  We detect and suppress those chunks so the user
    never sees raw JSON in the chat.
    """
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return False
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and _TOOL_ARG_KEYS & set(obj.keys()):
            return True
    except (json.JSONDecodeError, ValueError):
        pass
    return False


def _get_openrouter_client() -> AsyncOpenAI:
    """Create an AsyncOpenAI client pointing at OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def _get_model(model_name: Optional[str] = None) -> OpenAIChatCompletionsModel:
    """Build the model wrapper for the agents SDK."""
    if not model_name:
        model_name = os.getenv("OPENROUTER_MODEL", os.getenv("OPENAI_MODEL", FALLBACK_MODELS[0]))
    client = _get_openrouter_client()
    return OpenAIChatCompletionsModel(
        model=model_name,
        openai_client=client,
    )


def _get_fallback_models() -> list[str]:
    """Get the ordered list of models to try."""
    primary = os.getenv("OPENROUTER_MODEL", os.getenv("OPENAI_MODEL", FALLBACK_MODELS[0]))
    models = [primary]
    for m in FALLBACK_MODELS:
        if m not in models:
            models.append(m)
    return models


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def _get_mcp_server_url() -> str:
    """Build the MCP server URL from environment configuration."""
    port = os.getenv("BACKEND_PORT", "8000")
    return f"http://localhost:{port}/mcp/"


def create_agent(model_name: Optional[str] = None) -> Agent:
    """Create and return a configured Todo Assistant agent."""
    mcp_server = MCPServerStreamableHttp(
        params={"url": _get_mcp_server_url()},
        name="Todo Tools",
        client_session_timeout_seconds=30,
    )

    model = _get_model(model_name)

    return Agent(
        name="Todo Assistant",
        instructions=SYSTEM_PROMPT,
        model=model,
        mcp_servers=[mcp_server],
        model_settings=ModelSettings(max_tokens=2048),
    )


# ---------------------------------------------------------------------------
# Direct command parser (fallback when LLM is unavailable)
# ---------------------------------------------------------------------------


class DirectCommandParser:
    """Parse simple user commands and map them to MCP tool calls.

    Used as a fallback when all LLM providers are unavailable.
    """

    @staticmethod
    def parse(message: str, owner_user_id: str) -> Optional[dict]:
        """Parse a user message into a tool call dict, or None if unrecognized.

        Returns dict with keys: tool, args, description
        """
        msg = message.strip().lower()

        # --- Create task ---
        create_patterns = [
            r"(?:create|add|make|new)\s+(?:a\s+)?task\s+(?:called\s+|named\s+|titled\s+)?['\"]?(.+?)['\"]?\s*$",
            r"(?:create|add|make|new)\s+['\"](.+?)['\"]",
            r"^add\s+(.+)$",
        ]
        for pattern in create_patterns:
            m = re.match(pattern, msg, re.IGNORECASE)
            if m:
                title = m.group(1).strip().strip("'\"")
                return {
                    "tool": "create_task",
                    "args": {"owner_user_id": owner_user_id, "title": title},
                    "description": f'Creating task "{title}"',
                }

        # --- List tasks ---
        list_patterns = [
            r"(?:show|list|get|view|display|see)\s+(?:me\s+)?(?:all\s+)?(?:my\s+)?tasks",
            r"(?:what|which)\s+tasks?\s+(?:do i|have|are)",
            r"^(?:tasks|my tasks|all tasks)$",
            r"what(?:'s| is) left",
            r"(?:show|list|get)\s+(?:active|incomplete|pending)\s+tasks",
            r"(?:show|list|get)\s+(?:completed|done|finished)\s+tasks",
        ]
        for pattern in list_patterns:
            if re.search(pattern, msg, re.IGNORECASE):
                status_filter = "all"
                if any(w in msg for w in ["active", "incomplete", "pending", "left"]):
                    status_filter = "active"
                elif any(w in msg for w in ["completed", "done", "finished"]):
                    status_filter = "completed"
                return {
                    "tool": "list_tasks",
                    "args": {"owner_user_id": owner_user_id, "status_filter": status_filter},
                    "description": f"Listing {status_filter} tasks",
                }

        # --- Update task ---
        update_patterns = [
            r"(?:update|rename|change|edit)\s+(?:task\s+)?['\"](.+?)['\"](?:\s+to\s+['\"](.+?)['\"])",
            r"(?:update|rename|change|edit)\s+(?:task\s+)?(.+?)\s+to\s+(.+)",
        ]
        for pattern in update_patterns:
            m = re.match(pattern, msg, re.IGNORECASE)
            if m:
                old_name = m.group(1).strip().strip("'\"")
                new_name = m.group(2).strip().strip("'\"")
                return {
                    "tool": "update_task_by_name",
                    "args": {"owner_user_id": owner_user_id, "task_ref": old_name, "new_title": new_name},
                    "description": f'Updating task "{old_name}" to "{new_name}"',
                }

        # --- Complete task ---
        complete_patterns = [
            r"(?:complete|finish|done|mark.*(?:complete|done))\s+(?:task\s+)?['\"](.+?)['\"]",
            r"(?:complete|finish|done|mark.*(?:complete|done))\s+(?:task\s+)?(.+)",
        ]
        for pattern in complete_patterns:
            m = re.match(pattern, msg, re.IGNORECASE)
            if m:
                task_ref = m.group(1).strip().strip("'\"")
                return {
                    "tool": "complete_task_by_name",
                    "args": {"owner_user_id": owner_user_id, "task_ref": task_ref},
                    "description": f'Completing task "{task_ref}"',
                }

        # --- Delete task ---
        delete_patterns = [
            r"(?:delete|remove|drop)\s+(?:task\s+)?['\"](.+?)['\"]",
            r"(?:delete|remove|drop)\s+(?:task\s+)?(.+)",
        ]
        for pattern in delete_patterns:
            m = re.match(pattern, msg, re.IGNORECASE)
            if m:
                task_ref = m.group(1).strip().strip("'\"")
                return {
                    "tool": "delete_task_by_name",
                    "args": {"owner_user_id": owner_user_id, "task_ref": task_ref},
                    "description": f'Deleting task "{task_ref}"',
                }

        # --- Greeting / help ---
        if msg in ("hi", "hello", "hey", "help", "what can you do", "what can you do?"):
            return {
                "tool": "greeting",
                "args": {},
                "description": "Greeting",
            }

        return None

    @staticmethod
    async def execute(
        parsed: dict,
        owner_user_id: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute a parsed command directly using the TaskService."""
        from sqlmodel import Session
        from apps.backend.services.task_service import TaskService
        from apps.backend.api.v1.schemas.task import TaskCreate, TaskUpdate
        from db.session import engine

        tool = parsed["tool"]
        args = parsed["args"]

        try:
            if tool == "greeting":
                yield {"type": "text_delta", "content": (
                    "Hello! I'm your Todo Assistant. I can help you manage your tasks. "
                    "Here's what I can do:\n\n"
                    "- **Create a task**: \"Add task Buy groceries\"\n"
                    "- **List tasks**: \"Show my tasks\"\n"
                    "- **Complete a task**: \"Complete Buy groceries\"\n"
                    "- **Delete a task**: \"Delete Buy groceries\"\n\n"
                    "What would you like to do?"
                )}
                yield {"type": "done", "content": ""}
                return

            if tool == "create_task":
                task_data = TaskCreate(title=args["title"])
                with Session(engine) as session:
                    task = TaskService.create_task(session, task_data, owner_user_id)
                desc_part = f"\n**Description:** {task.description}" if task.description else ""
                created_time = task.created_at.strftime("%b %d, %Y at %I:%M %p")
                response = (
                    f'I\'ve created your task!\n\n'
                    f'**Title:** {task.title}{desc_part}\n'
                    f'**Status:** Active\n'
                    f'**Created:** {created_time}\n\n'
                    f'You can complete it anytime by saying "Complete {task.title}".'
                )
                yield {"type": "text_delta", "content": response}
                yield {"type": "done", "content": response}

            elif tool == "list_tasks":
                status_filter = args.get("status_filter", "all")
                with Session(engine) as session:
                    tasks = TaskService.get_tasks_by_owner(session, owner_user_id, skip=0, limit=20)

                if status_filter == "active":
                    tasks = [t for t in tasks if not t.is_completed]
                elif status_filter == "completed":
                    tasks = [t for t in tasks if t.is_completed]

                if not tasks:
                    msg = "You don't have any tasks yet. Try saying \"Add task Buy groceries\" to create one!"
                    if status_filter == "active":
                        msg = "You don't have any active tasks. Great job - everything is done!"
                    elif status_filter == "completed":
                        msg = "You haven't completed any tasks yet. Keep going!"
                    yield {"type": "text_delta", "content": msg}
                    yield {"type": "done", "content": msg}
                else:
                    active_count = sum(1 for t in tasks if not t.is_completed)
                    completed_count = sum(1 for t in tasks if t.is_completed)
                    header = f"Here are your {status_filter} tasks ({len(tasks)} total):\n\n"
                    lines = [header]
                    for i, t in enumerate(tasks, 1):
                        check = "x" if t.is_completed else " "
                        desc = f"\n   {t.description}" if t.description else ""
                        lines.append(f"{i}. [{check}] **{t.title}**{desc}")
                    lines.append(f"\n\n**Summary:** {active_count} active, {completed_count} completed")
                    response = "\n".join(lines)
                    yield {"type": "text_delta", "content": response}
                    yield {"type": "done", "content": response}

            elif tool == "update_task_by_name":
                task_ref = args["task_ref"]
                new_title = args["new_title"]
                with Session(engine) as session:
                    tasks = TaskService.get_tasks_by_owner(session, owner_user_id, skip=0, limit=50)
                    matched = [t for t in tasks if task_ref.lower() in t.title.lower()]
                    if not matched:
                        msg = f'No task found matching "{task_ref}". Try saying "Show my tasks" to see all your tasks.'
                        yield {"type": "text_delta", "content": msg}
                        yield {"type": "done", "content": msg}
                        return
                    task = matched[0]
                    old_title = task.title
                    updated = TaskService.update_task(
                        session, task.id, TaskUpdate(title=new_title), owner_user_id
                    )
                if updated:
                    msg = (
                        f'Task updated!\n\n'
                        f'**Before:** {old_title}\n'
                        f'**After:** {updated.title}\n'
                        f'**Status:** {"Completed" if updated.is_completed else "Active"}'
                    )
                    yield {"type": "text_delta", "content": msg}
                    yield {"type": "done", "content": msg}
                else:
                    msg = "Could not update that task. Please try again."
                    yield {"type": "text_delta", "content": msg}
                    yield {"type": "done", "content": msg}

            elif tool == "complete_task_by_name":
                task_ref = args["task_ref"]
                with Session(engine) as session:
                    tasks = TaskService.get_tasks_by_owner(session, owner_user_id, skip=0, limit=50)
                    matched = [t for t in tasks if task_ref.lower() in t.title.lower()]
                    if not matched:
                        msg = f'No task found matching "{task_ref}". Try listing your tasks first.'
                        yield {"type": "text_delta", "content": msg}
                        yield {"type": "done", "content": msg}
                        return
                    task = matched[0]
                    result = TaskService.complete_task(session, task.id, owner_user_id)
                if result:
                    msg = (
                        f'Great job! Task **"{result.title}"** has been marked as completed.\n\n'
                        f'**Status:** Completed\n'
                        f'**Completed at:** {result.updated_at.strftime("%b %d, %Y at %I:%M %p")}'
                    )
                    yield {"type": "text_delta", "content": msg}
                    yield {"type": "done", "content": msg}
                else:
                    msg = "Could not complete that task. Please try again."
                    yield {"type": "text_delta", "content": msg}
                    yield {"type": "done", "content": msg}

            elif tool == "delete_task_by_name":
                task_ref = args["task_ref"]
                with Session(engine) as session:
                    tasks = TaskService.get_tasks_by_owner(session, owner_user_id, skip=0, limit=50)
                    matched = [t for t in tasks if task_ref.lower() in t.title.lower()]
                    if not matched:
                        msg = f'No task found matching "{task_ref}". Try saying "Show my tasks" to see all your tasks first.'
                        yield {"type": "text_delta", "content": msg}
                        yield {"type": "done", "content": msg}
                        return
                    task = matched[0]
                    deleted = TaskService.delete_task(session, task.id, owner_user_id)
                if deleted:
                    msg = f'Task **"{task.title}"** has been permanently deleted.'
                    yield {"type": "text_delta", "content": msg}
                    yield {"type": "done", "content": msg}
                else:
                    msg = "Could not delete that task. Please try again."
                    yield {"type": "text_delta", "content": msg}
                    yield {"type": "done", "content": msg}

            else:
                msg = (
                    "I couldn't understand that command. Try:\n"
                    "- \"Add task [title]\"\n"
                    "- \"Show my tasks\"\n"
                    "- \"Complete [task name]\"\n"
                    "- \"Delete [task name]\""
                )
                yield {"type": "text_delta", "content": msg}
                yield {"type": "done", "content": msg}

        except Exception as exc:
            logger.exception("Direct command execution error: %s", exc)
            yield {"type": "error", "content": f"Sorry, something went wrong: {str(exc)}"}


# ---------------------------------------------------------------------------
# Chat message processor (streaming) with fallback
# ---------------------------------------------------------------------------


async def _try_agent_with_model(
    model_name: str,
    input_messages: list[TResponseInputItem],
) -> AsyncGenerator[dict[str, Any], None]:
    """Try running the agent with a specific model. Raises on failure."""
    agent = create_agent(model_name)

    async with agent.mcp_servers[0] as _mcp_conn:
        result = Runner.run_streamed(agent, input=input_messages)

        full_response = ""
        # Buffer to detect and suppress leaked JSON tool arguments
        _json_buffer = ""
        _buffering = False

        async for event in result.stream_events():
            if isinstance(event, RawResponsesStreamEvent):
                data = event.data
                if hasattr(data, "delta") and isinstance(data.delta, str):
                    delta = data.delta

                    # Detect start of potential JSON leak
                    if not _buffering and "{" in delta:
                        _buffering = True
                        _json_buffer = delta
                        continue
                    elif _buffering:
                        _json_buffer += delta
                        # Check if buffer forms a complete JSON object
                        if "}" in _json_buffer:
                            if _is_leaked_json(_json_buffer):
                                # Suppress the leaked JSON
                                logger.info("Filtered leaked JSON from model output")
                                _json_buffer = ""
                                _buffering = False
                                continue
                            else:
                                # Not leaked JSON — flush the buffer
                                full_response += _json_buffer
                                yield {"type": "text_delta", "content": _json_buffer}
                                _json_buffer = ""
                                _buffering = False
                        # Keep buffering until we see closing brace
                        continue

                    full_response += delta
                    yield {"type": "text_delta", "content": delta}

            elif isinstance(event, RunItemStreamEvent):
                # Flush any pending buffer when a tool event arrives
                if _buffering and _json_buffer:
                    if not _is_leaked_json(_json_buffer):
                        full_response += _json_buffer
                        yield {"type": "text_delta", "content": _json_buffer}
                    _json_buffer = ""
                    _buffering = False

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
                    item = event.item
                    raw_item = getattr(item, "raw_item", None)
                    if raw_item and hasattr(raw_item, "content"):
                        for part in raw_item.content:
                            if hasattr(part, "text"):
                                text = part.text
                                # Also filter final message content
                                if not _is_leaked_json(text):
                                    full_response = text

        # Flush remaining buffer
        if _buffering and _json_buffer:
            if not _is_leaked_json(_json_buffer):
                full_response += _json_buffer
                yield {"type": "text_delta", "content": _json_buffer}

        yield {"type": "done", "content": full_response}


async def process_chat_message(
    user_message: str,
    conversation_history: list[dict[str, Any]],
    owner_user_id: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Process a user chat message and yield streaming response events.

    Tries multiple LLM models with fallback, then falls back to direct
    command parsing if all models fail.

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

    input_messages.append(
        {
            "role": "user",
            "content": (
                f"[system note — do not display to the user] "
                f"The current user's owner_user_id is: {owner_user_id}"
            ),
        }
    )

    truncated = conversation_history[-context_window:]
    for msg in truncated:
        input_messages.append(
            {
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            }
        )

    input_messages.append({"role": "user", "content": user_message})

    # -- Try each model with fallback ----------------------------------
    models = _get_fallback_models()
    last_error = None

    for model_name in models:
        try:
            logger.info("Trying model: %s", model_name)
            async for event in _try_agent_with_model(model_name, input_messages):
                yield event
            return  # Success - we're done
        except Exception as exc:
            error_str = str(exc)
            last_error = exc
            logger.warning("Model %s failed: %s", model_name, error_str)

            # Don't retry other models for non-transient errors that affect all models
            if "402" in error_str and "spend limit" in error_str.lower():
                logger.error("API key spend limit exceeded - skipping remaining models")
                break
            # For 429 (rate limit), try next model
            if "429" in error_str:
                continue
            # For other errors, also try next model
            continue

    # -- All models failed: use direct command parser ------------------
    logger.warning(
        "All LLM models failed (last error: %s). Falling back to direct command parser.",
        last_error,
    )

    parser = DirectCommandParser()
    parsed = parser.parse(user_message, owner_user_id)

    if parsed:
        yield {"type": "tool_call", "name": parsed["tool"], "arguments": ""}
        async for event in parser.execute(parsed, owner_user_id):
            yield event
    else:
        # Unrecognized command in direct mode
        fallback_msg = (
            "I'm currently running in offline mode (AI service temporarily unavailable). "
            "I can still help with basic commands:\n\n"
            "- **\"Add task [title]\"** - Create a new task\n"
            "- **\"Show my tasks\"** - List all your tasks\n"
            "- **\"Complete [task name]\"** - Mark a task as done\n"
            "- **\"Delete [task name]\"** - Remove a task\n\n"
            "Please try one of these commands!"
        )
        yield {"type": "text_delta", "content": fallback_msg}
        yield {"type": "done", "content": fallback_msg}
