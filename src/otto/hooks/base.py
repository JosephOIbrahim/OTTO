"""
Hook Base Classes for OTTO OS
=============================

Provides the foundation for Claude Code hook integration with the
Pheromone Trail system.

Hooks are triggered on specific events and can:
- Read trails for context
- Deposit trails based on outcomes
- Inject context into the system message

ThinkingMachines [He2025] Compliance:
- Hooks execute in FIXED priority order
- Same event → same hooks → same result
- Trail operations are deterministic

Hook Events:
    PRE_TOOL_USE: Before any tool execution (inject context)
    POST_TOOL_USE: After tool execution (deposit trails based on outcome)
    SESSION_START: When a new session begins
    SESSION_END: When a session ends
    IDLE: Periodic maintenance (decay trails, health checks)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class HookEvent(Enum):
    """Events that can trigger hooks."""
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    IDLE = "idle"


@dataclass
class HookContext:
    """
    Context provided to hooks when triggered.

    Contains information about the triggering event and any relevant
    data for the hook to process.

    Attributes:
        event: The type of event that triggered the hook
        timestamp: When the event occurred
        tool_name: Name of tool (for PRE/POST_TOOL_USE events)
        tool_input: Tool input parameters (for PRE/POST_TOOL_USE events)
        tool_output: Tool output (for POST_TOOL_USE only)
        file_path: File being operated on (if applicable)
        session_id: Current session identifier
        user_message: The user's message (if available)
        metadata: Additional context data
    """
    event: HookEvent
    timestamp: datetime = field(default_factory=datetime.now)
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    file_path: Optional[str] = None
    session_id: Optional[str] = None
    user_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_file_operation(self) -> bool:
        """Check if this event involves a file operation."""
        file_tools = {"Edit", "Write", "Read", "NotebookEdit"}
        return self.tool_name in file_tools

    def get_target_path(self) -> Optional[str]:
        """Extract the target file path from tool input."""
        if self.file_path:
            return self.file_path

        if self.tool_input:
            # Try common parameter names
            for key in ["file_path", "path", "notebook_path"]:
                if key in self.tool_input:
                    return self.tool_input[key]

        return None


@dataclass
class HookResult:
    """
    Result returned by a hook after processing.

    Hooks can:
    - Inject additional context into the system message
    - Signal whether to continue or halt processing
    - Return arbitrary data for debugging/logging

    Attributes:
        hook_name: Name of the hook that produced this result
        success: Whether the hook executed successfully
        context_injection: Text to inject into system message
        halt: If True, stop processing further hooks
        trails_deposited: Number of trails deposited
        trails_read: Number of trails read
        data: Additional data returned by the hook
        error: Error message if success is False
    """
    hook_name: str
    success: bool = True
    context_injection: Optional[str] = None
    halt: bool = False
    trails_deposited: int = 0
    trails_read: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class Hook(ABC):
    """
    Abstract base class for hooks.

    Hooks are triggered on specific events and execute in priority order.
    Lower priority numbers execute first.

    Subclasses must implement:
    - events: Which events this hook responds to
    - priority: Execution order (lower = first)
    - process: The actual hook logic

    Example:
        class MyHook(Hook):
            @property
            def name(self) -> str:
                return "my_hook"

            @property
            def events(self) -> List[HookEvent]:
                return [HookEvent.POST_TOOL_USE]

            @property
            def priority(self) -> int:
                return 50

            def process(self, context: HookContext) -> HookResult:
                # Hook logic here
                return HookResult(hook_name=self.name)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this hook."""
        pass

    @property
    @abstractmethod
    def events(self) -> List[HookEvent]:
        """List of events this hook responds to."""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """
        Execution priority (lower = first).

        Recommended ranges:
        - 0-20: Critical system hooks
        - 20-40: Validation hooks
        - 40-60: Context injection hooks
        - 60-80: Trail management hooks
        - 80-100: Logging/observability hooks
        """
        pass

    @abstractmethod
    def process(self, context: HookContext) -> HookResult:
        """
        Process the hook event.

        Args:
            context: Context about the triggering event

        Returns:
            HookResult with processing outcome
        """
        pass

    def should_run(self, context: HookContext) -> bool:
        """
        Check if this hook should run for the given context.

        Override to add custom filtering logic beyond event type matching.

        Args:
            context: Context about the triggering event

        Returns:
            True if the hook should process this event
        """
        return context.event in self.events

    def is_otto_file(self, path: Optional[str]) -> bool:
        """
        Check if a path is within the OTTO OS codebase.

        Args:
            path: File path to check

        Returns:
            True if path is in OTTO OS
        """
        if not path:
            return False

        # Normalize path separators
        normalized = path.replace("\\", "/").lower()

        otto_patterns = [
            "otto_os/",
            "otto-os/",
            "/otto/",
            "src/otto/",
        ]

        return any(pattern in normalized for pattern in otto_patterns)


class HookRegistry:
    """
    Registry and executor for hooks.

    Manages hook registration and executes hooks in priority order
    for each event type.

    Attributes:
        hooks: List of registered hooks
    """

    def __init__(self):
        self._hooks: List[Hook] = []
        self._sorted = False

    def register(self, hook: Hook) -> None:
        """
        Register a hook.

        Args:
            hook: Hook instance to register
        """
        self._hooks.append(hook)
        self._sorted = False

    def unregister(self, hook_name: str) -> bool:
        """
        Unregister a hook by name.

        Args:
            hook_name: Name of hook to remove

        Returns:
            True if hook was found and removed
        """
        for i, hook in enumerate(self._hooks):
            if hook.name == hook_name:
                self._hooks.pop(i)
                return True
        return False

    def _ensure_sorted(self) -> None:
        """Sort hooks by priority if needed."""
        if not self._sorted:
            # Sort by priority (ascending), then by name for determinism
            self._hooks.sort(key=lambda h: (h.priority, h.name))
            self._sorted = True

    def get_hooks_for_event(self, event: HookEvent) -> List[Hook]:
        """
        Get all hooks that respond to an event, in priority order.

        Args:
            event: Event type

        Returns:
            List of hooks in execution order
        """
        self._ensure_sorted()
        return [h for h in self._hooks if event in h.events]

    def execute(self, context: HookContext) -> List[HookResult]:
        """
        Execute all hooks for an event.

        Hooks are executed in priority order. If any hook returns
        halt=True, execution stops.

        Args:
            context: Context for the event

        Returns:
            List of results from all executed hooks
        """
        results = []
        hooks = self.get_hooks_for_event(context.event)

        for hook in hooks:
            if not hook.should_run(context):
                continue

            try:
                result = hook.process(context)
                results.append(result)

                if result.halt:
                    break

            except Exception as e:
                results.append(HookResult(
                    hook_name=hook.name,
                    success=False,
                    error=str(e),
                ))

        return results

    def get_context_injections(self, results: List[HookResult]) -> str:
        """
        Combine context injections from all hook results.

        Args:
            results: Results from hook execution

        Returns:
            Combined context injection string
        """
        injections = []
        for result in results:
            if result.success and result.context_injection:
                injections.append(result.context_injection)

        return "\n".join(injections) if injections else ""


# =============================================================================
# Global Registry
# =============================================================================

_registry: Optional[HookRegistry] = None


def get_registry() -> HookRegistry:
    """Get or create the global hook registry."""
    global _registry
    if _registry is None:
        _registry = HookRegistry()
    return _registry


def register_hook(hook: Hook) -> None:
    """Register a hook in the global registry."""
    get_registry().register(hook)


def execute_hooks(context: HookContext) -> List[HookResult]:
    """Execute hooks for an event using the global registry."""
    return get_registry().execute(context)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "HookEvent",
    # Dataclasses
    "HookContext",
    "HookResult",
    # Base class
    "Hook",
    # Registry
    "HookRegistry",
    "get_registry",
    "register_hook",
    "execute_hooks",
]
