"""
Reflection Agent
================

Self-assessment and cognitive integration agent.

The Reflection Agent performs self-assessment:
- Evaluate progress toward goals
- Check for drift from original intent
- Assess cognitive state trajectory
- Generate course corrections

Philosophy:
    Reflection prevents drift. Regular check-ins catch problems
    before they become crises.

Determinism:
- Fixed reflection questions
- Deterministic assessment criteria
- Bounded reflection depth
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import Agent, AgentConfig

logger = logging.getLogger(__name__)


class ReflectionType:
    """Types of reflection."""
    PROGRESS = "progress"          # Are we making progress?
    ALIGNMENT = "alignment"        # Are we on track with goals?
    ENERGY = "energy"              # How is cognitive state?
    APPROACH = "approach"          # Is our approach working?
    COMPLETION = "completion"      # What have we accomplished?


@dataclass
class ReflectionQuestion:
    """A reflection question to answer."""
    question: str
    category: str  # ReflectionType
    weight: float = 1.0  # Importance weight
    answer: Optional[str] = None
    score: Optional[float] = None  # 0.0 (bad) to 1.0 (good)


@dataclass
class ReflectionAssessment:
    """Assessment result for a single area."""
    area: str
    score: float  # 0.0 to 1.0
    status: str   # "good", "concerning", "needs_attention"
    observations: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "area": self.area,
            "score": self.score,
            "status": self.status,
            "observations": self.observations,
            "recommendations": self.recommendations,
        }


@dataclass
class ReflectionResult:
    """Complete reflection result."""
    reflection_type: str
    timestamp: datetime
    overall_score: float  # 0.0 to 1.0
    overall_status: str   # "on_track", "drifting", "needs_intervention"
    assessments: List[ReflectionAssessment] = field(default_factory=list)
    course_corrections: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    next_check_after: int = 10  # exchanges

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_type": self.reflection_type,
            "timestamp": self.timestamp.isoformat(),
            "overall_score": self.overall_score,
            "overall_status": self.overall_status,
            "assessments": [a.to_dict() for a in self.assessments],
            "course_corrections": self.course_corrections,
            "insights": self.insights,
            "next_check_after": self.next_check_after,
        }

    def format_display(self) -> str:
        """Format for terminal display."""
        lines = [
            f"## Reflection: {self.reflection_type}",
            f"Status: {self.overall_status} (score: {self.overall_score:.0%})",
            "",
        ]

        if self.assessments:
            lines.append("### Assessments:")
            for assessment in self.assessments:
                icon = "✓" if assessment.status == "good" else "⚠" if assessment.status == "concerning" else "✗"
                lines.append(f"  {icon} {assessment.area}: {assessment.score:.0%}")
                for obs in assessment.observations[:2]:
                    lines.append(f"      - {obs}")

        if self.course_corrections:
            lines.append("")
            lines.append("### Course Corrections Needed:")
            for cc in self.course_corrections:
                lines.append(f"  - {cc}")

        if self.insights:
            lines.append("")
            lines.append("### Insights:")
            for insight in self.insights:
                lines.append(f"  - {insight}")

        return "\n".join(lines)

    def requires_intervention(self) -> bool:
        """Check if intervention is needed."""
        return self.overall_status == "needs_intervention"


class ReflectionAgent(Agent[ReflectionResult]):
    """
    Agent for self-assessment and cognitive integration.

    Features:
    - Progress tracking
    - Goal alignment checking
    - Energy trajectory assessment
    - Course correction generation
    - Insight extraction

    Example:
        agent = ReflectionAgent()
        result = await agent.run(
            "progress",
            {
                "goal": "Implement authentication",
                "completed_steps": ["Setup", "Login"],
                "cognitive_state": {"burnout": "YELLOW", "momentum": "rolling"}
            }
        )
    """

    agent_type = "reflection"

    # Standard reflection questions by type
    REFLECTION_QUESTIONS = {
        ReflectionType.PROGRESS: [
            ReflectionQuestion("Are we making measurable progress?", "progress", 1.0),
            ReflectionQuestion("What has been completed since last check?", "progress", 0.8),
            ReflectionQuestion("Are there any blockers?", "progress", 1.0),
        ],
        ReflectionType.ALIGNMENT: [
            ReflectionQuestion("Are we still working toward the original goal?", "alignment", 1.0),
            ReflectionQuestion("Has the scope changed?", "alignment", 0.8),
            ReflectionQuestion("Are we solving the right problem?", "alignment", 1.0),
        ],
        ReflectionType.ENERGY: [
            ReflectionQuestion("What is the current energy trajectory?", "energy", 1.0),
            ReflectionQuestion("Are there signs of burnout?", "energy", 1.0),
            ReflectionQuestion("Is the pace sustainable?", "energy", 0.8),
        ],
        ReflectionType.APPROACH: [
            ReflectionQuestion("Is the current approach working?", "approach", 1.0),
            ReflectionQuestion("Should we try a different strategy?", "approach", 0.8),
            ReflectionQuestion("Are there simpler alternatives?", "approach", 0.7),
        ],
        ReflectionType.COMPLETION: [
            ReflectionQuestion("What have we accomplished?", "completion", 1.0),
            ReflectionQuestion("What remains to be done?", "completion", 1.0),
            ReflectionQuestion("Are we ready to ship?", "completion", 0.8),
        ],
    }

    def __init__(self, config: AgentConfig = None):
        super().__init__(config)

    def _get_step_count(self) -> int:
        """Reflection has 4 phases."""
        return 4

    async def _execute(self, task: str, context: Dict[str, Any]) -> ReflectionResult:
        """
        Execute reflection process.

        Task is reflection type: progress, alignment, energy, approach, completion

        Phases:
        1. Gather context
        2. Answer reflection questions
        3. Generate assessments
        4. Derive course corrections
        """
        self.increment_turn()

        # Determine reflection type
        reflection_type = task.lower().strip()
        if reflection_type not in [
            ReflectionType.PROGRESS,
            ReflectionType.ALIGNMENT,
            ReflectionType.ENERGY,
            ReflectionType.APPROACH,
            ReflectionType.COMPLETION,
        ]:
            reflection_type = ReflectionType.PROGRESS  # Default

        # Phase 1: Gather context
        await self.report_progress(1, "Gathering context for reflection")
        gathered_context = self._gather_context(context)

        # Phase 2: Answer questions
        await self.report_progress(2, "Evaluating reflection questions")
        questions = self._answer_questions(reflection_type, gathered_context)

        # Phase 3: Generate assessments
        await self.report_progress(3, "Generating assessments")
        assessments = self._generate_assessments(questions, gathered_context)

        # Phase 4: Derive corrections
        await self.report_progress(4, "Deriving course corrections")
        corrections, insights = self._derive_corrections(assessments, gathered_context)

        # Calculate overall score and status
        if assessments:
            overall_score = sum(a.score for a in assessments) / len(assessments)
        else:
            overall_score = 0.5

        if overall_score >= 0.7:
            overall_status = "on_track"
            next_check = 15
        elif overall_score >= 0.4:
            overall_status = "drifting"
            next_check = 5
        else:
            overall_status = "needs_intervention"
            next_check = 1

        return ReflectionResult(
            reflection_type=reflection_type,
            timestamp=datetime.now(),
            overall_score=overall_score,
            overall_status=overall_status,
            assessments=assessments,
            course_corrections=corrections,
            insights=insights,
            next_check_after=next_check,
        )

    def _gather_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Gather and normalize context for reflection."""
        return {
            "goal": context.get("goal", "Unknown goal"),
            "completed_steps": context.get("completed_steps", []),
            "remaining_steps": context.get("remaining_steps", []),
            "cognitive_state": context.get("cognitive_state", {}),
            "session_duration": context.get("session_duration", 0),
            "exchange_count": context.get("exchange_count", 0),
            "errors_encountered": context.get("errors_encountered", []),
            "scope_changes": context.get("scope_changes", []),
        }

    def _answer_questions(
        self, reflection_type: str, context: Dict[str, Any]
    ) -> List[ReflectionQuestion]:
        """Answer reflection questions based on context."""
        questions = self.REFLECTION_QUESTIONS.get(reflection_type, [])
        answered = []

        for q in questions:
            answered_q = ReflectionQuestion(
                question=q.question,
                category=q.category,
                weight=q.weight,
            )

            # Answer based on context
            score, answer = self._evaluate_question(q, context)
            answered_q.score = score
            answered_q.answer = answer

            answered.append(answered_q)

        return answered

    def _evaluate_question(
        self, question: ReflectionQuestion, context: Dict[str, Any]
    ) -> tuple[float, str]:
        """Evaluate a single question."""
        q_lower = question.question.lower()

        # Progress questions
        if "making" in q_lower and "progress" in q_lower:
            completed = len(context.get("completed_steps", []))
            if completed > 0:
                return 0.8, f"Completed {completed} steps"
            return 0.3, "No steps completed yet"

        if "completed" in q_lower:
            completed = context.get("completed_steps", [])
            if completed:
                return 0.9, f"Completed: {', '.join(completed[:3])}"
            return 0.2, "Nothing completed yet"

        if "blocker" in q_lower:
            errors = context.get("errors_encountered", [])
            if errors:
                return 0.3, f"Blockers: {len(errors)} errors"
            return 0.9, "No blockers identified"

        # Alignment questions
        if "original goal" in q_lower:
            scope_changes = context.get("scope_changes", [])
            if not scope_changes:
                return 0.9, "Still aligned with original goal"
            return 0.5, f"Scope changed {len(scope_changes)} times"

        if "scope" in q_lower:
            scope_changes = context.get("scope_changes", [])
            if not scope_changes:
                return 0.9, "Scope unchanged"
            return 0.4, f"Scope changed: {scope_changes[-1] if scope_changes else 'unknown'}"

        if "right problem" in q_lower:
            return 0.7, "Assumed yes - verify with user if unsure"

        # Energy questions
        if "energy" in q_lower or "trajectory" in q_lower:
            cog_state = context.get("cognitive_state", {})
            burnout = cog_state.get("burnout", "GREEN")
            if burnout == "GREEN":
                return 0.9, "Energy good (GREEN)"
            elif burnout == "YELLOW":
                return 0.6, "Energy declining (YELLOW)"
            elif burnout == "ORANGE":
                return 0.3, "Energy low (ORANGE)"
            else:
                return 0.1, "Energy critical (RED)"

        if "burnout" in q_lower:
            cog_state = context.get("cognitive_state", {})
            burnout = cog_state.get("burnout", "GREEN")
            if burnout in ("ORANGE", "RED"):
                return 0.2, f"Burnout detected: {burnout}"
            return 0.8, "No burnout signs"

        if "sustainable" in q_lower:
            duration = context.get("session_duration", 0)
            if duration > 180:  # 3 hours
                return 0.3, f"Long session ({duration} min)"
            return 0.8, "Pace appears sustainable"

        # Approach questions
        if "approach working" in q_lower:
            errors = context.get("errors_encountered", [])
            completed = context.get("completed_steps", [])
            if len(errors) > len(completed):
                return 0.3, "Many errors - approach may need revision"
            return 0.7, "Approach appears to be working"

        if "different strategy" in q_lower:
            return 0.5, "Evaluate based on progress"

        if "simpler" in q_lower:
            return 0.5, "Always consider simpler alternatives"

        # Completion questions
        if "accomplished" in q_lower:
            completed = context.get("completed_steps", [])
            if completed:
                return 0.8, f"Accomplished: {len(completed)} steps"
            return 0.2, "Not much accomplished yet"

        if "remains" in q_lower:
            remaining = context.get("remaining_steps", [])
            if not remaining:
                return 0.9, "Nothing known remaining"
            return 0.5, f"Remaining: {len(remaining)} steps"

        if "ready to ship" in q_lower:
            remaining = context.get("remaining_steps", [])
            errors = context.get("errors_encountered", [])
            if not remaining and not errors:
                return 0.9, "Appears ready to ship"
            return 0.3, "Not yet ready"

        # Default
        return 0.5, "Unable to evaluate"

    def _generate_assessments(
        self,
        questions: List[ReflectionQuestion],
        context: Dict[str, Any],
    ) -> List[ReflectionAssessment]:
        """Generate assessments from answered questions."""
        # Group by category
        categories: Dict[str, List[ReflectionQuestion]] = {}
        for q in questions:
            if q.category not in categories:
                categories[q.category] = []
            categories[q.category].append(q)

        assessments = []
        for category, cat_questions in categories.items():
            # Calculate weighted score
            total_weight = sum(q.weight for q in cat_questions)
            weighted_score = sum(
                (q.score or 0.5) * q.weight for q in cat_questions
            ) / total_weight if total_weight > 0 else 0.5

            # Determine status
            if weighted_score >= 0.7:
                status = "good"
            elif weighted_score >= 0.4:
                status = "concerning"
            else:
                status = "needs_attention"

            # Collect observations and recommendations
            observations = [q.answer for q in cat_questions if q.answer]
            recommendations = []

            if status == "concerning":
                recommendations.append(f"Monitor {category} closely")
            elif status == "needs_attention":
                recommendations.append(f"Immediate attention needed for {category}")

            assessments.append(ReflectionAssessment(
                area=category,
                score=weighted_score,
                status=status,
                observations=observations,
                recommendations=recommendations,
            ))

        return assessments

    def _derive_corrections(
        self,
        assessments: List[ReflectionAssessment],
        context: Dict[str, Any],
    ) -> tuple[List[str], List[str]]:
        """Derive course corrections and insights from assessments."""
        corrections = []
        insights = []

        # Check for problem areas
        problem_areas = [a for a in assessments if a.status != "good"]

        for area in problem_areas:
            if area.status == "needs_attention":
                corrections.append(f"Address {area.area} immediately: {area.observations[0] if area.observations else 'low score'}")
            elif area.status == "concerning":
                corrections.append(f"Consider adjusting approach for {area.area}")

        # Energy-specific corrections
        cog_state = context.get("cognitive_state", {})
        burnout = cog_state.get("burnout", "GREEN")
        if burnout == "ORANGE":
            corrections.append("Consider taking a break - ORANGE burnout")
        elif burnout == "RED":
            corrections.append("STOP - RED burnout requires immediate rest")

        # Generate insights
        completed = context.get("completed_steps", [])
        if len(completed) >= 3:
            insights.append(f"Good momentum - {len(completed)} steps completed")

        if not problem_areas:
            insights.append("All areas on track - continue current approach")

        errors = context.get("errors_encountered", [])
        if errors and len(completed) > len(errors):
            insights.append("Errors encountered but progress outweighs them")

        return corrections, insights


__all__ = [
    "ReflectionAgent",
    "ReflectionType",
    "ReflectionQuestion",
    "ReflectionAssessment",
    "ReflectionResult",
]
