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


def _task_to_json(task: TaskResponse) -> str:
    """Serialize a TaskResponse to a JSON string for the AI agent."""
    return json.dumps(
        {
            "id": str(task.id),
            "title": task.title,
            "description": task.description,
            "is_completed": task.is_completed,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        },
        indent=2,
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
        JSON string with the created task details including id, title,
        description, is_completed, and created_at.
    """
    task_data = TaskCreate(title=title, description=description)
    with Session(engine) as session:
        task = TaskService.create_task(session, task_data, owner_user_id)
    return _task_to_json(task)


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
        JSON string with a list of tasks and total count metadata.
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

    return json.dumps(
        {
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "description": t.description,
                    "is_completed": t.is_completed,
                    "created_at": t.created_at.isoformat(),
                    "updated_at": t.updated_at.isoformat(),
                }
                for t in filtered
            ],
            "total": len(filtered),
            "status_filter": status_filter,
        },
        indent=2,
    )


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
        JSON string with the updated task details, or an error message if not found.
    """
    try:
        tid = UUID(task_id)
    except ValueError:
        return json.dumps({"error": f"Invalid task ID: {task_id}"})

    task_data = TaskUpdate(title=title, description=description)
    with Session(engine) as session:
        task = TaskService.update_task(session, tid, task_data, owner_user_id)

    if not task:
        return json.dumps({"error": "Task not found or not owned by you."})
    return _task_to_json(task)


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
        JSON confirmation message, or an error if the task was not found.
    """
    try:
        tid = UUID(task_id)
    except ValueError:
        return json.dumps({"error": f"Invalid task ID: {task_id}"})

    with Session(engine) as session:
        deleted = TaskService.delete_task(session, tid, owner_user_id)

    if not deleted:
        return json.dumps({"error": "Task not found or not owned by you."})
    return json.dumps({"message": "Task deleted successfully.", "task_id": task_id})


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
        JSON confirmation with task title and completion timestamp, or an error.
    """
    try:
        tid = UUID(task_id)
    except ValueError:
        return json.dumps({"error": f"Invalid task ID: {task_id}"})

    with Session(engine) as session:
        task = TaskService.complete_task(session, tid, owner_user_id)

    if not task:
        return json.dumps({"error": "Task not found or not owned by you."})
    return json.dumps(
        {
            "message": f'Task "{task.title}" marked as completed.',
            "task_id": str(task.id),
            "title": task.title,
            "completed_at": task.updated_at.isoformat(),
        },
        indent=2,
    )


@mcp.tool()
def incomplete_task(
    owner_user_id: str,
    task_id: str,
) -> str:
    """Mark a completed task as incomplete.

    Args:
        owner_user_id: The authenticated user's ID.
        task_id: UUID of the task to mark incomplete.

    Returns:
        JSON confirmation with task title, or an error if not found.
    """
    try:
        tid = UUID(task_id)
    except ValueError:
        return json.dumps({"error": f"Invalid task ID: {task_id}"})

    with Session(engine) as session:
        task = TaskService.incomplete_task(session, tid, owner_user_id)

    if not task:
        return json.dumps({"error": "Task not found or not owned by you."})
    return json.dumps(
        {
            "message": f'Task "{task.title}" marked as incomplete.',
            "task_id": str(task.id),
            "title": task.title,
        },
        indent=2,
    )
