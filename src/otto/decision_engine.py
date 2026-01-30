"""
Orchestra Decision Engine

The central orchestration layer that makes work/delegate/protect decisions
for incoming tasks. Integrates cognitive state, agent coordination, and
flow protection into a unified decision surface.

Philosophy: "Orchestra helps you finish projects by knowing when to do the
work yourself, when to delegate to agents, and when to protect your flow."

ThinkingMachines [He2025] Compliance:
- Fixed evaluation order
- Deterministic routing
- State snapshot before decisions
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple
import warnings
from enum import Enum
from datetime import datetime
import hashlib

from .agent_coordinator import (
    AgentCoordinator, FlowProtector, Decision, DecisionMode,
    TaskProfile, AgentType, CognitiveContext, AgentContext
)


class TaskCategory(Enum):
    """Categories of tasks for routing."""
    EXPLORATION = "exploration"      # Codebase search, understanding
    IMPLEMENTATION = "implementation" # Writing code
    DEBUGGING = "debugging"          # Finding and fixing issues
    REVIEW = "review"                # Code review, analysis
    RESEARCH = "research"            # External research
    DOCUMENTATION = "documentation"  # Writing docs
    PLANNING = "planning"            # Architecture, design
    SIMPLE = "simple"                # Quick actions


class SignalCategory(Enum):
    """Signal categories for routing priority (PRISM-aligned)."""
    EMOTIONAL = "emotional"    # Highest priority - safety first
    MODE_SWITCH = "mode_switch"
    DOMAIN = "domain"
    TASK = "task"
    DEFAULT = "default"        # Lowest priority


class ComplexityTier(Enum):
    """Complexity tiers for routing decisions."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class BudgetTier(Enum):
    """Cognitive budget tiers."""
    LOW = "low"       # < 0.3
    MEDIUM = "medium" # 0.3 - 0.7
    HIGH = "high"     # > 0.7


class FlowState(Enum):
    """Flow states for PROTECT decisions."""
    COLD_START = "cold_start"
    BUILDING = "building"
    ROLLING = "rolling"
    PEAK = "peak"
    CRASHED = "crashed"


# =============================================================================
# PRE-COMPUTED ROUTING TABLE (ThinkingMachines [He2025] Batch-Invariance)
# =============================================================================
# Key: (signal_category, complexity_tier, budget_tier, flow_state)
# Value: (DecisionMode, agent_list, rationale)
# Use "*" as wildcard for any value in that position
# First match wins - order matters!

