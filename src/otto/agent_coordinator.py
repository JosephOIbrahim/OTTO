"""
Orchestra Agent Coordinator

Implements the work/delegate/protect decision model:
- WORK: Direct action when focused and task is simple
- DELEGATE: Spawn agents when task benefits from parallelism and cognitive budget allows
- PROTECT: Queue results and shield flow state from interruption

Philosophy: Agents are energy investments. Every spawn costs cognitive budget.
The coordinator decides when that investment pays off vs. when direct work is better.

ThinkingMachines [He2025] Compliance:
- Fixed decision order (work -> delegate -> protect)
- Deterministic routing based on state
- State snapshot before any decision
"""

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Deque
from datetime import datetime
from pathlib import Path
import hashlib
import json
import logging
import time

logger = logging.getLogger(__name__)


class DecisionMode(Enum):
    """The three modes of agent coordination."""
    WORK = "work"           # Do it yourself
    DELEGATE = "delegate"   # Spawn agent(s)
    PROTECT = "protect"     # Shield flow, queue results


class AgentType(Enum):
    """Types of agents that can be spawned."""
    EXPLORE = "explore"         # Codebase exploration
    IMPLEMENT = "implement"     # Code implementation
    REVIEW = "review"           # Code review
    TEST = "test"               # Test execution
    RESEARCH = "research"       # Web/doc research
    GENERAL = "general"         # General purpose


@dataclass
class TaskProfile:
    """Profile of a task for decision-making."""
    description: str
    estimated_complexity: str  # simple, moderate, complex
    parallelizable: bool
    requires_focus: bool
    file_count: int
    domain: str

    def complexity_score(self) -> float:
        """Return 0-1 complexity score."""
        scores = {"simple": 0.2, "moderate": 0.5, "complex": 0.9}
        return scores.get(self.estimated_complexity, 0.5)


@dataclass
class CognitiveContext:
    """Current cognitive state for decision-making."""
    energy_level: str           # high, medium, low, depleted
    burnout_level: str          # GREEN, YELLOW, ORANGE, RED
    momentum_phase: str         # cold_start, building, rolling, peak, crashed
    active_agents: int          # Currently running agents
    working_memory_used: int    # Items in working memory
    in_flow_state: bool         # Is user in hyperfocus/flow
    mode: str                   # focused, exploring, teaching, recovery

    # Constitutional limits (from LIVRPS SPECIALIZES layer)
    max_parallel_agents: int = 3
    max_agent_depth: int = 3
    working_memory_limit: int = 3

    def cognitive_budget(self) -> float:
        """Calculate remaining cognitive budget (0-1)."""
        energy_scores = {"high": 1.0, "medium": 0.7, "low": 0.3, "depleted": 0.0}
        burnout_scores = {"GREEN": 1.0, "YELLOW": 0.7, "ORANGE": 0.3, "RED": 0.0}

        energy = energy_scores.get(self.energy_level, 0.5)
        burnout = burnout_scores.get(self.burnout_level, 0.5)

        # Working memory cost
        memory_cost = self.working_memory_used / self.working_memory_limit

        # Agent overhead cost
        agent_cost = self.active_agents / self.max_parallel_agents

        # Combined budget
        return max(0.0, min(1.0, (energy + burnout) / 2 - memory_cost * 0.3 - agent_cost * 0.2))

    def can_accept_new_agent(self) -> bool:
        """Check if we can spawn another agent."""
        return (
            self.active_agents < self.max_parallel_agents and
            self.working_memory_used < self.working_memory_limit and
            self.burnout_level not in ("ORANGE", "RED") and
            self.energy_level != "depleted"
        )


@dataclass
class Decision:
    """A work/delegate/protect decision with rationale."""
    mode: DecisionMode
    rationale: str
    agent_type: Optional[AgentType] = None
    agent_count: int = 0
    queue_results: bool = False
    protect_until: Optional[str] = None  # Condition for releasing protection
    checksum: str = ""

    def __post_init__(self):
        """Generate deterministic checksum."""
        data = f"{self.mode.value}|{self.rationale}|{self.agent_type}|{self.agent_count}"
        self.checksum = hashlib.md5(data.encode()).hexdigest()[:8]


@dataclass
class QueuedResult:
    """A result queued for later presentation."""
    agent_id: str
    result_type: str
    summary: str
    full_result: Any
    timestamp: datetime
    priority: int  # 1=high, 2=medium, 3=low
    presented: bool = False


