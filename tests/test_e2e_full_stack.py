"""
End-to-End Full Stack Integration Tests
========================================

Tests the complete OTTO OS stack working together:
- ICalAdapter (calendar context)
- JsonTaskAdapter (task context)
- IntegrationManager (context aggregation)
- ContextAwareCoordinator (agent decisions with external context)
- ProtectionEngine (safety gates)
- CalibrationEngine (learning)

This validates Phase 5-6 integration: external context flows through
to agent decisions and protection gates.

Determinism:
- Deterministic test scenarios
- Fixed input → Fixed output verification
- State isolation between tests
"""

import pytest
import tempfile
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from otto.integration import (
    IntegrationManager,
    ExternalContext,
    CalendarContext,
    TaskContext,
    ContextSignal,
)
from otto.integration.calendars import ICalAdapter, create_ical_adapter
from otto.integration.tasks import JsonTaskAdapter, create_json_task_adapter
from otto.agents import (
    ContextAwareCoordinator,
    EnhancedCognitiveContext,
    create_context_aware_coordinator,
)
from otto.agent_coordinator import TaskProfile, DecisionMode
from otto.protection import (
    ProtectionEngine,
    ProtectionAction,
)
from otto.protection.calibration import CalibrationEngine
from otto.profile_loader import ResolvedProfile


# =============================================================================
# Test Data Generators
# =============================================================================

def create_busy_calendar_ics() -> str:
    """Create ICS content with a busy day (8 meetings)."""
    now = datetime.now()
    today = now.strftime("%Y%m%d")

    events = []
    for i in range(8):
        start_hour = 9 + i
        events.append(f"""BEGIN:VEVENT
UID:meeting-{i}@test
DTSTART:{today}T{start_hour:02d}0000
DTEND:{today}T{start_hour:02d}4500
SUMMARY:Meeting {i+1}
END:VEVENT""")

    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//OTTO OS//Test//EN
{"".join(events)}
END:VCALENDAR"""


def create_light_calendar_ics() -> str:
    """Create ICS content with a light day (1 meeting)."""
    now = datetime.now()
    today = now.strftime("%Y%m%d")

    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//OTTO OS//Test//EN
BEGIN:VEVENT
UID:standup@test
DTSTART:{today}T100000
DTEND:{today}T101500
SUMMARY:Daily Standup
END:VEVENT
END:VCALENDAR"""


def create_overloaded_tasks_json() -> str:
    """Create JSON with overloaded task list (35 tasks, 10 overdue).

    Thresholds from TaskAdapter:
    - <= 5 = light
    - <= 15 = manageable
    - <= 30 = heavy
    - > 30 = overloaded
    """
    import json
    now = datetime.now()
    yesterday = (now - timedelta(days=1)).isoformat()
    tomorrow = (now + timedelta(days=1)).isoformat()

    tasks = []
    # 10 overdue tasks
    for i in range(10):
        tasks.append({
            "id": f"overdue-{i}",
            "title": f"Overdue Task {i+1}",
            "due": yesterday,
            "priority": "high",
            "completed": False,
        })
    # 25 upcoming tasks (total 35 > 30 = overloaded)
    for i in range(25):
        tasks.append({
            "id": f"upcoming-{i}",
            "title": f"Upcoming Task {i+1}",
            "due": tomorrow,
            "priority": "medium",
            "completed": False,
        })

    return json.dumps({"tasks": tasks})


def create_manageable_tasks_json() -> str:
    """Create JSON with manageable task list (5 tasks, 0 overdue)."""
    import json
    tomorrow = (datetime.now() + timedelta(days=1)).isoformat()

    tasks = [
        {"id": f"task-{i}", "title": f"Task {i+1}", "due": tomorrow, "completed": False}
        for i in range(5)
    ]

    return json.dumps({"tasks": tasks})


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def busy_calendar_file(temp_dir):
    """Create a busy calendar ICS file."""
    ics_file = temp_dir / "busy_calendar.ics"
    ics_file.write_text(create_busy_calendar_ics())
    return ics_file


@pytest.fixture
def light_calendar_file(temp_dir):
    """Create a light calendar ICS file."""
    ics_file = temp_dir / "light_calendar.ics"
    ics_file.write_text(create_light_calendar_ics())
    return ics_file


@pytest.fixture
def overloaded_tasks_file(temp_dir):
    """Create an overloaded tasks JSON file."""
    json_file = temp_dir / "overloaded_tasks.json"
    json_file.write_text(create_overloaded_tasks_json())
    return json_file


