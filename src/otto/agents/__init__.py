"""
OTTO OS Agent Module
====================

Intelligent agents for task execution with cognitive state awareness.

Philosophy:
    Agents are specialized workers that understand context. They respect
    burnout levels, adapt to energy states, and report progress clearly.

Agent Types:
- Planner: Task decomposition and execution planning
- Researcher: Deep research with knowledge integration
- Memory: Profile storage and recall (USD-backed)
- Reflection: Self-assessment and cognitive integration
- Explorer: Codebase exploration (existing)
- Implementer: Code generation (existing)
- Reviewer: Code review (existing)

ThinkingMachines [He2025] Compliance:
- Fixed agent types with deterministic behavior
- State propagation from parent to child
- Progress visibility at all times
"""

from .base import (
    Agent,
    AgentConfig,
    AgentResult,
    AgentProgress,
    AgentState,
    AgentError,
    RetryableError,
    NonRetryableError,
)

from .planner import PlannerAgent
from .researcher import ResearcherAgent
from .memory import MemoryAgent
from .reflection import ReflectionAgent
from .progress import ProgressTracker, ProgressEvent, ProgressLevel
from .context_aware_coordinator import (
    ContextAwareCoordinator,
    EnhancedCognitiveContext,
    create_context_aware_coordinator,
)

__all__ = [
    # Base classes
    "Agent",
    "AgentConfig",
    "AgentResult",
    "AgentProgress",
    "AgentState",
    "AgentError",
    "RetryableError",
    "NonRetryableError",
    # Agent types
    "PlannerAgent",
    "ResearcherAgent",
    "MemoryAgent",
    "ReflectionAgent",
    # Progress
    "ProgressTracker",
    "ProgressEvent",
    "ProgressLevel",
    # Context-Aware Coordination
    "ContextAwareCoordinator",
    "EnhancedCognitiveContext",
    "create_context_aware_coordinator",
]
