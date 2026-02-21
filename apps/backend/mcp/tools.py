"""Stateless MCP tool definitions for todo task management.

Each tool function is decorated with ``@mcp.tool()`` and receives
``owner_user_id`` as an explicit parameter so that data-isolation is
enforced at the tool level.  Every invocation creates its own database
session — the MCP layer is fully stateless.

Tools registered here are auto-discovered by the OpenAI Agents SDK
agent via the ``MCPServerStreamableHttp`` transport.
"""

import json
from typing import Optional
from uuid import UUID

from sqlmodel import Session

from apps.backend.mcp.server import mcp
from apps.backend.api.v1.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from apps.backend.services.task_service import TaskService
from db.session import engine


def _format_task_details(task: TaskResponse) -> str:
    """Format a TaskResponse as a human-readable summary for the AI agent.

    Returns a structured text block so the LLM can craft a
    conversational reply without leaking raw JSON.
    """
    status = "Completed" if task.is_completed else "Active"
    desc = task.description if task.description else "No description"
    return (
        f"Task details:\n"
        f"  Title: {task.title}\n"
        f"  Description: {desc}\n"
        f"  Status: {status}\n"
        f"  ID: {task.id}\n"
        f"  Created: {task.created_at.strftime('%b %d, %Y at %I:%M %p')}\n"
        f"  Updated: {task.updated_at.strftime('%b %d, %Y at %I:%M %p')}"
    )


@mcp.tool()
def create_task(
    owner_user_id: str,
    title: str,
    description: Optional[str] = None,
) -> str:
    """Create a new todo task for the user.

    Args:
        owner_user_id: The authenticated user's ID.
        title: Task title (1-100 characters).
        description: Optional task description (max 500 characters).

    Returns:
        Human-readable confirmation with the created task details.
    """
    task_data = TaskCreate(title=title, description=description)
    with Session(engine) as session:
        task = TaskService.create_task(session, task_data, owner_user_id)
    desc_part = f' with description "{task.description}"' if task.description else ""
    return (
        f'Successfully created task "{task.title}"{desc_part}.\n\n'
        f"{_format_task_details(task)}"
    )


@mcp.tool()
def list_tasks(
    owner_user_id: str,
    status_filter: str = "all",
    limit: int = 10,
    offset: int = 0,
) -> str:
    """List todo tasks for the user, optionally filtered by completion status.

    Args:
        owner_user_id: The authenticated user's ID.
        status_filter: Filter by status — "all" (default), "active", or "completed".
        limit: Maximum number of tasks to return (default 10).
        offset: Number of tasks to skip for pagination (default 0).

    Returns:
        Human-readable list of tasks with their details and summary counts.
    """
    with Session(engine) as session:
        all_tasks = TaskService.get_tasks_by_owner(
            session, owner_user_id, skip=offset, limit=limit
        )

    if status_filter == "active":
        filtered = [t for t in all_tasks if not t.is_completed]
    elif status_filter == "completed":
        filtered = [t for t in all_tasks if t.is_completed]
    else:
        filtered = all_tasks

    if not filtered:
        if status_filter == "active":
            return "No active tasks found. All tasks are either completed or the user has no tasks yet."
        elif status_filter == "completed":
            return "No completed tasks found."
        return "No tasks found. The user hasn't created any tasks yet."

    lines = [f"Found {len(filtered)} {status_filter} task(s):\n"]
    for i, t in enumerate(filtered, 1):
        status = "Completed" if t.is_completed else "Active"
        desc = f' - {t.description}' if t.description else ""
        lines.append(f"  {i}. [{status}] {t.title}{desc} (ID: {t.id})")

    active_count = sum(1 for t in all_tasks if not t.is_completed)
    completed_count = sum(1 for t in all_tasks if t.is_completed)
    lines.append(f"\nSummary: {active_count} active, {completed_count} completed out of {len(all_tasks)} total.")

    return "\n".join(lines)


@mcp.tool()
def update_task(
    owner_user_id: str,
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """Update an existing task's title and/or description.

    Args:
        owner_user_id: The authenticated user's ID.
        task_id: UUID of the task to update.
        title: New title (1-100 characters). Leave empty to keep current.
        description: New description (max 500 characters). Leave empty to keep current.

    Returns:
        Human-readable confirmation with updated task details, or an error message.
    """
    try:
        tid = UUID(task_id)
    except ValueError:
        return f"Error: Invalid task ID '{task_id}'. Please provide a valid task ID."

    task_data = TaskUpdate(title=title, description=description)
    with Session(engine) as session:
        task = TaskService.update_task(session, tid, task_data, owner_user_id)

    if not task:
        return "Error: Task not found or you don't have permission to update it."

    changes = []
    if title:
        changes.append(f'title to "{title}"')
    if description:
        changes.append(f'description to "{description}"')
    change_text = " and ".join(changes) if changes else "task"

    return (
        f'Successfully updated {change_text}.\n\n'
        f"{_format_task_details(task)}"
    )


@mcp.tool()
def delete_task(
    owner_user_id: str,
    task_id: str,
) -> str:
    """Permanently delete a task.

    Args:
        owner_user_id: The authenticated user's ID.
        task_id: UUID of the task to delete.

    Returns:
        Human-readable confirmation, or an error if the task was not found.
    """
    try:
        tid = UUID(task_id)
    except ValueError:
        return f"Error: Invalid task ID '{task_id}'. Please provide a valid task ID."

    with Session(engine) as session:
        deleted = TaskService.delete_task(session, tid, owner_user_id)

    if not deleted:
        return "Error: Task not found or you don't have permission to delete it."
    return f"Task has been permanently deleted (ID: {task_id})."


@mcp.tool()
def complete_task(
    owner_user_id: str,
    task_id: str,
) -> str:
    """Mark a task as completed.

    Args:
        owner_user_id: The authenticated user's ID.
        task_id: UUID of the task to complete.

    Returns:
        Human-readable confirmation with task title, or an error.
    """
    try:
        tid = UUID(task_id)
    except ValueError:
        return f"Error: Invalid task ID '{task_id}'. Please provide a valid task ID."

    with Session(engine) as session:
        task = TaskService.complete_task(session, tid, owner_user_id)

    if not task:
        return "Error: Task not found or you don't have permission to complete it."
    return (
        f'Task "{task.title}" has been marked as completed.\n\n'
        f"{_format_task_details(task)}"
    )


@mcp.tool()
def incomplete_task(
    owner_user_id: str,
    task_id: str,
) -> str:
    """Mark a completed task as incomplete (reopen it).

    Args:
        owner_user_id: The authenticated user's ID.
        task_id: UUID of the task to mark incomplete.

    Returns:
        Human-readable confirmation with task title, or an error.
    """
    try:
        tid = UUID(task_id)
    except ValueError:
        return f"Error: Invalid task ID '{task_id}'. Please provide a valid task ID."

    with Session(engine) as session:
        task = TaskService.incomplete_task(session, tid, owner_user_id)

    if not task:
        return "Error: Task not found or you don't have permission to update it."
    return (
        f'Task "{task.title}" has been reopened (marked as incomplete).\n\n'
        f"{_format_task_details(task)}"
    )