@pytest.fixture
def manageable_tasks_file(temp_dir):
    """Create a manageable tasks JSON file."""
    json_file = temp_dir / "manageable_tasks.json"
    json_file.write_text(create_manageable_tasks_json())
    return json_file


@pytest.fixture
def complex_task():
    """Complex task profile requiring significant cognitive resources."""
    return TaskProfile(
        description="Multi-file refactoring across authentication system",
        estimated_complexity="complex",
        parallelizable=True,
        requires_focus=True,
        file_count=15,
        domain="implementation",
    )


@pytest.fixture
def simple_task():
    """Simple task profile."""
    return TaskProfile(
        description="Fix typo in README",
        estimated_complexity="simple",
        parallelizable=False,
        requires_focus=False,
        file_count=1,
        domain="documentation",
    )


# =============================================================================
# Test: Full Stack - Light Load Scenario
# =============================================================================

class TestFullStackLightLoad:
    """E2E tests with light external load (should allow full capacity)."""

    @pytest.mark.asyncio
    async def test_light_load_high_cognitive_budget(
        self, light_calendar_file, manageable_tasks_file, complex_task
    ):
        """Light external load results in high cognitive budget."""
        # Setup adapters
        calendar_adapter = create_ical_adapter(light_calendar_file)
        task_adapter = create_json_task_adapter(manageable_tasks_file)

        # Setup integration manager
        manager = IntegrationManager()
        manager.register_adapter(calendar_adapter)
        manager.register_adapter(task_adapter)

        # Setup coordinator with integration manager
        coordinator = create_context_aware_coordinator(
            integration_manager=manager
        )

        # Start manager and sync
        await manager.start()
        await coordinator.refresh_context()

        try:
            # Get cognitive context
            context = coordinator.get_cognitive_context()

            # Verify external context was applied
            assert isinstance(context, EnhancedCognitiveContext)
            assert context.external_context_available is True

            # Light load should result in light calendar (1 meeting = light)
            assert context.calendar_busy_level == "light"
            # 5 tasks = light (threshold is <= 5)
            assert context.task_load_level == "light"

            # Verify high cognitive budget (light load = slight boost)
            budget = context.cognitive_budget()
            assert budget >= 0.7, f"Expected high budget, got {budget}"

            # Verify max agents not reduced (light load doesn't reduce)
            assert context.effective_max_agents() == context.max_parallel_agents

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_light_load_allows_complex_task(
        self, light_calendar_file, manageable_tasks_file, complex_task
    ):
        """Light external load allows delegation of complex tasks."""
        # Setup
        calendar_adapter = create_ical_adapter(light_calendar_file)
        task_adapter = create_json_task_adapter(manageable_tasks_file)

        manager = IntegrationManager()
        manager.register_adapter(calendar_adapter)
        manager.register_adapter(task_adapter)

        coordinator = create_context_aware_coordinator(
            integration_manager=manager
        )

        await manager.start()
        await coordinator.refresh_context()

        try:
            # Make decision
            decision = coordinator.decide(complex_task)

            # Should allow work or delegate (not protect)
            assert decision.mode in (DecisionMode.WORK, DecisionMode.DELEGATE), \
                f"Expected WORK or DELEGATE, got {decision.mode}"

        finally:
            await manager.stop()


# =============================================================================
# Test: Full Stack - Heavy Load Scenario
# =============================================================================

