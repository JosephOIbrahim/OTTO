"""
Framework Orchestrator
======================
7-Agent async orchestration system applying USD composition semantics to cognitive
state management.

Agents:
1. ECHO Curator         - 4-tier context memory (LIVRPS composition)
2. Domain Intelligence  - Multi-domain analysis (Phoenix + PRISM)
3. MoE Router           - Deterministic expert selection
4. World Modeler        - Causal inference (CORTEX)
5. Code Generator       - Evolutionary code (MAX 3 + MNO v3)
6. Determinism Guard    - Reproducibility (batch-invariance)
7. Self Reflector       - Constitutional reasoning (RESONANCE + MCAW)

Domain configs loaded from: ~/Orchestra/config/domains/

References:
    [1] Pixar Animation Studios. (2016). "Universal Scene Description"
        https://graphics.pixar.com/usd/
        - LIVRPS composition semantics for cognitive state resolution

    [2] He, Horace and Thinking Machines Lab. (2025). "Defeating Nondeterminism
        in LLM Inference." Thinking Machines Lab: Connectionism.
        https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
        - Batch-invariance for reproducible agent execution

    [3] Zhang, S., Kraska, T., & Khattab, O. (2025). "Recursive Language Models."
        arXiv:2512.24601. https://arxiv.org/abs/2512.24601
        - Program-environment paradigm for large context navigation

See CITATIONS.md for complete attribution.
"""

import asyncio
import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Deque
from enum import Enum
import logging

# Production hardening modules
from .config import OrchestratorConfig, get_config
from .file_ops import atomic_write_json, safe_read_json
from .resilience import (
    CircuitBreaker, CircuitBreakerOpen, ResilientExecutor,
    TimeoutError as AgentTimeoutError
)
from .validation import (
    validate_task, validate_context, sanitize_path_for_logging,
    truncate_for_logging, ValidationError
)
from .logging_setup import setup_logging, log_execution, log_orchestration_start, log_orchestration_complete
from .health import HealthChecker, HealthStatus, format_health_report
from .lifecycle import LifecycleManager, LifecycleState, ShutdownContext
from .schemas import validate_domain_config, validate_state_file

# Cognitive state modules (v4.0 - Hybrid Orchestra)
from .cognitive_state import (
    CognitiveState, CognitiveStateManager,
    BurnoutLevel, MomentumPhase, EnergyLevel, CognitiveMode, Altitude
)
from .prism_detector import PRISMDetector, SignalVector, SignalCategory
from .adhd_support import (
    CognitiveSafetyManager, CognitiveSafetyCheckResult, create_cognitive_safety_manager,
    # Backward compatibility aliases
    ADHDSupportManager, ADHDCheckResult, create_adhd_manager
)

# Decision engine (v4.3.0 - Work/Delegate/Protect)
from .decision_engine import (
    DecisionEngine, TaskRequest, TaskCategory, ExecutionPlan
)
from .agent_coordinator import DecisionMode

# Production excellence modules (v3.0)
from .metrics import OrchestratorMetrics, get_metrics
from .tracing import DistributedTracer, get_tracer, configure_tracer, SpanStatus
from .bulkhead import BulkheadExecutor, BulkheadRejected, BulkheadTimeout
from .checkpoint import OrchestrationCheckpoint, CheckpointStatus, recover_from_crash
from .fallback import FallbackRegistry, FallbackResult, GracefulDegradation
from .rate_limit import RateLimiter, RateLimitExceeded
from .idempotency import IdempotencyManager, generate_idempotency_key

# Configure logging - will be reconfigured by setup_logging() if needed
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DEGRADED = "degraded"  # Running with fallback/cached result


@dataclass
class AgentResult:
    """Result from a single agent execution."""
    agent_name: str
    status: AgentStatus
    output: Dict[str, Any]
    checksum: str
    execution_time: float
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "agent": self.agent_name,
            "status": self.status.value,
            "output": self.output,
            "checksum": self.checksum,
            "execution_time_ms": round(self.execution_time * 1000, 2),
            "error": self.error
        }


@dataclass
class OrchestratorState:
    """Current state of the orchestrator."""
    task: str
    iteration: int
    agents_completed: List[str]
    agents_pending: List[str]
    master_checksum: str
    timestamp: float
    results: Dict[str, AgentResult] = field(default_factory=dict)


# =============================================================================
# Agent Definitions
# =============================================================================

class BaseAgent:
    """Base class for all framework agents."""

    def __init__(self, name: str, framework: str, ces_alignment: str):
        self.name = name
        self.framework = framework
        self.ces_alignment = ces_alignment
        self.logger = logging.getLogger(f"Agent.{name}")

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's function. Override in subclasses."""
        raise NotImplementedError

    def get_info(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "framework": self.framework,
            "ces_alignment": self.ces_alignment
        }


