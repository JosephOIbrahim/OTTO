"""
Trail Context Injection Hook
=============================

Injects trail context before file operations, providing Claude with
information about:
- Quality status (he2025_compliant, violations)
- Related files (dependencies, used_by)
- Recent work (currently editing, mid_refactor)
- Historical decisions

Also detects potential collision when another session is editing.

ThinkingMachines [He2025] Compliance:
- Trails read in deterministic order
- Context format is consistent
- Same trails → same context injection
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .base import Hook, HookContext, HookEvent, HookResult
from ..trails import Trail, TrailStore, TrailType, TrailQuery, get_store


# =============================================================================
# Context Formatting
# =============================================================================

def format_quality_trails(trails: List[Trail]) -> List[str]:
    """
    Format QUALITY trails for context injection.

    Args:
        trails: Quality trails to format

    Returns:
        List of formatted context lines
    """
    lines = []

    # Check for compliance status
    compliant = any(t.signal == "he2025_compliant" for t in trails)
    violations = [t for t in trails if "violation" in t.signal]
    partial = any(t.signal == "he2025_partial" for t in trails)

    if compliant:
        lines.append("- [He2025] Compliant")
    elif partial:
        lines.append(f"- [He2025] Partial compliance ({len(violations)} issues)")
    elif violations:
        for v in violations[:3]:  # Limit to first 3
            # Extract line number from signal like "he2025_violation:type:line45"
            parts = v.signal.split(":")
            if len(parts) >= 3:
                lines.append(f"- [He2025] Violation at line {parts[-1].replace('line', '')}")

    # Check for import cleanliness
    clean_imports = any("imports_clean" in t.signal for t in trails)
    if clean_imports:
        lines.append("- Imports: Clean")

    # Check for test coverage
    tested = any("tested" in t.signal or "has_tests" in t.signal for t in trails)
    if tested:
        lines.append("- Tests: Present")

    return lines


def format_context_trails(trails: List[Trail]) -> List[str]:
    """
    Format CONTEXT trails (dependencies, relationships).

    Args:
        trails: Context trails to format

    Returns:
        List of formatted context lines
    """
    lines = []

    deps = []
    used_by = []

    for trail in trails:
        if trail.signal.startswith("depends_on:"):
            deps.append(trail.signal[len("depends_on:"):])
        elif trail.signal.startswith("used_by:"):
            used_by.append(trail.signal[len("used_by:"):])

    if deps:
        lines.append(f"- Depends on: {', '.join(deps[:5])}")
        if len(deps) > 5:
            lines.append(f"  (+{len(deps) - 5} more)")

    if used_by:
        lines.append(f"- Used by: {', '.join(used_by[:5])}")
        if len(used_by) > 5:
            lines.append(f"  (+{len(used_by) - 5} more)")

    return lines


def format_decision_trails(trails: List[Trail]) -> List[str]:
    """
    Format DECISION trails (historical choices).

    Args:
        trails: Decision trails to format

    Returns:
        List of formatted context lines
    """
    lines = []

    for trail in trails[:3]:  # Limit to 3 most recent decisions
        signal = trail.signal
        if signal.startswith("chose:"):
            # Format: "chose:sorted_max|reason:determinism"
            parts = signal[len("chose:"):].split("|")
            choice = parts[0]
            reason = ""
            for part in parts[1:]:
                if part.startswith("reason:"):
                    reason = part[len("reason:"):]
                    break
            if reason:
                lines.append(f"- Decision: {choice} (because {reason})")
            else:
                lines.append(f"- Decision: {choice}")

    return lines


def format_work_trails(trails: List[Trail], session_id: Optional[str]) -> List[str]:
    """
    Format WORK trails and detect collisions.

    Args:
        trails: Work trails to format
        session_id: Current session ID for collision detection

    Returns:
        List of formatted context lines
    """
    lines = []
    collision = False

    for trail in trails:
        # Check for collision (another session editing)
        if "currently_editing" in trail.signal:
            if session_id and trail.deposited_by != session_id:
                collision = True
                lines.append(f"- WARNING: Another session is editing this file")

        if "mid_refactor" in trail.signal:
            lines.append("- Note: File is mid-refactor")

        if "recently_edited" in trail.signal:
            # Check how recently
            elapsed = datetime.now() - trail.deposited_at
            if elapsed < timedelta(hours=1):
                lines.append("- Recently edited (< 1 hour ago)")
            elif elapsed < timedelta(days=1):
                lines.append("- Edited today")

    return lines


def format_pattern_trails(trails: List[Trail]) -> List[str]:
    """
    Format PATTERN trails (learned approaches).

    Args:
        trails: Pattern trails to format

    Returns:
        List of formatted context lines
    """
    lines = []

    for trail in trails[:3]:  # Limit to top 3 patterns
        signal = trail.signal

        if signal.startswith("when_stuck:"):
            tip = signal[len("when_stuck:"):]
            lines.append(f"- Tip: {tip}")

        if signal.startswith("pattern:"):
            pattern = signal[len("pattern:"):]
            lines.append(f"- Pattern: {pattern}")

    return lines


# =============================================================================
# Hook Implementation
# =============================================================================

class TrailContextHook(Hook):
    """
    Injects trail context before file operations.

    Triggers: PRE_TOOL_USE on Edit/Write/Read for OTTO files
    Injects: Summary of trails for target file
    Detects: Potential collision with other sessions
    """

    def __init__(self, store: Optional[TrailStore] = None):
        """
        Initialize the trail context hook.

        Args:
            store: TrailStore instance (uses default if not provided)
        """
        self._store = store

    @property
    def store(self) -> TrailStore:
        """Get the trail store, creating default if needed."""
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def name(self) -> str:
        return "trail_context"

    @property
    def events(self) -> List[HookEvent]:
        return [HookEvent.PRE_TOOL_USE]

    @property
    def priority(self) -> int:
        return 45  # Context injection in middle priority

    def should_run(self, context: HookContext) -> bool:
        """Only run for file operations on OTTO files."""
        if context.event != HookEvent.PRE_TOOL_USE:
            return False

        if context.tool_name not in {"Edit", "Write", "Read"}:
            return False

        path = context.get_target_path()
        return self.is_otto_file(path)

    def process(self, context: HookContext) -> HookResult:
        """
        Read trails and inject context.

        Args:
            context: Hook context with tool information

        Returns:
            HookResult with trail context injection
        """
        path = context.get_target_path()
        if not path:
            return HookResult(
                hook_name=self.name,
                success=False,
                error="No file path found in context",
            )

        # Read all trails for this path
        trails = self.store.read_trails(path)

        if not trails:
            return HookResult(
                hook_name=self.name,
                success=True,
                trails_read=0,
                data={"file": path, "has_trails": False},
            )

        # Group trails by type
        by_type: Dict[TrailType, List[Trail]] = {}
        for trail in trails:
            if trail.trail_type not in by_type:
                by_type[trail.trail_type] = []
            by_type[trail.trail_type].append(trail)

        # Build context sections
        sections = []

        # Quality section
        quality_trails = by_type.get(TrailType.QUALITY, [])
        if quality_trails:
            quality_lines = format_quality_trails(quality_trails)
            if quality_lines:
                sections.append("Quality:\n" + "\n".join(quality_lines))

        # Context section (dependencies)
        context_trails = by_type.get(TrailType.CONTEXT, [])
        if context_trails:
            context_lines = format_context_trails(context_trails)
            if context_lines:
                sections.append("Relationships:\n" + "\n".join(context_lines))

        # Work section (recent activity)
        work_trails = by_type.get(TrailType.WORK, [])
        if work_trails:
            work_lines = format_work_trails(work_trails, context.session_id)
            if work_lines:
                sections.append("Activity:\n" + "\n".join(work_lines))

        # Pattern section
        pattern_trails = by_type.get(TrailType.PATTERN, [])
        if pattern_trails:
            pattern_lines = format_pattern_trails(pattern_trails)
            if pattern_lines:
                sections.append("Patterns:\n" + "\n".join(pattern_lines))

        # Decision section
        decision_trails = by_type.get(TrailType.DECISION, [])
        if decision_trails:
            decision_lines = format_decision_trails(decision_trails)
            if decision_lines:
                sections.append("History:\n" + "\n".join(decision_lines))

        # Build final context injection
        context_injection = None
        if sections:
            context_injection = (
                f"\n[Trail Context for {path}]\n" +
                "\n\n".join(sections) +
                "\n[End Trail Context]\n"
            )

        return HookResult(
            hook_name=self.name,
            success=True,
            context_injection=context_injection,
            trails_read=len(trails),
            data={
                "file": path,
                "trail_counts": {t.value: len(ts) for t, ts in by_type.items()},
            },
        )


class WorkTrailHook(Hook):
    """
    Deposits WORK trails when editing begins/ends.

    Triggers:
        - PRE_TOOL_USE on Edit/Write: Deposit "currently_editing"
        - POST_TOOL_USE on Edit/Write: Update to "recently_edited"
    """

    def __init__(self, store: Optional[TrailStore] = None):
        """
        Initialize the work trail hook.

        Args:
            store: TrailStore instance (uses default if not provided)
        """
        self._store = store

    @property
    def store(self) -> TrailStore:
        """Get the trail store, creating default if needed."""
        if self._store is None:
            self._store = get_store()
        return self._store

    @property
    def name(self) -> str:
        return "work_trail"

    @property
    def events(self) -> List[HookEvent]:
        return [HookEvent.PRE_TOOL_USE, HookEvent.POST_TOOL_USE]

    @property
    def priority(self) -> int:
        return 70  # Trail management runs later

    def should_run(self, context: HookContext) -> bool:
        """Only run for Edit/Write on OTTO files."""
        if context.tool_name not in {"Edit", "Write"}:
            return False

        path = context.get_target_path()
        return self.is_otto_file(path)

    def process(self, context: HookContext) -> HookResult:
        """
        Deposit work trail.

        Args:
            context: Hook context with tool information

        Returns:
            HookResult with trail deposit outcome
        """
        path = context.get_target_path()
        if not path:
            return HookResult(
                hook_name=self.name,
                success=False,
                error="No file path found in context",
            )

        session_id = context.session_id or "unknown_session"

        if context.event == HookEvent.PRE_TOOL_USE:
            # Starting edit - deposit currently_editing
            self.store.deposit(Trail(
                trail_type=TrailType.WORK,
                path=path,
                signal="currently_editing",
                deposited_by=session_id,
                half_life_days=0.042,  # ~1 hour half-life
            ))
        else:
            # Finished edit - deposit recently_edited
            self.store.deposit(Trail(
                trail_type=TrailType.WORK,
                path=path,
                signal="recently_edited",
                deposited_by=session_id,
                half_life_days=1.0,  # 1 day half-life
            ))

            # Weaken currently_editing
            self.store.weaken(
                path=path,
                signal="currently_editing",
                trail_type=TrailType.WORK,
                reduction=1.0,  # Remove it
            )

        return HookResult(
            hook_name=self.name,
            success=True,
            trails_deposited=1,
            data={"event": context.event.value, "file": path},
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TrailContextHook",
    "WorkTrailHook",
    "format_quality_trails",
    "format_context_trails",
    "format_decision_trails",
    "format_work_trails",
    "format_pattern_trails",
]
