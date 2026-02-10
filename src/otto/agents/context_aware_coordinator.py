"""
Context-Aware Agent Coordinator
===============================

Extends AgentCoordinator with external context awareness.

Bridges:
- Agent system (work/delegate/protect decisions)
- Integration system (calendar, task context)
- Protection system (burnout, energy limits)

Philosophy:
    External context is INFORMATION, not control. A busy calendar
    doesn't prevent agent spawning - it adjusts cognitive budget.
    The user remains in control.

Determinism:
- FIXED adjustment factors (no runtime modification)
- DETERMINISTIC: Same context → Same budget adjustment
- State snapshot before any decision
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from ..agent_coordinator import (
    AgentCoordinator,
    CognitiveContext,
    Decision,
    DecisionMode,
    TaskProfile,
)
from ..integration.manager import IntegrationManager
from ..integration.models import (
    CalendarContext,
    ContextSignal,
    ExternalContext,
    TaskContext,
)
from ..protection import ProtectionEngine, ProtectionAction

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (FIXED - ThinkingMachines compliant)
# =============================================================================

# Budget adjustments based on external context
CALENDAR_BUSY_ADJUSTMENT = -0.15      # Heavy calendar reduces budget
CALENDAR_LIGHT_ADJUSTMENT = 0.05      # Light calendar slight increase
DEADLINE_APPROACHING_ADJUSTMENT = -0.10  # Deadline pressure
TASK_OVERLOAD_ADJUSTMENT = -0.20      # Task overload reduces capacity
TASK_MANAGEABLE_ADJUSTMENT = 0.05     # Clean task list slight boost

# Max parallel agents reduction when externally loaded
EXTERNAL_LOAD_AGENT_REDUCTION = 1  # Reduce by 1 when heavy external load


# =============================================================================
# Enhanced Cognitive Context
# =============================================================================

@dataclass
class EnhancedCognitiveContext(CognitiveContext):
    """
    Cognitive context enhanced with external signals.

    Adds external context signals that adjust cognitive budget
    and agent capacity without overriding user control.
    """

    # External context signals
    calendar_busy_level: str = "light"  # light, moderate, heavy
    task_load_level: str = "manageable"  # light, manageable, heavy, overloaded
    has_approaching_deadline: bool = False
    external_context_available: bool = False

    # Raw signals for debugging
    context_signals: list = None

    def __post_init__(self):
        if self.context_signals is None:
            self.context_signals = []

    def cognitive_budget(self) -> float:
        """
        Calculate cognitive budget including external factors.

        External factors ADJUST budget, they don't control it.
        User's internal state (energy, burnout) remains primary.
        """
        # Start with base calculation
        base_budget = super().cognitive_budget()

        # Apply external adjustments
        adjustment = 0.0

        # Calendar load
        if self.calendar_busy_level == "heavy":
            adjustment += CALENDAR_BUSY_ADJUSTMENT
        elif self.calendar_busy_level == "light":
            adjustment += CALENDAR_LIGHT_ADJUSTMENT

        # Task load
        if self.task_load_level == "overloaded":
            adjustment += TASK_OVERLOAD_ADJUSTMENT
        elif self.task_load_level in ("light", "manageable"):
            adjustment += TASK_MANAGEABLE_ADJUSTMENT

        # Deadline pressure
        if self.has_approaching_deadline:
            adjustment += DEADLINE_APPROACHING_ADJUSTMENT

        # Apply adjustment (bounded)
        adjusted = max(0.0, min(1.0, base_budget + adjustment))

        logger.debug(
            f"Budget: base={base_budget:.2f}, adjustment={adjustment:.2f}, "
            f"final={adjusted:.2f}"
        )

        return adjusted

    def effective_max_agents(self) -> int:
        """
        Get effective max agents considering external load.

        Heavy external load reduces parallel agent capacity
        to avoid overwhelming user with too much context.
        """
        base_max = self.max_parallel_agents

        # Reduce if heavily loaded externally
        if (self.calendar_busy_level == "heavy" or
            self.task_load_level == "overloaded"):
            return max(1, base_max - EXTERNAL_LOAD_AGENT_REDUCTION)

        return base_max

    def can_accept_new_agent(self) -> bool:
        """Check if we can spawn another agent, with external awareness."""
        effective_max = self.effective_max_agents()

        return (
            self.active_agents < effective_max and
            self.working_memory_used < self.working_memory_limit and
            self.burnout_level not in ("ORANGE", "RED") and
            self.energy_level != "depleted"
        )


# =============================================================================
# Context-Aware Coordinator
# =============================================================================

class ContextAwareCoordinator(AgentCoordinator):
    """
    Agent coordinator with external context awareness.

    Extends AgentCoordinator to consider:
    - Calendar context (busy level, upcoming meetings)
    - Task context (overdue count, load level)
    - Protection decisions (burnout gates)

    Usage:
        coordinator = ContextAwareCoordinator(
            integration_manager=manager,
            protection_engine=protection
        )

        # Decisions now consider external context
        decision = coordinator.decide(task_profile)
    """

    def __init__(
        self,
        cognitive_stage=None,
        integration_manager: Optional[IntegrationManager] = None,
        protection_engine: Optional[ProtectionEngine] = None,
        **kwargs,
    ):
        """
        Initialize context-aware coordinator.

        Args:
            cognitive_stage: USD cognitive stage (optional)
            integration_manager: External context provider (optional)
            protection_engine: Protection decision engine (optional)
            **kwargs: Additional args passed to AgentCoordinator
        """
        super().__init__(cognitive_stage=cognitive_stage, **kwargs)
        self.integration_manager = integration_manager
        self.protection_engine = protection_engine

        # Cache for external context (avoid frequent async calls)
        self._cached_external_context: Optional[ExternalContext] = None
        self._context_cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 30  # Cache for 30 seconds

    async def get_external_context(self) -> Optional[ExternalContext]:
        """
        Get external context from integration manager.

        Uses caching to avoid excessive async calls.
        """
        if not self.integration_manager:
            return None

        # Check cache
        now = datetime.now()
        if (self._cached_external_context and
            self._context_cache_time and
            (now - self._context_cache_time).total_seconds() < self._cache_ttl_seconds):
            return self._cached_external_context

        # Fetch fresh context
        try:
            context = await self.integration_manager.get_context()
            self._cached_external_context = context
            self._context_cache_time = now
            return context
        except Exception as e:
            logger.warning(f"Failed to get external context: {e}")
            return None

    def get_cognitive_context(self) -> EnhancedCognitiveContext:
        """
        Get enhanced cognitive context with external signals.

        Note: This is synchronous. External context is fetched
        asynchronously and cached. Use refresh_context() to update.
        """
        # Get base context
        base = super().get_cognitive_context()

        # Enhance with external context
        context = EnhancedCognitiveContext(
            # Copy base fields
            energy_level=base.energy_level,
            burnout_level=base.burnout_level,
            momentum_phase=base.momentum_phase,
            active_agents=base.active_agents,
            working_memory_used=base.working_memory_used,
            in_flow_state=base.in_flow_state,
            mode=base.mode,
            max_parallel_agents=base.max_parallel_agents,
            max_agent_depth=base.max_agent_depth,
            working_memory_limit=base.working_memory_limit,
        )

        # Add external context if available
        if self._cached_external_context:
            self._apply_external_context(context, self._cached_external_context)

        return context

    def _apply_external_context(
        self,
        context: EnhancedCognitiveContext,
        external: ExternalContext,
    ) -> None:
        """Apply external context to enhanced context."""
        context.external_context_available = True
        context.context_signals = external.get_all_signals()

        # Apply calendar context
        if external.calendar:
            context.calendar_busy_level = external.calendar.busy_level

            # Check deadline signals
            if ContextSignal.DEADLINE_APPROACHING in context.context_signals:
                context.has_approaching_deadline = True

        # Apply task context
        if external.tasks:
            context.task_load_level = external.tasks.load_level

    async def refresh_context(self) -> None:
        """
        Refresh external context cache.

        Call this before making decisions if you need fresh data.
        Forces a fresh fetch, bypassing the cache.
        """
        if not self.integration_manager:
            return

        try:
            # Bypass cache - fetch directly from manager
            context = await self.integration_manager.get_context()
            self._cached_external_context = context
            self._context_cache_time = datetime.now()
        except Exception as e:
            logger.warning(f"Failed to refresh external context: {e}")

    def decide(self, task: TaskProfile) -> Decision:
        """
        Make work/delegate/protect decision with context awareness.

        Extends base decision with:
        - External load awareness (adjusts budget)
        - Protection engine check (respects burnout gates)
        """
        context = self.get_cognitive_context()

        # Log enhanced state
        logger.debug(
            f"Context-aware decision: calendar={context.calendar_busy_level}, "
            f"tasks={context.task_load_level}, budget={context.cognitive_budget():.2f}"
        )

        # Check protection first (if available)
        if self.protection_engine:
            # Import here to avoid circular dependency
            from ..cognitive_state import CognitiveState, BurnoutLevel, EnergyLevel

            # Create minimal cognitive state for protection check
            burnout_map = {
                "GREEN": BurnoutLevel.GREEN,
                "YELLOW": BurnoutLevel.YELLOW,
                "ORANGE": BurnoutLevel.ORANGE,
                "RED": BurnoutLevel.RED,
            }
            energy_map = {
                "high": EnergyLevel.HIGH,
                "medium": EnergyLevel.MEDIUM,
                "low": EnergyLevel.LOW,
                "depleted": EnergyLevel.DEPLETED,
            }

            state = CognitiveState(
                burnout_level=burnout_map.get(context.burnout_level, BurnoutLevel.GREEN),
                energy_level=energy_map.get(context.energy_level, EnergyLevel.MEDIUM),
            )

            decision = self.protection_engine.check(state)

            # If protection requires confirmation, don't delegate
            if decision.action == ProtectionAction.REQUIRE_CONFIRM:
                return Decision(
                    mode=DecisionMode.PROTECT,
                    rationale=f"Protection active: {decision.message}",
                    protect_until="protection_cleared",
                )

        # Proceed with normal decision (budget already adjusted for external context)
        return super().decide(task)

    def get_status(self) -> Dict[str, Any]:
        """Get enhanced coordinator status."""
        status = super().get_status()

        # Add external context info
        if self._cached_external_context:
            status["external_context"] = {
                "available": True,
                "calendar_busy": (
                    self._cached_external_context.calendar.busy_level
                    if self._cached_external_context.calendar else None
                ),
                "task_load": (
                    self._cached_external_context.tasks.load_level
                    if self._cached_external_context.tasks else None
                ),
                "integrations": self._cached_external_context.available_integrations,
                "cache_age_seconds": (
                    (datetime.now() - self._context_cache_time).total_seconds()
                    if self._context_cache_time else None
                ),
            }
        else:
            status["external_context"] = {"available": False}

        return status


# =============================================================================
# Factory Functions
# =============================================================================

def create_context_aware_coordinator(
    integration_manager: Optional[IntegrationManager] = None,
    protection_engine: Optional[ProtectionEngine] = None,
    cognitive_stage=None,
) -> ContextAwareCoordinator:
    """
    Create a context-aware agent coordinator.

    Args:
        integration_manager: For external context (optional)
        protection_engine: For protection decisions (optional)
        cognitive_stage: USD cognitive stage (optional)

    Returns:
        Configured ContextAwareCoordinator
    """
    return ContextAwareCoordinator(
        cognitive_stage=cognitive_stage,
        integration_manager=integration_manager,
        protection_engine=protection_engine,
    )


__all__ = [
    "ContextAwareCoordinator",
    "EnhancedCognitiveContext",
    "create_context_aware_coordinator",
    # Re-export constants for testing
    "CALENDAR_BUSY_ADJUSTMENT",
    "TASK_OVERLOAD_ADJUSTMENT",
]