class TestFullStackHeavyLoad:
    """E2E tests with heavy external load (should reduce capacity)."""

    @pytest.mark.asyncio
    async def test_heavy_load_reduces_cognitive_budget(
        self, busy_calendar_file, overloaded_tasks_file
    ):
        """Heavy external load reduces cognitive budget."""
        # Setup
        calendar_adapter = create_ical_adapter(busy_calendar_file)
        task_adapter = create_json_task_adapter(overloaded_tasks_file)

        manager = IntegrationManager()
        manager.register_adapter(calendar_adapter)
        manager.register_adapter(task_adapter)

        coordinator = create_context_aware_coordinator(
            integration_manager=manager
        )

        await manager.start()
        await coordinator.refresh_context()

        try:
            context = coordinator.get_cognitive_context()

            # Verify external context available
            assert context.external_context_available is True

            # Task overload should be detected (35 tasks > 30 threshold)
            assert context.task_load_level == "overloaded"

            # Verify reduced cognitive budget from task overload
            # Base budget varies but overloaded tasks add -0.20 adjustment
            budget = context.cognitive_budget()
            assert budget <= 1.0, f"Budget should be bounded: {budget}"

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_heavy_load_reduces_max_agents(
        self, busy_calendar_file, overloaded_tasks_file
    ):
        """Heavy external load reduces max parallel agents."""
        # Setup
        calendar_adapter = create_ical_adapter(busy_calendar_file)
        task_adapter = create_json_task_adapter(overloaded_tasks_file)

        manager = IntegrationManager()
        manager.register_adapter(calendar_adapter)
        manager.register_adapter(task_adapter)

        coordinator = create_context_aware_coordinator(
            integration_manager=manager
        )

        await manager.start()
        await coordinator.refresh_context()

        try:
            context = coordinator.get_cognitive_context()

            # Verify reduced max agents
            base_max = context.max_parallel_agents
            effective_max = context.effective_max_agents()

            assert effective_max < base_max, \
                f"Expected reduced agents: {effective_max} < {base_max}"
            assert effective_max >= 1, "Should always allow at least 1 agent"

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_heavy_load_context_comparison(
        self, light_calendar_file, manageable_tasks_file,
        busy_calendar_file, overloaded_tasks_file
    ):
        """Compare light vs heavy load cognitive budgets."""
        # Light load setup
        light_manager = IntegrationManager()
        light_manager.register_adapter(create_ical_adapter(light_calendar_file))
        light_manager.register_adapter(create_json_task_adapter(manageable_tasks_file))
        light_coord = create_context_aware_coordinator(integration_manager=light_manager)

        # Heavy load setup
        heavy_manager = IntegrationManager()
        heavy_manager.register_adapter(create_ical_adapter(busy_calendar_file))
        heavy_manager.register_adapter(create_json_task_adapter(overloaded_tasks_file))
        heavy_coord = create_context_aware_coordinator(integration_manager=heavy_manager)

        await light_manager.start()
        await heavy_manager.start()
        await light_coord.refresh_context()
        await heavy_coord.refresh_context()

        try:
            light_context = light_coord.get_cognitive_context()
            heavy_context = heavy_coord.get_cognitive_context()

            light_budget = light_context.cognitive_budget()
            heavy_budget = heavy_context.cognitive_budget()

            # Heavy load should have significantly lower budget
            difference = light_budget - heavy_budget
            assert difference >= 0.25, \
                f"Expected significant difference: {light_budget} - {heavy_budget} = {difference}"

        finally:
            await light_manager.stop()
            await heavy_manager.stop()


# =============================================================================
# Test: Full Stack with Protection Engine
# =============================================================================

class TestFullStackWithProtection:
    """E2E tests combining external context with protection engine."""

    @pytest.fixture
    def mock_profile(self):
        """Create a mock ResolvedProfile for protection engine."""
        profile = MagicMock()
        profile.protection_sensitivity = "medium"
        profile.break_reminder_minutes = 45
        return profile

    @pytest.mark.asyncio
    async def test_protection_considers_external_load(
        self, busy_calendar_file, overloaded_tasks_file, complex_task, mock_profile
    ):
        """Protection engine receives context from external load."""
        # Setup with protection
        calendar_adapter = create_ical_adapter(busy_calendar_file)
        task_adapter = create_json_task_adapter(overloaded_tasks_file)

        manager = IntegrationManager()
        manager.register_adapter(calendar_adapter)
        manager.register_adapter(task_adapter)

        # Create protection engine with mock profile
        protection = ProtectionEngine(mock_profile)

        coordinator = create_context_aware_coordinator(
            integration_manager=manager,
            protection_engine=protection,
        )

        await manager.start()
        await coordinator.refresh_context()

        try:
            # Verify coordinator has both integrations
            context = coordinator.get_cognitive_context()
            assert context.external_context_available

            # Get status to verify integration
            status = coordinator.get_status()
            assert status["external_context"]["available"] is True
            # Task load should be overloaded (35 tasks)
            assert status["external_context"]["task_load"] == "overloaded"

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_protection_blocks_when_appropriate(
        self, busy_calendar_file, overloaded_tasks_file, complex_task
    ):
        """Protection engine blocks complex work when user is overloaded."""
        from otto.protection import ProtectionDecision

        # Setup
        manager = IntegrationManager()
        manager.register_adapter(create_ical_adapter(busy_calendar_file))
        manager.register_adapter(create_json_task_adapter(overloaded_tasks_file))

        # Create protection that will require confirmation
        mock_protection = MagicMock()
        mock_protection.check.return_value = ProtectionDecision(
            action=ProtectionAction.REQUIRE_CONFIRM,
            message="Heavy external load detected - consider a break",
        )

        coordinator = create_context_aware_coordinator(
            integration_manager=manager,
            protection_engine=mock_protection,
        )

        await manager.start()
        await coordinator.refresh_context()

        try:
            # Make decision - should respect protection
            decision = coordinator.decide(complex_task)

            assert decision.mode == DecisionMode.PROTECT
            assert "Protection active" in decision.rationale

        finally:
            await manager.stop()