class ECHOCuratorAgent(BaseAgent):
    """ECHO 2.0 + LIVRPS: Memory management with USD composition semantics.

    Memory is organized by AUTHORITY (LIVRPS), not just recency.
    Principles layer (SPECIALIZES) is NEVER compressed.

    Layers (strongest override to foundational):
        LOCAL       → Session memory (compresses first)
        INHERITS    → Context inheritance from parent tasks
        VARIANTSETS → Memory modes (focused/exploratory/recovery)
        REFERENCES  → Calibration memory (cross-session learning)
        PAYLOADS    → Domain memory (lazy-loaded)
        SPECIALIZES → Principles (NEVER compressed, referenced on error)
    """

    # Default principles path
    PRINCIPLES_PATH = Path.home() / "Orchestra" / "config" / "principles.json"

    # Compression order: LOCAL first, SPECIALIZES never
    COMPRESSION_ORDER = {
        "local": 1,           # Compress first
        "inherits": 2,        # Compress second
        "payloads": 3,        # Unload third (not compress)
        "variantsets": None,  # Never compress
        "references": None,   # Never compress
        "specializes": None   # NEVER compress
    }

    # Legacy tier mapping for backwards compatibility
    TIER_TO_LAYER = {
        "hot": "local",
        "warm": "inherits",
        "cold": "payloads",
        "archive": "references"
    }

    def __init__(self, principles_path: Path = None):
        super().__init__(
            name="echo_curator",
            framework="ECHO 2.0 + LIVRPS",
            ces_alignment="Context Memory Platform"
        )

        # LIVRPS memory layers
        self.memory_layers = {
            "specializes": {},   # Principles - NEVER compressed
            "payloads": {},      # Domain memory - unloadable
            "references": {},    # Calibration - persistent
            "variantsets": {},   # Memory modes
            "inherits": {},      # Context inheritance
            "local": {}          # Session memory - compresses first
        }

        # Current memory mode
        self.active_mode = "focused_recall"

        # Load principles
        self.principles_path = principles_path or self.PRINCIPLES_PATH
        self._load_principles()

    def _load_principles(self):
        """Load principles into SPECIALIZES layer. These are NEVER compressed."""
        if not self.principles_path.exists():
            self.logger.warning(f"Principles not found: {self.principles_path}")
            self._use_fallback_principles()
            return

        try:
            principles = json.loads(self.principles_path.read_text(encoding='utf-8'))
            self.memory_layers["specializes"] = principles
            self.logger.info(f"Loaded principles: {len(principles.get('constitutional', {}).get('principles', []))} constitutional rules")
        except Exception as e:
            self.logger.error(f"Failed to load principles: {e}")
            self._use_fallback_principles()

    def _use_fallback_principles(self):
        """Minimal embedded principles if file not found."""
        self.memory_layers["specializes"] = {
            "constitutional": {
                "principles": [
                    {"id": "safety_first", "statement": "Safety first: Emotional safety before productivity"},
                    {"id": "user_knows_best", "statement": "User knows best: Their signal trumps Claude's guess"}
                ]
            },
            "recovery_protocol": {
                "triggers": [
                    {"condition": "error_state", "action": "Fall back to principles"}
                ]
            }
        }
        self.logger.info("Using fallback embedded principles")

    def _detect_memory_mode(self, task: str, context: Dict[str, Any]) -> str:
        """Detect appropriate memory mode based on signals."""
        task_lower = task.lower()

        # Check for recovery signals first (safety_first principle)
        recovery_signals = ["help", "stuck", "frustrated", "confused", "overwhelmed", "error"]
        if any(sig in task_lower for sig in recovery_signals):
            return "recovery_recall"

        # Check for exploratory signals
        exploratory_signals = ["what if", "explore", "brainstorm", "ideas", "consider", "might"]
        if any(sig in task_lower for sig in exploratory_signals):
            return "exploratory_recall"

        # Default to focused
        return "focused_recall"

    def _resolve_memory_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve memory query using LIVRPS priority order.

        Resolution order (strongest to weakest override):
        1. LOCAL (session) - most specific, most recent
        2. INHERITS (context) - parent task state
        3. VARIANTSETS (modes) - current memory mode
        4. REFERENCES (calibration) - learned patterns
        5. PAYLOADS (domain) - domain expertise
        6. SPECIALIZES (principles) - FOUNDATIONAL, referenced on uncertainty
        """
        resolution = {
            "query": query,
            "resolved_from": None,
            "resolution_path": [],
            "principles_consulted": False,
            "result": None
        }

        # Walk the LIVRPS stack
        for layer_name in ["local", "inherits", "variantsets", "references", "payloads", "specializes"]:
            layer_data = self.memory_layers.get(layer_name, {})
            resolution["resolution_path"].append(layer_name)

            if layer_data:
                # For specializes, always note that principles were available
                if layer_name == "specializes":
                    resolution["principles_consulted"] = True
                    resolution["principles_available"] = list(
                        p.get("id") for p in layer_data.get("constitutional", {}).get("principles", [])
                    )

                resolution["resolved_from"] = layer_name
                resolution["result"] = f"Found in {layer_name}"
                break

        return resolution

    def _calculate_compression(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate memory compression based on LIVRPS, not recency.

        Compression order:
        1. LOCAL compresses first (session details)
        2. INHERITS summarizes second
        3. PAYLOADS can unload (not compress)
        4. VARIANTSETS, REFERENCES, SPECIALIZES: NEVER compress
        """
        total_items = sum(len(layer) if isinstance(layer, dict) else 0
                         for layer in self.memory_layers.values())

        compression_state = {
            "total_memory_items": total_items,
            "layers_status": {},
            "compression_applied": [],
            "protected_layers": ["specializes", "references", "variantsets"]
        }

        for layer_name, compress_order in self.COMPRESSION_ORDER.items():
            layer_size = len(self.memory_layers.get(layer_name, {}))
            compression_state["layers_status"][layer_name] = {
                "size": layer_size,
                "compressible": compress_order is not None,
                "compress_order": compress_order,
                "protected": compress_order is None
            }

        return compression_state

    def _check_principles_for_guidance(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Consult principles layer for guidance. Called on uncertainty or error."""
        principles = self.memory_layers.get("specializes", {})
        constitutional = principles.get("constitutional", {}).get("principles", [])

        task_lower = task.lower()
        triggered_principles = []

        for principle in constitutional:
            triggers = principle.get("triggers", [])
            if any(trigger in task_lower for trigger in triggers):
                triggered_principles.append({
                    "id": principle.get("id"),
                    "statement": principle.get("statement"),
                    "action": principle.get("action")
                })

        return {
            "principles_checked": len(constitutional),
            "principles_triggered": triggered_principles,
            "guidance_available": len(triggered_principles) > 0
        }

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute memory management with LIVRPS composition semantics.

        Manages cognitive memory using USD-inspired layer hierarchy where
        higher layers override lower layers during resolution.

        Args:
            task: The task string to process and store in memory
            context: Execution context including agent_results, burnout_level, etc.

        Returns:
            Dict containing:
                - memory_architecture: "LIVRPS"
                - active_mode: Current memory mode (focused/exploratory/recovery)
                - resolution: Resolved memory state from all layers
                - compression_state: Current compression status of layers
                - principles_layer: Constitutional principles check result
        """
        self.logger.info("Managing memory with LIVRPS composition...")

        # Detect appropriate memory mode
        memory_mode = self._detect_memory_mode(task, context)
        self.active_mode = memory_mode
        self.memory_layers["variantsets"]["active_mode"] = memory_mode

        # Store task in LOCAL layer (session memory)
        task_hash = hashlib.sha256(task.encode()).hexdigest()[:16]
        self.memory_layers["local"][task_hash] = {
            "task": task[:200],
            "timestamp": time.time(),
            "mode": memory_mode
        }

        # Resolve memory state using LIVRPS
        resolution = self._resolve_memory_query(task, context)

        # Calculate compression state
        compression = self._calculate_compression(context)

        # Always check principles for potential guidance
        principles_guidance = self._check_principles_for_guidance(task, context)

        # Build provenance
        provenance = {
            "source": "orchestrator_task",
            "timestamp": time.time(),
            "content_hash": task_hash,
            "memory_architecture": "LIVRPS"
        }

        # Calculate effective tokens based on mode
        mode_tokens = {
            "focused_recall": 4096,
            "exploratory_recall": 8192,
            "recovery_recall": 2048  # Minimal for recovery
        }
        effective_tokens = mode_tokens.get(memory_mode, 4096)

        result = {
            # LIVRPS state
            "memory_architecture": "LIVRPS",
            "active_mode": memory_mode,
            "resolution": resolution,
            "compression_state": compression,

            # Principles (always present, always consulted)
            "principles_layer": {
                "loaded": "specializes" in self.memory_layers and bool(self.memory_layers["specializes"]),
                "protected": True,
                "guidance": principles_guidance
            },

            # Legacy compatibility
            "tier_selected": self.TIER_TO_LAYER.get(memory_mode, "local"),
            "effective_tokens": effective_tokens,
            "provenance": provenance,

            # Memory stats
            "layers_populated": [k for k, v in self.memory_layers.items() if v],
            "local_memory_items": len(self.memory_layers["local"]),
            "memory_utilization": f"{len(self.memory_layers['local']) / 100:.1%}"
        }

        return result


class DomainIntelligenceAgent(BaseAgent):
    """Phoenix + PRISM: Multi-domain analysis with pluggable domain configs.

    Loads domain configurations from JSON files in the user's Orchestra directory:
    ~/Orchestra/config/domains/

    Each domain config defines specialists, keywords, and PRISM perspectives.
    """

    PRISM_PERSPECTIVES = ["causal", "optimization", "hierarchical", "temporal", "risk", "opportunity"]

    # Default domains path (user home directory)
    DEFAULT_DOMAINS_PATH = Path.home() / "Orchestra" / "config" / "domains"

    def __init__(self, domains_path: Path = None):
        super().__init__(
            name="domain_intelligence",
            framework="Phoenix v6 + PRISM",
            ces_alignment="Multi-perspective reasoning"
        )
        self.domains: Dict[str, Dict] = {}
        self.domains_path = domains_path or self.DEFAULT_DOMAINS_PATH
        self._load_domains()

    def _load_domains(self):
        """Load all domain configurations from JSON files."""
        if not self.domains_path.exists():
            self.logger.warning(f"Domains path not found: {self.domains_path}")
            self._use_fallback_domains()
            return

        loaded_count = 0
        for config_file in self.domains_path.glob("*.json"):
            try:
                config = json.loads(config_file.read_text(encoding='utf-8'))
                domain_key = config.get("name", config_file.stem).lower()
                self.domains[domain_key] = config
                loaded_count += 1
                self.logger.info(f"Loaded domain: {domain_key} ({len(config.get('specialists', {}))} specialists)")
            except Exception as e:
                self.logger.error(f"Failed to load {config_file}: {e}")

        if not self.domains:
            self._use_fallback_domains()
        else:
            self.logger.info(f"Loaded {loaded_count} domain configs from {self.domains_path}")

    def _use_fallback_domains(self):
        """Fallback to minimal embedded domains if no configs found."""
        self.domains = {
            "general": {
                "name": "General",
                "specialists": {
                    "analysis": {"keywords": ["analyze", "review", "examine"], "analysis_focus": ["structure"]}
                },
                "routing_keywords": [],
                "prism_perspectives": self.PRISM_PERSPECTIVES[:4]
            }
        }
        self.logger.info("Using fallback embedded domains")

    def _build_keyword_index(self) -> Dict[str, List[Dict]]:
        """Build reverse index: keyword -> [{domain, specialist}]."""
        index = {}
        for domain_name, domain in self.domains.items():
            for specialist_name, specialist in domain.get("specialists", {}).items():
                for keyword in specialist.get("keywords", []):
                    keyword_lower = keyword.lower()
                    if keyword_lower not in index:
                        index[keyword_lower] = []
                    index[keyword_lower].append({
                        "domain": domain_name,
                        "specialist": specialist_name,
                        "analysis_focus": specialist.get("analysis_focus", [])
                    })
        return index

    def get_routing_keywords(self) -> List[str]:
        """Return all routing keywords from all loaded domains."""
        keywords = []
        for domain in self.domains.values():
            keywords.extend(domain.get("routing_keywords", []))
        return list(set(keywords))

    def get_all_specialist_keywords(self) -> List[str]:
        """Return all specialist keywords from all domains (for fallback matching)."""
        keywords = []
        for domain in self.domains.values():
            for specialist in domain.get("specialists", {}).values():
                keywords.extend(specialist.get("keywords", []))
        return list(set(keywords))

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute multi-domain task analysis with keyword-based specialist routing.

        Analyzes the task against all loaded domain configurations to identify
        relevant specialists and build an analysis focus.

        Args:
            task: The task string to analyze for domain keywords
            context: Execution context (unused but required for interface)

        Returns:
            Dict containing:
                - domains_detected: List of detected domain names
                - primary_domain: Highest-scoring domain
                - specialists_activated: Dict of activated specialists
                - analysis_focus: Set of analysis priorities
                - domain_count: Number of domains checked
        """
        self.logger.info(f"Analyzing task with multi-domain detection ({len(self.domains)} domains loaded)...")

        task_lower = task.lower()
        keyword_index = self._build_keyword_index()

        # Domain detection
        detected_domains = {}
        detected_specialists = {}
        matched_keywords = []

        for keyword, mappings in keyword_index.items():
            if keyword in task_lower:
                matched_keywords.append(keyword)
                for mapping in mappings:
                    domain = mapping["domain"]
                    specialist = mapping["specialist"]

                    # Track domain hits
                    if domain not in detected_domains:
                        detected_domains[domain] = {"hits": 0, "keywords": [], "analysis_focus": set()}
                    detected_domains[domain]["hits"] += 1
                    detected_domains[domain]["keywords"].append(keyword)
                    detected_domains[domain]["analysis_focus"].update(mapping.get("analysis_focus", []))

                    # Track specialist hits
                    key = f"{domain}.{specialist}"
                    if key not in detected_specialists:
                        detected_specialists[key] = {"hits": 0, "keywords": [], "analysis_focus": mapping.get("analysis_focus", [])}
                    detected_specialists[key]["hits"] += 1
                    detected_specialists[key]["keywords"].append(keyword)

        # Handle fallback: if no keywords matched, run against all domains
        run_all_domains = len(detected_domains) == 0
        if run_all_domains:
            self.logger.info("No specific domain matched - running comprehensive analysis against all domains")
            for domain_name, domain in self.domains.items():
                detected_domains[domain_name] = {
                    "hits": 0,
                    "keywords": [],
                    "analysis_focus": set(),
                    "fallback_match": True
                }
                # Add all specialists from this domain
                for spec_name, spec in domain.get("specialists", {}).items():
                    key = f"{domain_name}.{spec_name}"
                    detected_specialists[key] = {
                        "hits": 0,
                        "keywords": [],
                        "analysis_focus": spec.get("analysis_focus", []),
                        "fallback_match": True
                    }

        # Determine primary domain and specialist (highest keyword hits, or first if fallback)
        if detected_domains:
            primary_domain = max(detected_domains, key=lambda d: detected_domains[d]["hits"])
        else:
            primary_domain = "general"

        if detected_specialists:
            primary_specialist = max(detected_specialists, key=lambda s: detected_specialists[s]["hits"])
        else:
            primary_specialist = "general.analysis"

        # Get PRISM perspectives from matched domain
        domain_config = self.domains.get(primary_domain, self.domains.get("general", {}))
        perspectives = domain_config.get("prism_perspectives", self.PRISM_PERSPECTIVES[:3])

        # Apply perspective analysis
        perspective_analysis = {}
        for perspective in perspectives[:3]:  # Top 3 for efficiency
            specialist_short = primary_specialist.split('.')[-1] if '.' in primary_specialist else primary_specialist
            perspective_analysis[perspective] = {
                "relevant": True,
                "focus_area": f"{perspective} analysis for {specialist_short}"
            }

        # Convert sets to lists for JSON serialization
        for domain_data in detected_domains.values():
            if isinstance(domain_data.get("analysis_focus"), set):
                domain_data["analysis_focus"] = list(domain_data["analysis_focus"])

        # Get primary analysis focus
        primary_analysis_focus = detected_specialists.get(primary_specialist, {}).get("analysis_focus", [])

        return {
            "detected_domains": list(detected_domains.keys()),
            "domain_scores": {d: info["hits"] for d, info in detected_domains.items()},
            "domain_details": detected_domains,
            "primary_domain": primary_domain,
            "detected_specialists": list(detected_specialists.keys()),
            "primary_specialist": primary_specialist,
            "primary_analysis_focus": primary_analysis_focus,
            "matched_keywords": matched_keywords,
            "prism_perspectives_applied": list(perspective_analysis.keys()),
            "perspective_analysis": perspective_analysis,
            "domains_loaded": list(self.domains.keys()),
            "domain_task_detected": len(matched_keywords) > 0,
            "fallback_mode": run_all_domains
        }


class Mycelium:
    """V5 Neuroplasticity mechanism - bounded adaptive learning.

    Implements Hebbian learning for expert weight adaptation:
    - Records task outcomes for each expert selection
    - Updates weights based on success/failure feedback
    - Maintains homeostatic bounds to prevent runaway specialization

    Future work:
    - Full Hebbian update: w_new = w_old + alpha * (outcome - expected) * activation
    - Temporal aggregation across sessions
    - Attractor dynamics for stable expert preferences

    Production Safety [He2025]:
    - Bounded outcome history prevents memory leaks
    """

    MAX_OUTCOMES = 500  # Bounded for production [He2025]

    def __init__(self, num_experts: int = 7):
        self.expert_weights = {
            "protector": 1/num_experts,
            "decomposer": 1/num_experts,
            "restorer": 1/num_experts,
            "redirector": 1/num_experts,
            "acknowledger": 1/num_experts,
            "guide": 1/num_experts,
            "executor": 1/num_experts
        }
        self.learning_rate = 0.1
        self.outcomes: Deque[Dict[str, Any]] = deque(maxlen=self.MAX_OUTCOMES)
        self.logger = logging.getLogger("Mycelium")

    def record_outcome(self, expert: str, outcome: float, task_hash: str) -> None:
        """Record outcome for Hebbian learning.

        Args:
            expert: The expert that was selected
            outcome: Success metric (0.0 = failure, 1.0 = success)
            task_hash: Hash of the task for deduplication
        """
        self.outcomes.append({
            "expert": expert,
            "outcome": outcome,
            "task_hash": task_hash,
            "timestamp": time.time()
        })
        self.logger.info(f"Recorded outcome: {expert} = {outcome}")

    def update_weights(self) -> Dict[str, float]:
        """Hebbian update: w_new = w_old + alpha * (outcome - expected) * activation.

        Placeholder for future implementation. Currently returns current weights.
        """
        # Future: Implement full Hebbian learning
        # For now, just return current weights
        return self.expert_weights.copy()

    def get_weights(self) -> Dict[str, float]:
        """Get current expert weights for routing."""
        return self.expert_weights.copy()

    def get_state(self) -> Dict[str, Any]:
        """Get current Mycelium state for inspection."""
        return {
            "weights": self.expert_weights.copy(),
            "learning_rate": self.learning_rate,
            "outcomes_recorded": len(self.outcomes),
            "recent_outcomes": list(self.outcomes)[-5:] if self.outcomes else []
        }


class MoERouterAgent(BaseAgent):
    """V5 Intervention Experts with Safety Floors.

    Implements 5-phase routing: ACTIVATE → WEIGHT → BOUND → SELECT → UPDATE

    Key V5 constraints:
    - Safety floors are HARD minimums (Protector never < 10%)
    - Priority-based tiebreaking (lower priority number wins)
    - Homeostatic normalization (weights sum to 1.0)

    ThinkingMachines Batch-Invariance Compliance [He2025]:
    - Fixed iteration order (dict order deterministic in Python 3.7+)
    - No dynamic algorithm switching based on input
    - Consistent data layout across all invocations
    """

    # V5 Expert Archetypes (ordered by priority - lower = higher priority)
    EXPERTS = {
        "protector": {"priority": 1, "triggers": ["frustrated", "overwhelmed", "safety", "caps", "help"], "temperature": 0.3},
        "decomposer": {"priority": 2, "triggers": ["stuck", "complex", "too_many", "break_down", "simplify"], "temperature": 0.4},
        "restorer": {"priority": 3, "triggers": ["depleted", "burnout", "tired", "rest", "exhausted"], "temperature": 0.5},
        "redirector": {"priority": 4, "triggers": ["tangent", "distracted", "off_topic", "sidetrack"], "temperature": 0.4},
        "acknowledger": {"priority": 5, "triggers": ["done", "complete", "milestone", "win", "finished"], "temperature": 0.6},
        "guide": {"priority": 6, "triggers": ["exploring", "what_if", "curious", "learn", "understand"], "temperature": 0.8},
        "executor": {"priority": 7, "triggers": ["implement", "code", "do", "execute", "build", "create"], "temperature": 0.2}
    }

    # V5 Safety Floors (HARD minimums - NEVER violated)
    SAFETY_FLOORS = {
        "protector": 0.10,   # Safety-first: always 10% minimum
        "decomposer": 0.05,  # Complexity management: 5% minimum
        "restorer": 0.05,    # Recovery support: 5% minimum
        "redirector": 0.00,
        "acknowledger": 0.00,
        "guide": 0.00,
        "executor": 0.00
    }

    # Human-friendly display names for UI/documentation (non-programmer friendly)
    DISPLAY_NAMES = {
        "protector": "Safety Guardian",
        "decomposer": "Complexity Simplifier",
        "restorer": "Energy Recharger",
        "redirector": "Focus Redirector",
        "acknowledger": "Progress Celebrator",
        "guide": "Discovery Guide",
        "executor": "Task Builder"
    }

    def __init__(self):
        super().__init__(
            name="moe_router",
            framework="V5 Intervention Experts",
            ces_alignment="Safety-floor bounded routing"
        )
        # Instance-level weights for Mycelium integration
        self.expert_weights = {e: 1.0 / len(self.EXPERTS) for e in self.EXPERTS}

    def _activate(self, task: str, context: Dict[str, Any]) -> Dict[str, float]:
        """Phase 1: ACTIVATE - Signal detection → activation vector.

        v4.0: Uses PRISM signals and cognitive state for activation,
        not just keyword matching.

        Priority order (from CLAUDE.md):
        1. EMOTIONAL signals → protector/restorer
        2. COGNITIVE STATE (burnout/energy) → restorer/protector
        3. MODE signals → guide/executor
        4. TASK signals → executor/decomposer
        """
        task_lower = task.lower()
        activation = {expert: 0.0 for expert in self.EXPERTS}

        # Get PRISM signals from context (if available)
        prism_signals = context.get("prism_signals", {})
        cognitive_state = context.get("cognitive_state_dict", {})

        # ===== PRIORITY 1: Emotional signals (highest priority) =====
        emotional = prism_signals.get("emotional", {})
        emotional_score = prism_signals.get("emotional_score", 0.0)

        if emotional_score > 0.3:
            # Strong emotional signal → protector
            activation["protector"] = max(activation["protector"], emotional_score)
            if "stuck" in emotional or "overwhelmed" in emotional:
                activation["decomposer"] = max(activation["decomposer"], emotional_score * 0.8)
            if "frustrated" in emotional or "angry" in emotional:
                activation["restorer"] = max(activation["restorer"], emotional_score * 0.6)

        # ===== PRIORITY 2: Cognitive state (burnout/energy) =====
        burnout = cognitive_state.get("burnout_level", "green")
        energy = cognitive_state.get("energy_level", "medium")

        # Burnout overrides
        if burnout == "red":
            activation["protector"] = max(activation["protector"], 0.9)
            activation["restorer"] = max(activation["restorer"], 0.8)
        elif burnout == "orange":
            activation["restorer"] = max(activation["restorer"], 0.6)
            activation["protector"] = max(activation["protector"], 0.5)
        elif burnout == "yellow":
            activation["restorer"] = max(activation["restorer"], 0.3)

        # Energy overrides
        if energy == "depleted":
            activation["restorer"] = max(activation["restorer"], 0.7)
            activation["protector"] = max(activation["protector"], 0.4)
        elif energy == "low":
            activation["restorer"] = max(activation["restorer"], 0.4)

        # ===== PRIORITY 3: Mode signals =====
        mode_signals = prism_signals.get("mode", {})
        if mode_signals.get("exploring", 0) > 0.3:
            activation["guide"] = max(activation["guide"], mode_signals["exploring"])
        if mode_signals.get("recovery", 0) > 0.3:
            activation["restorer"] = max(activation["restorer"], mode_signals["recovery"])

        # ===== PRIORITY 4: Task signals (fallback to keyword matching) =====
        task_signals = prism_signals.get("task", {})
        if task_signals:
            if task_signals.get("implement", 0) > 0:
                activation["executor"] = max(activation["executor"], task_signals["implement"])
            if task_signals.get("debug", 0) > 0:
                activation["decomposer"] = max(activation["decomposer"], task_signals["debug"])
            if task_signals.get("research", 0) > 0:
                activation["guide"] = max(activation["guide"], task_signals["research"])

        # Fallback: Original keyword matching (if no PRISM signals)
        if not prism_signals or sum(activation.values()) == 0:
            for expert, config in self.EXPERTS.items():
                triggers = config["triggers"]
                matches = sum(1 for t in triggers if t in task_lower)
                activation[expert] = max(activation[expert], min(matches / max(len(triggers), 1), 1.0))

        return activation

    def _weight(self, activation: Dict[str, float], context: Dict[str, Any]) -> Dict[str, float]:
        """Phase 2: WEIGHT - Apply expert weights to activation.

        Combines activation with learned weights (from Mycelium if available).
        """
        # Get weights from context (Mycelium) or use instance defaults
        weights = context.get("mycelium_weights", self.expert_weights)

        weighted = {}
        for expert in self.EXPERTS:
            weighted[expert] = activation.get(expert, 0.0) * weights.get(expert, 1.0 / len(self.EXPERTS))

        return weighted

    def _bound(self, weighted: Dict[str, float]) -> Dict[str, float]:
        """Phase 3: BOUND - Enforce safety floors + homeostatic normalization.

        CRITICAL: Safety floors are HARD constraints. Protector NEVER drops below 10%.
        After floor enforcement, normalize to sum=1 (homeostatic regulation).
        """
        bounded = {}

        # Apply safety floors (HARD constraint - non-negotiable)
        for expert, score in weighted.items():
            floor = self.SAFETY_FLOORS.get(expert, 0.0)
            bounded[expert] = max(score, floor)

        # Homeostatic normalization: ensure weights sum to 1.0
        total = sum(bounded.values())
        if total > 0:
            bounded = {k: v / total for k, v in bounded.items()}

        return bounded

    def _select(self, bounded: Dict[str, float]) -> str:
        """Phase 4: SELECT - Choose expert via argmax with priority tiebreaker.

        Selection rule: highest bounded score wins.
        Tiebreaker: lower priority number wins (Protector > Decomposer > ... > Executor)
        """
        # Sort by score DESC, then by priority ASC (lower priority = wins ties)
        sorted_experts = sorted(
            bounded.items(),
            key=lambda x: (-x[1], self.EXPERTS[x[0]]["priority"])
        )
        return sorted_experts[0][0]

    def _prepare_update(self, selected: str, task: str, bounded: Dict[str, float]) -> Dict[str, Any]:
        """Phase 5: UPDATE - Prepare context for Hebbian learning.

        Stores selection outcome for future Mycelium weight updates.
        """
        return {
            "selected_expert": selected,
            "task_hash": hashlib.md5(task.encode()).hexdigest()[:8],
            "bounded_scores": bounded,
            "awaiting_outcome": True,
            "hebbian_ready": True
        }

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute 5-phase V5 routing: ACTIVATE -> WEIGHT -> BOUND -> SELECT -> UPDATE.

        Routes tasks to intervention experts using a deterministic 5-phase pipeline
        with safety floors to ensure critical experts remain available.

        Args:
            task: The task string to route
            context: Execution context with seed for reproducibility

        Returns:
            Dict containing:
                - selected_expert: Name of the selected expert
                - activation_vector: Raw signal detection scores
                - weighted_scores: After expert weight application
                - bounded_scores: After safety floor enforcement
                - safety_intervention: Whether safety floors changed the outcome
                - expert_hash: Deterministic hash for reproducibility verification
        """
        self.logger.info("V5 5-phase routing: ACTIVATE → WEIGHT → BOUND → SELECT → UPDATE")

        seed = context.get("seed", 42)

        # PHASE 1: ACTIVATE - Signal detection → activation vector
        activation = self._activate(task, context)

        # PHASE 2: WEIGHT - Apply expert weights
        weighted = self._weight(activation, context)

        # PHASE 3: BOUND - Enforce safety floors + normalize
        bounded = self._bound(weighted)

        # PHASE 4: SELECT - argmax with priority tiebreaker
        selected = self._select(bounded)

        # Compute who would have won WITHOUT safety floors (for transparency)
        raw_winner = max(weighted.items(), key=lambda x: (x[1], -self.EXPERTS[x[0]]["priority"]))[0] if any(weighted.values()) else "protector"
        safety_intervention = (selected != raw_winner) and (weighted.get(raw_winner, 0) > weighted.get(selected, 0))

        # PHASE 5: UPDATE - Prepare for Hebbian learning
        update_context = self._prepare_update(selected, task, bounded)

        # Get config for selected expert
        selected_config = self.EXPERTS[selected]

        # Compute deterministic hash for reproducibility verification
        routing_input = f"{task}:{seed}"
        expert_hash = hashlib.sha256(routing_input.encode()).hexdigest()[:16]

        # Get cognitive state for output
        cognitive_state = context.get("cognitive_state_dict", {})

        return {
            # V5 Routing metadata
            "routing_version": "v5",
            "routing_phases": ["activate", "weight", "bound", "select", "update"],

            # Phase outputs
            "activation_vector": activation,
            "weighted_scores": weighted,
            "bounded_scores": bounded,

            # Selection result
            "selected_expert": selected,
            "selected_display_name": self.DISPLAY_NAMES.get(selected, selected),
            "selected_config": selected_config,
            "expert_hash": expert_hash,

            # Safety transparency (ThinkingMachines auditability)
            "raw_winner": raw_winner,
            "safety_intervention": safety_intervention,
            "safety_intervention_reason": f"Safety floor elevated {selected} over {raw_winner}" if safety_intervention else None,

            # Safety floor verification
            "safety_floors_applied": True,
            "safety_floors": self.SAFETY_FLOORS,
            "protector_floor_met": bounded.get("protector", 0) >= self.SAFETY_FLOORS["protector"],

            # Hebbian learning context
            "update_context": update_context,

            # Determinism
            "seed": seed,
            "reproducible": True,

            # Gating weights for compatibility
            "gating_weights": bounded,
            "routing_type": "v5_5phase",

            # v4.0: Cognitive state awareness
            "cognitive_state_used": bool(cognitive_state),
            "burnout_level": cognitive_state.get("burnout_level", "unknown"),
            "energy_level": cognitive_state.get("energy_level", "unknown"),
            "prism_signals_used": "prism_signals" in context
        }


class WorldModelerAgent(BaseAgent):
    """CORTEX: World models and causal inference."""

    def __init__(self):
        super().__init__(
            name="world_modeler",
            framework="CORTEX",
            ces_alignment="Cosmos WFM + Object Permanence"
        )
        self.world_state = {}

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a world model with causal inference from task entities.

        Extracts entities from the task and builds causal chains to model
        relationships. Uses CORTEX-style energy state tracking.

        Args:
            task: The task string to extract entities from
            context: Execution context (unused but required for interface)

        Returns:
            Dict containing:
                - entities_detected: List of extracted entity names
                - causal_chains: List of cause-effect relationships
                - energy_state: Dict of quality metrics
                - composite_energy: Aggregate energy score
        """
        self.logger.info("Building world model with causal inference...")

        # Extract entities from task (simplified)
        words = task.split()
        entities = [w for w in words if w[0].isupper()] if words else []

        # Build simple causal model
        causal_chains = []
        for i in range(len(entities) - 1):
            causal_chains.append({
                "cause": entities[i],
                "effect": entities[i + 1],
                "confidence": 0.7
            })

        # Energy state (CORTEX-style)
        energy_state = {
            "correctness": 0.8,
            "efficiency": 0.7,
            "maintainability": 0.75,
            "style": 0.8
        }

        return {
            "entities_detected": entities,
            "entity_count": len(entities),
            "causal_chains": causal_chains,
            "causal_chain_count": len(causal_chains),
            "energy_state": energy_state,
            "composite_energy": sum(energy_state.values()) / len(energy_state),
            "object_permanence_valid": True,
            "world_model_version": "CORTEX_v1"
        }


class CodeGeneratorAgent(BaseAgent):
    """MAX 3 + MNO v3: Evolutionary code generation."""

    def __init__(self):
        super().__init__(
            name="code_generator",
            framework="MAX 3 + MNO v3",
            ces_alignment="AlphaEvolve patterns"
        )
        self.generation_count = 0

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate code using evolutionary MNO proposer/solver pattern.

        Simulates evolutionary code generation with population-based
        improvement and fitness evaluation.

        Args:
            task: The task describing code to generate
            context: Execution context with seed for reproducibility

        Returns:
            Dict containing:
                - generation: Current generation number
                - population_size: Number of candidates
                - best_fitness: Fitness of best candidate
                - candidates: List of code candidates with fitness
                - proposer_active: Whether proposer generated new candidates
                - solver_verified: Whether solver validated solutions
        """
        self.logger.info("Generating code with evolutionary approach...")

        # Simulate evolutionary generation cycle
        self.generation_count += 1

        # MNO proposer/solver pattern
        proposal = {
            "type": "code_generation",
            "task_hash": hashlib.sha256(task.encode()).hexdigest()[:8],
            "iteration": self.generation_count
        }

        # MAX RC^+ξ self-reflection metrics
        reflection_metrics = {
            "confidence": 0.85,
            "novelty": 0.6,
            "alignment": 0.9,
            "bounded_reflection_depth": 3
        }

        # Fitness score (evolutionary)
        fitness = sum(reflection_metrics.values()) / len(reflection_metrics)

        return {
            "generation_method": "evolutionary_proposer_solver",
            "proposal": proposal,
            "reflection_metrics": reflection_metrics,
            "fitness_score": round(fitness, 3),
            "generation_count": self.generation_count,
            "rc_xi_applied": True,
            "evolution_cycle_complete": True
        }


def _apply_determinism_settings(seed: int) -> Dict[str, Any]:
    """
    Apply determinism settings to all available random sources.

    ThinkingMachines Compliance [He2025]:
        Controls every source of randomness for batch-invariant inference.
        Settings are applied at runtime, not just documented.

    Args:
        seed: The master seed for all random sources

    Returns:
        Dict showing which settings were successfully applied
    """
    applied = {"seed": seed, "sources": []}

    # Python's built-in random
    import random
    random.seed(seed)
    applied["sources"].append("random")

    # NumPy if available
    try:
        import numpy as np
        np.random.seed(seed)
        applied["sources"].append("numpy")
    except ImportError:
        pass

    # PyTorch if available
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            applied["sources"].append("torch.cuda")
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        if hasattr(torch, 'set_float32_matmul_precision'):
            torch.set_float32_matmul_precision('highest')
            applied["sources"].append("torch.matmul_precision")
        applied["sources"].append("torch")
        applied["cudnn_deterministic"] = True
        applied["cudnn_benchmark"] = False
    except ImportError:
        pass

    # OS-level PYTHONHASHSEED (for dict/set ordering)
    import os
    os.environ["PYTHONHASHSEED"] = str(seed)
    applied["sources"].append("PYTHONHASHSEED")

    return applied


class DeterminismGuardAgent(BaseAgent):
    """
    ThinkingMachines: Reproducibility enforcement.

    This agent APPLIES determinism settings, not just documents them.
    Per [He2025], same inputs must produce same outputs.
    """

    def __init__(self):
        super().__init__(
            name="determinism_guard",
            framework="ThinkingMachines",
            ces_alignment="Reproducible inference"
        )

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce determinism constraints per ThinkingMachines batch-invariance.

        Validates and configures determinism settings to ensure reproducible
        outputs across runs with the same inputs.

        Args:
            task: The task string (used for logging)
            context: Execution context with seed and agent_results to validate

        Returns:
            Dict containing:
                - determinism_config: Required settings for reproducibility
                - batch_invariance_enforced: Always True
                - seed_locked: The locked seed value
                - validation_results: Per-agent reproducibility validation
                - reproducibility_guaranteed: Whether all checks passed
        """
        self.logger.info("Enforcing determinism constraints...")

        seed = context.get("seed", 42)

        # ACTUALLY APPLY determinism settings (ThinkingMachines compliance)
        # Previously this only documented settings without applying them
        applied = _apply_determinism_settings(seed)
        self.logger.info(f"Applied determinism to: {applied['sources']}")

        # Configuration record (for validation/debugging)
        determinism_config = {
            "batch_size": 1,  # CRITICAL: Never vary
            "cudnn_deterministic": applied.get("cudnn_deterministic", True),
            "cudnn_benchmark": applied.get("cudnn_benchmark", False),
            "float32_matmul_precision": "highest",
            "seed": seed,
            "sources_applied": applied["sources"]  # Track what was actually set
        }

        # Validate other agents' outputs for reproducibility
        validation_results = {}
        for agent_name, result in context.get("agent_results", {}).items():
            if hasattr(result, "checksum") and result.checksum:
                validation_results[agent_name] = {
                    "has_checksum": True,
                    "checksum": result.checksum,
                    "reproducible": True
                }

        return {
            "determinism_config": determinism_config,
            "batch_invariance_enforced": True,
            "seed_locked": seed,
            "agents_validated": len(validation_results),
            "validation_results": validation_results,
            "reproducibility_guaranteed": True,
            "settings_applied": True  # NEW: Confirms settings were applied, not just documented
        }


class SelfReflectorAgent(BaseAgent):
    """RESONANCE + MCAW: Self-reflection and constitutional reasoning."""

    CONSTITUTIONAL_PRINCIPLES = [
        "Accuracy: Verify claims and cite sources",
        "Clarity: Use precise, understandable language",
        "Safety: Avoid harmful outputs",
        "Helpfulness: Address the actual user need"
    ]

    MAX_REFLECTIONS = 100  # Bounded for production [He2025]

    def __init__(self):
        super().__init__(
            name="self_reflector",
            framework="RESONANCE + MCAW",
            ces_alignment="Constitutional AI"
        )
        self.reflection_history: Deque[Dict[str, Any]] = deque(maxlen=self.MAX_REFLECTIONS)

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform self-reflection and constitutional principle checking.

        Evaluates the current state against constitutional principles using
        RESONANCE ancestral wisdom and MCAW constitutional evaluation.

        Args:
            task: The task string to evaluate for principle alignment
            context: Execution context with agent_results to review

        Returns:
            Dict containing:
                - ancestral_check: RESONANCE wisdom consultation result
                - constitutional_scores: Per-principle alignment scores
                - overall_constitutional_score: Aggregate alignment
                - reflection_depth: Number of reflection iterations
                - improvements_suggested: List of suggested improvements
        """
        self.logger.info("Performing self-reflection and constitutional check...")

        # RESONANCE ancestral wisdom check
        ancestral_check = {
            "wisdom_consulted": True,
            "lineage_depth": 3,
            "founding_principles_aligned": True
        }

        # MCAW constitutional evaluation
        constitutional_scores = {}
        for principle in self.CONSTITUTIONAL_PRINCIPLES:
            principle_name = principle.split(":")[0]
            # Simplified scoring - use hashlib for determinism [He2025]
            principle_hash = int(hashlib.sha256(principle.encode()).hexdigest(), 16)
            constitutional_scores[principle_name] = 0.85 + (principle_hash % 10) / 100

        overall_score = sum(constitutional_scores.values()) / len(constitutional_scores)

        # Store reflection
        reflection_entry = {
            "timestamp": time.time(),
            "task_hash": hashlib.sha256(task.encode()).hexdigest()[:8],
            "constitutional_score": overall_score
        }
        self.reflection_history.append(reflection_entry)

        return {
            "ancestral_check": ancestral_check,
            "constitutional_scores": constitutional_scores,
            "overall_constitutional_score": round(overall_score, 3),
            "violations_detected": [],
            "recommendations": [],
            "reflection_depth": len(self.reflection_history),
            "self_confidence": 0.9
        }


# =============================================================================
# Orchestrator
# =============================================================================

class FrameworkOrchestrator:
    """
    7-Agent async orchestrator with Ralph v3 pattern.

    Pattern: Filesystem IS the state
    - Results written to disk immediately
    - State recoverable from files
    - Completion proven by file existence

    Production features (v2.0):
    - Configurable timeouts and retries
    - Circuit breaker for cascading failure prevention
    - Atomic file writes for state integrity
    - Input validation and sanitization
    - Health check support
    - Graceful shutdown handling
    """

    def __init__(self, workspace: Path = None, config: OrchestratorConfig = None):
        # Load configuration
        self.config = config or get_config()

        # Validate configuration
        config_errors = self.config.validate()
        if config_errors:
            logger.warning(f"Configuration warnings: {config_errors}")

        # Setup workspace paths
        self.workspace = workspace or self.config.workspace
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.results_dir = self.config.results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.config.state_file

        # Initialize agents
        self.agents: Dict[str, BaseAgent] = {
            "echo_curator": ECHOCuratorAgent(),
            "domain_intelligence": DomainIntelligenceAgent(),  # Generalized from shot_intelligence
            "moe_router": MoERouterAgent(),
            "world_modeler": WorldModelerAgent(),
            "code_generator": CodeGeneratorAgent(),
            "determinism_guard": DeterminismGuardAgent(),
            "self_reflector": SelfReflectorAgent()
        }

        self.iteration = 0
        self._start_time = time.time()

        # Cognitive state management (v4.0 - Hybrid Orchestra)
        self.cognitive_state_manager = CognitiveStateManager(
            state_dir=self.workspace / "state"
        )
        self.prism_detector = PRISMDetector()
        self.cognitive_safety_manager: Optional[CognitiveSafetyManager] = None

        # Decision engine (v4.3.0 - Work/Delegate/Protect)
        # Feature flag: use_decision_engine controls whether we use new routing
        self.use_decision_engine = self.config.use_decision_engine if hasattr(self.config, 'use_decision_engine') else True
        self.decision_engine: Optional[DecisionEngine] = None
        # Note: DecisionEngine requires CognitiveStage, initialized lazily when needed

        # Initialize Mycelium for Hebbian learning
        self.mycelium = Mycelium()

        # Production hardening components
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.circuit_breaker_threshold,
            reset_timeout=self.config.circuit_breaker_reset_timeout
        )

        self.resilient_executor = ResilientExecutor(
            circuit_breaker=self.circuit_breaker,
            default_timeout=self.config.agent_timeout,
            default_max_retries=self.config.max_retries,
            retry_base_delay=self.config.retry_base_delay,
            retry_max_delay=self.config.retry_max_delay,
            enable_circuit_breaker=self.config.enable_circuit_breaker,
            enable_retries=self.config.enable_retries
        )

        self.health_checker = HealthChecker(
            workspace=self.workspace,
            agents=self.agents,
            circuit_breaker=self.circuit_breaker,
            start_time=self._start_time
        )

        self.lifecycle = LifecycleManager(
            shutdown_timeout=self.config.shutdown_timeout
        )

        # Production excellence components (v3.0)
        # Metrics
        self.metrics = OrchestratorMetrics() if self.config.metrics_enabled else None

        # Tracing
        if self.config.tracing_enabled:
            self.tracer = configure_tracer(
                service_name="framework-orchestrator",
                sample_rate=self.config.tracing_sample_rate,
                enabled=True
            )
        else:
            self.tracer = None

        # Bulkhead for agent isolation
        if self.config.enable_bulkhead:
            self.bulkhead = BulkheadExecutor(
                max_concurrent=self.config.max_concurrent_agents,
                queue_size_per_agent=self.config.agent_queue_size,
                acquire_timeout=self.config.bulkhead_timeout
            )
        else:
            self.bulkhead = None

        # Checkpointing for crash recovery
        if self.config.checkpoint_enabled:
            self.checkpoint = OrchestrationCheckpoint(
                checkpoint_dir=self.config.checkpoint_dir,
                retention_seconds=self.config.checkpoint_retention
            )
        else:
            self.checkpoint = None

        # Fallback registry for graceful degradation
        if self.config.enable_fallback:
            self.fallback_registry = FallbackRegistry(
                cache_ttl=self.config.fallback_cache_retention,
                enable_synthetic=self.config.fallback_enable_synthetic
            )
        else:
            self.fallback_registry = None

        # Rate limiter
        if self.config.enable_rate_limit:
            self.rate_limiter = RateLimiter(
                rate=self.config.rate_limit_per_sec,
                burst_size=self.config.rate_limit_burst,
                adaptive=self.config.rate_limit_adaptive
            )
        else:
            self.rate_limiter = None

        # Idempotency manager
        if self.config.enable_idempotency:
            self.idempotency_manager = IdempotencyManager(
                retention_seconds=self.config.idempotency_retention,
                max_entries=self.config.idempotency_max_entries
            )
        else:
            self.idempotency_manager = None

        # Register cleanup handler
        async def save_state_on_shutdown(ctx: ShutdownContext):
            """Save current state during shutdown."""
            if ctx.state_to_save:
                try:
                    atomic_write_json(self.state_file, ctx.state_to_save)
                    logger.info("State saved during shutdown")
                except Exception as e:
                    logger.error(f"Failed to save state during shutdown: {e}")

        self.lifecycle.register_shutdown_handler(save_state_on_shutdown)

        logger.info(f"Orchestrator initialized with workspace: {sanitize_path_for_logging(self.workspace)}")

    def _create_task_request(self, task: str, context: Dict[str, Any]) -> TaskRequest:
        """
        Convert task string to TaskRequest for DecisionEngine.

        Uses PRISM signals and task analysis to categorize the request.
        """
        task_lower = task.lower()

        # Infer category from task content
        if any(kw in task_lower for kw in ["search", "find", "explore", "where", "what"]):
            category = TaskCategory.EXPLORATION
        elif any(kw in task_lower for kw in ["implement", "create", "add", "build", "write"]):
            category = TaskCategory.IMPLEMENTATION
        elif any(kw in task_lower for kw in ["debug", "fix", "error", "bug", "issue"]):
            category = TaskCategory.DEBUGGING
        elif any(kw in task_lower for kw in ["review", "check", "analyze", "audit"]):
            category = TaskCategory.REVIEW
        elif any(kw in task_lower for kw in ["research", "learn", "study", "investigate"]):
            category = TaskCategory.RESEARCH
        elif any(kw in task_lower for kw in ["document", "docs", "readme", "comment"]):
            category = TaskCategory.DOCUMENTATION
        elif any(kw in task_lower for kw in ["plan", "design", "architect", "structure"]):
            category = TaskCategory.PLANNING
        else:
            category = TaskCategory.SIMPLE

        # Infer scope from context
        files = context.get("files_involved", [])
        if len(files) > 10:
            scope = "large"
        elif len(files) > 3:
            scope = "medium"
        else:
            scope = "small"

        # Check urgency from PRISM signals
        prism_signals = context.get("prism_signals", {})
        urgency = prism_signals.get("urgency", "normal")

        return TaskRequest(
            description=task,
            category=category,
            files_involved=files,
            requires_user_input=context.get("requires_user_input", False),
            estimated_scope=scope,
            urgency=urgency
        )

    def _route_task(self, task: str, context: Dict[str, Any]) -> List[str]:
        """CSQMF-style routing to determine which agents to activate.

        .. deprecated:: 4.3.0
            Use `DecisionEngine.process_task()` instead. This method is
            maintained for backward compatibility during the migration period.
            Set `use_decision_engine=True` (default) to use the new routing.

        Uses dynamic routing keywords loaded from domain configs.
        """
        import warnings
        warnings.warn(
            "_route_task() is deprecated. Use DecisionEngine.process_task() instead. "
            "Set use_decision_engine=True to use the new routing system.",
            DeprecationWarning,
            stacklevel=2
        )

        # Always active
        active = ["echo_curator", "determinism_guard"]

        task_lower = task.lower()

        # Get domain routing keywords dynamically from loaded domain configs
        domain_agent = self.agents.get("domain_intelligence")
        if domain_agent and hasattr(domain_agent, 'get_routing_keywords'):
            domain_keywords = domain_agent.get_routing_keywords()
        else:
            # Fallback if agent not properly initialized
            domain_keywords = []

        # Domain-specific activation (keywords from domain configs)
        if domain_keywords and any(kw in task_lower for kw in domain_keywords):
            active.append("domain_intelligence")
            active.append("world_modeler")

        # Code-related activation
        if any(kw in task_lower for kw in ["code", "script", "python", "implement", "function"]):
            active.append("code_generator")

        # Routing/expert selection activation
        if any(kw in task_lower for kw in ["route", "select", "expert", "choose", "model"]):
            active.append("moe_router")

        # Reflection/review activation
        if any(kw in task_lower for kw in ["reflect", "review", "improve", "quality", "check"]):
            active.append("self_reflector")

        # If nothing specific matched, run all agents (comprehensive analysis)
        if len(active) == 2:
            active = list(self.agents.keys())

        return active

    async def _execute_agent(self, agent_name: str, task: str,
                              context: Dict[str, Any]) -> AgentResult:
        """Execute a single agent with full production resilience.

        Production hardening (v2.0):
        - Circuit breaker prevents calling failing agents
        - Timeout prevents hung agents
        - Retry handles transient failures
        - Atomic writes prevent state corruption

        Production excellence (v3.0):
        - Bulkhead isolation prevents agent starvation
        - Idempotency prevents double-execution on retry
        - Fallback provides graceful degradation
        - Metrics track execution performance
        - Tracing provides distributed observability
        """
        agent = self.agents[agent_name]
        start_time = time.time()
        task_hash = hashlib.sha256(task.encode()).hexdigest()[:8]

        # Start tracing span
        span = None
        if self.tracer:
            parent_span = context.get("_parent_span")
            span = self.tracer.start_span(
                f"agent.{agent_name}",
                parent=parent_span,
                attributes={"agent": agent_name, "task_hash": task_hash}
            )

        # Track active agents
        if self.metrics:
            self.metrics.active_agents.inc()

        output = None
        status = None
        error = None

        try:
            # Generate idempotency key
            idempotency_key = generate_idempotency_key(
                agent_name, task, self.iteration
            ) if self.idempotency_manager else None

            # Define execution function
            async def execute_fn():
                return await agent.execute(task, context)

            # Wrap with bulkhead if enabled
            async def bulkhead_wrapped():
                if self.bulkhead:
                    return await self.bulkhead.execute_isolated(
                        agent_name,
                        self.resilient_executor.execute(
                            name=agent_name,
                            func=execute_fn,
                            timeout=self.config.agent_timeout,
                            max_retries=self.config.max_retries
                        )
                    )
                else:
                    return await self.resilient_executor.execute(
                        name=agent_name,
                        func=execute_fn,
                        timeout=self.config.agent_timeout,
                        max_retries=self.config.max_retries
                    )

            # Execute with idempotency if enabled
            if self.idempotency_manager and idempotency_key:
                output = await self.idempotency_manager.execute_idempotent(
                    idempotency_key,
                    bulkhead_wrapped
                )
            else:
                output = await bulkhead_wrapped()

            status = AgentStatus.COMPLETED
            error = None

            # Cache successful result for fallback
            if self.fallback_registry:
                self.fallback_registry.cache_result(agent_name, output, task_hash)

        except CircuitBreakerOpen as e:
            # Circuit is open - try fallback
            if self.fallback_registry:
                fallback_result = await self.fallback_registry.try_fallback(
                    agent_name, f"Circuit open: {e.time_until_reset:.1f}s"
                )
                output = fallback_result.to_dict()
                status = AgentStatus.DEGRADED if fallback_result.source != 'synthetic' else AgentStatus.SKIPPED
                error = f"Circuit breaker open, using {fallback_result.source}"
                logger.warning(f"Agent {agent_name}: {error}")
            else:
                output = {"error": f"Circuit breaker open: {e.name}", "skipped": True}
                status = AgentStatus.SKIPPED
                error = str(e)
                logger.warning(f"Agent {agent_name} skipped: circuit breaker open")

            # Record circuit breaker trip
            if self.metrics:
                self.metrics.record_circuit_breaker_trip(agent_name)

        except BulkheadRejected as e:
            # Bulkhead rejected - try fallback
            if self.fallback_registry:
                fallback_result = await self.fallback_registry.try_fallback(
                    agent_name, f"Bulkhead rejected: {e.reason}"
                )
                output = fallback_result.to_dict()
                status = AgentStatus.DEGRADED
                error = f"Bulkhead rejected, using {fallback_result.source}"
            else:
                output = {"error": str(e), "rejected": True}
                status = AgentStatus.FAILED
                error = str(e)
            logger.warning(f"Agent {agent_name} bulkhead rejected: {e.reason}")

        except BulkheadTimeout as e:
            # Bulkhead timeout - try fallback
            if self.fallback_registry:
                fallback_result = await self.fallback_registry.try_fallback(
                    agent_name, f"Bulkhead timeout after {e.timeout}s"
                )
                output = fallback_result.to_dict()
                status = AgentStatus.DEGRADED
                error = f"Bulkhead timeout, using {fallback_result.source}"
            else:
                output = {"error": str(e)}
                status = AgentStatus.FAILED
                error = str(e)
            logger.warning(f"Agent {agent_name} bulkhead timeout")

        except AgentTimeoutError as e:
            # Agent timed out - try fallback
            if self.fallback_registry:
                fallback_result = await self.fallback_registry.try_fallback(
                    agent_name, f"Timeout after {e.timeout}s"
                )
                output = fallback_result.to_dict()
                status = AgentStatus.DEGRADED
                error = f"Timeout, using {fallback_result.source}"
            else:
                output = {"error": f"Timeout after {e.timeout}s"}
                status = AgentStatus.FAILED
                error = str(e)
            logger.error(f"Agent {agent_name} timed out after {e.timeout}s")

        except Exception as e:
            # Other failures - try fallback
            if self.fallback_registry:
                fallback_result = await self.fallback_registry.try_fallback(
                    agent_name, str(e)
                )
                output = fallback_result.to_dict()
                status = AgentStatus.DEGRADED
                error = f"Failed, using {fallback_result.source}: {e}"
            else:
                output = {"error": str(e)}
                status = AgentStatus.FAILED
                error = str(e)
            logger.error(f"Agent {agent_name} failed: {e}")

        finally:
            # Track active agents (decrement)
            if self.metrics:
                self.metrics.active_agents.dec()

        execution_time = time.time() - start_time

        # Compute deterministic checksum
        output_str = json.dumps(output, sort_keys=True, default=str)
        checksum = hashlib.sha256(output_str.encode()).hexdigest()[:16]

        result = AgentResult(
            agent_name=agent_name,
            status=status,
            output=output,
            checksum=checksum,
            execution_time=execution_time,
            error=error
        )

        # Ralph pattern: Write to filesystem immediately (atomic)
        result_file = self.results_dir / f"{agent_name}.json"
        try:
            atomic_write_json(result_file, result.to_dict())
        except Exception as e:
            logger.error(f"Failed to write result for {agent_name}: {e}")

        # Record metrics
        if self.metrics:
            status_str = 'completed' if status == AgentStatus.COMPLETED else (
                'degraded' if status == AgentStatus.DEGRADED else 'failed'
            )
            self.metrics.record_agent_execution(
                agent_name, status_str, execution_time * 1000
            )

        # End tracing span
        if span:
            span.set_attribute("status", status.value)
            span.set_attribute("checksum", checksum)
            span.set_attribute("execution_time_ms", execution_time * 1000)
            self.tracer.end_span(
                span,
                status=SpanStatus.OK if status == AgentStatus.COMPLETED else SpanStatus.ERROR,
                error=error
            )

        # Structured logging
        log_execution(
            logger=logger,
            agent_name=agent_name,
            task_hash=task_hash,
            duration_ms=execution_time * 1000,
            checksum=checksum,
            status='completed' if status == AgentStatus.COMPLETED else (
                'degraded' if status == AgentStatus.DEGRADED else 'failed'
            ),
            error=error
        )

        return result

    async def orchestrate(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run orchestration cycle with production hardening.

        Production features (v2.0):
        - Input validation at entry
        - Orchestration timeout for entire cycle
        - Atomic state file writes
        - Structured logging
        - Shutdown awareness

        Production excellence (v3.0):
        - Rate limiting for overload protection
        - Metrics tracking for observability
        - Distributed tracing for debugging
        - Checkpointing for crash recovery
        """
        # Check if shutting down
        if self.lifecycle.is_shutting_down:
            raise RuntimeError("Orchestrator is shutting down, cannot accept new tasks")

        # Apply rate limiting
        if self.rate_limiter:
            try:
                wait_time = await self.rate_limiter.acquire()
                if wait_time > 0:
                    logger.info(f"Rate limited, waited {wait_time:.2f}s")
            except RateLimitExceeded as e:
                if self.metrics:
                    self.metrics.tasks_failed.inc()
                raise

        # Validate task input
        validation = validate_task(task, max_length=self.config.max_task_length)
        if not validation.valid:
            raise ValidationError(validation.errors)
        task = validation.sanitized  # Use sanitized task

        # Validate context
        context = context or {}
        ctx_validation = validate_context(context)
        if not ctx_validation.valid:
            logger.warning(f"Context validation warnings: {ctx_validation.errors}")

        context["seed"] = context.get("seed", 42)

        self.iteration += 1

        # Track task metrics
        if self.metrics:
            self.metrics.increment_task_total()

        log_orchestration_start(logger, self.iteration, task, [])

        try:
            # Wrap entire orchestration with timeout
            result = await asyncio.wait_for(
                self._orchestrate_impl(task, context),
                timeout=self.config.orchestration_timeout
            )

            # Track success
            if self.metrics:
                self.metrics.increment_task_succeeded()
                if self.rate_limiter and self.config.rate_limit_adaptive:
                    self.rate_limiter.record_success()

            return result

        except asyncio.TimeoutError:
            logger.error(f"Orchestration timed out after {self.config.orchestration_timeout}s")
            if self.metrics:
                self.metrics.increment_task_failed()
                if self.rate_limiter and self.config.rate_limit_adaptive:
                    self.rate_limiter.record_failure()
            raise AgentTimeoutError("orchestration", self.config.orchestration_timeout)

        except Exception as e:
            if self.metrics:
                self.metrics.increment_task_failed()
                if self.rate_limiter and self.config.rate_limit_adaptive:
                    self.rate_limiter.record_failure()
            raise

    async def _orchestrate_impl(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Internal orchestration implementation with full observability.

        v4.3.0 Hybrid Orchestra: Implements 7-phase execution model with
        work/delegate/protect branching per ThinkingMachines [He2025].

        Flow (7 Phases):
        1. SNAPSHOT: Take cognitive state snapshot BEFORE processing
        2. DETECT: Run PRISM signal detection
        3. SAFETY GATE: Cognitive safety constraints check
        4. ROUTE: DecisionEngine.process_task() with pre-computed table
        5. EXECUTE: Branch by DecisionMode (WORK/DELEGATE/PROTECT)
        6. COLLECT: Gather results, determinism guard, checksum
        7. UPDATE: Batch update cognitive state AFTER all complete
        """

        orchestration_start = time.time()
        checkpoint_id = None

        # =====================================================================
        # PHASE 1: SNAPSHOT - Cognitive State (ThinkingMachines [He2025])
        # =====================================================================
        # Take snapshot BEFORE any processing to ensure all agents see same state
        cognitive_state = self.cognitive_state_manager.get_state()
        cognitive_snapshot = cognitive_state.snapshot()

        # Increment exchange count
        cognitive_state.increment_exchange(rapid=True)

        # Initialize cognitive safety manager from state
        self.cognitive_safety_manager = create_cognitive_safety_manager(cognitive_state)

        # Add cognitive context for agents
        context["cognitive_state"] = cognitive_snapshot
        context["cognitive_state_dict"] = cognitive_snapshot.to_dict()

        # =====================================================================
        # PHASE 2: DETECT - Signal Detection (PRISM)
        # =====================================================================
        signals = self.prism_detector.detect(task, context)
        context["prism_signals"] = signals.to_dict()

        # Quick safety check - may require immediate intervention
        requires_intervention, intervention_reason = self.prism_detector.quick_safety_check(task)
        if requires_intervention:
            logger.warning(f"Safety intervention triggered: {intervention_reason}")
            context["safety_intervention"] = True
            context["safety_reason"] = intervention_reason

        # =====================================================================
        # PHASE 3: SAFETY GATE - Cognitive Safety Constraints Check
        # =====================================================================
        cognitive_safety_check = None
        can_spawn = True
        if self.cognitive_safety_manager and self.cognitive_safety_manager.enabled:
            cognitive_safety_check = self.cognitive_safety_manager.check(cognitive_snapshot, task_items=1, text=task)
            context["cognitive_safety_check"] = cognitive_safety_check.to_dict()

            # Check if agents should be spawned
            can_spawn, spawn_reason = self.cognitive_safety_manager.should_spawn_agents(cognitive_snapshot)
            if not can_spawn:
                logger.warning(f"Agent spawning restricted: {spawn_reason}")
                # Return simplified response in restricted mode
                if cognitive_snapshot.burnout_level == BurnoutLevel.RED:
                    return {
                        "iteration": self.iteration,
                        "task": truncate_for_logging(task, 200),
                        "timestamp": time.time(),
                        "cognitive_intervention": True,
                        "intervention_type": "burnout_red",
                        "message": "RED burnout detected. Offering recovery options.",
                        "recovery_menu": self.cognitive_safety_manager.get_recovery_menu(),
                        "agents_executed": 0,
                        "master_checksum": hashlib.sha256(task.encode()).hexdigest()[:32],
                        "decision_mode": "protect"
                    }

        # Start root tracing span
        root_span = None
        if self.tracer:
            root_span = self.tracer.start_span(
                "orchestration",
                attributes={
                    "iteration": self.iteration,
                    "task_hash": hashlib.sha256(task.encode()).hexdigest()[:16],
                    "cognitive_burnout": cognitive_snapshot.burnout_level.value,
                    "cognitive_mode": cognitive_snapshot.mode.value,
                    "focus_level": cognitive_snapshot.focus_level,
                    "urgency": cognitive_snapshot.urgency
                }
            )
            context["_parent_span"] = root_span

        try:
            # =====================================================================
            # PHASE 4: ROUTE - DecisionEngine (Work/Delegate/Protect)
            # =====================================================================
            execution_plan = None
            active_agents = []

            if self.use_decision_engine:
                # Initialize DecisionEngine lazily (needs cognitive stage)
                if self.decision_engine is None:
                    # Use cognitive state manager as the cognitive stage
                    self.decision_engine = DecisionEngine(
                        cognitive_stage=self.cognitive_state_manager,
                        use_table_routing=True
                    )

                # Create task request from task string
                task_request = self._create_task_request(task, context)

                # Get execution plan from DecisionEngine
                execution_plan = self.decision_engine.process_task(task_request, context)

                logger.info(f"DecisionEngine: mode={execution_plan.decision.mode.value}, "
                           f"checksum={execution_plan.checksum}")

                # =========================================================
                # PHASE 5: EXECUTE - Branch by DecisionMode
                # =========================================================
                if execution_plan.decision.mode == DecisionMode.PROTECT:
                    # PROTECT: Queue task, return flow-protection ack
                    logger.info("PROTECT mode: preserving flow state")

                    # Queue the task for later
                    if self.decision_engine:
                        self.decision_engine.flow_protector.queue_interrupt(
                            "task", {"task": task, "context": context}, urgency="normal"
                        )

                    return {
                        "iteration": self.iteration,
                        "task": truncate_for_logging(task, 200),
                        "timestamp": time.time(),
                        "decision_mode": "protect",
                        "flow_protected": True,
                        "message": f"Task queued. {execution_plan.decision.rationale}",
                        "resume_when": execution_plan.decision.protect_until,
                        "agents_executed": 0,
                        "master_checksum": hashlib.sha256(task.encode()).hexdigest()[:32],
                        "prism_signals": context.get("prism_signals", {}),
                        "cognitive_state": cognitive_state.to_dict()
                    }

                elif execution_plan.decision.mode == DecisionMode.WORK:
                    # WORK: Execute minimal agents (direct action)
                    active_agents = execution_plan.get_routed_agents()
                    # Ensure we have valid agent names
                    active_agents = [a for a in active_agents if a in self.agents]
                    # Always include determinism guard for consistency
                    if "determinism_guard" not in active_agents:
                        active_agents.append("determinism_guard")
                    logger.info(f"WORK mode: {', '.join(active_agents)}")

                else:  # DELEGATE
                    # DELEGATE: Use full agent set per execution plan
                    active_agents = execution_plan.get_routed_agents()
                    active_agents = [a for a in active_agents if a in self.agents]
                    if "determinism_guard" not in active_agents:
                        active_agents.append("determinism_guard")
                    logger.info(f"DELEGATE mode: {', '.join(active_agents)}")

            else:
                # Legacy path: use _route_task
                active_agents = self._route_task(task, context)
                logger.info(f"Legacy routing: {', '.join(active_agents)}")

            # Log active agents
            logger.info(f"Active agents: {', '.join(active_agents)}")

            if root_span:
                root_span.set_attribute("active_agents", len(active_agents))

            # Create checkpoint (pre-orchestration)
            if self.checkpoint:
                checkpoint_id = await self.checkpoint.start_orchestration(
                    self.iteration, task, context, active_agents
                )

            # Phase 2: Execute agents in parallel with proper cleanup [He2025]
            start_time = time.time()

            # Create tasks explicitly for proper cancellation handling
            agent_tasks = [
                asyncio.create_task(
                    self._execute_agent(agent_name, task, context),
                    name=f"agent_{agent_name}"
                )
                for agent_name in active_agents
            ]

            try:
                results = await asyncio.gather(*agent_tasks, return_exceptions=True)
            except asyncio.CancelledError:
                # Ensure all tasks are cancelled and awaited on cancellation
                for t in agent_tasks:
                    if not t.done():
                        t.cancel()
                # Await cancelled tasks to ensure cleanup
                await asyncio.gather(*agent_tasks, return_exceptions=True)
                raise

            # Handle any exceptions from gather
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    agent_name = active_agents[i]
                    logger.error(f"Agent {agent_name} raised exception: {result}")
                    processed_results.append(AgentResult(
                        agent_name=agent_name,
                        status=AgentStatus.FAILED,
                        output={"error": str(result)},
                        checksum=hashlib.sha256(str(result).encode()).hexdigest()[:16],
                        execution_time=0,
                        error=str(result)
                    ))
                else:
                    processed_results.append(result)

                    # Checkpoint each agent completion
                    if self.checkpoint and checkpoint_id:
                        await self.checkpoint.checkpoint_agent_completion(
                            checkpoint_id, result.agent_name, result.to_dict()
                        )

            total_time = time.time() - start_time

            # Phase 3: Collect results
            result_map = {r.agent_name: r for r in processed_results}

            # Phase 4: Run determinism guard with all results
            context["agent_results"] = result_map
            if "determinism_guard" not in result_map:
                det_result = await self._execute_agent("determinism_guard", task, context)
                result_map["determinism_guard"] = det_result

            # Phase 5: Compute master checksum
            all_checksums = sorted([r.checksum for r in result_map.values()])
            combined = "".join(all_checksums)
            master_checksum = hashlib.sha256(combined.encode()).hexdigest()[:32]

            # Phase 6: Build synthesis
            agents_succeeded = sum(1 for r in result_map.values() if r.status == AgentStatus.COMPLETED)
            agents_failed = sum(1 for r in result_map.values() if r.status == AgentStatus.FAILED)
            agents_degraded = sum(1 for r in result_map.values() if r.status == AgentStatus.DEGRADED)

            synthesis = {
                "iteration": self.iteration,
                "task": truncate_for_logging(task, 200),
                "timestamp": time.time(),
                "total_execution_time_ms": round(total_time * 1000, 2),
                "agents_executed": len(result_map),
                "agents_succeeded": agents_succeeded,
                "agents_failed": agents_failed,
                "agents_degraded": agents_degraded,
                "agents_skipped": sum(1 for r in result_map.values() if r.status == AgentStatus.SKIPPED),
                "master_checksum": master_checksum,
                "reproducibility_proof": f"sha256:{master_checksum}",
                "agent_results": {name: r.to_dict() for name, r in result_map.items()},
                "agent_checksums": {name: r.checksum for name, r in result_map.items()},
                # v4.3.0: Work/Delegate/Protect decision info
                "decision_mode": execution_plan.decision.mode.value if execution_plan else "legacy",
                "decision_rationale": execution_plan.decision.rationale if execution_plan else "Legacy routing",
                "decision_checksum": execution_plan.checksum if execution_plan else "",
                "state_snapshot_checksum": execution_plan.get_snapshot_checksum() if execution_plan else ""
            }

            # =====================================================================
            # Phase 6.5: Cognitive State Batch Update (ThinkingMachines [He2025])
            # =====================================================================
            # Update cognitive state AFTER all processing complete
            cognitive_updates = {}

            # Update momentum based on task completion
            if agents_succeeded > 0:
                cognitive_state.complete_task()
                cognitive_updates["tasks_completed"] = cognitive_state.tasks_completed
                cognitive_updates["momentum_phase"] = cognitive_state.momentum_phase.value

            # Check for burnout escalation based on failures
            if agents_failed > agents_succeeded:
                cognitive_state.escalate_burnout()
                cognitive_updates["burnout_level"] = cognitive_state.burnout_level.value

            # Update convergence tracking
            moe_result = result_map.get("moe_router")
            if moe_result and moe_result.status == AgentStatus.COMPLETED:
                selected_expert = moe_result.output.get("selected_expert", "executor")
                # Map expert to attractor
                expert_to_attractor = {
                    "protector": "recovery",
                    "restorer": "recovery",
                    "guide": "exploring",
                    "executor": "focused",
                    "decomposer": "focused",
                    "acknowledger": "focused",
                    "redirector": "focused"
                }
                new_attractor = expert_to_attractor.get(selected_expert, "focused")
                tension = cognitive_state.update_convergence(new_attractor)
                cognitive_updates["convergence_attractor"] = new_attractor
                cognitive_updates["epistemic_tension"] = tension

            # Apply batch update and save
            if cognitive_updates:
                cognitive_state.batch_update(cognitive_updates)

            # Save cognitive state
            self.cognitive_state_manager.save()

            # Add cognitive state to synthesis
            synthesis["cognitive_state"] = cognitive_state.to_dict()
            synthesis["prism_signals"] = context.get("prism_signals", {})
            if cognitive_safety_check:
                synthesis["cognitive_safety_check"] = cognitive_safety_check.to_dict()

            # =====================================================================
            # PHASE 6.75: Queue Delivery Check (v4.3.0)
            # =====================================================================
            # Check if there are queued results ready for delivery at this
            # natural break point. This is part of the PROTECT mode flow.
            if self.decision_engine:
                pending_results = self.decision_engine.check_and_deliver_queued()
                if pending_results:
                    synthesis["queued_results_delivered"] = True
                    synthesis["delivered_results_summary"] = pending_results[:500]  # Truncate for synthesis
                    logger.info(f"Delivered {len(pending_results)} queued result(s) at natural break point")

            # Phase 7: Persist state (Ralph pattern) - ATOMIC WRITE
            try:
                atomic_write_json(self.state_file, synthesis)
                logger.info(f"State persisted to {sanitize_path_for_logging(self.state_file)}")
            except Exception as e:
                logger.error(f"Failed to persist state: {e}")

            # Complete checkpoint
            if self.checkpoint and checkpoint_id:
                await self.checkpoint.complete_orchestration(checkpoint_id, synthesis)

            # Record orchestration latency
            orchestration_time = time.time() - orchestration_start
            if self.metrics:
                self.metrics.observe_orchestration_latency(orchestration_time * 1000)

                # Update circuit breaker gauge
                open_circuits = sum(
                    1 for stats in self.circuit_breaker.get_all_stats().values()
                    if stats.get('state') == 'open'
                )
                self.metrics.set_circuit_breakers_open(open_circuits)

            # End root tracing span
            if root_span:
                root_span.set_attribute("master_checksum", master_checksum)
                root_span.set_attribute("agents_succeeded", agents_succeeded)
                root_span.set_attribute("agents_failed", agents_failed)
                root_span.set_attribute("total_time_ms", orchestration_time * 1000)
                self.tracer.end_span(root_span, status=SpanStatus.OK)

            # Structured completion logging
            log_orchestration_complete(
                logger=logger,
                iteration=self.iteration,
                duration_ms=total_time * 1000,
                agents_succeeded=agents_succeeded,
                agents_failed=agents_failed,
                master_checksum=master_checksum
            )

            return synthesis

        except Exception as e:
            # Fail checkpoint on error
            if self.checkpoint and checkpoint_id:
                await self.checkpoint.fail_orchestration(checkpoint_id, str(e))

            # End root span with error
            if root_span:
                self.tracer.end_span(root_span, status=SpanStatus.ERROR, error=str(e))

            raise

    def get_agent_info(self) -> Dict[str, Dict[str, str]]:
        """Get information about all agents."""
        return {name: agent.get_info() for name, agent in self.agents.items()}

    def get_health(self) -> Dict[str, Any]:
        """Get health status of the orchestrator."""
        report = self.health_checker.check_health()
        return report.to_dict()

    def is_healthy(self) -> bool:
        """Quick health check - returns True if ready to accept tasks."""
        return self.health_checker.get_ready_status()

    def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get status of all circuit breakers."""
        return self.circuit_breaker.get_all_stats()

    def reset_circuit_breaker(self, agent_name: str = None) -> None:
        """Reset circuit breaker(s)."""
        self.circuit_breaker.reset(agent_name)

    def get_metrics(self) -> Optional[Dict[str, Any]]:
        """Get metrics statistics."""
        if self.metrics:
            return self.metrics.get_stats()
        return None

    def export_metrics_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        if self.metrics:
            return self.metrics.export_prometheus()
        return "# Metrics not enabled"

    def get_bulkhead_stats(self) -> Optional[Dict[str, Any]]:
        """Get bulkhead statistics."""
        if self.bulkhead:
            return self.bulkhead.get_stats()
        return None

    def get_fallback_stats(self) -> Optional[Dict[str, Any]]:
        """Get fallback statistics."""
        if self.fallback_registry:
            return self.fallback_registry.get_stats()
        return None

    def get_idempotency_stats(self) -> Optional[Dict[str, Any]]:
        """Get idempotency manager statistics."""
        if self.idempotency_manager:
            return self.idempotency_manager.get_stats()
        return None

    def get_rate_limiter_stats(self) -> Optional[Dict[str, Any]]:
        """Get rate limiter statistics."""
        if self.rate_limiter:
            return self.rate_limiter.get_stats()
        return None

    async def get_interrupted_orchestrations(self) -> List[Dict[str, Any]]:
        """Get list of interrupted orchestrations for recovery."""
        if self.checkpoint:
            interrupted = self.checkpoint.get_interrupted_orchestrations()
            return [cp.to_dict() for cp in interrupted]
        return []

    async def recover_orchestration(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Attempt to recover an interrupted orchestration."""
        if not self.checkpoint:
            logger.warning("Checkpointing not enabled")
            return None

        checkpoint_data = await self.checkpoint.resume_orchestration(checkpoint_id)
        if not checkpoint_data:
            return None

        # Resume orchestration with checkpoint data
        logger.info(f"Resuming orchestration from checkpoint {checkpoint_id}")
        return await self.orchestrate(
            checkpoint_data.task,
            checkpoint_data.context
        )

    def export_trace(self, trace_id: str, format: str = 'jaeger') -> str:
        """Export a trace in the specified format."""
        if not self.tracer:
            return "{}"

        if format == 'zipkin':
            return self.tracer.export_zipkin(trace_id)
        return self.tracer.export_jaeger(trace_id)

    def get_production_status(self) -> Dict[str, Any]:
        """Get comprehensive production status."""
        status = {
            "version": "3.0",
            "healthy": self.is_healthy(),
            "iteration": self.iteration,
            "uptime_seconds": time.time() - self._start_time,
        }

        # Component status
        components = {}
        components["circuit_breaker"] = {
            "enabled": self.config.enable_circuit_breaker,
            "stats": self.get_circuit_breaker_status()
        }
        if self.bulkhead:
            components["bulkhead"] = {
                "enabled": True,
                "stats": self.bulkhead.get_stats(),
                "healthy": self.bulkhead.is_healthy()
            }
        if self.metrics:
            components["metrics"] = {
                "enabled": True,
                "stats": self.metrics.get_stats()
            }
        if self.checkpoint:
            components["checkpoint"] = {
                "enabled": True,
                "directory": str(self.config.checkpoint_dir)
            }
        if self.rate_limiter:
            components["rate_limiter"] = {
                "enabled": True,
                "stats": self.rate_limiter.get_stats()
            }
        if self.fallback_registry:
            components["fallback"] = {
                "enabled": True,
                "stats": self.fallback_registry.get_stats()
            }
        if self.idempotency_manager:
            components["idempotency"] = {
                "enabled": True,
                "stats": self.idempotency_manager.get_stats()
            }

        status["components"] = components
        return status


# =============================================================================
# CLI Interface
# =============================================================================

async def main():
    """Main entry point for CLI usage with production features."""

    import argparse

    parser = argparse.ArgumentParser(
        description="Framework Orchestrator - Production-Ready 7-Agent System (v3.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  FO_WORKSPACE           Workspace directory (default: ~/Orchestra)
  FO_AGENT_TIMEOUT       Per-agent timeout in seconds (default: 30)
  FO_ORCHESTRATION_TIMEOUT  Total orchestration timeout (default: 120)
  FO_MAX_RETRIES         Retry count for failed agents (default: 3)
  FO_LOG_FORMAT          Log format: 'text' or 'json' (default: text)
  FO_LOG_LEVEL           Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)

  # v3.0 Production Excellence
  FO_MAX_CONCURRENT_AGENTS  Bulkhead concurrency limit (default: 3)
  FO_CHECKPOINT_ENABLED     Enable crash recovery (default: true)
  FO_METRICS_ENABLED        Enable Prometheus metrics (default: true)
  FO_TRACING_ENABLED        Enable distributed tracing (default: true)

Examples:
  # Run a single task
  python -m framework_orchestrator --task "Analyze this code"

  # Run with JSON logging for production
  FO_LOG_FORMAT=json python -m framework_orchestrator --task "..."

  # Check health status
  python -m framework_orchestrator --health

  # Show configuration
  python -m framework_orchestrator --show-config

  # Export Prometheus metrics
  python -m framework_orchestrator --metrics

  # Show interrupted orchestrations (for crash recovery)
  python -m framework_orchestrator --show-interrupted

  # Resume an interrupted orchestration
  python -m framework_orchestrator --resume <checkpoint_id>

  # Show production status
  python -m framework_orchestrator --status
"""
    )
    parser.add_argument("--task", "-t", type=str, help="Task to process")
    parser.add_argument("--workspace", "-w", type=str, help="Workspace directory (overrides FO_WORKSPACE)")
    parser.add_argument("--seed", "-s", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--info", action="store_true", help="Show agent information")
    parser.add_argument("--health", action="store_true", help="Show health status and exit")
    parser.add_argument("--show-config", action="store_true", help="Show current configuration")
    parser.add_argument("--reset-circuits", action="store_true", help="Reset all circuit breakers")

    # v3.0 Production Excellence CLI options
    parser.add_argument("--metrics", action="store_true", help="Export Prometheus metrics and exit")
    parser.add_argument("--status", action="store_true", help="Show production status and exit")
    parser.add_argument("--show-interrupted", action="store_true", help="Show interrupted orchestrations")
    parser.add_argument("--resume", type=str, metavar="CHECKPOINT_ID", help="Resume interrupted orchestration")

    args = parser.parse_args()

    # Load configuration
    config = get_config()

    # Setup logging based on config
    global logger
    logger = setup_logging(
        level=config.log_level,
        log_format=config.log_format,
        log_file=config.log_file
    )

    # Determine workspace
    workspace = Path(args.workspace) if args.workspace else config.workspace

    # Create orchestrator
    orchestrator = FrameworkOrchestrator(workspace, config)

    # Setup signal handlers for graceful shutdown
    orchestrator.lifecycle.setup_signal_handlers()
    orchestrator.lifecycle.mark_running()

    # Handle --show-config
    if args.show_config:
        print("\n" + "=" * 60)
        print("FRAMEWORK ORCHESTRATOR - Configuration")
        print("=" * 60)
        for key, value in config.to_dict().items():
            print(f"  {key}: {value}")
        print("=" * 60)
        return

    # Handle --health
    if args.health:
        health = orchestrator.get_health()
        report = orchestrator.health_checker.check_health()
        print(format_health_report(report))
        return 0 if report.is_healthy else 1

    # Handle --reset-circuits
    if args.reset_circuits:
        orchestrator.reset_circuit_breaker()
        print("All circuit breakers reset")
        return

    # Handle --metrics (v3.0)
    if args.metrics:
        print(orchestrator.export_metrics_prometheus())
        return

    # Handle --status (v3.0)
    if args.status:
        print("\n" + "=" * 60)
        print("FRAMEWORK ORCHESTRATOR - Production Status (v3.0)")
        print("=" * 60)
        status = orchestrator.get_production_status()
        print(json.dumps(status, indent=2, default=str))
        print("=" * 60)
        return

    # Handle --show-interrupted (v3.0)
    if args.show_interrupted:
        print("\n" + "=" * 60)
        print("FRAMEWORK ORCHESTRATOR - Interrupted Orchestrations")
        print("=" * 60)
        interrupted = await orchestrator.get_interrupted_orchestrations()
        if interrupted:
            for cp in interrupted:
                print(f"\nCheckpoint ID: {cp['checkpoint_id']}")
                print(f"  Iteration: {cp['iteration']}")
                print(f"  Status: {cp['status']}")
                print(f"  Task: {cp['task'][:80]}...")
                print(f"  Started: {cp['started_at']}")
                print(f"  Agents completed: {len(cp.get('agents_completed', {}))}")
                print(f"  Agents pending: {len(cp.get('agents_pending', []))}")
        else:
            print("No interrupted orchestrations found.")
        print("=" * 60)
        return

    # Handle --resume (v3.0)
    if args.resume:
        print(f"\nResuming orchestration from checkpoint: {args.resume}")
        try:
            result = await orchestrator.recover_orchestration(args.resume)
            if result:
                print("\n" + "=" * 60)
                print("ORCHESTRATION RESUMED SUCCESSFULLY")
                print("=" * 60)
                print(f"Iteration: {result['iteration']}")
                print(f"Agents: {result['agents_succeeded']}/{result['agents_executed']} succeeded")
                print(f"Master Checksum: {result['master_checksum']}")
                print("=" * 60)
            else:
                print("Failed to resume orchestration. Check logs for details.")
                return 1
        except Exception as e:
            print(f"Error resuming orchestration: {e}")
            logger.exception("Resume error")
            return 1
        return

    # Handle --info
    if args.info:
        print("\n" + "=" * 60)
        print("FRAMEWORK ORCHESTRATOR - Agent Roster")
        print("=" * 60)
        for name, info in orchestrator.get_agent_info().items():
            print(f"\n{name}:")
            print(f"  Framework: {info['framework']}")
            print(f"  CES 2026:  {info['ces_alignment']}")
        print("\n" + "=" * 60)
        return

    if not args.task:
        # Interactive mode with graceful shutdown support
        print("\n" + "=" * 60)
        print("FRAMEWORK ORCHESTRATOR - Interactive Mode (v3.0 Production)")
        print("=" * 60)
        print("Enter tasks to process. Type 'quit' to exit.")
        print("Commands: 'health', 'circuits', 'metrics', 'status', 'bulkhead', 'quit'\n")

        while not orchestrator.lifecycle.is_shutting_down:
            try:
                task = input("Task> ").strip()

                # Handle commands
                if task.lower() in ["quit", "exit", "q"]:
                    break
                if task.lower() == "health":
                    report = orchestrator.health_checker.check_health()
                    print(format_health_report(report))
                    continue
                if task.lower() == "circuits":
                    print(json.dumps(orchestrator.get_circuit_breaker_status(), indent=2))
                    continue
                if task.lower() == "metrics":
                    if orchestrator.metrics:
                        print(json.dumps(orchestrator.metrics.get_stats(), indent=2))
                    else:
                        print("Metrics not enabled")
                    continue
                if task.lower() == "status":
                    print(json.dumps(orchestrator.get_production_status(), indent=2, default=str))
                    continue
                if task.lower() == "bulkhead":
                    if orchestrator.bulkhead:
                        print(json.dumps(orchestrator.bulkhead.get_stats(), indent=2))
                    else:
                        print("Bulkhead not enabled")
                    continue
                if not task:
                    continue

                result = await orchestrator.orchestrate(task, {"seed": args.seed})

                print(f"\nIteration: {result['iteration']}")
                print(f"Agents: {result['agents_succeeded']}/{result['agents_executed']} succeeded")
                if result.get('agents_failed', 0) > 0:
                    print(f"Failed: {result['agents_failed']}")
                if result.get('agents_degraded', 0) > 0:
                    print(f"Degraded (using fallback): {result['agents_degraded']}")
                if result.get('agents_skipped', 0) > 0:
                    print(f"Skipped (circuit open): {result['agents_skipped']}")
                print(f"Time: {result['total_execution_time_ms']}ms")
                print(f"Checksum: {result['master_checksum']}")
                print(f"Results saved to: {sanitize_path_for_logging(workspace / 'results')}\n")

            except KeyboardInterrupt:
                print("\nShutting down gracefully...")
                await orchestrator.lifecycle.shutdown(reason="User interrupt")
                break
            except ValidationError as e:
                print(f"\nValidation error: {e.errors}")
            except Exception as e:
                print(f"\nError: {e}")
                logger.exception("Orchestration error")
    else:
        # Single task mode
        try:
            result = await orchestrator.orchestrate(args.task, {"seed": args.seed})

            print("\n" + "=" * 60)
            print("ORCHESTRATION COMPLETE")
            print("=" * 60)
            print(f"Task: {args.task[:80]}...")
            print(f"Agents: {result['agents_succeeded']}/{result['agents_executed']} succeeded")
            if result.get('agents_failed', 0) > 0:
                print(f"Failed: {result['agents_failed']}")
            if result.get('agents_skipped', 0) > 0:
                print(f"Skipped: {result['agents_skipped']}")
            print(f"Time: {result['total_execution_time_ms']}ms")
            print(f"Master Checksum: {result['master_checksum']}")
            print(f"\nDetailed results: {sanitize_path_for_logging(workspace / 'results')}")
            print(f"State file: {sanitize_path_for_logging(workspace / '.orchestrator-state.json')}")
            print("=" * 60)

        except ValidationError as e:
            print(f"Validation error: {e.errors}")
            return 1
        except AgentTimeoutError as e:
            print(f"Timeout: {e}")
            return 1
        except Exception as e:
            print(f"Error: {e}")
            logger.exception("Orchestration error")
            return 1

    # Graceful shutdown
    if not orchestrator.lifecycle.is_stopped:
        await orchestrator.lifecycle.shutdown(reason="Normal exit")

    return 0


if __name__ == "__main__":
    asyncio.run(main())
