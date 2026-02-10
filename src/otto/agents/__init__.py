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
- Validation: Determinism checking
- Context: Import analysis and dependency mapping
- Explorer: Codebase exploration (existing)
- Implementer: Code generation (existing)
- Reviewer: Code review (existing)

Determinism:
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
from .validation_agent import (
    ValidationAgent,
    ValidationResult,
    ValidationFinding,
    ValidationSeverity,
    validate_file,
    validate_directory,
)
from .context_agent import (
    ContextAgent,
    FileContext,
    ImportInfo,
    DependencyGraph,
    analyze_file as analyze_file_context,
    analyze_directory as analyze_directory_context,
    build_dependency_graph,
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
    # Validation Agent
    "ValidationAgent",
    "ValidationResult",
    "ValidationFinding",
    "ValidationSeverity",
    "validate_file",
    "validate_directory",
    # Context Agent
    "ContextAgent",
    "FileContext",
    "ImportInfo",
    "DependencyGraph",
    "analyze_file_context",
    "analyze_directory_context",
    "build_dependency_graph",
]
