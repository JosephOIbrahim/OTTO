"""
Planner Agent
=============

Task decomposition and execution planning agent.

The Planner breaks down complex tasks into manageable steps,
identifies dependencies, and creates execution plans.

Philosophy:
    Break down complexity while respecting cognitive limits.
    A 3-step plan that's achievable beats a 10-step plan that overwhelms.

ThinkingMachines [He2025] Compliance:
- Fixed planning phases
- Deterministic step generation
- Bounded complexity
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# [He2025] Determinism utilities
from ..determinism import sorted_set_to_list

from .base import Agent, AgentConfig, NonRetryableError

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    number: int
    description: str
    category: str  # "exploration", "implementation", "review", "test", "other"
    estimated_complexity: str  # "simple", "moderate", "complex"
    dependencies: List[int] = field(default_factory=list)  # Step numbers this depends on
    files_involved: List[str] = field(default_factory=list)
    can_parallelize: bool = False
    agent_type: Optional[str] = None  # Suggested agent type for delegation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "description": self.description,
            "category": self.category,
            "estimated_complexity": self.estimated_complexity,
            "dependencies": self.dependencies,
            "files_involved": self.files_involved,
            "can_parallelize": self.can_parallelize,
            "agent_type": self.agent_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        return cls(
            number=data["number"],
            description=data["description"],
            category=data["category"],
            estimated_complexity=data["estimated_complexity"],
            dependencies=data.get("dependencies", []),
            files_involved=data.get("files_involved", []),
            can_parallelize=data.get("can_parallelize", False),
            agent_type=data.get("agent_type"),
        )


@dataclass
class ExecutionPlan:
    """Complete execution plan for a task."""
    task: str
    summary: str
    steps: List[PlanStep]
    total_complexity: str  # "simple", "moderate", "complex"
    estimated_turns: int
    parallelizable_groups: List[List[int]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "summary": self.summary,
            "steps": [s.to_dict() for s in self.steps],
            "total_complexity": self.total_complexity,
            "estimated_turns": self.estimated_turns,
            "parallelizable_groups": self.parallelizable_groups,
            "warnings": self.warnings,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionPlan":
        return cls(
            task=data["task"],
            summary=data["summary"],
            steps=[PlanStep.from_dict(s) for s in data["steps"]],
            total_complexity=data["total_complexity"],
            estimated_turns=data["estimated_turns"],
            parallelizable_groups=data.get("parallelizable_groups", []),
            warnings=data.get("warnings", []),
            notes=data.get("notes", []),
        )

    def format_display(self) -> str:
        """Format plan for terminal display."""
        lines = [
            f"## Plan: {self.task[:50]}...",
            f"Summary: {self.summary}",
            f"Complexity: {self.total_complexity} | Est. turns: {self.estimated_turns}",
            "",
            "### Steps:",
        ]

        for step in self.steps:
            deps = f" (after: {step.dependencies})" if step.dependencies else ""
            agent = f" [{step.agent_type}]" if step.agent_type else ""
            lines.append(f"  {step.number}. {step.description}{deps}{agent}")

        if self.parallelizable_groups:
            lines.append("")
            lines.append("### Parallel groups:")
            for i, group in enumerate(self.parallelizable_groups):
                lines.append(f"  Group {i+1}: Steps {group}")

        if self.warnings:
            lines.append("")
            lines.append("### Warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")

        return "\n".join(lines)


class PlannerAgent(Agent[ExecutionPlan]):
    """
    Agent for task decomposition and planning.

    Takes a complex task description and produces a step-by-step
    execution plan with dependencies and complexity estimates.

    Features:
    - Adaptive step count based on cognitive state
    - Dependency detection
    - Parallel execution grouping
    - Agent type suggestions for delegation

    Example:
        agent = PlannerAgent()
        result = await agent.run(
            "Implement user authentication with JWT tokens",
            {"files": ["src/auth/"], "scope": "medium"}
        )
        plan = result.result
    """

    agent_type = "planner"

    # Complexity budgets based on cognitive state
    STEP_LIMITS = {
        "depleted": 3,
        "low": 5,
        "medium": 7,
        "high": 10,
    }

    def __init__(self, config: AgentConfig = None):
        super().__init__(config)
        self._step_limit = self.STEP_LIMITS.get(
            self.config.energy_level, 7
        )

    def _get_step_count(self) -> int:
        """Planner has 4 phases."""
        return 4

    async def _execute(self, task: str, context: Dict[str, Any]) -> ExecutionPlan:
        """
        Execute planning process.

        Phases:
        1. Analyze task requirements
        2. Identify components and dependencies
        3. Generate execution steps
        4. Optimize and finalize plan
        """
        self.increment_turn()

        # Phase 1: Analyze requirements
        await self.report_progress(1, "Analyzing task requirements")
        analysis = self._analyze_task(task, context)

        # Phase 2: Identify components
        await self.report_progress(2, "Identifying components and dependencies")
        components = self._identify_components(task, context, analysis)

        # Phase 3: Generate steps
        await self.report_progress(3, "Generating execution steps")
        steps = self._generate_steps(task, components, context)

        # Phase 4: Optimize
        await self.report_progress(4, "Optimizing plan")
        plan = self._create_plan(task, steps, context)

        return plan

    def _analyze_task(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze task to understand requirements."""
        task_lower = task.lower()

        # Detect task categories
        categories = []
        if any(w in task_lower for w in ["find", "search", "look for", "where", "explore"]):
            categories.append("exploration")
        if any(w in task_lower for w in ["implement", "create", "build", "add", "write"]):
            categories.append("implementation")
        if any(w in task_lower for w in ["fix", "bug", "error", "issue", "debug"]):
            categories.append("debugging")
        if any(w in task_lower for w in ["test", "verify", "check", "validate"]):
            categories.append("testing")
        if any(w in task_lower for w in ["review", "analyze", "audit"]):
            categories.append("review")
        if any(w in task_lower for w in ["refactor", "improve", "optimize"]):
            categories.append("refactoring")

        if not categories:
            categories = ["implementation"]  # Default

        # Detect scope
        scope = context.get("scope", "medium")
        files = context.get("files", [])

        # Estimate complexity
        if len(files) > 10 or scope == "large":
            complexity = "complex"
        elif len(files) > 3 or scope == "medium":
            complexity = "moderate"
        else:
            complexity = "simple"

        return {
            "categories": categories,
            "scope": scope,
            "complexity": complexity,
            "files": files,
            "keywords": self._extract_keywords(task),
        }

    def _extract_keywords(self, task: str) -> List[str]:
        """Extract key terms from task description."""
        # Simple keyword extraction - look for important nouns
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "must",
            "this", "that", "these", "those", "i", "we", "you", "it", "they",
        }

        words = task.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords[:10]  # Limit keywords

    def _identify_components(
        self, task: str, context: Dict[str, Any], analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify task components from analysis."""
        components = []
        categories = analysis["categories"]
        files = analysis.get("files", [])

        # Always start with exploration if there are files
        if files or "exploration" in categories:
            components.append({
                "type": "exploration",
                "description": "Understand existing code and patterns",
                "files": files[:5],  # Limit files per component
            })

        # Add components based on categories
        if "implementation" in categories:
            components.append({
                "type": "implementation",
                "description": "Implement the required functionality",
                "files": [],
            })

        if "debugging" in categories:
            components.append({
                "type": "debugging",
                "description": "Debug and fix the issue",
                "files": [],
            })

        if "testing" in categories:
            components.append({
                "type": "testing",
                "description": "Write or run tests",
                "files": [],
            })

        if "review" in categories:
            components.append({
                "type": "review",
                "description": "Review code quality and patterns",
                "files": files,
            })

        if "refactoring" in categories:
            components.append({
                "type": "refactoring",
                "description": "Refactor and improve code",
                "files": [],
            })

        # Always end with verification
        if len(components) > 0:
            components.append({
                "type": "verification",
                "description": "Verify changes work correctly",
                "files": [],
            })

        return components

    def _generate_steps(
        self,
        task: str,
        components: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[PlanStep]:
        """Generate execution steps from components."""
        steps = []
        step_num = 1

        for component in components:
            comp_type = component["type"]
            comp_files = component.get("files", [])

            # Map component type to step category and agent type
            category_map = {
                "exploration": ("exploration", "explore"),
                "implementation": ("implementation", "implement"),
                "debugging": ("implementation", "implement"),
                "testing": ("testing", "test"),
                "review": ("review", "review"),
                "refactoring": ("implementation", "implement"),
                "verification": ("testing", "test"),
            }

            category, agent_type = category_map.get(comp_type, ("other", "general"))

            # Estimate complexity of this step
            if len(comp_files) > 5:
                complexity = "complex"
            elif len(comp_files) > 2:
                complexity = "moderate"
            else:
                complexity = "simple"

            # Create step
            step = PlanStep(
                number=step_num,
                description=component["description"],
                category=category,
                estimated_complexity=complexity,
                dependencies=[step_num - 1] if step_num > 1 else [],
                files_involved=comp_files,
                can_parallelize=comp_type in ("exploration", "review"),
                agent_type=agent_type,
            )
            steps.append(step)
            step_num += 1

            # Limit steps based on cognitive state
            if step_num > self._step_limit:
                self.add_warning(f"Plan truncated to {self._step_limit} steps due to cognitive limits")
                break

        return steps

    def _create_plan(
        self,
        task: str,
        steps: List[PlanStep],
        context: Dict[str, Any],
    ) -> ExecutionPlan:
        """Create final execution plan."""
        # Calculate overall complexity from step complexities
        complexities = [s.estimated_complexity for s in steps]
        if "complex" in complexities:
            total_complexity = "complex"
        elif complexities.count("moderate") > len(complexities) // 2:
            total_complexity = "moderate"
        else:
            total_complexity = "simple"

        # Also consider context-level scope and file count
        # Large scope or many files elevates complexity
        scope = context.get("scope", "medium")
        files = context.get("files", [])
        if len(files) > 10 or scope == "large":
            total_complexity = "complex"
        elif len(files) > 3 or scope == "medium":
            if total_complexity == "simple":
                total_complexity = "moderate"

        # Estimate turns (2-3 turns per step)
        estimated_turns = sum(
            3 if s.estimated_complexity == "complex" else
            2 if s.estimated_complexity == "moderate" else 1
            for s in steps
        )

        # Identify parallel groups
        parallel_groups = self._find_parallel_groups(steps)

        # Generate summary
        summary = self._generate_summary(task, steps)

        # Collect warnings
        warnings = self._warnings.copy()
        if total_complexity == "complex" and self.config.energy_level in ("low", "depleted"):
            warnings.append("Complex task with low energy - consider breaking into sessions")

        # Generate notes
        notes = []
        if parallel_groups:
            notes.append(f"Contains {len(parallel_groups)} parallelizable groups")
        if any(s.agent_type for s in steps):
            # [He2025] Use sorted_set_to_list for deterministic ordering
            agent_types = sorted_set_to_list(set(s.agent_type for s in steps if s.agent_type))
            notes.append(f"Suggested agents: {', '.join(agent_types)}")

        return ExecutionPlan(
            task=task,
            summary=summary,
            steps=steps,
            total_complexity=total_complexity,
            estimated_turns=estimated_turns,
            parallelizable_groups=parallel_groups,
            warnings=warnings,
            notes=notes,
        )

    def _find_parallel_groups(self, steps: List[PlanStep]) -> List[List[int]]:
        """Find groups of steps that can run in parallel."""
        groups = []
        current_group = []

        for step in steps:
            if step.can_parallelize:
                current_group.append(step.number)
            else:
                if len(current_group) > 1:
                    groups.append(current_group)
                current_group = []

        # Check final group
        if len(current_group) > 1:
            groups.append(current_group)

        return groups

    def _generate_summary(self, task: str, steps: List[PlanStep]) -> str:
        """Generate plan summary."""
        step_count = len(steps)
        # [He2025] Use sorted_set_to_list for deterministic ordering
        categories = sorted_set_to_list(set(s.category for s in steps))

        if step_count == 1:
            return f"Single-step {categories[0]} task"
        elif step_count <= 3:
            return f"Simple {step_count}-step plan: {', '.join(categories)}"
        else:
            return f"Multi-step plan ({step_count} steps) covering {', '.join(categories)}"


__all__ = [
    "PlannerAgent",
    "PlanStep",
    "ExecutionPlan",
]