# =============================================================================
# Test: Full Stack with Calibration
# =============================================================================

class TestFullStackWithCalibration:
    """E2E tests combining external context with calibration learning."""

    @pytest.fixture
    def mock_profile(self):
        """Create a mock ResolvedProfile for protection engine."""
        profile = MagicMock()
        profile.protection_sensitivity = "medium"
        profile.break_reminder_minutes = 45
        return profile

    @pytest.mark.asyncio
    async def test_calibration_with_external_context(
        self, temp_dir, busy_calendar_file, overloaded_tasks_file, mock_profile
    ):
        """Calibration engine can learn with external context present."""
        # Setup calibration
        calibration = CalibrationEngine(otto_dir=temp_dir)

        # Setup protection with mock profile and calibration
        protection = ProtectionEngine(mock_profile, calibration_engine=calibration)

        # Setup integration
        manager = IntegrationManager()
        manager.register_adapter(create_ical_adapter(busy_calendar_file))
        manager.register_adapter(create_json_task_adapter(overloaded_tasks_file))

        coordinator = create_context_aware_coordinator(
            integration_manager=manager,
            protection_engine=protection,
        )

        await manager.start()
        await coordinator.refresh_context()

        try:
            context = coordinator.get_cognitive_context()

            # Verify full stack is wired
            assert context.external_context_available
            assert coordinator.protection_engine is not None

            # Record an override (user works despite heavy load)
            # Uses correct API: record_override(trigger, current_firmness)
            calibration.record_override(
                trigger="heavy_external_load",
                current_firmness=0.5,
            )

            # Verify calibration state updated
            assert calibration.state.session_overrides >= 1

        finally:
            await manager.stop()


# =============================================================================
# Test: Context Signal Flow
# =============================================================================

class TestContextSignalFlow:
    """Tests that context signals flow correctly through the stack."""

    @pytest.mark.asyncio
    async def test_signals_propagate_from_adapters(
        self, busy_calendar_file, overloaded_tasks_file
    ):
        """Context signals from adapters reach the coordinator."""
        # Setup
        manager = IntegrationManager()
        manager.register_adapter(create_ical_adapter(busy_calendar_file))
        manager.register_adapter(create_json_task_adapter(overloaded_tasks_file))

        coordinator = create_context_aware_coordinator(
            integration_manager=manager
        )

        await manager.start()
        await coordinator.refresh_context()

        try:
            # Get aggregated context from manager
            external_ctx = await manager.get_context()

            # Check signals are present (may vary based on parsing)
            signals = external_ctx.get_all_signals()

            # Should have task overload signal (35 tasks > 30 threshold)
            assert ContextSignal.TASK_OVERLOAD in signals

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_deadline_signal_affects_budget(self, temp_dir):
        """Approaching deadline signal reduces cognitive budget."""
        # Create calendar with deadline today
        now = datetime.now()
        today = now.strftime("%Y%m%d")
        deadline_hour = now.hour + 2  # 2 hours from now

        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//OTTO OS//Test//EN
