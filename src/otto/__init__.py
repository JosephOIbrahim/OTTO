"""
Orchestra - Cognitive Orchestration System (v5.0)

A production-hardened async orchestration system with cognitive state management
and ThinkingMachines [He2025] compliant deterministic execution.

v5.0 Cognitive Engine:
- 5-Phase NEXUS Pipeline (DETECT → CASCADE → LOCK → EXECUTE → UPDATE)
- Cognitive Safety MoE expert routing (7 experts, fixed priority, first-match-wins)
- MAX3 bounded reflection with cognitive safety gating
- RC^+xi convergence tracking with attractor basins
- Deterministic checksums for reproducible behavior
- Claude Code hook integration (python -m orchestra.hooks)
- Session staleness detection with 2-hour auto-reset
- Unified state path (~/.orchestra/state/)

v4.0 Hybrid Orchestra (Cognitive Layer):
- CognitiveState tracking (burnout, momentum, energy, mode)
- PRISM signal detection with FIXED evaluation order
- Cognitive support (always active, no toggle)
- Research and synthesis worker agents
- ThinkingMachines [He2025] batch-invariance compliance

v3.0 Production Excellence:
- Prometheus-compatible metrics for observability
- Distributed tracing (Jaeger/Zipkin compatible)
- Bulkhead pattern for agent isolation
- Crash recovery checkpointing
- Graceful degradation with fallbacks

v2.0 Production Hardening:
- Circuit breaker for cascading failure prevention
- Configurable timeouts and retries
- Atomic file writes for state integrity

Usage:
    from otto import create_orchestrator

    orchestrator = create_orchestrator()
    result = orchestrator.process_message("Your task here")
    print(result.to_anchor())  # [EXEC:a3f2b8|direct|Cortex|30000ft|standard]

CLI Usage:
    orchestra                    # Launch TUI dashboard
    orchestra status             # Show cognitive status
    orchestra install-hook       # Install Claude Code hook
    orchestra uninstall-hook     # Remove Claude Code hook
    python -m orchestra.hooks    # Hook entry point (for hooks.json)

Environment Variables:
    FO_WORKSPACE - Workspace directory
    FO_AGENT_TIMEOUT - Per-agent timeout (seconds)
    FO_LOG_FORMAT - 'text' or 'json'
    FO_LOG_LEVEL - DEBUG, INFO, WARNING, ERROR
"""

__version__ = "5.0.1"
__author__ = "Framework Ecosystem Integration"

# Core orchestrator
from .framework_orchestrator import (
    FrameworkOrchestrator,
    AgentResult,
    AgentStatus,
    OrchestratorState,
    BaseAgent,
    # Agent implementations (for testing)
    ECHOCuratorAgent,
    DomainIntelligenceAgent,
    MoERouterAgent,
    WorldModelerAgent,
    CodeGeneratorAgent,
    DeterminismGuardAgent,
    SelfReflectorAgent,
    Mycelium,
)

# Configuration
from .config import (
    OrchestratorConfig,
    get_config,
    set_config,
)

# Resilience patterns
from .resilience import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    ResilientExecutor,
    TimeoutError,
    with_timeout,
    with_retry,
    RetryConfig,
)

# File operations
from .file_ops import (
    atomic_write_json,
    atomic_write_text,
    safe_read_json,
    AtomicWriteError,
)

# Validation
from .validation import (
    validate_task,
    validate_context,
    validate_agent_name,
    validate_domain_config,
    sanitize_path_for_logging,
    sanitize_error_message,
    truncate_for_logging,
    ValidationResult,
    ValidationError,
)

# Logging
from .logging_setup import (
    setup_logging,
    get_logger,
    JSONFormatter,
    TextFormatter,
    log_execution,
    log_orchestration_start,
    log_orchestration_complete,
)

# Health checks
from .health import (
    HealthChecker,
    HealthStatus,
    HealthReport,
    ComponentHealth,
    format_health_report,
)

# Lifecycle management
from .lifecycle import (
    LifecycleManager,
    LifecycleState,
    ShutdownContext,
    run_with_lifecycle,
)

# Schema validation
from .schemas import (
    validate_json_schema,
    validate_domain_config as validate_domain_schema,
    validate_principles,
    validate_state_file,
    validate_agent_result,
    DOMAIN_CONFIG_SCHEMA,
    PRINCIPLES_SCHEMA,
    STATE_FILE_SCHEMA,
    AGENT_RESULT_SCHEMA,
)