@dataclass
class AgentContext:
    """Context to propagate to child agents (LIVRPS INHERITS layer)."""
    parent_session_id: str
    burnout_level: str          # MUST propagate for safety
    energy_level: str           # MUST propagate for pacing
    active_project: str         # Context continuity
    original_goal: str          # Goal alignment
    depth: int                  # Agent chain depth

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parent_session_id": self.parent_session_id,
            "burnout_level": self.burnout_level,
            "energy_level": self.energy_level,
            "active_project": self.active_project,
            "original_goal": self.original_goal,
            "depth": self.depth
        }


class AgentCoordinator:
    """
    Coordinates agent spawning and result management.

    Core philosophy: Orchestra helps you finish projects by knowing when to
    do the work yourself, when to delegate to agents, and when to protect your flow.
    """

    # Production-ready limits [He2025]
    MAX_DECISION_HISTORY = 1000
    MAX_RESULT_QUEUE = 500
    RESULT_TTL_SECONDS = 3600  # 1 hour

    def __init__(self, cognitive_stage=None, state_dir: Path = None):
        self.cognitive_stage = cognitive_stage
        self.active_agents: Dict[str, Dict[str, Any]] = {}
        # Bounded queues for production safety [He2025]
        self.result_queue: Deque[QueuedResult] = deque(maxlen=self.MAX_RESULT_QUEUE)
        self.decision_history: Deque[Decision] = deque(maxlen=self.MAX_DECISION_HISTORY)
        self.flow_protection_active: bool = False

        # Queue persistence (v4.3.0)
        self.state_dir = state_dir or Path.home() / ".orchestra" / "state"
        self.queue_file = self.state_dir / "result_queue.json"

        # Load persisted queue on init
        self._load_queue()

    def get_cognitive_context(self) -> CognitiveContext:
        """Get current cognitive context from stage or defaults."""
        if self.cognitive_stage:
            return CognitiveContext(
                energy_level=self.cognitive_stage.get_resolved_value("energy_level", "medium"),
                burnout_level=self.cognitive_stage.get_resolved_value("burnout_level", "GREEN"),
                momentum_phase=self.cognitive_stage.get_resolved_value("momentum_phase", "cold_start"),
                active_agents=len(self.active_agents),
                working_memory_used=self.cognitive_stage.get_resolved_value("working_memory_used", 0),
                in_flow_state=self.cognitive_stage.get_resolved_value("mode", "focused") == "focused" and
                              self.cognitive_stage.get_resolved_value("momentum_phase", "") == "peak",
                mode=self.cognitive_stage.get_resolved_value("mode", "focused"),
                max_parallel_agents=self.cognitive_stage.get_resolved_value("max_parallel_agents", 3),
                max_agent_depth=self.cognitive_stage.get_resolved_value("max_agent_depth", 3),
                working_memory_limit=self.cognitive_stage.get_resolved_value("working_memory_limit", 3)
            )
        else:
            return CognitiveContext(
                energy_level="medium",
                burnout_level="GREEN",
                momentum_phase="cold_start",
                active_agents=len(self.active_agents),
                working_memory_used=0,
                in_flow_state=False,
                mode="focused"
            )

    def decide(self, task: TaskProfile) -> Decision:
        """
        Make a work/delegate/protect decision for a task.

        Decision order (FIXED for determinism):
        1. Check PROTECT conditions (flow state)
        2. Check WORK conditions (simple + focused)
        3. Check DELEGATE conditions (complex + budget available)
        4. Default to WORK
        """
        context = self.get_cognitive_context()

        # Snapshot state for determinism
        state_snapshot = {
            "energy": context.energy_level,
            "burnout": context.burnout_level,
            "momentum": context.momentum_phase,
            "agents": context.active_agents,
            "memory": context.working_memory_used,
            "flow": context.in_flow_state,
            "task_complexity": task.complexity_score()
        }

        # === Phase 1: PROTECT check ===
        if context.in_flow_state and context.momentum_phase == "peak":
            # User is in peak flow - protect at all costs
            decision = Decision(
                mode=DecisionMode.PROTECT,
                rationale="Peak flow state detected. Protecting momentum.",
                queue_results=True,
                protect_until="flow_exits_peak"
            )
            self.flow_protection_active = True
            self.decision_history.append(decision)
            return decision

        # === Phase 2: WORK check ===
        # Prefer direct work when:
        # - Task is simple
        # - User is focused
        # - Not much cognitive overhead
        if (task.complexity_score() < 0.4 and
            not task.parallelizable and
            context.mode == "focused"):
            decision = Decision(
                mode=DecisionMode.WORK,
                rationale=f"Simple task ({task.estimated_complexity}), direct action preferred."
            )
            self.decision_history.append(decision)
            return decision

        # === Phase 3: DELEGATE check ===
        # Delegate when:
        # - Task is complex or parallelizable
        # - Cognitive budget allows
        # - Not in burnout/depleted state
        if context.can_accept_new_agent():
            if task.parallelizable or task.complexity_score() > 0.6:
                agent_type = self._select_agent_type(task)
                agent_count = self._calculate_agent_count(task, context)

                if agent_count > 0:
                    decision = Decision(
                        mode=DecisionMode.DELEGATE,
                        rationale=f"Complex/parallel task. Budget: {context.cognitive_budget():.2f}. Spawning {agent_count} agent(s).",
                        agent_type=agent_type,
                        agent_count=agent_count
                    )
                    self.decision_history.append(decision)
                    return decision

        # === Phase 4: Default to WORK ===
        # When delegation isn't available, do it yourself
        if not context.can_accept_new_agent():
            rationale = "Agent limit reached or low cognitive budget. Direct work."
        else:
            rationale = "Task profile favors direct action."

        decision = Decision(
            mode=DecisionMode.WORK,
            rationale=rationale
        )
        self.decision_history.append(decision)
        return decision

    def _select_agent_type(self, task: TaskProfile) -> AgentType:
        """Select appropriate agent type based on task."""
        domain_to_agent = {
            "exploration": AgentType.EXPLORE,
            "implementation": AgentType.IMPLEMENT,
            "review": AgentType.REVIEW,
            "testing": AgentType.TEST,
            "research": AgentType.RESEARCH
        }
        return domain_to_agent.get(task.domain, AgentType.GENERAL)

    def _calculate_agent_count(self, task: TaskProfile, context: CognitiveContext) -> int:
        """Calculate how many agents to spawn."""
        available_slots = context.max_parallel_agents - context.active_agents

        if available_slots <= 0:
            return 0

        # For parallelizable tasks with multiple files
        if task.parallelizable and task.file_count > 1:
            # One agent per file group, up to available slots
            return min(
                available_slots,
                (task.file_count + 2) // 3  # ~3 files per agent
            )

        # Complex single task
        if task.complexity_score() > 0.7:
            return 1

        return 1

    def create_agent_context(self, session_id: str, goal: str, project: str = "") -> AgentContext:
        """Create context to propagate to child agents."""
        context = self.get_cognitive_context()

        return AgentContext(
            parent_session_id=session_id,
            burnout_level=context.burnout_level,
            energy_level=context.energy_level,
            active_project=project,
            original_goal=goal,
            depth=1  # Will be incremented for nested agents
        )

    def register_agent(self, agent_id: str, agent_type: AgentType, task_description: str):
        """Register a newly spawned agent."""
        self.active_agents[agent_id] = {
            "type": agent_type,
            "task": task_description,
            "started": datetime.now(),
            "status": "running"
        }

    def agent_completed(self, agent_id: str, result: Any) -> Optional[QueuedResult]:
        """
        Handle agent completion.

        If flow protection is active, queue the result.
        Otherwise, return it for immediate presentation.
        """
        if agent_id not in self.active_agents:
            return None

        agent_info = self.active_agents.pop(agent_id)

        # Create result record
        queued = QueuedResult(
            agent_id=agent_id,
            result_type=agent_info["type"].value,
            summary=self._summarize_result(result),
            full_result=result,
            timestamp=datetime.now(),
            priority=self._calculate_priority(result)
        )

        # If flow protection is active, queue it with persistence
        if self.flow_protection_active:
            self.queue_result(queued)  # Uses persistence
            return None  # Signal to not present now

        return queued

    def _summarize_result(self, result: Any) -> str:
        """Create brief summary of result."""
        if isinstance(result, str):
            return result[:100] + "..." if len(result) > 100 else result
        if isinstance(result, dict):
            if "summary" in result:
                return result["summary"]
            if "status" in result:
                return f"Status: {result['status']}"
        return "Task completed"

    def _calculate_priority(self, result: Any) -> int:
        """Calculate presentation priority (1=high, 3=low)."""
        if isinstance(result, dict):
            if result.get("has_errors"):
                return 1  # Errors are high priority
            if result.get("needs_attention"):
                return 1
            if result.get("informational"):
                return 3
        return 2  # Default medium

    def check_flow_exit(self) -> bool:
        """Check if flow protection should be released."""
        context = self.get_cognitive_context()

        # Exit flow protection when:
        # - No longer in peak momentum
        # - User explicitly requests results
        # - Energy drops significantly
        if context.momentum_phase != "peak":
            self.flow_protection_active = False
            return True

        return False

    def get_queued_results(self, max_results: int = 3) -> List[QueuedResult]:
        """
        Get queued results for presentation.

        Respects working memory limit - don't overwhelm with results.
        """
        # Sort by priority, then timestamp, then agent_id for determinism [He2025]
        pending = [r for r in self.result_queue if not r.presented]
        pending.sort(key=lambda r: (r.priority, r.timestamp, r.agent_id))

        # Return up to working memory limit
        to_present = pending[:max_results]

        for result in to_present:
            result.presented = True

        return to_present

    def format_results_for_state(self, results: List[QueuedResult], context: CognitiveContext) -> str:
        """
        Format results appropriately for current cognitive state.

        - Depleted: Ultra-brief summaries only
        - Low energy: Brief summaries
        - Normal: Full results
        """
        if context.energy_level == "depleted":
            # Ultra-brief: just status indicators
            lines = []
            for r in results:
                status = "[OK]" if r.priority > 1 else "[!]"
                lines.append(f"{status} {r.result_type}: {r.summary[:50]}")
            return "\n".join(lines)

        elif context.energy_level == "low":
            # Brief summaries
            lines = []
            for r in results:
                lines.append(f"## {r.result_type.title()}")
                lines.append(r.summary)
                lines.append("")
            return "\n".join(lines)

        else:
            # Full results
            lines = []
            for r in results:
                lines.append(f"## {r.result_type.title()} (Agent: {r.agent_id})")
                lines.append(r.summary)
                if isinstance(r.full_result, dict):
                    for k, v in r.full_result.items():
                        if k not in ("summary", "status"):
                            lines.append(f"- {k}: {v}")
                lines.append("")
            return "\n".join(lines)

    def get_status(self) -> Dict[str, Any]:
        """Get current coordinator status."""
        context = self.get_cognitive_context()

        return {
            "active_agents": len(self.active_agents),
            "agents": {aid: info["task"] for aid, info in self.active_agents.items()},
            "queued_results": len([r for r in self.result_queue if not r.presented]),
            "flow_protection": self.flow_protection_active,
            "cognitive_budget": context.cognitive_budget(),
            "can_spawn": context.can_accept_new_agent(),
            "decisions_made": len(self.decision_history)
        }

    # =========================================================================
    # Queue Persistence (v4.3.0 - PROTECT mode support)
    # =========================================================================

    def _load_queue(self):
        """Load persisted queue from disk."""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r') as f:
                    data = json.load(f)

                self.result_queue = []
                for item in data.get("results", []):
                    self.result_queue.append(QueuedResult(
                        agent_id=item["agent_id"],
                        result_type=item["result_type"],
                        summary=item["summary"],
                        full_result=item["full_result"],
                        timestamp=datetime.fromisoformat(item["timestamp"]),
                        priority=item["priority"],
                        presented=item.get("presented", False)
                    ))

                self.flow_protection_active = data.get("flow_protection_active", False)
                logger.info(f"Loaded {len(self.result_queue)} queued results from disk")

            except Exception as e:
                logger.warning(f"Failed to load queue from disk: {e}")
                self.result_queue = []

    def _save_queue(self):
        """Persist queue to disk with secure atomic write [He2025]."""
        from .file_ops import atomic_write_json

        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)

            data = {
                "results": [
                    {
                        "agent_id": r.agent_id,
                        "result_type": r.result_type,
                        "summary": r.summary,
                        "full_result": r.full_result,
                        "timestamp": r.timestamp.isoformat(),
                        "priority": r.priority,
                        "presented": r.presented
                    }
                    for r in self.result_queue
                ],
                "flow_protection_active": self.flow_protection_active,
                "saved_at": datetime.now().isoformat()
            }

            atomic_write_json(self.queue_file, data)
            logger.debug(f"Saved {len(self.result_queue)} results to queue file")

        except Exception as e:
            logger.error(f"Failed to save queue to disk: {e}")

    def queue_result(self, result: QueuedResult):
        """Add result to queue and persist."""
        self.result_queue.append(result)
        self._save_queue()

    def get_pending_results_for_delivery(self) -> List[QueuedResult]:
        """
        Get results that are ready for delivery.

        Called at natural break points to deliver queued results.
        Only returns results when flow protection is not active.

        Returns:
            List of QueuedResult that can be presented to user
        """
        context = self.get_cognitive_context()

        # Don't deliver during peak flow
        if self.flow_protection_active and context.momentum_phase == "peak":
            return []

        # Release flow protection if no longer in peak
        if self.flow_protection_active and context.momentum_phase != "peak":
            self.flow_protection_active = False
            self._save_queue()
            logger.info("Flow protection released - delivering queued results")

        # Get unpresented results
        pending = [r for r in self.result_queue if not r.presented]
        if not pending:
            return []

        # Sort by priority (1=high) then timestamp, then agent_id for determinism [He2025]
        pending.sort(key=lambda r: (r.priority, r.timestamp, r.agent_id))

        # Respect working memory limit
        context = self.get_cognitive_context()
        max_results = context.working_memory_limit

        to_deliver = pending[:max_results]

        # Mark as presented and save
        for result in to_deliver:
            result.presented = True
        self._save_queue()

        return to_deliver

    def clear_delivered_results(self):
        """Remove results that have been presented."""
        self.result_queue = deque(
            (r for r in self.result_queue if not r.presented),
            maxlen=self.MAX_RESULT_QUEUE
        )
        self._save_queue()

    def cleanup_expired_results(self):
        """
        Remove results older than TTL [He2025 production safety].
        Called periodically to prevent stale result accumulation.
        """
        current_time = time.time()
        self.result_queue = deque(
            (r for r in self.result_queue
             if (current_time - r.timestamp.timestamp()) < self.RESULT_TTL_SECONDS),
            maxlen=self.MAX_RESULT_QUEUE
        )
        self._save_queue()
        logger.debug(f"Cleaned up expired results, {len(self.result_queue)} remaining")