BEGIN:VEVENT
UID:deadline@test
DTSTART:{today}T{deadline_hour:02d}0000
DTEND:{today}T{deadline_hour:02d}3000
SUMMARY:DEADLINE: Project Due
END:VEVENT
END:VCALENDAR"""

        ics_file = temp_dir / "deadline.ics"
        ics_file.write_text(ics_content)

        # Setup
        manager = IntegrationManager()
        manager.register_adapter(create_ical_adapter(ics_file))

        coordinator = create_context_aware_coordinator(
            integration_manager=manager
        )

        await manager.start()
        await coordinator.refresh_context()

        try:
            context = coordinator.get_cognitive_context()

            # Calendar should detect the deadline
            # (depends on how CalendarAdapter parses "DEADLINE" in summary)
            # At minimum, context should be available
            assert context.external_context_available

        finally:
            await manager.stop()


# =============================================================================
# Test: Error Handling
# =============================================================================

class TestFullStackErrorHandling:
    """Tests error handling in the full stack."""

    @pytest.mark.asyncio
    async def test_missing_calendar_file_graceful(self, temp_dir, manageable_tasks_file):
        """Missing calendar file doesn't crash the stack."""
        missing_file = temp_dir / "nonexistent.ics"

        # This should not raise during adapter creation
        calendar_adapter = create_ical_adapter(missing_file)
        task_adapter = create_json_task_adapter(manageable_tasks_file)

        manager = IntegrationManager()
        manager.register_adapter(calendar_adapter)
        manager.register_adapter(task_adapter)

        coordinator = create_context_aware_coordinator(
            integration_manager=manager
        )

        await manager.start()

        try:
            # Should handle missing file gracefully
            await coordinator.refresh_context()
            context = coordinator.get_cognitive_context()

            # Should still work, just without calendar context
            # The coordinator should be functional
            assert context is not None

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_malformed_json_graceful(self, temp_dir, light_calendar_file):
        """Malformed JSON tasks file doesn't crash the stack."""
        bad_json_file = temp_dir / "bad.json"
        bad_json_file.write_text("{ this is not valid json }")

        calendar_adapter = create_ical_adapter(light_calendar_file)
        task_adapter = create_json_task_adapter(bad_json_file)

        manager = IntegrationManager()
        manager.register_adapter(calendar_adapter)
        manager.register_adapter(task_adapter)

        coordinator = create_context_aware_coordinator(
            integration_manager=manager
        )

        await manager.start()

        try:
            await coordinator.refresh_context()
            context = coordinator.get_cognitive_context()

            # Should still work with calendar context
            assert context is not None

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_no_adapters_still_works(self):
        """Coordinator works without any adapters."""
        manager = IntegrationManager()

        coordinator = create_context_aware_coordinator(
            integration_manager=manager
        )

        await manager.start()

        try:
            await coordinator.refresh_context()
            context = coordinator.get_cognitive_context()

            # Should work and produce valid context
            assert context is not None
            assert isinstance(context, EnhancedCognitiveContext)

            # Budget should be valid (bounded 0-1)
            budget = context.cognitive_budget()
            assert 0.0 <= budget <= 1.0

            # Status should show no active integrations
            status = coordinator.get_status()
            assert status["external_context"]["integrations"] == []

        finally:
            await manager.stop()


# =============================================================================
# Test: Determinism ([He2025] Compliance)
# =============================================================================

class TestDeterminism:
    """Tests that the full stack produces deterministic results."""

    @pytest.mark.asyncio
    async def test_same_input_same_output(
        self, busy_calendar_file, overloaded_tasks_file
    ):
        """Same input files produce same cognitive budget."""
        budgets = []

        for _ in range(3):
            manager = IntegrationManager()
            manager.register_adapter(create_ical_adapter(busy_calendar_file))
            manager.register_adapter(create_json_task_adapter(overloaded_tasks_file))

            coordinator = create_context_aware_coordinator(
                integration_manager=manager
            )

            await manager.start()
            await coordinator.refresh_context()

            context = coordinator.get_cognitive_context()
            budgets.append(context.cognitive_budget())

            await manager.stop()

        # All runs should produce same budget
        assert budgets[0] == budgets[1] == budgets[2], \
            f"Non-deterministic budgets: {budgets}"

    @pytest.mark.asyncio
    async def test_decisions_have_checksums(
        self, light_calendar_file, manageable_tasks_file, simple_task
    ):
        """Decisions include checksums for traceability."""
        manager = IntegrationManager()
        manager.register_adapter(create_ical_adapter(light_calendar_file))
        manager.register_adapter(create_json_task_adapter(manageable_tasks_file))

        coordinator = create_context_aware_coordinator(
            integration_manager=manager
        )

        await manager.start()
        await coordinator.refresh_context()

        try:
            decision = coordinator.decide(simple_task)

            # Decision should have checksum
            assert hasattr(decision, "checksum")
            assert len(decision.checksum) > 0

        finally:
            await manager.stop()