# ============================================================================
# v3.0 Production Excellence Modules
# ============================================================================

# Metrics (Prometheus-compatible)
from .metrics import (
    OrchestratorMetrics,
    get_metrics,
    reset_metrics,
    Counter,
    Histogram,
    Gauge,
)

# Distributed Tracing
from .tracing import (
    DistributedTracer,
    get_tracer,
    configure_tracer,
    trace,
    TraceContext,
    Span,
    SpanStatus,
)

# Bulkhead (Agent Isolation)
from .bulkhead import (
    BulkheadExecutor,
    AdaptiveBulkhead,
    BulkheadRejected,
    BulkheadTimeout,
)

# Checkpointing (Crash Recovery)
from .checkpoint import (
    OrchestrationCheckpoint,
    CheckpointData,
    CheckpointStatus,
    recover_from_crash,
)

# Fallback (Graceful Degradation)
from .fallback import (
    FallbackRegistry,
    FallbackResult,
    GracefulDegradation,
    CachedResult,
)

# Rate Limiting
from .rate_limit import (
    RateLimiter,
    SlidingWindowLimiter,
    CompositeRateLimiter,
    RateLimitExceeded,
)

# Idempotency
from .idempotency import (
    IdempotencyManager,
    ExecutionStatus,
    ExecutionRecord,
    IdempotencyConflict,
    generate_idempotency_key,
)

# ============================================================================
# v4.0 Hybrid Orchestra (Cognitive Layer)
# ============================================================================

# Cognitive State Management
from .cognitive_state import (
    CognitiveState,
    CognitiveStateManager,
    BurnoutLevel,
    MomentumPhase,
    EnergyLevel,
    CognitiveMode,
    Altitude,
    ATTRACTOR_BASINS,
)

# PRISM Signal Detection
from .prism_detector import (
    PRISMDetector,
    SignalVector,
    SignalCategory,
    SIGNAL_PATTERNS,
    PRISM_PERSPECTIVES,
    create_detector,
)

# Cognitive Support (replaces ADHD Support - no toggle, always active)
from .cognitive_support import (
    CognitiveSupportManager,
    CognitiveConstraints,
    CognitiveCheckResult,
    WorkingMemoryTracker,
    RecoveryOption,
    RECOVERY_OPTIONS,
    create_cognitive_manager,
    # Backward compatibility aliases
    ADHDSupportManager,
    ADHDConstraints,
    ADHDCheckResult,
    create_adhd_manager,
)

# Worker Agents
from .research_agent import (
    ResearchAgent,
    ResearchResult,
    ResearchFinding,
    ResearchType,
)

from .synthesis_agent import (
    SynthesisAgent,
    CognitiveAwareSynthesis,
    SynthesisResult,
    SynthesisMode,
    AGENT_PRIORITY,
)

# Dashboard
from .dashboard import (
    Dashboard,
)

# ============================================================================
# v5.0 USD-Native Cognitive Architecture
# ============================================================================

# USD-Native Cognitive Stage
from .cognitive_stage import (
    CognitiveStage,
    CognitiveLayer,
    LayerPriority,
    AttributeOpinion,
    CONSTITUTIONAL_VALUES,
    PXR_AVAILABLE,
    create_cognitive_stage,
)

# Tension Surfacing
from .tension_surfacer import (
    TensionType,
    TensionSeverity,
    Tension,
    TensionReport,
    TensionSurfacer,
    create_tension_surfacer,
)

# Agent Coordination (work/delegate/protect)
from .agent_coordinator import (
    AgentCoordinator,
    FlowProtector,
    Decision,
    DecisionMode,
    TaskProfile,
    AgentType,
    CognitiveContext,
    AgentContext,
    QueuedResult,
    should_delegate,
)

# Decision Engine
from .decision_engine import (
    DecisionEngine,
    TaskRequest,
    TaskCategory,
    ExecutionPlan,
    process_quick,
)

# ============================================================================
# v6.0 ThinkingMachines [He2025] Compliant Execution
# ============================================================================

# Expert Router (Cognitive Safety MoE)
from .expert_router import (
    Expert,
    RoutingResult,
    ExpertRouter,
    EXPERT_TRIGGERS,
    EXPERT_PRIORITY,
    create_router,
)

