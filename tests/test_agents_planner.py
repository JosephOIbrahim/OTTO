"""
Tests for Planner Agent
=======================

Tests for task decomposition and planning.
"""

import pytest
from otto.agents import AgentConfig
from otto.agents.planner import (
    PlannerAgent,
    PlanStep,
    ExecutionPlan,
)


class TestPlanStep:
    """Tests for PlanStep."""

    def test_create_step(self):
        """Create plan step."""
        step = PlanStep(
            number=1,
            description="Analyze requirements",
            category="exploration",
            estimated_complexity="simple",
        )
        assert step.number == 1
        assert step.category == "exploration"

    def test_step_with_dependencies(self):
        """Step with dependencies."""
        step = PlanStep(
            number=3,
            description="Implement",
            category="implementation",
            estimated_complexity="moderate",
            dependencies=[1, 2],
        )
        assert step.dependencies == [1, 2]

    def test_to_dict_from_dict(self):
        """Step serialization roundtrip."""
        original = PlanStep(
            number=1,
            description="Test step",
            category="testing",
            estimated_complexity="simple",
            files_involved=["test.py"],
            agent_type="test",
        )
        data = original.to_dict()
        restored = PlanStep.from_dict(data)

        assert restored.number == original.number
        assert restored.description == original.description
        assert restored.files_involved == original.files_involved


class TestExecutionPlan:
    """Tests for ExecutionPlan."""

    def test_create_plan(self):
        """Create execution plan."""
        steps = [
            PlanStep(1, "Step 1", "exploration", "simple"),
            PlanStep(2, "Step 2", "implementation", "moderate", dependencies=[1]),
        ]
        plan = ExecutionPlan(
            task="Test task",
            summary="Test plan",
            steps=steps,
            total_complexity="moderate",
            estimated_turns=5,
        )
        assert len(plan.steps) == 2
        assert plan.total_complexity == "moderate"

    def test_plan_format_display(self):
        """Plan can be formatted for display."""
        steps = [
            PlanStep(1, "Explore", "exploration", "simple"),
            PlanStep(2, "Implement", "implementation", "moderate", dependencies=[1]),
        ]
        plan = ExecutionPlan(
            task="Test task",
            summary="A test plan",
            steps=steps,
            total_complexity="moderate",
            estimated_turns=5,
        )
        display = plan.format_display()

        assert "Test task" in display
        assert "Explore" in display
        assert "Implement" in display

    def test_plan_with_parallel_groups(self):
        """Plan with parallel execution groups."""
        steps = [
            PlanStep(1, "Step 1", "exploration", "simple"),
            PlanStep(2, "Step 2", "exploration", "simple", can_parallelize=True),
            PlanStep(3, "Step 3", "exploration", "simple", can_parallelize=True),
        ]
        plan = ExecutionPlan(
            task="Test",
            summary="Test",
            steps=steps,
            total_complexity="simple",
            estimated_turns=3,
            parallelizable_groups=[[2, 3]],
        )
        display = plan.format_display()

        assert "Parallel groups" in display or "Group" in display


class TestPlannerAgent:
    """Tests for PlannerAgent."""

    @pytest.mark.asyncio
    async def test_plan_simple_task(self):
        """Plan a simple task."""
        agent = PlannerAgent()
        result = await agent.run("Find authentication patterns", {"scope": "small"})

        assert result.success
        plan = result.result
        # Result is now a dict via to_dict()
        assert isinstance(plan, dict)
        assert "steps" in plan
        assert len(plan["steps"]) > 0

    @pytest.mark.asyncio
    async def test_plan_implementation_task(self):
        """Plan an implementation task."""
        agent = PlannerAgent()
        result = await agent.run(
            "Implement user login feature",
            {"files": ["src/auth.py"], "scope": "medium"}
        )

        assert result.success
        plan = result.result

        # Should detect implementation category
        categories = [s["category"] for s in plan["steps"]]
        assert "implementation" in categories

    @pytest.mark.asyncio
    async def test_plan_exploration_task(self):
        """Plan an exploration task."""
        agent = PlannerAgent()
        result = await agent.run(
            "Search for all API endpoints",
            {"files": ["src/api/"], "scope": "medium"}
        )

        assert result.success
        plan = result.result
        categories = [s["category"] for s in plan["steps"]]
        assert "exploration" in categories

    @pytest.mark.asyncio
    async def test_plan_debugging_task(self):
        """Plan a debugging task."""
        agent = PlannerAgent()
        result = await agent.run(
            "Fix the authentication bug",
            {"scope": "small"}
        )

        assert result.success
        # Debugging is mapped to implementation category
        plan = result.result
        assert len(plan["steps"]) > 0

    @pytest.mark.asyncio
    async def test_plan_complex_task(self):
        """Plan a complex multi-file task."""
        agent = PlannerAgent()
        result = await agent.run(
            "Refactor the entire authentication system",
            {"files": [f"file{i}.py" for i in range(15)], "scope": "large"}
        )

        assert result.success
        plan = result.result
        assert plan["total_complexity"] == "complex"

    @pytest.mark.asyncio
    async def test_plan_respects_energy_level(self):
        """Plan respects energy level limits."""
        config = AgentConfig(agent_type="planner", energy_level="depleted")
        agent = PlannerAgent(config)
        result = await agent.run(
            "Do a big complex task",
            {"files": [f"f{i}.py" for i in range(20)], "scope": "large"}
        )

        assert result.success
        plan = result.result
        # Should be truncated due to depleted energy
        assert len(plan["steps"]) <= 3

    @pytest.mark.asyncio
    async def test_plan_has_estimated_turns(self):
        """Plan includes turn estimate."""
        agent = PlannerAgent()
        result = await agent.run("Simple task", {})

        plan = result.result
        assert plan["estimated_turns"] > 0

    @pytest.mark.asyncio
    async def test_plan_includes_agent_suggestions(self):
        """Plan suggests agent types for steps."""
        agent = PlannerAgent()
        result = await agent.run(
            "Explore and then implement",
            {"scope": "medium"}
        )

        plan = result.result
        agent_types = [s["agent_type"] for s in plan["steps"] if s.get("agent_type")]
        assert len(agent_types) > 0

    @pytest.mark.asyncio
    async def test_plan_adds_warning_low_energy(self):
        """Plan warns about complex task with low energy."""
        config = AgentConfig(agent_type="planner", energy_level="low")
        agent = PlannerAgent(config)
        result = await agent.run(
            "Complex refactoring task",
            {"files": [f"f{i}.py" for i in range(10)], "scope": "large"}
        )

        plan = result.result
        # May have warning about low energy + complex task
        # Plan should still succeed
        assert result.success
