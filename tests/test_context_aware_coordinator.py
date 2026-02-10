"""
Tests for Context-Aware Agent Coordinator
=========================================

Tests the enhanced coordinator that integrates external context
with agent decisions.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from otto.agents.context_aware_coordinator import (
    ContextAwareCoordinator,
    EnhancedCognitiveContext,
    create_context_aware_coordinator,
    CALENDAR_BUSY_ADJUSTMENT,
    TASK_OVERLOAD_ADJUSTMENT,
)
from otto.agent_coordinator import (
    CognitiveContext,
    Decision,
    DecisionMode,
    TaskProfile,
)
from otto.integration.models import (
    CalendarContext,
    ContextSignal,
    ExternalContext,
    TaskContext,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def basic_task():
    """Simple task profile."""
    return TaskProfile(
        description="Simple task",
        estimated_complexity="simple",
        parallelizable=False,
        requires_focus=False,
        file_count=1,
        domain="general",
    )


@pytest.fixture
def complex_task():
    """Complex task profile."""
    return TaskProfile(
        description="Complex multi-file refactoring",
        estimated_complexity="complex",
        parallelizable=True,
        requires_focus=True,
        file_count=10,
        domain="implementation",
    )


@pytest.fixture
def light_calendar():
    """Light calendar context."""
    return CalendarContext(
        events_today=1,
        total_busy_minutes_today=30,
        busy_level="light",
    )


@pytest.fixture
def heavy_calendar():
    """Heavy calendar context."""
    return CalendarContext(
        events_today=8,
        total_busy_minutes_today=300,
        busy_level="heavy",
        next_deadline_in_hours=4,
    )


@pytest.fixture
def overloaded_tasks():
    """Overloaded task context."""
    return TaskContext(
        total_tasks=25,
        overdue_count=10,
        load_level="overloaded",
    )


@pytest.fixture
def manageable_tasks():
    """Manageable task context."""
    return TaskContext(
        total_tasks=5,
        overdue_count=0,
        load_level="manageable",
    )


# =============================================================================
# Test: Enhanced Cognitive Context
# =============================================================================

class TestEnhancedCognitiveContext:
    """Tests for EnhancedCognitiveContext."""

    def test_base_budget_calculation(self):
        """Base budget works without external context."""
        context = EnhancedCognitiveContext(
            energy_level="high",
            burnout_level="GREEN",
            momentum_phase="rolling",
            active_agents=0,
            working_memory_used=0,
            in_flow_state=False,
            mode="focused",
        )

        budget = context.cognitive_budget()
        assert 0.8 <= budget <= 1.0  # High energy + GREEN = high budget

    def test_calendar_busy_reduces_budget(self):
        """Heavy calendar reduces cognitive budget."""
        base = EnhancedCognitiveContext(
            energy_level="high",
            burnout_level="GREEN",
            momentum_phase="rolling",
            active_agents=0,
            working_memory_used=0,
            in_flow_state=False,
            mode="focused",
            calendar_busy_level="light",
        )

        heavy = EnhancedCognitiveContext(
            energy_level="high",
            burnout_level="GREEN",
            momentum_phase="rolling",
            active_agents=0,
            working_memory_used=0,
            in_flow_state=False,
            mode="focused",
            calendar_busy_level="heavy",
        )

        # Heavy calendar should have lower budget
        assert heavy.cognitive_budget() < base.cognitive_budget()
        # Difference should be approximately the adjustment factor
        diff = base.cognitive_budget() - heavy.cognitive_budget()
        expected_diff = abs(CALENDAR_BUSY_ADJUSTMENT)
        assert abs(diff - expected_diff) < 0.1

    def test_task_overload_reduces_budget(self):
        """Task overload reduces cognitive budget."""
        manageable = EnhancedCognitiveContext(
            energy_level="high",
            burnout_level="GREEN",
            momentum_phase="rolling",
            active_agents=0,
            working_memory_used=0,
            in_flow_state=False,
            mode="focused",
            task_load_level="manageable",
        )

        overloaded = EnhancedCognitiveContext(
            energy_level="high",
            burnout_level="GREEN",
            momentum_phase="rolling",
            active_agents=0,
            working_memory_used=0,
            in_flow_state=False,
            mode="focused",
            task_load_level="overloaded",
        )

        # Overloaded should have lower budget
        assert overloaded.cognitive_budget() < manageable.cognitive_budget()

    def test_deadline_approaching_reduces_budget(self):
        """Approaching deadline reduces budget."""
        # Use medium energy so adjustments are visible (not capped at 1.0)
        no_deadline = EnhancedCognitiveContext(
            energy_level="medium",
            burnout_level="YELLOW",
            momentum_phase="rolling",
            active_agents=1,
            working_memory_used=1,
            in_flow_state=False,
            mode="focused",
            has_approaching_deadline=False,
        )

        with_deadline = EnhancedCognitiveContext(
            energy_level="medium",
            burnout_level="YELLOW",
            momentum_phase="rolling",
            active_agents=1,
            working_memory_used=1,
            in_flow_state=False,
            mode="focused",
            has_approaching_deadline=True,
        )

        assert with_deadline.cognitive_budget() < no_deadline.cognitive_budget()

    def test_budget_bounded_zero_to_one(self):
        """Budget is always bounded between 0 and 1."""
        # Maximum stress scenario
        stressed = EnhancedCognitiveContext(
            energy_level="depleted",
            burnout_level="RED",
            momentum_phase="crashed",
            active_agents=3,
            working_memory_used=3,
            in_flow_state=False,
            mode="recovery",
            calendar_busy_level="heavy",
            task_load_level="overloaded",
            has_approaching_deadline=True,
        )

        budget = stressed.cognitive_budget()
        assert 0.0 <= budget <= 1.0

        # Maximum relaxed scenario
        relaxed = EnhancedCognitiveContext(
            energy_level="high",
            burnout_level="GREEN",
            momentum_phase="peak",
            active_agents=0,
            working_memory_used=0,
            in_flow_state=True,
            mode="focused",
            calendar_busy_level="light",
            task_load_level="light",
            has_approaching_deadline=False,
        )

        budget = relaxed.cognitive_budget()
        assert 0.0 <= budget <= 1.0

    def test_effective_max_agents_normal(self):
        """Normal context keeps max agents."""
        context = EnhancedCognitiveContext(
            energy_level="high",
            burnout_level="GREEN",
            momentum_phase="rolling",
            active_agents=0,
            working_memory_used=0,
            in_flow_state=False,
            mode="focused",
            max_parallel_agents=3,
            calendar_busy_level="light",
            task_load_level="manageable",
        )

        assert context.effective_max_agents() == 3

    def test_effective_max_agents_reduced_on_heavy_load(self):
        """Heavy external load reduces max agents."""
        context = EnhancedCognitiveContext(
            energy_level="high",
            burnout_level="GREEN",
            momentum_phase="rolling",
            active_agents=0,
            working_memory_used=0,
            in_flow_state=False,
            mode="focused",
            max_parallel_agents=3,
            calendar_busy_level="heavy",
            task_load_level="manageable",
        )

        # Heavy calendar should reduce by 1
        assert context.effective_max_agents() == 2

    def test_effective_max_agents_minimum_one(self):
        """Effective max agents never goes below 1."""
        context = EnhancedCognitiveContext(
            energy_level="high",
            burnout_level="GREEN",
            momentum_phase="rolling",
            active_agents=0,
            working_memory_used=0,
            in_flow_state=False,
            mode="focused",
            max_parallel_agents=1,  # Already at 1
            calendar_busy_level="heavy",
            task_load_level="overloaded",
        )

        # Should not go below 1
        assert context.effective_max_agents() == 1


# =============================================================================
# Test: Context-Aware Coordinator Initialization
# =============================================================================

class TestContextAwareCoordinatorInit:
    """Tests for ContextAwareCoordinator initialization."""

    def test_init_without_dependencies(self):
        """Can initialize without integration manager or protection."""
        coordinator = ContextAwareCoordinator()

        assert coordinator.integration_manager is None
        assert coordinator.protection_engine is None

    def test_init_with_integration_manager(self):
        """Can initialize with integration manager."""
        mock_manager = MagicMock()

        coordinator = ContextAwareCoordinator(
            integration_manager=mock_manager
        )

        assert coordinator.integration_manager is mock_manager

    def test_factory_function(self):
        """Factory function creates coordinator."""
        coordinator = create_context_aware_coordinator()

        assert isinstance(coordinator, ContextAwareCoordinator)


# =============================================================================
# Test: External Context Integration
# =============================================================================

class TestExternalContextIntegration:
    """Tests for external context integration."""

    @pytest.mark.asyncio
    async def test_get_external_context_none_without_manager(self):
        """Returns None if no integration manager."""
        coordinator = ContextAwareCoordinator()

        context = await coordinator.get_external_context()
        assert context is None

    @pytest.mark.asyncio
    async def test_get_external_context_fetches_from_manager(self):
        """Fetches context from integration manager."""
        external = ExternalContext(
            calendar=CalendarContext(busy_level="moderate"),
            tasks=TaskContext(load_level="manageable"),
            last_updated=datetime.now(),
        )

        mock_manager = MagicMock()
        mock_manager.get_context = AsyncMock(return_value=external)

        coordinator = ContextAwareCoordinator(integration_manager=mock_manager)

        result = await coordinator.get_external_context()

        assert result == external
        mock_manager.get_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_external_context_caching(self):
        """External context is cached to avoid excessive calls."""
        external = ExternalContext()

        mock_manager = MagicMock()
        mock_manager.get_context = AsyncMock(return_value=external)

        coordinator = ContextAwareCoordinator(integration_manager=mock_manager)

        # First call
        await coordinator.get_external_context()
        # Second call (should use cache)
        await coordinator.get_external_context()

        # Should only call once (cached)
        assert mock_manager.get_context.call_count == 1

    @pytest.mark.asyncio
    async def test_refresh_context_updates_cache(self):
        """refresh_context() bypasses cache and fetches fresh data."""
        external = ExternalContext()

        mock_manager = MagicMock()
        mock_manager.get_context = AsyncMock(return_value=external)

        coordinator = ContextAwareCoordinator(integration_manager=mock_manager)

        # Initial fetch
        await coordinator.get_external_context()
        assert mock_manager.get_context.call_count == 1

        # Refresh should bypass cache and fetch again
        await coordinator.refresh_context()
        assert mock_manager.get_context.call_count == 2

        # Cache should be updated
        assert coordinator._cached_external_context == external


# =============================================================================
# Test: Decision Making with External Context
# =============================================================================

class TestDecisionMakingWithContext:
    """Tests for decision making with external context."""

    def test_decide_without_external_context(self, basic_task):
        """Decision works without external context."""
        coordinator = ContextAwareCoordinator()

        decision = coordinator.decide(basic_task)

        assert isinstance(decision, Decision)
        assert decision.mode in (DecisionMode.WORK, DecisionMode.DELEGATE, DecisionMode.PROTECT)

    def test_decide_with_cached_external_context(self, basic_task, heavy_calendar):
        """Decision considers cached external context."""
        coordinator = ContextAwareCoordinator()

        # Manually set cached context
        coordinator._cached_external_context = ExternalContext(
            calendar=heavy_calendar,
            tasks=None,
            last_updated=datetime.now(),
        )
        coordinator._context_cache_time = datetime.now()

        # Get enhanced context
        context = coordinator.get_cognitive_context()

        assert isinstance(context, EnhancedCognitiveContext)
        assert context.calendar_busy_level == "heavy"

    def test_heavy_external_load_affects_decisions(self, complex_task):
        """Heavy external load affects delegation decisions."""
        # Light load coordinator
        light_coord = ContextAwareCoordinator()
        light_coord._cached_external_context = ExternalContext(
            calendar=CalendarContext(busy_level="light"),
            tasks=TaskContext(load_level="light"),
            last_updated=datetime.now(),
        )
        light_coord._context_cache_time = datetime.now()

        # Heavy load coordinator
        heavy_coord = ContextAwareCoordinator()
        heavy_coord._cached_external_context = ExternalContext(
            calendar=CalendarContext(busy_level="heavy"),
            tasks=TaskContext(load_level="overloaded"),
            last_updated=datetime.now(),
        )
        heavy_coord._context_cache_time = datetime.now()

        light_context = light_coord.get_cognitive_context()
        heavy_context = heavy_coord.get_cognitive_context()

        # Heavy should have lower budget
        assert heavy_context.cognitive_budget() < light_context.cognitive_budget()


# =============================================================================
# Test: Status Reporting
# =============================================================================

class TestStatusReporting:
    """Tests for status reporting."""

    def test_status_without_external_context(self):
        """Status reports no external context when unavailable."""
        coordinator = ContextAwareCoordinator()

        status = coordinator.get_status()

        assert "external_context" in status
        assert status["external_context"]["available"] is False

    def test_status_with_external_context(self):
        """Status includes external context details."""
        coordinator = ContextAwareCoordinator()
        coordinator._cached_external_context = ExternalContext(
            calendar=CalendarContext(busy_level="moderate"),
            tasks=TaskContext(load_level="manageable"),
            last_updated=datetime.now(),
            available_integrations=["google_calendar", "todoist"],
        )
        coordinator._context_cache_time = datetime.now()

        status = coordinator.get_status()

        assert status["external_context"]["available"] is True
        assert status["external_context"]["calendar_busy"] == "moderate"
        assert status["external_context"]["task_load"] == "manageable"
        assert "google_calendar" in status["external_context"]["integrations"]


# =============================================================================
# Test: Protection Engine Integration
# =============================================================================

class TestProtectionEngineIntegration:
    """Tests for protection engine integration."""

    def test_decide_respects_protection_require_confirm(self, basic_task):
        """Decision respects protection REQUIRE_CONFIRM."""
        from otto.protection import ProtectionDecision, ProtectionAction

        mock_protection = MagicMock()
        mock_protection.check.return_value = ProtectionDecision(
            action=ProtectionAction.REQUIRE_CONFIRM,
            message="You need a break",
        )

        coordinator = ContextAwareCoordinator(protection_engine=mock_protection)

        decision = coordinator.decide(basic_task)

        assert decision.mode == DecisionMode.PROTECT
        assert "Protection active" in decision.rationale

    def test_decide_allows_when_protection_allows(self, basic_task):
        """Decision proceeds when protection allows."""
        from otto.protection import ProtectionDecision, ProtectionAction

        mock_protection = MagicMock()
        mock_protection.check.return_value = ProtectionDecision(
            action=ProtectionAction.ALLOW,
        )

        coordinator = ContextAwareCoordinator(protection_engine=mock_protection)

        decision = coordinator.decide(basic_task)

        # Should make normal decision (WORK for simple task)
        assert decision.mode in (DecisionMode.WORK, DecisionMode.DELEGATE)


# =============================================================================
# Test: Determinism Compliance
# =============================================================================

class TestDeterminismCompliance:
    """Tests for determinism ([He2025])."""

    def test_adjustment_factors_are_fixed(self):
        """Adjustment factors are constants (not runtime configurable)."""
        # These should be module-level constants
        assert isinstance(CALENDAR_BUSY_ADJUSTMENT, float)
        assert isinstance(TASK_OVERLOAD_ADJUSTMENT, float)

    def test_budget_calculation_deterministic(self):
        """Same context produces same budget."""
        def create_context():
            return EnhancedCognitiveContext(
                energy_level="medium",
                burnout_level="YELLOW",
                momentum_phase="building",
                active_agents=1,
                working_memory_used=1,
                in_flow_state=False,
                mode="focused",
                calendar_busy_level="moderate",
                task_load_level="manageable",
                has_approaching_deadline=True,
            )

        ctx1 = create_context()
        ctx2 = create_context()

        assert ctx1.cognitive_budget() == ctx2.cognitive_budget()

    def test_decision_includes_checksum(self, basic_task):
        """Decisions include checksum for traceability."""
        coordinator = ContextAwareCoordinator()

        decision = coordinator.decide(basic_task)

        assert hasattr(decision, "checksum")
        assert len(decision.checksum) > 0
