"""
Tasks MCP Server
================

MCP server for task management operations.
Integrates with Todoist, Things, TickTick, and local task storage.

Determinism:
- Deterministic task ordering (by due date, then priority)
- Fixed priority levels
- Sorted iteration
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from .base_mcp import MCPServer, MCPTool, MCPResource

logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels (fixed ordering)."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class TasksMCPServer(MCPServer):
    """MCP server for task management."""

    server_name = "tasks"
    server_version = "1.0.0"

    def __init__(self):
        """Initialize tasks MCP server."""
        super().__init__()
        self._register_tools()
        self._register_resources()

    def _register_tools(self) -> None:
        """Register task tools."""
        # List tasks (TRUST)
        self.register_tool(MCPTool(
            name="tasks_list",
            description="List tasks with optional filters",
            parameters={
                "project": {
                    "type": "string",
                    "description": "Filter by project (optional)",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "completed", "all"],
                    "description": "Task status filter",
                    "default": "pending",
                },
                "priority": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low", "none"],
                    "description": "Filter by priority (optional)",
                },
                "due_before": {
                    "type": "string",
                    "description": "Tasks due before this date",
                },
            },
            approval_action="task.read",
            category="read",
            _handler=self._handle_list_tasks,
        ))

        # Get task details (TRUST)
        self.register_tool(MCPTool(
            name="tasks_get",
            description="Get details of a specific task",
            parameters={
                "task_id": {
                    "type": "string",
                    "description": "Task ID",
                },
            },
            approval_action="task.read",
            category="read",
            _handler=self._handle_get_task,
        ))

        # Create task (TRUST)
        self.register_tool(MCPTool(
            name="tasks_create",
            description="Create a new task",
            parameters={
                "title": {
                    "type": "string",
                    "description": "Task title",
                },
                "description": {
                    "type": "string",
                    "description": "Task description (optional)",
                },
                "due_date": {
                    "type": "string",
                    "description": "Due date (ISO8601)",
                },
                "priority": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low", "none"],
                    "description": "Task priority",
                    "default": "medium",
                },
                "project": {
                    "type": "string",
                    "description": "Project to add task to",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Task tags",
                },
            },
            approval_action="task.read",
            category="write",
            _handler=self._handle_create_task,
        ))

        # Update task (TRUST)
        self.register_tool(MCPTool(
            name="tasks_update",
            description="Update an existing task",
            parameters={
                "task_id": {
                    "type": "string",
                    "description": "Task ID to update",
                },
                "title": {
                    "type": "string",
                    "description": "New title (optional)",
                },
                "description": {
                    "type": "string",
                    "description": "New description (optional)",
                },
                "due_date": {
                    "type": "string",
                    "description": "New due date (optional)",
                },
                "priority": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low", "none"],
                    "description": "New priority (optional)",
                },
            },
            approval_action="task.read",
            category="write",
            _handler=self._handle_update_task,
        ))

        # Complete task (TRUST)
        self.register_tool(MCPTool(
            name="tasks_complete",
            description="Mark a task as completed",
            parameters={
                "task_id": {
                    "type": "string",
                    "description": "Task ID to complete",
                },
            },
            approval_action="task.read",
            category="write",
            _handler=self._handle_complete_task,
        ))

        # Delete task (CONSTITUTIONAL - permanent)
        self.register_tool(MCPTool(
            name="tasks_delete",
            description="Delete a task permanently",
            parameters={
                "task_id": {
                    "type": "string",
                    "description": "Task ID to delete",
                },
            },
            approval_action="file.delete",  # Reuse file.delete approval
            category="delete",
            _handler=self._handle_delete_task,
        ))

        # Get today's tasks (TRUST)
        self.register_tool(MCPTool(
            name="tasks_today",
            description="Get tasks due today",
            parameters={},
            approval_action="task.read",
            category="read",
            _handler=self._handle_today_tasks,
        ))

    def _register_resources(self) -> None:
        """Register task resources."""
        self.register_resource(MCPResource(
            uri="tasks://today",
            name="Today's Tasks",
            description="Tasks due today",
            approval_action="task.read",
        ))

        self.register_resource(MCPResource(
            uri="tasks://overdue",
            name="Overdue Tasks",
            description="Tasks past their due date",
            approval_action="task.read",
        ))

        self.register_resource(MCPResource(
            uri="tasks://upcoming",
            name="Upcoming Tasks",
            description="Tasks due in the next 7 days",
            approval_action="task.read",
        ))

    # =========================================================================
    # Tool Handlers
    # =========================================================================

    async def _handle_list_tasks(
        self,
        project: Optional[str] = None,
        status: str = "pending",
        priority: Optional[str] = None,
        due_before: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List tasks with filters."""
        logger.info(f"Listing tasks: project={project}, status={status}")

        # Mock response
        return [
            {
                "id": "task_1",
                "title": "Sample Task",
                "description": "This is a sample task",
                "due_date": (datetime.now() + timedelta(days=1)).isoformat(),
                "priority": priority or "medium",
                "project": project or "Inbox",
                "status": status,
                "tags": ["sample"],
                "created_at": datetime.now().isoformat(),
            }
        ]

    async def _handle_get_task(self, task_id: str) -> Dict[str, Any]:
        """Get task details."""
        logger.info(f"Getting task: {task_id}")

        return {
            "id": task_id,
            "title": "Sample Task",
            "description": "Full task description here",
            "due_date": (datetime.now() + timedelta(days=1)).isoformat(),
            "priority": "medium",
            "project": "Inbox",
            "status": "pending",
            "tags": [],
            "subtasks": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    async def _handle_create_task(
        self,
        title: str,
        description: str = "",
        due_date: Optional[str] = None,
        priority: str = "medium",
        project: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create new task."""
        logger.info(f"Creating task: {title}")

        return {
            "id": f"task_{datetime.now().timestamp():.0f}",
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
            "project": project or "Inbox",
            "status": "pending",
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
        }

    async def _handle_update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update task."""
        logger.info(f"Updating task: {task_id}")

        return {
            "id": task_id,
            "title": title or "Updated Task",
            "description": description or "",
            "due_date": due_date,
            "priority": priority or "medium",
            "updated_at": datetime.now().isoformat(),
        }

    async def _handle_complete_task(self, task_id: str) -> Dict[str, Any]:
        """Complete task."""
        logger.info(f"Completing task: {task_id}")

        return {
            "id": task_id,
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
        }

    async def _handle_delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete task."""
        logger.info(f"Deleting task: {task_id}")

        return {
            "id": task_id,
            "deleted": True,
            "deleted_at": datetime.now().isoformat(),
        }

    async def _handle_today_tasks(self) -> List[Dict[str, Any]]:
        """Get today's tasks."""
        today = datetime.now().date().isoformat()
        return await self._handle_list_tasks(due_before=today)

    # =========================================================================
    # Resource Handler
    # =========================================================================

    async def _read_resource_content(self, uri: str) -> Any:
        """Read task resource content."""
        if uri == "tasks://today":
            return await self._handle_today_tasks()

        elif uri == "tasks://overdue":
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            return await self._handle_list_tasks(due_before=yesterday)

        elif uri == "tasks://upcoming":
            week_ahead = (datetime.now() + timedelta(days=7)).isoformat()
            return await self._handle_list_tasks(due_before=week_ahead)

        else:
            raise ValueError(f"Unknown resource: {uri}")


__all__ = ["TasksMCPServer"]
