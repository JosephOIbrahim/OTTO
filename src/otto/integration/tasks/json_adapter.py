"""
JSON Task Adapter
=================

File-based task adapter that reads tasks from JSON files.

This provides task context without requiring OAuth setup:
- Export your tasks as JSON from Todoist, Things, or other apps
- Create a simple JSON file manually
- Point OTTO to the file path
- OTTO reads tasks and calculates context

JSON Format:
    {
        "tasks": [
            {
                "due_date": "2024-01-15",      // ISO date or datetime, optional
                "priority": "high",             // low/normal/high/urgent or 1-4
                "is_completed": false           // optional, defaults to false
            }
        ]
    }

Use Cases:
1. Quick setup without OAuth complexity
2. Task managers without API access
3. Manual task tracking
4. Testing and development

Determinism:
- DETERMINISTIC: Same file → Same tasks → Same context
- FIXED: Parsing rules are immutable
- BOUNDED: Max tasks limit prevents memory issues
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..adapter import IntegrationError
from ..models import IntegrationConfig, IntegrationType
from .base import TaskAdapter

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (FIXED - determinism compliant)
# =============================================================================

MAX_TASKS = 1000         # Prevent memory issues with huge task lists
MAX_FILES = 5            # Max JSON files to read
ENCODING = "utf-8"       # Standard encoding


# =============================================================================
# JSON Task Adapter
# =============================================================================

class JsonTaskAdapter(TaskAdapter):
    """
    JSON file-based task adapter.

    Reads tasks from JSON files and provides task context
    without requiring OAuth or API access.

    Config Settings:
        tasks_path: Path to JSON file or directory containing JSON files

    Example:
        config = IntegrationConfig(
            integration_type=IntegrationType.TASK_MANAGER,
            service_name="json_tasks",
            settings={"tasks_path": "~/.tasks/todos.json"}
        )
        adapter = JsonTaskAdapter(config)
        context = await adapter.get_context()
    """

    SERVICE_NAME = "json_tasks"
    INTEGRATION_TYPE = IntegrationType.TASK_MANAGER
    SUPPORTS_WRITE = False  # Read-only in Phase 5.1

    def __init__(self, config: IntegrationConfig):
        """
        Initialize JSON task adapter.

        Args:
            config: Configuration with 'tasks_path' in settings
        """
        super().__init__(config)
        self._tasks_path: Optional[Path] = None
        self._files: List[Path] = []

    # =========================================================================
    # IntegrationAdapter Implementation
    # =========================================================================

    async def initialize(self) -> bool:
        """
        Initialize adapter by validating the tasks path.

        Returns:
            True if path exists and contains valid JSON files
        """
        tasks_path_str = self.config.settings.get("tasks_path")
        if not tasks_path_str:
            logger.error("JsonTaskAdapter: No 'tasks_path' in config settings")
            return False

        # Expand user path
        self._tasks_path = Path(tasks_path_str).expanduser()

        if not self._tasks_path.exists():
            logger.error(f"JsonTaskAdapter: Path does not exist: {self._tasks_path}")
            return False

        # Find JSON files
        if self._tasks_path.is_file():
            if self._tasks_path.suffix.lower() == ".json":
                self._files = [self._tasks_path]
            else:
                logger.error(f"JsonTaskAdapter: Not a JSON file: {self._tasks_path}")
                return False
        else:
            # Directory - find all JSON files
            self._files = sorted(self._tasks_path.glob("*.json"))[:MAX_FILES]

        if not self._files:
            logger.warning(f"JsonTaskAdapter: No JSON files found in {self._tasks_path}")
            # Still return True - adapter works, just no tasks
            return True

        logger.info(f"JsonTaskAdapter: Found {len(self._files)} JSON file(s)")
        return True

    async def _fetch_raw_tasks(self) -> List[dict]:
        """
        Fetch tasks from JSON files.

        Returns:
            List of task dictionaries
        """
        all_tasks: List[dict] = []

        for json_file in self._files:
            try:
                tasks = self._read_json_file(json_file)
                all_tasks.extend(tasks)

                if len(all_tasks) >= MAX_TASKS:
                    logger.warning(f"Reached max tasks limit ({MAX_TASKS})")
                    break
            except Exception as e:
                logger.warning(f"Failed to read {json_file}: {e}")
                continue

        logger.debug(f"JsonTaskAdapter: Found {len(all_tasks)} tasks")
        return all_tasks

    def _read_json_file(self, path: Path) -> List[dict]:
        """
        Read tasks from a single JSON file.

        Args:
            path: Path to JSON file

        Returns:
            List of task dictionaries

        Supports multiple formats:
        1. {"tasks": [...]} - standard format
        2. [...] - direct array of tasks
        3. {"items": [...]} - alternative key
        """
        try:
            content = path.read_text(encoding=ENCODING)
        except UnicodeDecodeError:
            content = path.read_text(encoding="latin-1")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {path}: {e}")
            return []

        # Handle different JSON structures
        if isinstance(data, list):
            # Direct array of tasks
            tasks = data
        elif isinstance(data, dict):
            # Object with tasks array
            tasks = data.get("tasks") or data.get("items") or data.get("todos") or []
        else:
            return []

        # Filter only valid task dicts
        valid_tasks = []
        for task in tasks:
            if isinstance(task, dict):
                # Only include incomplete tasks by default
                if not task.get("is_completed", False):
                    valid_tasks.append(task)

        return valid_tasks[:MAX_TASKS]


def create_json_task_adapter(tasks_path: str) -> JsonTaskAdapter:
    """
    Factory function to create a JsonTaskAdapter.

    Args:
        tasks_path: Path to JSON file or directory

    Returns:
        Configured JsonTaskAdapter
    """
    config = IntegrationConfig(
        integration_type=IntegrationType.TASK_MANAGER,
        service_name="json_tasks",
        settings={"tasks_path": tasks_path},
    )
    return JsonTaskAdapter(config)


__all__ = [
    "JsonTaskAdapter",
    "create_json_task_adapter",
]
