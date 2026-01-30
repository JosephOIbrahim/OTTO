"""
Memory Agent
============

Profile storage and recall agent.

The Memory Agent handles persistent knowledge storage:
- User preferences and calibration data
- Session history and patterns
- Project-specific context
- Cross-session continuity

Philosophy:
    Remember what matters, forget what doesn't.
    Preferences inform behavior; history enables continuity.

ThinkingMachines [He2025] Compliance:
- Fixed memory categories
- Deterministic storage format
- Bounded memory size
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import Agent, AgentConfig, NonRetryableError

logger = logging.getLogger(__name__)


class MemoryCategory:
    """Categories of stored memories."""
    PREFERENCE = "preference"      # User preferences
    CALIBRATION = "calibration"    # Learned calibration data
    SESSION = "session"            # Session history
    PROJECT = "project"            # Project-specific context
    PATTERN = "pattern"            # Detected patterns
    INSIGHT = "insight"            # Cross-session insights


@dataclass
class MemoryEntry:
    """A single memory entry."""
    key: str
    category: str
    value: Any
    confidence: float  # 0.0 to 1.0
    created_at: datetime
    updated_at: datetime
    access_count: int = 0
    source: str = "observation"  # "explicit", "observation", "inference"
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "category": self.category,
            "value": self.value,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "access_count": self.access_count,
            "source": self.source,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        return cls(
            key=data["key"],
            category=data["category"],
            value=data["value"],
            confidence=data["confidence"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            access_count=data.get("access_count", 0),
            source=data.get("source", "observation"),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
        )

    def is_expired(self) -> bool:
        """Check if memory has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass
class MemoryQuery:
    """Query for memory retrieval."""
    category: Optional[str] = None
    key_pattern: Optional[str] = None
    min_confidence: float = 0.0
    include_expired: bool = False
    limit: int = 10


@dataclass
class MemoryResult:
    """Result from memory operations."""
    operation: str  # "store", "recall", "update", "forget"
    success: bool
    entries: List[MemoryEntry] = field(default_factory=list)
    message: str = ""
    affected_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "success": self.success,
            "entries": [e.to_dict() for e in self.entries],
            "message": self.message,
            "affected_count": self.affected_count,
        }