class FlowProtector:
    """
    Protects user flow state by managing interruptions.

    When user is in peak flow:
    - Queues non-urgent results
    - Batches notifications
    - Defers context switches
    """

    def __init__(self, coordinator: AgentCoordinator):
        self.coordinator = coordinator
        self.interrupt_queue: List[Dict[str, Any]] = []
        self.last_check: Optional[datetime] = None

    def should_interrupt(self, urgency: str = "normal") -> bool:
        """
        Decide if we should interrupt user.

        Urgency levels:
        - critical: Always interrupt (errors, safety)
        - high: Interrupt unless peak flow
        - normal: Queue if in flow
        - low: Always queue
        """
        if urgency == "critical":
            return True

        context = self.coordinator.get_cognitive_context()

        if context.in_flow_state:
            if urgency == "high":
                # High urgency can interrupt building/rolling, not peak
                return context.momentum_phase != "peak"
            return False  # Queue everything else

        if urgency == "low":
            # Low urgency waits for natural breaks
            return context.momentum_phase in ("cold_start", "crashed")

        return True  # Normal urgency, not in flow

    def queue_interrupt(self, interrupt_type: str, content: Any, urgency: str = "normal"):
        """Queue an interrupt for later delivery."""
        self.interrupt_queue.append({
            "type": interrupt_type,
            "content": content,
            "urgency": urgency,
            "timestamp": datetime.now()
        })

    def get_pending_interrupts(self) -> List[Dict[str, Any]]:
        """Get interrupts that are now safe to deliver."""
        context = self.coordinator.get_cognitive_context()

        # If still in peak flow, only return critical
        if context.in_flow_state and context.momentum_phase == "peak":
            critical = [i for i in self.interrupt_queue if i["urgency"] == "critical"]
            return critical

        # Otherwise return all pending
        all_pending = self.interrupt_queue.copy()
        self.interrupt_queue.clear()
        return all_pending

    def natural_break_point(self) -> bool:
        """Check if this is a natural break point to deliver queued items."""
        context = self.coordinator.get_cognitive_context()

        # Natural breaks:
        # - Task just completed
        # - Momentum transitioning down
        # - User explicitly paused
        return context.momentum_phase in ("cold_start", "building", "crashed")


# Convenience function for quick decisions
def should_delegate(task_description: str, file_count: int = 1,
                    parallelizable: bool = False) -> Decision:
    """
    Quick decision helper for common cases.

    Usage:
        decision = should_delegate("Search for auth patterns", file_count=20, parallelizable=True)
        if decision.mode == DecisionMode.DELEGATE:
            # Spawn agent
    """
    coordinator = AgentCoordinator()
    task = TaskProfile(
        description=task_description,
        estimated_complexity="moderate" if file_count > 3 else "simple",
        parallelizable=parallelizable,
        requires_focus=False,
        file_count=file_count,
        domain="general"
    )
    return coordinator.decide(task)