ROUTING_TABLE = [
    # ---------------------------------------------------------------------
    # EMOTIONAL signals → PROTECT (safety first, constitutional principle)
    # ---------------------------------------------------------------------
    (("emotional", "*", "*", "*"),
     (DecisionMode.PROTECT, [], "Emotional safety - protect flow")),

    # ---------------------------------------------------------------------
    # PEAK flow → PROTECT (preserve momentum at all costs)
    # ---------------------------------------------------------------------
    (("*", "*", "*", "peak"),
     (DecisionMode.PROTECT, [], "Peak flow - protecting momentum")),

    # ---------------------------------------------------------------------
    # RED burnout (handled by safety gate, but table entry for completeness)
    # ---------------------------------------------------------------------
    # Note: burnout=RED should be caught by safety gate before table lookup

    # ---------------------------------------------------------------------
    # LOW budget + simple → WORK (direct action, minimal overhead)
    # ---------------------------------------------------------------------
    (("*", "simple", "low", "*"),
     (DecisionMode.WORK, ["echo_curator"], "Low budget + simple task - direct work")),

    (("*", "simple", "medium", "*"),
     (DecisionMode.WORK, ["echo_curator", "moe_router"], "Simple task - direct work")),

    # ---------------------------------------------------------------------
    # HIGH budget + complex → DELEGATE (parallel execution)
    # ---------------------------------------------------------------------
    (("*", "complex", "high", "*"),
     (DecisionMode.DELEGATE, ["domain_intelligence", "moe_router", "code_generator", "world_modeler"],
      "Complex task + high budget - parallel delegation")),

    (("*", "complex", "medium", "*"),
     (DecisionMode.DELEGATE, ["echo_curator", "moe_router", "code_generator"],
      "Complex task + medium budget - targeted delegation")),

    # ---------------------------------------------------------------------
    # MODERATE complexity → conditional WORK or DELEGATE
    # ---------------------------------------------------------------------
    (("*", "moderate", "high", "rolling"),
     (DecisionMode.DELEGATE, ["echo_curator", "domain_intelligence", "moe_router"],
      "Moderate + high budget + rolling momentum - delegate to maintain flow")),

    (("*", "moderate", "high", "*"),
     (DecisionMode.WORK, ["echo_curator", "moe_router", "code_generator"],
      "Moderate + high budget - direct work with support")),

    (("*", "moderate", "medium", "*"),
     (DecisionMode.WORK, ["echo_curator", "moe_router"],
      "Moderate + medium budget - focused direct work")),

    (("*", "moderate", "low", "*"),
     (DecisionMode.WORK, ["echo_curator"],
      "Moderate + low budget - minimal direct work")),

    # ---------------------------------------------------------------------
    # CRASHED momentum → WORK with minimal set (recovery mode)
    # ---------------------------------------------------------------------
    (("*", "*", "*", "crashed"),
     (DecisionMode.WORK, ["echo_curator"],
      "Crashed momentum - minimal work for easy wins")),

    # ---------------------------------------------------------------------
    # DEFAULT → WORK with standard agent set
    # ---------------------------------------------------------------------
    (("*", "*", "*", "*"),
     (DecisionMode.WORK, ["echo_curator", "moe_router"],
      "Default - direct work with standard support")),
]


@dataclass
class StateSnapshot:
    """
    Immutable snapshot of cognitive state for deterministic routing.

    ThinkingMachines [He2025]: Snapshot taken BEFORE any decision
    to ensure batch-invariance.
    """
    signal_category: str
    complexity_tier: str
    budget_tier: str
    flow_state: str
    burnout_level: str
    energy_level: str
    can_spawn_agents: bool
    checksum: str = ""

    def __post_init__(self):
        """Generate deterministic checksum of state."""
        data = f"{self.signal_category}|{self.complexity_tier}|{self.budget_tier}|{self.flow_state}"
        self.checksum = hashlib.md5(data.encode()).hexdigest()[:8]

    def to_routing_key(self) -> Tuple[str, str, str, str]:
        """Convert to routing table lookup key."""
        return (self.signal_category, self.complexity_tier, self.budget_tier, self.flow_state)


@dataclass
class TaskRequest:
    """Incoming task request."""
    description: str
    category: TaskCategory
    files_involved: List[str] = field(default_factory=list)
    requires_user_input: bool = False
    estimated_scope: str = "small"  # small, medium, large
    urgency: str = "normal"  # low, normal, high, critical

    def to_profile(self) -> TaskProfile:
        """Convert to TaskProfile for coordinator."""
        complexity = {
            "small": "simple",
            "medium": "moderate",
            "large": "complex"
        }.get(self.estimated_scope, "moderate")

        return TaskProfile(
            description=self.description,
            estimated_complexity=complexity,
            parallelizable=len(self.files_involved) > 3,
            requires_focus=self.category in (TaskCategory.IMPLEMENTATION, TaskCategory.DEBUGGING),
            file_count=len(self.files_involved),
            domain=self.category.value
        )