class MemoryAgent(Agent[MemoryResult]):
    """
    Agent for memory storage and retrieval.

    Features:
    - Store preferences and calibration
    - Recall past context
    - Pattern detection
    - Cross-session continuity
    - Automatic expiration

    Example:
        agent = MemoryAgent(storage_path=Path("~/.otto/memory"))
        result = await agent.run(
            "store preference:output_style=concise",
            {"confidence": 0.9, "source": "explicit"}
        )
    """

    agent_type = "memory"

    # Storage limits
    MAX_ENTRIES_PER_CATEGORY = 100
    MAX_TOTAL_ENTRIES = 500

    def __init__(self, config: AgentConfig = None, storage_path: Path = None):
        super().__init__(config)
        self.storage_path = storage_path or Path.home() / ".otto" / "memory"
        self._memory: Dict[str, MemoryEntry] = {}
        self._loaded = False

    def _get_step_count(self) -> int:
        """Memory operations have 3 phases."""
        return 3

    async def _execute(self, task: str, context: Dict[str, Any]) -> MemoryResult:
        """
        Execute memory operation.

        Task format:
        - "store <category>:<key>=<value>"
        - "recall <category>:<key_pattern>"
        - "update <category>:<key>=<value>"
        - "forget <category>:<key_pattern>"
        - "list <category>"

        Phases:
        1. Load memory store
        2. Execute operation
        3. Persist changes
        """
        self.increment_turn()

        # Phase 1: Load
        await self.report_progress(1, "Loading memory store")
        if not self._loaded:
            self._load_memory()

        # Phase 2: Execute
        await self.report_progress(2, "Executing memory operation")
        result = self._execute_operation(task, context)

        # Phase 3: Persist
        await self.report_progress(3, "Persisting changes")
        if result.success and result.operation in ("store", "update", "forget"):
            self._save_memory()

        return result

    def _execute_operation(self, task: str, context: Dict[str, Any]) -> MemoryResult:
        """Parse and execute memory operation."""
        task = task.strip()
        parts = task.split(maxsplit=1)

        if len(parts) < 2:
            return MemoryResult(
                operation="error",
                success=False,
                message="Invalid task format. Expected: <operation> <args>",
            )

        operation = parts[0].lower()
        args = parts[1]

        if operation == "store":
            return self._store(args, context)
        elif operation == "recall":
            return self._recall(args, context)
        elif operation == "update":
            return self._update(args, context)
        elif operation == "forget":
            return self._forget(args, context)
        elif operation == "list":
            return self._list_category(args, context)
        else:
            return MemoryResult(
                operation="error",
                success=False,
                message=f"Unknown operation: {operation}",
            )

    def _store(self, args: str, context: Dict[str, Any]) -> MemoryResult:
        """Store a new memory."""
        # Parse: category:key=value
        try:
            category_key, value = args.split("=", 1)
            category, key = category_key.split(":", 1)
        except ValueError:
            return MemoryResult(
                operation="store",
                success=False,
                message="Invalid store format. Expected: category:key=value",
            )

        # Check limits
        category_entries = [e for e in self._memory.values() if e.category == category]
        if len(category_entries) >= self.MAX_ENTRIES_PER_CATEGORY:
            self._evict_oldest(category)

        if len(self._memory) >= self.MAX_TOTAL_ENTRIES:
            self._evict_oldest()

        # Parse value (try JSON, fall back to string)
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value.strip()

        # Create entry
        full_key = f"{category}:{key}"
        now = datetime.now()

        entry = MemoryEntry(
            key=full_key,
            category=category,
            value=parsed_value,
            confidence=context.get("confidence", 0.5),
            created_at=now,
            updated_at=now,
            source=context.get("source", "observation"),
            expires_at=context.get("expires_at"),
        )

        self._memory[full_key] = entry

        return MemoryResult(
            operation="store",
            success=True,
            entries=[entry],
            message=f"Stored {full_key}",
            affected_count=1,
        )

    def _recall(self, args: str, context: Dict[str, Any]) -> MemoryResult:
        """Recall memories matching pattern."""
        # Parse: category:key_pattern or just key_pattern
        if ":" in args:
            category, key_pattern = args.split(":", 1)
        else:
            category = None
            key_pattern = args

        min_confidence = context.get("min_confidence", 0.0)
        include_expired = context.get("include_expired", False)
        limit = context.get("limit", 10)

        matches = []
        for full_key, entry in self._memory.items():
            # Filter by category
            if category and entry.category != category:
                continue

            # Filter by key pattern
            if key_pattern and key_pattern not in full_key:
                continue

            # Filter by confidence
            if entry.confidence < min_confidence:
                continue

            # Filter by expiration
            if not include_expired and entry.is_expired():
                continue

            # Update access count
            entry.access_count += 1
            matches.append(entry)

            if len(matches) >= limit:
                break

        return MemoryResult(
            operation="recall",
            success=True,
            entries=matches,
            message=f"Found {len(matches)} matching memories",
            affected_count=len(matches),
        )

    def _update(self, args: str, context: Dict[str, Any]) -> MemoryResult:
        """Update an existing memory."""
        try:
            category_key, value = args.split("=", 1)
            category, key = category_key.split(":", 1)
        except ValueError:
            return MemoryResult(
                operation="update",
                success=False,
                message="Invalid update format. Expected: category:key=value",
            )

        full_key = f"{category}:{key}"

        if full_key not in self._memory:
            # Store new if not exists
            return self._store(args, context)

        # Parse value
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value.strip()

        # Update entry
        entry = self._memory[full_key]
        entry.value = parsed_value
        entry.updated_at = datetime.now()
        entry.confidence = max(entry.confidence, context.get("confidence", entry.confidence))

        return MemoryResult(
            operation="update",
            success=True,
            entries=[entry],
            message=f"Updated {full_key}",
            affected_count=1,
        )

    def _forget(self, args: str, context: Dict[str, Any]) -> MemoryResult:
        """Forget memories matching pattern."""
        if ":" in args:
            category, key_pattern = args.split(":", 1)
        else:
            category = None
            key_pattern = args

        to_remove = []
        for full_key, entry in self._memory.items():
            if category and entry.category != category:
                continue
            if key_pattern and key_pattern not in full_key:
                continue
            to_remove.append(full_key)

        for key in to_remove:
            del self._memory[key]

        return MemoryResult(
            operation="forget",
            success=True,
            message=f"Forgot {len(to_remove)} memories",
            affected_count=len(to_remove),
        )

    def _list_category(self, category: str, context: Dict[str, Any]) -> MemoryResult:
        """List all memories in a category."""
        category = category.strip()

        entries = [
            entry for entry in self._memory.values()
            if entry.category == category
        ]

        return MemoryResult(
            operation="list",
            success=True,
            entries=entries,
            message=f"Found {len(entries)} entries in {category}",
            affected_count=len(entries),
        )

    def _evict_oldest(self, category: str = None):
        """Evict oldest entries to make room."""
        entries = list(self._memory.items())

        if category:
            entries = [(k, e) for k, e in entries if e.category == category]

        # Sort by last access (updated_at), oldest first
        entries.sort(key=lambda x: x[1].updated_at)

        # Remove oldest 10%
        to_remove = max(1, len(entries) // 10)
        for i in range(to_remove):
            if i < len(entries):
                del self._memory[entries[i][0]]

    def _load_memory(self):
        """Load memory from disk."""
        self._memory = {}

        memory_file = self.storage_path / "memory.json"
        if memory_file.exists():
            try:
                with open(memory_file, "r") as f:
                    data = json.load(f)

                for entry_data in data.get("entries", []):
                    entry = MemoryEntry.from_dict(entry_data)
                    if not entry.is_expired():
                        self._memory[entry.key] = entry

                logger.debug(f"Loaded {len(self._memory)} memories from disk")

            except Exception as e:
                logger.warning(f"Failed to load memory: {e}")
                self._memory = {}

        self._loaded = True

    def _save_memory(self):
        """Save memory to disk."""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            memory_file = self.storage_path / "memory.json"

            data = {
                "version": 1,
                "saved_at": datetime.now().isoformat(),
                "entries": [e.to_dict() for e in self._memory.values()],
            }

            with open(memory_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self._memory)} memories to disk")

        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            self.add_warning(f"Memory persistence failed: {e}")

    # =========================================================================
    # Direct access methods (for non-task usage)
    # =========================================================================

    def get(self, category: str, key: str, default: Any = None) -> Any:
        """Direct get (synchronous)."""
        if not self._loaded:
            self._load_memory()

        full_key = f"{category}:{key}"
        entry = self._memory.get(full_key)

        if entry and not entry.is_expired():
            entry.access_count += 1
            return entry.value

        return default

    def set(self, category: str, key: str, value: Any, confidence: float = 0.5):
        """Direct set (synchronous)."""
        if not self._loaded:
            self._load_memory()

        full_key = f"{category}:{key}"
        now = datetime.now()

        self._memory[full_key] = MemoryEntry(
            key=full_key,
            category=category,
            value=value,
            confidence=confidence,
            created_at=now,
            updated_at=now,
            source="explicit",
        )

        self._save_memory()


__all__ = [
    "MemoryAgent",
    "MemoryCategory",
    "MemoryEntry",
    "MemoryQuery",
    "MemoryResult",
]
