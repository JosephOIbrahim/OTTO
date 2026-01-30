"""
Tests for Reflection Agent
==========================

Tests for self-assessment and cognitive integration.
"""

import pytest
from datetime import datetime

from otto.agents import AgentConfig
from otto.agents.reflection import (
    ReflectionAgent,
    ReflectionType,
    ReflectionQuestion,
    ReflectionAssessment,
    ReflectionResult,
)


class TestReflectionAssessment:
    """Tests for ReflectionAssessment."""

    def test_create_assessment(self):
        """Create assessment."""
        assessment = ReflectionAssessment(
            area="progress",
            score=0.8,
            status="good",
            observations=["Making progress"],
        )
        assert assessment.score == 0.8
        assert assessment.status == "good"

    def test_assessment_to_dict(self):
        """Assessment can be serialized."""
        assessment = ReflectionAssessment(
            area="energy",
            score=0.4,
            status="concerning",
            recommendations=["Take a break"],
        )
        data = assessment.to_dict()
        assert data["area"] == "energy"
        assert data["status"] == "concerning"


class TestReflectionResult:
    """Tests for ReflectionResult."""

    def test_create_result(self):
        """Create reflection result."""
        result = ReflectionResult(
            reflection_type="progress",
            timestamp=datetime.now(),
            overall_score=0.75,
            overall_status="on_track",
        )
        assert result.overall_status == "on_track"

    def test_result_requires_intervention(self):
        """Check intervention requirement."""
        needs_help = ReflectionResult(
            reflection_type="progress",
            timestamp=datetime.now(),
            overall_score=0.2,
            overall_status="needs_intervention",
        )
        assert needs_help.requires_intervention()

        on_track = ReflectionResult(
            reflection_type="progress",
            timestamp=datetime.now(),
            overall_score=0.8,
            overall_status="on_track",
        )
        assert not on_track.requires_intervention()

    def test_result_format_display(self):
        """Result can be formatted for display."""
        assessments = [
            ReflectionAssessment("progress", 0.8, "good", ["Good progress"]),
            ReflectionAssessment("energy", 0.4, "concerning", ["Energy declining"]),
        ]
        result = ReflectionResult(
            reflection_type="progress",
            timestamp=datetime.now(),
            overall_score=0.6,
            overall_status="drifting",
            assessments=assessments,
            course_corrections=["Consider a break"],
        )
        display = result.format_display()

        assert "progress" in display.lower()
        assert "drifting" in display.lower()


class TestReflectionAgent:
    """Tests for ReflectionAgent."""

    @pytest.mark.asyncio
    async def test_reflect_progress(self):
        """Reflect on progress."""
        agent = ReflectionAgent()
        result = await agent.run(
            "progress",
            {
                "goal": "Implement authentication",
                "completed_steps": ["Setup", "Login form"],
                "remaining_steps": ["JWT tokens", "Logout"],
            }
        )

        assert result.success
        reflection = result.result
        # Result is now a dict via to_dict()
        assert isinstance(reflection, dict)
        assert reflection["reflection_type"] == "progress"

    @pytest.mark.asyncio
    async def test_reflect_alignment(self):
        """Reflect on goal alignment."""
        agent = ReflectionAgent()
        result = await agent.run(
            "alignment",
            {
                "goal": "Build user dashboard",
                "scope_changes": [],
            }
        )

        assert result.success
        reflection = result.result
        assert reflection["reflection_type"] == "alignment"

    @pytest.mark.asyncio
    async def test_reflect_energy(self):
        """Reflect on energy state."""
        agent = ReflectionAgent()
        result = await agent.run(
            "energy",
            {
                "cognitive_state": {
                    "burnout": "YELLOW",
                    "momentum": "rolling",
                }
            }
        )

        assert result.success
        reflection = result.result
        assert reflection["reflection_type"] == "energy"

    @pytest.mark.asyncio
    async def test_reflect_approach(self):
        """Reflect on current approach."""
        agent = ReflectionAgent()
        result = await agent.run(
            "approach",
            {
                "completed_steps": ["Step 1", "Step 2"],
                "errors_encountered": [],
            }
        )

        assert result.success
        reflection = result.result
        assert reflection["reflection_type"] == "approach"

    @pytest.mark.asyncio
    async def test_reflect_completion(self):
        """Reflect on completion status."""
        agent = ReflectionAgent()
        result = await agent.run(
            "completion",
            {
                "completed_steps": ["A", "B", "C"],
                "remaining_steps": [],
                "errors_encountered": [],
            }
        )

        assert result.success
        reflection = result.result
        assert reflection["reflection_type"] == "completion"

    @pytest.mark.asyncio
    async def test_reflect_detects_burnout(self):
        """Reflection detects burnout."""
        agent = ReflectionAgent()
        result = await agent.run(
            "energy",
            {
                "cognitive_state": {
                    "burnout": "ORANGE",
                }
            }
        )

        assert result.success
        reflection = result.result

        # Should have course correction for burnout
        corrections = reflection["course_corrections"]
        assert any("break" in c.lower() or "ORANGE" in c for c in corrections)

    @pytest.mark.asyncio
    async def test_reflect_detects_red_burnout(self):
        """Reflection detects RED burnout urgently."""
        agent = ReflectionAgent()
        result = await agent.run(
            "energy",
            {
                "cognitive_state": {
                    "burnout": "RED",
                }
            }
        )

        assert result.success
        reflection = result.result

        # Should have urgent course correction
        assert any("STOP" in c or "RED" in c for c in reflection["course_corrections"])

    @pytest.mark.asyncio
    async def test_reflect_on_track(self):
        """Reflection shows on track when healthy."""
        agent = ReflectionAgent()
        result = await agent.run(
            "progress",
            {
                "goal": "Simple task",
                "completed_steps": ["Step 1", "Step 2", "Step 3"],
                "remaining_steps": [],
                "errors_encountered": [],
                "cognitive_state": {"burnout": "GREEN"},
            }
        )

        assert result.success
        reflection = result.result

        # Good progress should be on track
        assert reflection["overall_score"] >= 0.5

    @pytest.mark.asyncio
    async def test_reflect_generates_insights(self):
        """Reflection generates insights."""
        agent = ReflectionAgent()
        result = await agent.run(
            "progress",
            {
                "completed_steps": ["A", "B", "C", "D"],
            }
        )

        assert result.success
        reflection = result.result

        # Should have insights about momentum
        assert len(reflection["insights"]) > 0

    @pytest.mark.asyncio
    async def test_reflect_sets_next_check(self):
        """Reflection sets appropriate next check interval."""
        agent = ReflectionAgent()

        # Good state - longer interval
        good_result = await agent.run(
            "progress",
            {
                "completed_steps": ["A", "B", "C"],
                "cognitive_state": {"burnout": "GREEN"},
            }
        )
        assert good_result.result["next_check_after"] >= 5

        # Bad state - shorter interval
        bad_result = await agent.run(
            "energy",
            {
                "cognitive_state": {"burnout": "ORANGE"},
            }
        )
        assert bad_result.result["next_check_after"] <= 5

    @pytest.mark.asyncio
    async def test_unknown_reflection_type(self):
        """Unknown reflection type defaults to progress."""
        agent = ReflectionAgent()
        result = await agent.run("unknown_type", {})

        assert result.success
        assert result.result["reflection_type"] == "progress"