# Parameter Locker (MAX3 + Safety Gating)
from .parameter_locker import (
    ThinkDepth,
    Paradigm,
    LockStatus,
    LockedParams,
    LockResult,
    ParameterLocker,
    DEPTH_BUDGETS,
    create_locker,
)

# Convergence Tracker (RC^+xi)
from .convergence_tracker import (
    AttractorBasin,
    ConvergenceResult,
    StateVector,
    ConvergenceTracker,
    ATTRACTOR_DEFINITIONS,
    get_tension_color,
    create_tracker,
)

# Cognitive Orchestrator (5-Phase NEXUS Pipeline)
from .cognitive_orchestrator import (
    NexusResult,
    CognitiveOrchestrator,
    create_orchestrator,
)

# Dashboard Bridge
from .dashboard_bridge import (
    DashboardBridge,
    map_nexus_to_dashboard,
    create_bridge,
)

# ============================================================================
# v7.0 USD Cognitive Substrate Runtime
# ============================================================================

# Substrate Runtime (extracted from cognitive-orchestrator)
from .substrate import (
    # Knowledge - O(1) factual retrieval
    KnowledgePrim,
    KnowledgeRetriever,
    RetrievalResult,
    get_retriever,
    retrieve,
    search,
    # EWM - External Working Memory
    EWMManager,
    EWMState,
    Project,
    ProjectFriction,
    SessionAnchor,
    TimeBeacon,
    get_ewm_manager,
    # Hardening - Graceful degradation, backup, recovery
    HandoffDocument,
    HandoffManager,
    StateManager,
    StateResult,
    get_handoff_manager,
    get_state_manager,
)

