"""
Task Manager Adapters
=====================

Adapters for task management services (Todoist, Apple Reminders, Things).

Available Adapters:
- TaskAdapter: Base class for all task adapters
- JsonTaskAdapter: File-based adapter for JSON files (no OAuth required)
"""

from .base import TaskAdapter
from .json_adapter import JsonTaskAdapter, create_json_task_adapter

__all__ = [
    "TaskAdapter",
    "JsonTaskAdapter",
    "create_json_task_adapter",
]