@dataclass
class ExecutionPlan:
    """Plan for executing a task."""
    decision: Decision
    task: TaskRequest
    steps: List[str]
    agent_configs: List[Dict[str, Any]] = field(default_factory=list)
    flow_protection_enabled: bool = False
    checksum: str = ""
    _state_snapshot: Optional['StateSnapshot'] = field(default=None, repr=False)

    def __post_init__(self):
        """Generate deterministic checksum."""
        data = f"{self.decision.mode.value}|{self.task.description}|{len(self.steps)}"
        self.checksum = hashlib.md5(data.encode()).hexdigest()[:8]

    def get_routed_agents(self) -> List[str]:
        """
        Get list of agents to execute based on routing decision.

        Used by FrameworkOrchestrator to know which agents to run.
        """
        if hasattr(self.decision, '_routing_agents') and self.decision._routing_agents:
            return self.decision._routing_agents
        # Fallback: extract from agent_configs
        return [cfg.get("type", "general") for cfg in self.agent_configs]

    def get_snapshot_checksum(self) -> str:
        """Get checksum of state snapshot for reproducibility verification."""
        if self._state_snapshot:
            return self._state_snapshot.checksum
        return ""


class DecisionEngine:
    """
    Central decision-making engine for Orchestra.

    Evaluates incoming tasks and produces execution plans that
    respect cognitive state and optimize for project completion.

    ThinkingMachines [He2025] Compliance:
    - Pre-computed routing table (ROUTING_TABLE)
    - State snapshot BEFORE decisions
    - Deterministic table lookup (first-match-wins)
    - Checksum verification for reproducibility
    """

    def __init__(self, cognitive_stage=None, use_table_routing: bool = True):
        self.cognitive_stage = cognitive_stage
        self.coordinator = AgentCoordinator(cognitive_stage)
        self.flow_protector = FlowProtector(self.coordinator)
        self.execution_history: List[ExecutionPlan] = []
        self.use_table_routing = use_table_routing  # Feature flag for migration

    def _create_state_snapshot(self, request: TaskRequest, context: Dict[str, Any] = None) -> StateSnapshot:
        """
        Create immutable state snapshot for deterministic routing.

        ThinkingMachines [He2025]: Snapshot taken BEFORE any decision.
        """
        context = context or {}
        cog_context = self.coordinator.get_cognitive_context()

        # Categorize signal (from PRISM if available, else from request)
        prism_signals = context.get("prism_signals", {})
        signal_category = self._categorize_signal(prism_signals, request)

        # Categorize complexity
        complexity_tier = self._categorize_complexity(request)

        # Categorize budget
        budget = cog_context.cognitive_budget()
        if budget < 0.3:
            budget_tier = "low"
        elif budget < 0.7:
            budget_tier = "medium"
        else:
            budget_tier = "high"

        # Flow state
        flow_state = cog_context.momentum_phase

        return StateSnapshot(
            signal_category=signal_category,
            complexity_tier=complexity_tier,
            budget_tier=budget_tier,
            flow_state=flow_state,
            burnout_level=cog_context.burnout_level,
            energy_level=cog_context.energy_level,
            can_spawn_agents=cog_context.can_accept_new_agent()
        )

    def _categorize_signal(self, prism_signals: Dict[str, Any], request: TaskRequest) -> str:
        """Categorize signals into routing priority (PRISM-aligned)."""
        # Check PRISM signals first (highest priority)
        if prism_signals:
            emotional_signals = prism_signals.get("emotional_signals", [])
            if emotional_signals and any(s in ["frustrated", "overwhelmed", "stuck", "depleted"]
                                          for s in emotional_signals):
                return "emotional"

            mode_signals = prism_signals.get("mode_signals", [])
            if mode_signals and any(s in ["switch", "change", "explore", "what if"]
                                     for s in mode_signals):
                return "mode_switch"

            domain_signals = prism_signals.get("domain_signals", [])
            if domain_signals:
                return "domain"

        # Fall back to task category
        return "task"

    def _categorize_complexity(self, request: TaskRequest) -> str:
        """Categorize task complexity for routing."""
        scope_to_complexity = {
            "small": "simple",
            "medium": "moderate",
            "large": "complex"
        }
        base = scope_to_complexity.get(request.estimated_scope, "moderate")

        # Adjust based on file count
        file_count = len(request.files_involved)
        if file_count > 10:
            return "complex"
        elif file_count > 3 and base == "simple":
            return "moderate"

        return base

    def _table_lookup(self, snapshot: StateSnapshot) -> Tuple[DecisionMode, List[str], str]:
        """
        Perform deterministic table lookup.

        ThinkingMachines [He2025]: First-match-wins with wildcard support.

        Returns:
            (DecisionMode, agent_list, rationale)
        """
        key = snapshot.to_routing_key()

        for pattern, result in ROUTING_TABLE:
            if self._pattern_matches(pattern, key):
                return result

        # Should never reach here (default pattern catches all)
        return (DecisionMode.WORK, ["echo_curator"], "Fallback - no pattern matched")

    def _pattern_matches(self, pattern: Tuple[str, str, str, str],
                         key: Tuple[str, str, str, str]) -> bool:
        """Check if pattern matches key (with wildcard support)."""
        for p, k in zip(pattern, key):
            if p != "*" and p != k:
                return False
        return True

    def process_task(self, request: TaskRequest, context: Dict[str, Any] = None) -> ExecutionPlan:
        """
        Process an incoming task request.

        This is the main entry point for all orchestration. It:
        1. Takes state snapshot (ThinkingMachines [He2025])
        2. Performs table lookup for deterministic routing
        3. Builds execution plan based on work/delegate/protect decision

        Args:
            request: The task request to process
            context: Optional context dict (PRISM signals, etc.)

        Returns:
            ExecutionPlan with decision, steps, and agent configs
        """
        context = context or {}

        # =================================================================
        # PHASE 1: STATE SNAPSHOT (ThinkingMachines [He2025])
        # =================================================================
        snapshot = self._create_state_snapshot(request, context)

        # =================================================================
        # PHASE 2: SAFETY GATE (Cognitive safety constraints)
        # =================================================================
        # RED burnout → force recovery, no agents
        if snapshot.burnout_level == "RED":
            decision = Decision(
                mode=DecisionMode.PROTECT,
                rationale="RED burnout - recovery mode only",
                queue_results=True,
                protect_until="burnout_exits_red"
            )
            return self._build_protect_plan(request, decision, recovery_menu=True)

        # Can't spawn agents → force WORK
        force_work = not snapshot.can_spawn_agents

        # =================================================================
        # PHASE 3: ROUTE (table lookup or legacy)
        # =================================================================
        if self.use_table_routing:
            mode, agents, rationale = self._table_lookup(snapshot)

            # Safety override: force WORK if can't spawn
            if force_work and mode == DecisionMode.DELEGATE:
                mode = DecisionMode.WORK
                rationale = f"Forced WORK (can't spawn agents): {rationale}"

            # Build decision from table lookup
            decision = Decision(
                mode=mode,
                rationale=f"[TABLE:{snapshot.checksum}] {rationale}",
                agent_type=self._infer_agent_type(request) if mode == DecisionMode.DELEGATE else None,
                agent_count=len(agents) if mode == DecisionMode.DELEGATE else 0,
                queue_results=mode == DecisionMode.PROTECT,
                protect_until="flow_exits_peak" if mode == DecisionMode.PROTECT else None
            )

            # Store agents in decision for orchestrator
            decision._routing_agents = agents
        else:
            # Legacy path: use coordinator.decide()
            profile = request.to_profile()
            decision = self.coordinator.decide(profile)
            decision._routing_agents = None

        # =================================================================
        # PHASE 4: BUILD EXECUTION PLAN
        # =================================================================
        if decision.mode == DecisionMode.WORK:
            plan = self._build_work_plan(request, decision)
        elif decision.mode == DecisionMode.DELEGATE:
            plan = self._build_delegate_plan(request, decision)
        else:  # PROTECT
            plan = self._build_protect_plan(request, decision)

        # Record snapshot for reproducibility
        plan._state_snapshot = snapshot

        self.execution_history.append(plan)
        return plan

    def _infer_agent_type(self, request: TaskRequest) -> AgentType:
        """Infer agent type from task category."""
        category_to_agent = {
            TaskCategory.EXPLORATION: AgentType.EXPLORE,
            TaskCategory.IMPLEMENTATION: AgentType.IMPLEMENT,
            TaskCategory.DEBUGGING: AgentType.IMPLEMENT,
            TaskCategory.REVIEW: AgentType.REVIEW,
            TaskCategory.RESEARCH: AgentType.RESEARCH,
            TaskCategory.DOCUMENTATION: AgentType.GENERAL,
            TaskCategory.PLANNING: AgentType.GENERAL,
            TaskCategory.SIMPLE: AgentType.GENERAL,
        }
        return category_to_agent.get(request.category, AgentType.GENERAL)

    def _build_work_plan(self, request: TaskRequest, decision: Decision) -> ExecutionPlan:
        """Build plan for direct work."""
        steps = self._generate_work_steps(request)

        return ExecutionPlan(
            decision=decision,
            task=request,
            steps=steps,
            flow_protection_enabled=False
        )

    def _build_delegate_plan(self, request: TaskRequest, decision: Decision) -> ExecutionPlan:
        """Build plan for delegated work."""
        steps = []
        agent_configs = []

        # Determine agent configuration
        if decision.agent_count == 1:
            # Single agent
            steps.append(f"Spawn {decision.agent_type.value} agent for: {request.description}")
            steps.append("Monitor progress")
            steps.append("Present results when complete")

            agent_configs.append({
                "type": decision.agent_type,
                "task": request.description,
                "files": request.files_involved,
                "max_turns": self._calculate_max_turns(request)
            })
        else:
            # Multiple parallel agents
            file_groups = self._partition_files(request.files_involved, decision.agent_count)

            for i, file_group in enumerate(file_groups):
                steps.append(f"Spawn agent {i+1}/{decision.agent_count} for: {', '.join(file_group[:2])}...")
                agent_configs.append({
                    "type": decision.agent_type,
                    "task": f"{request.description} (group {i+1})",
                    "files": file_group,
                    "max_turns": self._calculate_max_turns(request) // decision.agent_count
                })

            steps.append("Coordinate parallel execution")
            steps.append("Aggregate results")

        return ExecutionPlan(
            decision=decision,
            task=request,
            steps=steps,
            agent_configs=agent_configs,
            flow_protection_enabled=False
        )

    def _build_protect_plan(self, request: TaskRequest, decision: Decision,
                            recovery_menu: bool = False) -> ExecutionPlan:
        """Build plan for flow-protected execution."""
        if recovery_menu:
            # RED burnout recovery mode
            steps = [
                "RECOVERY MODE ACTIVATED",
                "Options: 1) Done for today (save state)",
                "         2) Switch to easy wins",
                "         3) Talk it out (no code)",
                "         4) 15-min break, reassess",
                "         5) Scope cut"
            ]
        else:
            steps = [
                "Queue task for later execution",
                "Continue current flow",
                f"Execute when: {decision.protect_until}"
            ]

        return ExecutionPlan(
            decision=decision,
            task=request,
            steps=steps,
            flow_protection_enabled=True
        )

    def _generate_work_steps(self, request: TaskRequest) -> List[str]:
        """Generate execution steps for direct work."""
        category_steps = {
            TaskCategory.EXPLORATION: [
                "Search codebase for relevant patterns",
                "Read key files",
                "Synthesize findings"
            ],
            TaskCategory.IMPLEMENTATION: [
                "Read existing code",
                "Plan changes",
                "Implement",
                "Verify"
            ],
            TaskCategory.DEBUGGING: [
                "Reproduce issue",
                "Isolate cause",
                "Implement fix",
                "Verify fix"
            ],
            TaskCategory.REVIEW: [
                "Read code",
                "Identify issues",
                "Provide feedback"
            ],
            TaskCategory.RESEARCH: [
                "Search documentation",
                "Gather information",
                "Summarize findings"
            ],
            TaskCategory.DOCUMENTATION: [
                "Review code to document",
                "Draft documentation",
                "Format and finalize"
            ],
            TaskCategory.PLANNING: [
                "Analyze requirements",
                "Design approach",
                "Document plan"
            ],
            TaskCategory.SIMPLE: [
                "Execute directly"
            ]
        }

        base_steps = category_steps.get(request.category, ["Execute task"])

        # Add file-specific steps if files are involved
        if request.files_involved:
            file_steps = [f"Work on: {f}" for f in request.files_involved[:3]]
            if len(request.files_involved) > 3:
                file_steps.append(f"...and {len(request.files_involved) - 3} more files")
            return base_steps[:1] + file_steps + base_steps[1:]

        return base_steps

    def _calculate_max_turns(self, request: TaskRequest) -> int:
        """Calculate max turns for agent based on task scope."""
        scope_turns = {
            "small": 5,
            "medium": 15,
            "large": 30
        }
        return scope_turns.get(request.estimated_scope, 10)

    def _partition_files(self, files: List[str], count: int) -> List[List[str]]:
        """Partition files into groups for parallel agents."""
        if not files:
            return [[]]

        # Evenly distribute files
        group_size = (len(files) + count - 1) // count
        return [files[i:i + group_size] for i in range(0, len(files), group_size)]

    def handle_agent_result(self, agent_id: str, result: Any) -> Tuple[bool, Optional[str]]:
        """
        Handle result from completed agent.

        Returns:
            (should_present, formatted_result)
        """
        queued = self.coordinator.agent_completed(agent_id, result)

        if queued is None:
            # Result was queued due to flow protection
            return False, None

        # Format for current state
        context = self.coordinator.get_cognitive_context()
        formatted = self.coordinator.format_results_for_state([queued], context)

        return True, formatted

    def check_and_deliver_queued(self) -> Optional[str]:
        """
        Check if we should deliver queued results.

        Called periodically or at natural break points.
        """
        # Check if flow protection should be released
        if self.coordinator.check_flow_exit():
            # Flow exited, get queued results
            results = self.coordinator.get_queued_results()
            if results:
                context = self.coordinator.get_cognitive_context()
                return self.coordinator.format_results_for_state(results, context)

        return None

    def get_pending_work(self) -> Dict[str, Any]:
        """Get status of pending work."""
        return {
            "coordinator_status": self.coordinator.get_status(),
            "pending_interrupts": len(self.flow_protector.interrupt_queue),
            "executions_today": len(self.execution_history)
        }

    def suggest_next_action(self) -> str:
        """
        Suggest what to do next based on current state.

        This is the "finishing projects" intelligence.
        """
        context = self.coordinator.get_cognitive_context()
        status = self.coordinator.get_status()

        # Check agent results first
        if status["queued_results"] > 0 and not status["flow_protection"]:
            return f"Review {status['queued_results']} queued agent result(s)"

        # Check energy/burnout
        if context.burnout_level == "RED":
            return "Take a break. Recovery mode."
        if context.burnout_level == "ORANGE":
            return "Consider switching to easy wins or taking a break."
        if context.energy_level == "depleted":
            return "Energy depleted. Save progress and rest."
        if context.energy_level == "low":
            return "Low energy. Finish current task, then break."

        # Check momentum
        if context.momentum_phase == "peak":
            return "Peak flow. Keep going with current task."
        if context.momentum_phase == "rolling":
            return "Good momentum. Continue or queue next task."
        if context.momentum_phase == "crashed":
            return "Momentum crashed. Start small or rest."
        if context.momentum_phase == "cold_start":
            return "Start with a small win to build momentum."

        # Default
        if status["active_agents"] > 0:
            return f"Waiting on {status['active_agents']} agent(s). Continue current work."

        return "Ready for next task."


# Quick task processing helper
def process_quick(description: str, category: str = "simple",
                  files: List[str] = None) -> ExecutionPlan:
    """
    Quick task processing for common cases.

    Usage:
        plan = process_quick("Find all TODO comments", "exploration", ["src/**/*.py"])
    """
    engine = DecisionEngine()

    category_enum = TaskCategory[category.upper()] if category.upper() in TaskCategory.__members__ else TaskCategory.SIMPLE

    request = TaskRequest(
        description=description,
        category=category_enum,
        files_involved=files or [],
        estimated_scope="small" if not files or len(files) < 5 else "medium"
    )

    return engine.process_task(request)