__all__ = [
    # Version
    "__version__",

    # Core
    "FrameworkOrchestrator",
    "AgentResult",
    "AgentStatus",
    "OrchestratorState",
    "BaseAgent",
    # Agent implementations
    "ECHOCuratorAgent",
    "DomainIntelligenceAgent",
    "MoERouterAgent",
    "WorldModelerAgent",
    "CodeGeneratorAgent",
    "DeterminismGuardAgent",
    "SelfReflectorAgent",
    "Mycelium",

    # Configuration
    "OrchestratorConfig",
    "get_config",
    "set_config",

    # Resilience
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
    "ResilientExecutor",
    "TimeoutError",
    "with_timeout",
    "with_retry",
    "RetryConfig",

    # File operations
    "atomic_write_json",
    "atomic_write_text",
    "safe_read_json",
    "AtomicWriteError",

    # Validation
    "validate_task",
    "validate_context",
    "validate_agent_name",
    "validate_domain_config",
    "sanitize_path_for_logging",
    "sanitize_error_message",
    "truncate_for_logging",
    "ValidationResult",
    "ValidationError",

    # Logging
    "setup_logging",
    "get_logger",
    "JSONFormatter",
    "TextFormatter",

    # Health
    "HealthChecker",
    "HealthStatus",
    "HealthReport",
    "ComponentHealth",
    "format_health_report",

    # Lifecycle
    "LifecycleManager",
    "LifecycleState",
    "ShutdownContext",
    "run_with_lifecycle",

    # Schemas
    "validate_json_schema",
    "validate_domain_schema",
    "validate_principles",
    "validate_state_file",
    "validate_agent_result",

    # ========================================
    # v3.0 Production Excellence
    # ========================================

    # Metrics
    "OrchestratorMetrics",
    "get_metrics",
    "reset_metrics",
    "Counter",
    "Histogram",
    "Gauge",

    # Tracing
    "DistributedTracer",
    "get_tracer",
    "configure_tracer",
    "trace",
    "TraceContext",
    "Span",
    "SpanStatus",

    # Bulkhead
    "BulkheadExecutor",
    "AdaptiveBulkhead",
    "BulkheadRejected",
    "BulkheadTimeout",

    # Checkpoint
    "OrchestrationCheckpoint",
    "CheckpointData",
    "CheckpointStatus",
    "recover_from_crash",

    # Fallback
    "FallbackRegistry",
    "FallbackResult",
    "GracefulDegradation",
    "CachedResult",

    # Rate Limiting
    "RateLimiter",
    "SlidingWindowLimiter",
    "CompositeRateLimiter",
    "RateLimitExceeded",

    # Idempotency
    "IdempotencyManager",
    "ExecutionStatus",
    "ExecutionRecord",
    "IdempotencyConflict",
    "generate_idempotency_key",

    # ========================================
    # v4.0 Hybrid Orchestra (Cognitive Layer)
    # ========================================

    # Cognitive State
    "CognitiveState",
    "CognitiveStateManager",
    "BurnoutLevel",
    "MomentumPhase",
    "EnergyLevel",
    "CognitiveMode",
    "Altitude",
    "ATTRACTOR_BASINS",

    # PRISM Detector
    "PRISMDetector",
    "SignalVector",
    "SignalCategory",
    "SIGNAL_PATTERNS",
    "PRISM_PERSPECTIVES",
    "create_detector",

    # Cognitive Support (always active)
    "CognitiveSupportManager",
    "CognitiveConstraints",
    "CognitiveCheckResult",
    "create_cognitive_manager",
    # Backward compatibility
    "ADHDSupportManager",
    "ADHDConstraints",
    "ADHDCheckResult",
    "create_adhd_manager",
    # Shared
    "WorkingMemoryTracker",
    "RecoveryOption",
    "RECOVERY_OPTIONS",

    # Worker Agents
    "ResearchAgent",
    "ResearchResult",
    "ResearchFinding",
    "ResearchType",
    "SynthesisAgent",
    "CognitiveAwareSynthesis",
    "SynthesisResult",
    "SynthesisMode",
    "AGENT_PRIORITY",

    # Dashboard
    "Dashboard",

    # ========================================
    # v5.0 USD-Native Cognitive Architecture
    # ========================================

    # USD-Native Cognitive Stage
    "CognitiveStage",
    "CognitiveLayer",
    "LayerPriority",
    "AttributeOpinion",
    "CONSTITUTIONAL_VALUES",
    "PXR_AVAILABLE",
    "create_cognitive_stage",

    # Tension Surfacing
    "TensionType",
    "TensionSeverity",
    "Tension",
    "TensionReport",
    "TensionSurfacer",
    "create_tension_surfacer",

    # Agent Coordination (work/delegate/protect)
    "AgentCoordinator",
    "FlowProtector",
    "Decision",
    "DecisionMode",
    "TaskProfile",
    "AgentType",
    "CognitiveContext",
    "AgentContext",
    "QueuedResult",
    "should_delegate",

    # Decision Engine
    "DecisionEngine",
    "TaskRequest",
    "TaskCategory",
    "ExecutionPlan",
    "process_quick",

    # ========================================
    # v6.0 ThinkingMachines [He2025] Compliant Execution
    # ========================================

    # Expert Router (Cognitive Safety MoE)
    "Expert",
    "RoutingResult",
    "ExpertRouter",
    "EXPERT_TRIGGERS",
    "EXPERT_PRIORITY",
    "create_router",

    # Parameter Locker (MAX3 + Safety Gating)
    "ThinkDepth",
    "Paradigm",
    "LockStatus",
    "LockedParams",
    "LockResult",
    "ParameterLocker",
    "DEPTH_BUDGETS",
    "create_locker",

    # Convergence Tracker (RC^+xi)
    "AttractorBasin",
    "ConvergenceResult",
    "StateVector",
    "ConvergenceTracker",
    "ATTRACTOR_DEFINITIONS",
    "get_tension_color",
    "create_tracker",

    # Cognitive Orchestrator (5-Phase NEXUS Pipeline)
    "NexusResult",
    "CognitiveOrchestrator",
    "create_orchestrator",

    # Dashboard Bridge
    "DashboardBridge",
    "map_nexus_to_dashboard",
    "create_bridge",

    # ========================================
    # v7.0 USD Cognitive Substrate Runtime
    # ========================================

    # Knowledge - O(1) factual retrieval
    "KnowledgePrim",
    "KnowledgeRetriever",
    "RetrievalResult",
    "get_retriever",
    "retrieve",
    "search",

    # EWM - External Working Memory
    "EWMManager",
    "EWMState",
    "Project",
    "ProjectFriction",
    "SessionAnchor",
    "TimeBeacon",
    "get_ewm_manager",

    # Hardening - Graceful degradation, backup, recovery
    "HandoffDocument",
    "HandoffManager",
    "StateManager",
    "StateResult",
    "get_handoff_manager",
    "get_state_manager",
]
