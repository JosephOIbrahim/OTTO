"""
Unified Memory Interface
========================

Single interface for all OTTO memory operations.
Wraps existing systems - no parallel storage.

Determinism:
- Fixed seeds for determinism
- Sorted iteration
- Kahan summation for aggregations
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Set, Union

logger = logging.getLogger(__name__)

# ============================================================================
# Constants - Determinism
# ============================================================================

MEMORY_SEED: Final[int] = 0xAE0717E5
COGNITIVE_TILE_SIZE: Final[int] = 32
HASH_ALGORITHM: Final[str] = "sha256"

# Trust thresholds for auto-approval
AUTO_APPROVE_THRESHOLD: Final[float] = 0.8
LEARNING_THRESHOLD: Final[float] = 0.7


class Outcome(str, Enum):
    """Outcome of an action for trail deposits."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class MemoryTier(str, Enum):
    """Memory tier for substrate operations."""
    CONSTITUTIONAL = "constitutional"  # Immutable
    LEARNED = "learned"                 # Persistent, mutable with approval
    EPHEMERAL = "ephemeral"             # Session-scoped


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Episode:
    """
    An episodic memory record - what happened.

    Maps to a Pheromone Trail deposit.
    """
    type: str                           # e.g., "calendar.create", "email.send"
    data: Dict[str, Any]                # Event data (sanitized)
    outcome: Outcome                    # What happened
    timestamp: datetime = field(default_factory=datetime.now)
    actor: str = "otto"                 # Who did it
    service: Optional[str] = None       # Which service
    resource: Optional[str] = None      # What resource
    context: Optional[Dict[str, Any]] = None  # Additional context

    def to_trail_signal(self) -> str:
        """Convert to trail signal format."""
        return f"{self.outcome.value}"

    def to_trail_metadata(self) -> Dict[str, Any]:
        """Convert to trail metadata."""
        return {
            "data": self.data,
            "actor": self.actor,
            "service": self.service,
            "resource": self.resource,
            "context": self.context or {},
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class EpisodeQuery:
    """Query for episodic memories."""
    type: Optional[str] = None          # Filter by type (glob pattern)
    outcome: Optional[Outcome] = None   # Filter by outcome
    actor: Optional[str] = None         # Filter by actor
    service: Optional[str] = None       # Filter by service
    since: Optional[datetime] = None    # Filter by time
    limit: int = 100                    # Max results
    min_strength: float = 0.1           # Min trail strength


@dataclass
class Context:
    """
    Current contextual memory - where you are.

    Maps to LIVRPS layers + EWM state.
    """
    # Session info
    session_goal: Optional[str] = None
    session_start: Optional[datetime] = None
    exchange_count: int = 0

    # Cognitive state
    current_expert: str = "Direct"
    current_altitude: str = "30000ft"
    burnout_level: str = "GREEN"
    momentum_phase: str = "cold_start"

    # Active context
    active_mode: str = "focused"
    active_paradigm: str = "Cortex"
    energy_level: str = "medium"

    # Last session (for cross-session continuity)
    last_session: Optional[Dict[str, Any]] = None

    @classmethod
    def fresh(cls) -> "Context":
        """Create fresh context for new session."""
        return cls(
            session_start=datetime.now(),
            exchange_count=0,
            momentum_phase="cold_start",
        )


@dataclass
class ContextDelta:
    """
    A change to context.

    Applied via EWM manager.
    """
    type: str                           # e.g., "session_end", "state_change"
    data: Dict[str, Any]                # Delta data
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Identity:
    """
    Identity memory - who you are.

    Maps to Cognitive Substrate constitutional + learned tiers.
    """
    # Constitutional (immutable)
    safety_first: bool = True
    ship_over_perfect: bool = True
    protect_momentum: bool = True

    # Learned (persistent, mutable)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    calibration_data: Dict[str, Any] = field(default_factory=dict)

    # Computed from substrate
    @classmethod
    def from_substrate(cls, substrate) -> "Identity":
        """Build identity from substrate state."""
        return cls(
            safety_first=substrate.get("safety_first", True),
            ship_over_perfect=substrate.get("ship_over_perfect", True),
            protect_momentum=substrate.get("protect_momentum", True),
            user_preferences=substrate.get("user_preferences", {}),
            calibration_data=substrate.get("calibration_data", {}),
        )


@dataclass
class Relationship:
    """A relationship between entities."""
    entity1: str
    relation: str                       # e.g., "depends_on", "used_by"
    entity2: str
    strength: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrailStrength:
    """Result of trail strength query."""
    action: str
    signal: str
    strength: float                     # 0.0 - 1.0
    reinforced_count: int
    last_deposit: Optional[datetime]

    @property
    def name(self) -> str:
        """Alias for action (used in query results)."""
        return self.action

    @property
    def auto_approvable(self) -> bool:
        """Check if strength warrants auto-approval."""
        return self.strength >= AUTO_APPROVE_THRESHOLD


# ============================================================================
# Unified Memory Interface
# ============================================================================

class OTTOMemory:
    """
    Unified memory interface for all OTTO operations.

    Wraps existing memory systems:
    - TrailStore for episodic/procedural memory
    - CognitiveSubstrate for identity/learned memory
    - EWMManager for contextual/session memory

    All services should use THIS interface, not direct access.

    Example:
        >>> memory = OTTOMemory()
        >>> memory.record_episode(Episode(
        ...     type="calendar.create",
        ...     data={"title": "Dentist"},
        ...     outcome=Outcome.SUCCESS
        ... ))
        >>> strength = memory.follow_trail("calendar.create")
        >>> if strength.auto_approvable:
        ...     # Skip approval prompt
    """

    _instance: Optional["OTTOMemory"] = None

    def __new__(cls, data_dir: Optional[Path] = None):
        """Singleton pattern - one memory instance for all surfaces.

        When data_dir is specified, creates an isolated (non-singleton)
        instance for testing.
        """
        if data_dir is not None:
            # Non-singleton: isolated instance for testing
            instance = super().__new__(cls)
            instance._initialized = False
            return instance
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize memory systems (once)."""
        if self._initialized:
            return

        self._initialized = True
        self._data_dir = data_dir
        self._trail_store = None
        self._substrate = None
        self._ewm_manager = None
        self._stage = None

        # Knowledge Graph and metrics (NEW)
        self._knowledge_graph: Optional[KnowledgeGraph] = None
        self._decay_worker: Optional[TrailDecayWorker] = None
        self._metrics = MemoryMetrics()

        # Lazy initialization - don't fail if systems unavailable
        self._init_trails()
        self._init_substrate()
        self._init_ewm()
        self._init_stage()
        self._init_knowledge()
        self._init_decay_worker()

        logger.info("OTTOMemory initialized")

    def _init_trails(self) -> None:
        """Initialize trail store."""
        try:
            from otto.trails.store import TrailStore
            if self._data_dir is not None:
                db_path = Path(self._data_dir) / "trails.db"
                self._trail_store = TrailStore(db_path=db_path)
            else:
                self._trail_store = TrailStore()
            logger.info("TrailStore connected")
        except ImportError:
            logger.warning("TrailStore not available - using mock")
            self._trail_store = MockTrailStore()

    def _init_substrate(self) -> None:
        """Initialize cognitive substrate."""
        try:
            from otto.substrate.interface import CognitiveSubstrate
            self._substrate = CognitiveSubstrate()
            logger.info("CognitiveSubstrate connected")
        except ImportError:
            logger.warning("CognitiveSubstrate not available - using mock")
            self._substrate = MockSubstrate()

    def _init_ewm(self) -> None:
        """Initialize EWM manager."""
        try:
            from otto.substrate.ewm.manager import EWMManager
            self._ewm_manager = EWMManager()
            logger.info("EWMManager connected")
        except ImportError:
            logger.warning("EWMManager not available - using mock")
            self._ewm_manager = MockEWMManager()

    def _init_stage(self) -> None:
        """Initialize cognitive stage (LIVRPS)."""
        try:
            from otto.cognitive_stage import CognitiveStage
            self._stage = CognitiveStage()
            logger.info("CognitiveStage connected")
        except ImportError:
            logger.warning("CognitiveStage not available - using mock")
            self._stage = MockStage()

    def _init_knowledge(self) -> None:
        """Initialize knowledge graph."""
        self._knowledge_graph = KnowledgeGraph()
        logger.info("KnowledgeGraph initialized")

    def _init_decay_worker(self) -> None:
        """Initialize trail decay worker."""
        self._decay_worker = TrailDecayWorker(half_life_days=7.0)
        logger.info("TrailDecayWorker initialized")

    # =========================================================================
    # Episodic Memory (What Happened) - via Trails
    # =========================================================================

    def record_episode(self, episode: Episode) -> None:
        """
        Record an episodic memory.

        Deposits a pheromone trail for the action.

        Args:
            episode: The episode to record
        """
        start = datetime.now()
        logger.info(
            f"[MEMORY DEBUG] record_episode called. "
            f"trail_store type: {type(self._trail_store).__name__}"
        )
        try:
            from otto.trails.models import Trail, TrailType

            logger.info("[MEMORY DEBUG] Using REAL Trail path for deposit")
            trail = Trail(
                id=None,
                trail_type=TrailType.PATTERN,
                path=episode.type,
                signal=episode.to_trail_signal(),
                strength=1.0 if episode.outcome == Outcome.SUCCESS else 0.5,
                deposited_by=episode.actor,
                deposited_at=episode.timestamp,
                reinforced_count=0,
                metadata=episode.to_trail_metadata(),
                half_life_days=7.0,
            )

            self._trail_store.deposit(trail)
            logger.info(f"[MEMORY DEBUG] Episode deposited via REAL path: {episode.type}")

        except ImportError as e:
            # Fallback to mock
            logger.info(f"[MEMORY DEBUG] Using MOCK deposit path (ImportError: {e})")
            self._trail_store.deposit_mock(
                episode.type,
                episode.to_trail_signal(),
                episode.to_trail_metadata()
            )
            logger.info(
                f"[MEMORY DEBUG] Episode deposited via MOCK path. "
                f"Trail count now: {len(getattr(self._trail_store, '_trails', []))}"
            )

        # Track metrics
        if self._metrics:
            self._metrics.episodes_recorded += 1
            self._metrics.record_latency((datetime.now() - start).total_seconds() * 1000)

    def query_episodes(
        self,
        query: Optional[EpisodeQuery] = None,
        *,
        event_type: Optional[str] = None,
        event_type_prefix: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = 100,
    ) -> List[Episode]:
        """
        Query episodic memories.

        Queries pheromone trails and converts to episodes.
        Accepts either an EpisodeQuery object or keyword args.

        Args:
            query: Query parameters (EpisodeQuery object)
            event_type: Filter by exact event type
            event_type_prefix: Filter by event type prefix
            service: Filter by service name
            limit: Max results

        Returns:
            List of matching episodes (sorted by timestamp, newest first)
        """
        # Build query from kwargs if not provided
        if query is None:
            query = EpisodeQuery(
                type=event_type or event_type_prefix,
                service=service,
                limit=limit,
            )
        # Track metrics
        if self._metrics:
            self._metrics.episodes_queried += 1

        logger.info(
            f"[MEMORY DEBUG] query_episodes called. "
            f"trail_store type: {type(self._trail_store).__name__}, "
            f"trail count: {len(getattr(self._trail_store, '_trails', []))}"
        )

        try:
            from otto.trails.models import TrailQuery, TrailType

            logger.info("[MEMORY DEBUG] Using REAL TrailQuery path for query")
            # Use path_prefix for prefix matching (episodes have unique timestamps in path)
            trail_query = TrailQuery(
                trail_type=TrailType.PATTERN,
                path_prefix=query.type,  # Prefix match, not exact match
                min_strength=query.min_strength,
            )

            trails = self._trail_store.query(trail_query)
            logger.info(f"[MEMORY DEBUG] REAL query returned {len(trails)} trails")

            episodes = []
            for trail in trails:
                metadata = trail.metadata or {}
                ep_service = metadata.get("service")

                # Post-query service filter (TrailQuery doesn't support service)
                if query.service and ep_service != query.service:
                    continue

                episodes.append(Episode(
                    type=trail.path,
                    data=metadata.get("data", {}),
                    outcome=Outcome(trail.signal) if trail.signal in Outcome.__members__.values() else Outcome.SUCCESS,
                    timestamp=trail.deposited_at,
                    actor=trail.deposited_by,
                    service=ep_service,
                    resource=metadata.get("resource"),
                    context=metadata.get("context"),
                ))

                if len(episodes) >= query.limit:
                    break

            return sorted(episodes, key=lambda e: e.timestamp, reverse=True)

        except ImportError as e:
            logger.info(f"[MEMORY DEBUG] Using MOCK query path (ImportError: {e})")
            return self._trail_store.query_mock(query)

    # =========================================================================
    # Procedural Memory (What Works) - via Trails
    # =========================================================================

    def deposit_trail(self, action: str, outcome: Outcome) -> None:
        """
        Deposit a procedural trail.

        Records that an action succeeded/failed for future reference.
        Auto-approval decisions use trail strength.

        Args:
            action: Action identifier (e.g., "calendar.create")
            outcome: What happened
        """
        try:
            from otto.trails.models import Trail, TrailType

            trail = Trail(
                id=None,
                trail_type=TrailType.PATTERN,
                path=action,
                signal=outcome.value,
                strength=1.0 if outcome == Outcome.SUCCESS else 0.3,
                deposited_by="otto",
                deposited_at=datetime.now(),
                reinforced_count=0,
                metadata={"outcome": outcome.value},
                half_life_days=7.0,
            )

            self._trail_store.deposit(trail)
            logger.debug(f"Trail deposited: {action} -> {outcome}")

        except ImportError:
            self._trail_store.deposit_mock(action, outcome.value, {})

        # Track metrics
        if self._metrics:
            self._metrics.trails_deposited += 1

    # Normalization constant for trail strength calculation.
    # Higher K means more deposits needed to approach strength=1.0.
    _TRAIL_STRENGTH_K: int = 5

    def follow_trail(self, action: str) -> TrailStrength:
        """
        Follow a procedural trail to get strength.

        Computes composite strength from success/failure deposit counts:
          strength = (total / (total + K)) * (successes / total)

        This ensures:
          - More deposits → higher strength (asymptotic to 1.0)
          - Failures reduce the success ratio → lower strength

        Used for auto-approval decisions.

        Args:
            action: Action identifier

        Returns:
            Trail strength info
        """
        # Track metrics
        if self._metrics:
            self._metrics.trails_followed += 1

        try:
            from otto.trails.models import TrailQuery, TrailType

            # Query success trails
            success_query = TrailQuery(
                trail_type=TrailType.PATTERN,
                path=action,
                signal="success",
            )
            success_trails = self._trail_store.query(success_query)

            # Query failure trails
            failure_query = TrailQuery(
                trail_type=TrailType.PATTERN,
                path=action,
                signal="failure",
            )
            failure_trails = self._trail_store.query(failure_query)

            success_trail = success_trails[0] if success_trails else None
            failure_trail = failure_trails[0] if failure_trails else None

            # Count deposits (reinforced_count starts at 0, so +1 for initial)
            success_count = (success_trail.reinforced_count + 1) if success_trail else 0
            failure_count = (failure_trail.reinforced_count + 1) if failure_trail else 0
            total = success_count + failure_count

            if total == 0:
                return TrailStrength(
                    action=action,
                    signal="success",
                    strength=0.0,
                    reinforced_count=0,
                    last_deposit=None,
                )

            # Composite strength: quantity * quality
            K = self._TRAIL_STRENGTH_K
            quantity_factor = total / (total + K)
            quality_factor = success_count / total
            strength = quantity_factor * quality_factor

            last_deposit = None
            if success_trail:
                last_deposit = success_trail.deposited_at
            elif failure_trail:
                last_deposit = failure_trail.deposited_at

            return TrailStrength(
                action=action,
                signal="success",
                strength=strength,
                reinforced_count=total,
                last_deposit=last_deposit,
            )

        except ImportError:
            return self._trail_store.get_strength_mock(action)

    def query_trails(self) -> List[TrailStrength]:
        """
        Query all active trails.

        Returns:
            List of TrailStrength for all known trail paths,
            sorted by action name for determinism.
        """
        try:
            from otto.trails.models import TrailQuery, TrailType

            query = TrailQuery(trail_type=TrailType.PATTERN)
            trails = self._trail_store.query(query)

            # Group by path, take strongest per path
            by_path: Dict[str, Any] = {}
            for t in trails:
                if t.path not in by_path or t.strength > by_path[t.path].strength:
                    by_path[t.path] = t

            return sorted([
                TrailStrength(
                    action=t.path,
                    signal=t.signal,
                    strength=t.strength,
                    reinforced_count=t.reinforced_count,
                    last_deposit=t.deposited_at,
                )
                for t in by_path.values()
            ], key=lambda ts: ts.action)

        except ImportError:
            return self._trail_store.query_trails_mock()

    # =========================================================================
    # Contextual Memory (Where You Are) - via EWM + LIVRPS
    # =========================================================================

    def get_context(self) -> Context:
        """
        Get current contextual memory.

        Combines EWM session state with LIVRPS layers.

        Returns:
            Current context
        """
        # Track metrics
        if self._metrics:
            self._metrics.context_reads += 1

        try:
            ewm_state = self._ewm_manager.get_state()

            return Context(
                session_goal=ewm_state.session_goal,
                session_start=ewm_state.session_start,
                exchange_count=ewm_state.exchange_count,
                current_expert=ewm_state.current_expert,
                current_altitude=ewm_state.current_altitude,
                burnout_level=ewm_state.burnout_level,
                momentum_phase=ewm_state.momentum_phase,
                active_mode=self._stage.get_attribute("active_mode") or "focused",
                active_paradigm=self._stage.get_attribute("active_paradigm") or "Cortex",
                energy_level=self._stage.get_attribute("energy_level") or "medium",
                last_session=ewm_state.last_session,
            )

        except (ImportError, AttributeError):
            return Context.fresh()

    def update_context(self, delta: ContextDelta) -> None:
        """
        Update contextual memory.

        Applies delta to EWM and/or LIVRPS layers.

        Args:
            delta: The change to apply
        """
        # Track metrics
        if self._metrics:
            self._metrics.context_updates += 1

        try:
            if delta.type == "session_end":
                # Save session for cross-session continuity
                self._ewm_manager.save_handoff(delta.data)

            elif delta.type == "session_start":
                # Initialize new session
                self._ewm_manager.start_session(delta.data.get("goal", ""))

            elif delta.type == "state_change":
                # Update LIVRPS layers
                for key, value in delta.data.items():
                    self._stage.set_attribute(key, value)

            elif delta.type == "tick":
                # Increment exchange count
                self._ewm_manager.tick()

            logger.debug(f"Context updated: {delta.type}")

        except (ImportError, AttributeError) as e:
            logger.warning(f"Context update failed: {e}")

    # =========================================================================
    # Identity Memory (Who You Are) - via Substrate
    # =========================================================================

    def get_identity(self) -> Identity:
        """
        Get identity memory.

        Returns constitutional + learned values from substrate.

        Returns:
            Identity state
        """
        return Identity.from_substrate(self._substrate)

    def get_substrate_value(self, path: str, default: Any = None) -> Any:
        """
        Get a value from cognitive substrate.

        Resolution: EPHEMERAL > LEARNED > CONSTITUTIONAL

        Args:
            path: Key path (e.g., "safety.burnout_threshold")
            default: Default if not found

        Returns:
            Value from appropriate tier
        """
        return self._substrate.get(path, default)

    def set_substrate_value(
        self,
        path: str,
        value: Any,
        tier: MemoryTier = MemoryTier.EPHEMERAL,
        reason: Optional[str] = None,
        approval_token: Optional[str] = None,
    ) -> bool:
        """
        Set a value in cognitive substrate.

        Args:
            path: Key path
            value: Value to set
            tier: Which tier (CONSTITUTIONAL not allowed)
            reason: Why (required for LEARNED)
            approval_token: Approval ID (for LEARNED protected fields)

        Returns:
            True if successful
        """
        if tier == MemoryTier.CONSTITUTIONAL:
            logger.error("Cannot modify CONSTITUTIONAL tier")
            return False

        try:
            if tier == MemoryTier.EPHEMERAL:
                result = self._substrate.set_ephemeral(path, value)
            else:
                result = self._substrate.set_learned(
                    path, value, reason or "No reason provided", approval_token
                )

            return result.success if hasattr(result, 'success') else True

        except Exception as e:
            logger.error(f"Substrate set failed: {e}")
            return False

    def propose_learning(
        self,
        path: str,
        proposed_value: Any,
        reason: str,
        evidence: List[str],
    ) -> bool:
        """
        Propose a modification to learned tier.

        Used by learning observer to suggest changes.

        Args:
            path: What to modify
            proposed_value: New value
            reason: Why
            evidence: Supporting evidence

        Returns:
            True if proposal accepted for review
        """
        try:
            result = self._substrate.propose_modification(
                path, proposed_value, reason, evidence
            )
            return result.accepted if hasattr(result, 'accepted') else True

        except Exception as e:
            logger.error(f"Learning proposal failed: {e}")
            return False

    # =========================================================================
    # Relational Memory (Connections) - via Trail Metadata
    # =========================================================================

    def record_relationship(
        self,
        entity1: str,
        relation: str,
        entity2: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a relationship between entities.

        Stored as CONTEXT trail.

        Args:
            entity1: First entity
            relation: Relationship type (e.g., "depends_on")
            entity2: Second entity
            metadata: Additional info
        """
        try:
            from otto.trails.models import Trail, TrailType

            trail = Trail(
                id=None,
                trail_type=TrailType.CONTEXT,
                path=entity1,
                signal=f"{relation}:{entity2}",
                strength=1.0,
                deposited_by="otto",
                deposited_at=datetime.now(),
                reinforced_count=0,
                metadata=metadata or {},
                half_life_days=30.0,  # Relationships decay slower
            )

            self._trail_store.deposit(trail)
            logger.debug(f"Relationship recorded: {entity1} {relation} {entity2}")

        except ImportError:
            pass

    def query_relationships(self, entity: str) -> List[Relationship]:
        """
        Query relationships for an entity.

        Args:
            entity: Entity to query

        Returns:
            List of relationships
        """
        try:
            from otto.trails.models import TrailQuery, TrailType

            query = TrailQuery(
                trail_type=TrailType.CONTEXT,
                path=entity,
            )

            trails = self._trail_store.query(query)

            relationships = []
            for trail in trails:
                if ":" in trail.signal:
                    relation, entity2 = trail.signal.split(":", 1)
                    relationships.append(Relationship(
                        entity1=trail.path,
                        relation=relation,
                        entity2=entity2,
                        strength=trail.strength,
                        metadata=trail.metadata or {},
                    ))

            return sorted(relationships, key=lambda r: r.relation)

        except ImportError:
            return []

    # =========================================================================
    # Session Management
    # =========================================================================

    def start_session(self, goal: str) -> Context:
        """
        Start a new session.

        Args:
            goal: Session goal

        Returns:
            Fresh context with goal
        """
        # Track metrics
        if self._metrics:
            self._metrics.sessions_started += 1

        self.update_context(ContextDelta(
            type="session_start",
            data={"goal": goal}
        ))

        return self.get_context()

    def end_session(
        self,
        progress: List[str],
        position: str,
        next_steps: List[str],
    ) -> None:
        """
        End current session with handoff.

        Args:
            progress: What was accomplished
            position: Where we stopped
            next_steps: What to do next
        """
        # Track metrics
        if self._metrics:
            self._metrics.sessions_ended += 1

        context = self.get_context()

        self.update_context(ContextDelta(
            type="session_end",
            data={
                "goal": context.session_goal,
                "progress": progress,
                "stopped_at": position,
                "next_steps": next_steps,
                "state": {
                    "expert": context.current_expert,
                    "altitude": context.current_altitude,
                    "burnout": context.burnout_level,
                    "momentum": context.momentum_phase,
                },
            }
        ))

    def tick(self) -> None:
        """Increment exchange count."""
        self.update_context(ContextDelta(type="tick", data={}))

    # =========================================================================
    # Utility
    # =========================================================================

    def compute_hash(self) -> str:
        """
        Compute hash of current memory state.

        For integrity verification.

        Returns:
            SHA-256 hash
        """
        state = {
            "substrate_hash": self._substrate.compute_state_hash() if hasattr(self._substrate, 'compute_state_hash') else "",
            "context": str(self.get_context()),
        }

        canonical = "|".join(f"{k}={v}" for k, v in sorted(state.items()))
        return hashlib.sha256(canonical.encode()).hexdigest()

    # =========================================================================
    # Knowledge Graph Access
    # =========================================================================

    def get_knowledge(self, path: str) -> Optional[KnowledgePrim]:
        """
        Get knowledge prim by exact path.

        O(1) retrieval for known paths.

        Args:
            path: Knowledge path (e.g., "/Knowledge/OTTO/Memory")

        Returns:
            KnowledgePrim if found, None otherwise
        """
        if self._knowledge_graph is None:
            return None
        return self._knowledge_graph.get(path)

    def query_knowledge(
        self,
        query: str,
        min_confidence: float = 0.5,
    ) -> List[KnowledgePrim]:
        """
        Query knowledge by trigger match.

        Results sorted deterministically by path.

        Args:
            query: Search query
            min_confidence: Minimum confidence threshold

        Returns:
            List of matching knowledge prims
        """
        if self._knowledge_graph is None:
            return []
        return self._knowledge_graph.query(query, min_confidence)

    def has_knowledge(self, path: str) -> bool:
        """Check if knowledge path exists."""
        if self._knowledge_graph is None:
            return False
        return self._knowledge_graph.has(path)

    def list_knowledge(self, prefix: str = "/Knowledge") -> List[str]:
        """List all knowledge paths under prefix (sorted)."""
        if self._knowledge_graph is None:
            return []
        return self._knowledge_graph.list_paths(prefix)

    # =========================================================================
    # Trail Decay Operations
    # =========================================================================

    def run_decay(self, force: bool = False) -> int:
        """
        Run trail decay if needed.

        Deterministic decay using fixed half-life.

        Args:
            force: Run even if recent decay occurred

        Returns:
            Number of trails decayed
        """
        if self._decay_worker is None:
            return 0

        if not force and not self._decay_worker.should_decay():
            return 0

        return self._decay_worker.decay_trails(self._trail_store)

    def get_decay_factor(self, hours_elapsed: float) -> float:
        """
        Get decay factor for given time elapsed.

        Formula: factor = 0.5 ** (hours_elapsed / half_life_hours)

        Args:
            hours_elapsed: Hours since trail deposit

        Returns:
            Decay factor (0.0-1.0)
        """
        if self._decay_worker is None:
            return 1.0
        return self._decay_worker.compute_decay_factor(hours_elapsed)

    # =========================================================================
    # Metrics Access
    # =========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive memory metrics.

        Returns:
            Dictionary with all metrics
        """
        result = {
            "memory": self._metrics.to_dict() if self._metrics else {},
        }

        if self._knowledge_graph:
            kg_metrics = self._knowledge_graph.get_metrics()
            result["knowledge"] = {
                "cache_hits": kg_metrics.cache_hits,
                "cache_misses": kg_metrics.cache_misses,
                "queries": kg_metrics.queries,
                "total_hits": kg_metrics.total_hits,
                "hit_rate": kg_metrics.hit_rate,
                "avg_latency_ms": kg_metrics.avg_latency_ms(),
            }

        if self._decay_worker:
            decay_metrics = self._decay_worker.get_metrics()
            result["decay"] = {
                "decay_runs": decay_metrics.decay_runs,
                "total_trails_decayed": decay_metrics.total_trails_decayed,
                "total_decay_amount": decay_metrics.total_decay_amount,
                "last_run": decay_metrics.last_run.isoformat() if decay_metrics.last_run else None,
            }

        return result

    def record_auto_approval(self, approved: bool) -> None:
        """Record an approval decision for metrics."""
        if self._metrics:
            if approved:
                self._metrics.auto_approvals += 1
            else:
                self._metrics.manual_approvals += 1


# ============================================================================
# Mock Implementations (Fallback)
# ============================================================================

class MockTrailStore:
    """Mock trail store when real one unavailable."""

    def __init__(self):
        self._trails: List[Dict] = []

    def deposit(self, trail) -> None:
        self._trails.append({
            "path": trail.path,
            "signal": trail.signal,
            "strength": trail.strength,
            "metadata": trail.metadata,
            "deposited_at": trail.deposited_at,
        })

    def deposit_mock(self, path: str, signal: str, metadata: dict) -> None:
        self._trails.append({
            "path": path,
            "signal": signal,
            "strength": 1.0,
            "metadata": metadata,
            "deposited_at": datetime.now(),
        })

    def query(self, query) -> List:
        return [t for t in self._trails if t.get("path", "").startswith(query.path or "")]

    def query_mock(self, query: EpisodeQuery) -> List[Episode]:
        """
        Query stored episodes from mock trail storage.

        Fixed order: sorted by timestamp, newest first.
        """
        logger.info(f"[MEMORY DEBUG] query_mock called. Total trails in store: {len(self._trails)}")
        for i, t in enumerate(self._trails):
            logger.info(f"[MEMORY DEBUG] Trail {i}: path={t.get('path')}, has_metadata={bool(t.get('metadata'))}")

        # Filter by type/path if specified
        matching = self._trails
        if query.type:
            matching = [t for t in matching if t.get("path", "").startswith(query.type)]

        # Filter by service if specified
        if query.service:
            matching = [
                t for t in matching
                if t.get("metadata", {}).get("service") == query.service
            ]

        # Filter by min_strength
        matching = [t for t in matching if t.get("strength", 0.0) >= query.min_strength]

        # Sort by timestamp, newest first
        matching = sorted(matching, key=lambda t: t.get("deposited_at", datetime.min), reverse=True)

        # Apply limit
        matching = matching[:query.limit]

        # Convert to Episode objects
        episodes = []
        for trail in matching:
            metadata = trail.get("metadata", {})
            signal = trail.get("signal", "success")
            try:
                outcome = Outcome(signal)
            except ValueError:
                outcome = Outcome.SUCCESS

            episodes.append(Episode(
                type=trail.get("path", ""),
                data=metadata.get("data", {}),
                outcome=outcome,
                timestamp=trail.get("deposited_at", datetime.now()),
                actor=metadata.get("actor", "otto"),
                service=metadata.get("service"),
                resource=metadata.get("resource"),
                context=metadata.get("context"),
            ))

        return episodes

    def get_strength_mock(self, action: str) -> TrailStrength:
        successes = [t for t in self._trails if t["path"] == action and t["signal"] == "success"]
        failures = [t for t in self._trails if t["path"] == action and t["signal"] == "failure"]
        success_count = len(successes)
        failure_count = len(failures)
        total = success_count + failure_count

        if total == 0:
            return TrailStrength(action=action, signal="success", strength=0.0, reinforced_count=0, last_deposit=None)

        # Same composite formula as OTTOMemory.follow_trail
        K = OTTOMemory._TRAIL_STRENGTH_K
        quantity_factor = total / (total + K)
        quality_factor = success_count / total
        strength = quantity_factor * quality_factor

        last = successes[-1]["deposited_at"] if successes else (failures[-1]["deposited_at"] if failures else None)
        return TrailStrength(
            action=action,
            signal="success",
            strength=strength,
            reinforced_count=total,
            last_deposit=last,
        )

    def query_trails_mock(self) -> List[TrailStrength]:
        """Return all unique trails as TrailStrength objects."""
        by_path: Dict[str, Dict] = {}
        for t in self._trails:
            path = t["path"]
            if path not in by_path or t.get("strength", 0) > by_path[path].get("strength", 0):
                by_path[path] = t
        return sorted([
            TrailStrength(
                action=path,
                signal=t.get("signal", "success"),
                strength=t.get("strength", 0.0),
                reinforced_count=len([x for x in self._trails if x["path"] == path]),
                last_deposit=t.get("deposited_at"),
            )
            for path, t in by_path.items()
        ], key=lambda ts: ts.action)


class MockSubstrate:
    """Mock substrate when real one unavailable."""

    def __init__(self):
        self._values: Dict[str, Any] = {
            "safety_first": True,
            "ship_over_perfect": True,
            "protect_momentum": True,
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def set_ephemeral(self, key: str, value: Any) -> Any:
        self._values[key] = value
        return type("Result", (), {"success": True})()

    def set_learned(self, key: str, value: Any, reason: str, token: str = None) -> Any:
        self._values[key] = value
        return type("Result", (), {"success": True})()

    def propose_modification(self, key: str, value: Any, reason: str, evidence: List) -> Any:
        return type("Result", (), {"accepted": True})()

    def compute_state_hash(self) -> str:
        return hashlib.sha256(str(sorted(self._values.items())).encode()).hexdigest()


class MockEWMManager:
    """Mock EWM manager when real one unavailable."""

    def __init__(self):
        self._state = type("State", (), {
            "session_goal": None,
            "session_start": None,
            "exchange_count": 0,
            "current_expert": "Direct",
            "current_altitude": "30000ft",
            "burnout_level": "GREEN",
            "momentum_phase": "cold_start",
            "last_session": None,
        })()

    def get_state(self):
        return self._state

    def start_session(self, goal: str) -> None:
        self._state.session_goal = goal
        self._state.session_start = datetime.now()
        self._state.exchange_count = 0

    def tick(self) -> None:
        self._state.exchange_count += 1

    def save_handoff(self, data: dict) -> None:
        self._state.last_session = data


class MockStage:
    """Mock cognitive stage when real one unavailable."""

    def __init__(self):
        self._attributes: Dict[str, Any] = {}

    def get_attribute(self, name: str) -> Any:
        return self._attributes.get(name)

    def set_attribute(self, name: str, value: Any) -> None:
        self._attributes[name] = value


# ============================================================================
# Knowledge Graph Integration
# ============================================================================

@dataclass
class KnowledgePrim:
    """
    A knowledge primitive - atomic fact unit.

    Maps to the Knowledge Prims system for O(1) factual retrieval.
    """
    path: str                           # e.g., "/Knowledge/USD/LIVRPS"
    summary: str                        # Brief description
    content: str                        # Full content
    triggers: List[str]                 # Search triggers
    confidence: float = 0.95            # 0.0-1.0
    domain: str = "general"             # Domain category
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches_query(self, query: str) -> bool:
        """Check if query matches any trigger."""
        query_lower = query.lower()
        return any(trigger.lower() in query_lower for trigger in self.triggers)


class KnowledgeGraph:
    """
    Knowledge Graph for O(1) factual retrieval.

    Deterministic retrieval, fixed evaluation order.

    Example:
        >>> kg = KnowledgeGraph()
        >>> prim = kg.get("/Knowledge/USD/LIVRPS")
        >>> if prim and prim.confidence >= 0.85:
        ...     return prim.content
    """

    def __init__(self):
        self._prims: Dict[str, KnowledgePrim] = {}
        self._triggers: Dict[str, str] = {}  # trigger -> path
        self._metrics = KnowledgeMetrics()
        self._load_bootstrap()

    def _load_bootstrap(self) -> None:
        """Load bootstrap knowledge prims."""
        # Core OTTO knowledge
        self._register(KnowledgePrim(
            path="/Knowledge/OTTO/Memory",
            summary="OTTO unified memory interface",
            content="OTTOMemory provides unified access to episodic, procedural, contextual, and identity memory through pheromone trails, cognitive substrate, and EWM.",
            triggers=["otto memory", "unified memory", "ottomemory"],
            confidence=0.95,
            domain="otto",
        ))

        self._register(KnowledgePrim(
            path="/Knowledge/OTTO/Trails",
            summary="Pheromone trail system for procedural memory",
            content="Trails record action outcomes with decay (7-day half-life). Trail strength >= 0.8 enables auto-approval. Deposits are deterministic.",
            triggers=["pheromone", "trails", "auto-approval", "trail strength"],
            confidence=0.95,
            domain="otto",
        ))

        self._register(KnowledgePrim(
            path="/Knowledge/OTTO/LIVRPS",
            summary="USD composition semantics for cognitive state",
            content="LIVRPS (Local > Inherits > Variants > References > Payloads > Specializes) resolves conflicting state. Higher priority wins.",
            triggers=["livrps", "composition", "priority resolution"],
            confidence=0.95,
            domain="otto",
        ))

        self._register(KnowledgePrim(
            path="/Knowledge/He2025/Determinism",
            summary="ThinkingMachines determinism principles",
            content="Fixed seeds, fixed evaluation order, sorted iteration, Kahan summation, COGNITIVE_TILE_SIZE=32. Same inputs -> same outputs.",
            triggers=["he2025", "determinism", "thinkingmachines", "batch invariance"],
            confidence=0.95,
            domain="research",
        ))

    def _register(self, prim: KnowledgePrim) -> None:
        """Register a knowledge prim."""
        self._prims[prim.path] = prim
        for trigger in prim.triggers:
            self._triggers[trigger.lower()] = prim.path

    def get(self, path: str) -> Optional[KnowledgePrim]:
        """Get knowledge prim by exact path. O(1)."""
        start = datetime.now()
        prim = self._prims.get(path)
        self._metrics.record_access(
            hit=prim is not None,
            latency_ms=(datetime.now() - start).total_seconds() * 1000
        )
        return prim

    def query(self, query: str, min_confidence: float = 0.5) -> List[KnowledgePrim]:
        """
        Query knowledge prims by trigger match.

        Results sorted deterministically by path.
        """
        start = datetime.now()
        results = []

        # Check exact trigger match first
        query_lower = query.lower()
        if query_lower in self._triggers:
            path = self._triggers[query_lower]
            prim = self._prims.get(path)
            if prim and prim.confidence >= min_confidence:
                results.append(prim)

        # Then check partial matches (sorted for determinism)
        for path in sorted(self._prims.keys()):
            prim = self._prims[path]
            if prim not in results and prim.matches_query(query):
                if prim.confidence >= min_confidence:
                    results.append(prim)

        self._metrics.record_query(
            hits=len(results),
            latency_ms=(datetime.now() - start).total_seconds() * 1000
        )

        return results

    def has(self, path: str) -> bool:
        """Check if path exists."""
        return path in self._prims

    def list_paths(self, prefix: str = "/Knowledge") -> List[str]:
        """List all paths under prefix (sorted)."""
        return sorted(p for p in self._prims.keys() if p.startswith(prefix))

    def get_metrics(self) -> "KnowledgeMetrics":
        """Get metrics."""
        return self._metrics


# ============================================================================
# Trail Decay Worker
# ============================================================================

class TrailDecayWorker:
    """
    Worker for decaying trail strength over time.

   :
    - Deterministic decay formula
    - Kahan summation for aggregations
    - COGNITIVE_TILE_SIZE=32 for batch processing
    - Fixed half-life (7 days default)
    """

    def __init__(self, half_life_days: float = 7.0):
        self.half_life_days = half_life_days
        self.half_life_hours = half_life_days * 24
        self._last_decay = datetime.now()
        self._metrics = DecayMetrics()

    def compute_decay_factor(self, hours_elapsed: float) -> float:
        """
        Compute decay factor for given time elapsed.

        Formula: factor = 0.5 ** (hours_elapsed / half_life_hours)

        Deterministic - same input always gives same output.
        """
        if hours_elapsed <= 0:
            return 1.0
        return 0.5 ** (hours_elapsed / self.half_life_hours)

    def decay_strength(self, strength: float, hours_elapsed: float) -> float:
        """Decay a single strength value."""
        factor = self.compute_decay_factor(hours_elapsed)
        return max(0.0, min(1.0, strength * factor))

    def decay_trails(self, trail_store, now: Optional[datetime] = None) -> int:
        """
        Decay all trails in the store.

       :
        - Process in batches of COGNITIVE_TILE_SIZE
        - Sort by path for deterministic order
        - Use Kahan summation for aggregate calculations

        Returns:
            Number of trails decayed
        """
        if now is None:
            now = datetime.now()

        try:
            from otto.trails.models import TrailQuery, TrailType

            # Query all trails (sorted by path)
            query = TrailQuery(trail_type=TrailType.PATTERN)
            all_trails = trail_store.query(query)

            # Sort for deterministic processing
            all_trails = sorted(all_trails, key=lambda t: t.path)

            decayed_count = 0
            total_decay = 0.0
            compensation = 0.0  # Kahan summation

            # Process in tiles
            for i in range(0, len(all_trails), COGNITIVE_TILE_SIZE):
                tile = all_trails[i:i + COGNITIVE_TILE_SIZE]

                for trail in tile:
                    if trail.deposited_at is None:
                        continue

                    hours_elapsed = (now - trail.deposited_at).total_seconds() / 3600
                    old_strength = trail.strength
                    new_strength = self.decay_strength(old_strength, hours_elapsed)

                    if abs(new_strength - old_strength) > 0.001:
                        trail.strength = new_strength
                        decayed_count += 1

                        # Kahan summation for total decay
                        decay_amount = old_strength - new_strength
                        y = decay_amount - compensation
                        t = total_decay + y
                        compensation = (t - total_decay) - y
                        total_decay = t

            self._last_decay = now
            self._metrics.record_decay_run(
                trails_decayed=decayed_count,
                total_decay=total_decay,
            )

            return decayed_count

        except ImportError:
            logger.debug("Trail store not available for decay")
            return 0

    def should_decay(self, min_interval_hours: float = 1.0) -> bool:
        """Check if decay should run based on time since last decay."""
        hours_since = (datetime.now() - self._last_decay).total_seconds() / 3600
        return hours_since >= min_interval_hours

    def get_metrics(self) -> "DecayMetrics":
        """Get decay metrics."""
        return self._metrics


# ============================================================================
# Memory Metrics
# ============================================================================

@dataclass
class MemoryMetrics:
    """
    Metrics for memory system instrumentation.

    All counters are deterministic - no sampling.
    """
    # Episode metrics
    episodes_recorded: int = 0
    episodes_queried: int = 0

    # Trail metrics
    trails_deposited: int = 0
    trails_followed: int = 0
    auto_approvals: int = 0
    manual_approvals: int = 0

    # Context metrics
    context_reads: int = 0
    context_updates: int = 0

    # Session metrics
    sessions_started: int = 0
    sessions_ended: int = 0

    # Latency tracking (last 100 samples)
    _latencies: List[float] = field(default_factory=list)

    def record_latency(self, latency_ms: float) -> None:
        """Record access latency."""
        self._latencies.append(latency_ms)
        if len(self._latencies) > 100:
            self._latencies = self._latencies[-100:]

    def avg_latency_ms(self) -> float:
        """Get average latency using Kahan summation."""
        if not self._latencies:
            return 0.0

        total = 0.0
        compensation = 0.0
        for lat in sorted(self._latencies):  # Sorted
            y = lat - compensation
            t = total + y
            compensation = (t - total) - y
            total = t

        return total / len(self._latencies)

    @property
    def auto_approval_rate(self) -> float:
        """Get auto-approval rate."""
        total = self.auto_approvals + self.manual_approvals
        if total == 0:
            return 0.0
        return self.auto_approvals / total

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "episodes_recorded": self.episodes_recorded,
            "episodes_queried": self.episodes_queried,
            "trails_deposited": self.trails_deposited,
            "trails_followed": self.trails_followed,
            "auto_approvals": self.auto_approvals,
            "manual_approvals": self.manual_approvals,
            "auto_approval_rate": self.auto_approval_rate,
            "context_reads": self.context_reads,
            "context_updates": self.context_updates,
            "sessions_started": self.sessions_started,
            "sessions_ended": self.sessions_ended,
            "avg_latency_ms": self.avg_latency_ms(),
        }


@dataclass
class KnowledgeMetrics:
    """Metrics for knowledge graph."""
    cache_hits: int = 0
    cache_misses: int = 0
    queries: int = 0
    total_hits: int = 0
    _latencies: List[float] = field(default_factory=list)

    def record_access(self, hit: bool, latency_ms: float) -> None:
        """Record access."""
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        self._latencies.append(latency_ms)
        if len(self._latencies) > 100:
            self._latencies = self._latencies[-100:]

    def record_query(self, hits: int, latency_ms: float) -> None:
        """Record query."""
        self.queries += 1
        self.total_hits += hits
        self._latencies.append(latency_ms)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    def avg_latency_ms(self) -> float:
        """Average latency."""
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)


@dataclass
class DecayMetrics:
    """Metrics for trail decay."""
    decay_runs: int = 0
    total_trails_decayed: int = 0
    total_decay_amount: float = 0.0
    last_run: Optional[datetime] = None

    def record_decay_run(self, trails_decayed: int, total_decay: float) -> None:
        """Record decay run."""
        self.decay_runs += 1
        self.total_trails_decayed += trails_decayed
        self.total_decay_amount += total_decay
        self.last_run = datetime.now()


# ============================================================================
# Module Initialization
# ============================================================================

# Global singleton (lazy initialization)
_memory: Optional[OTTOMemory] = None


def get_memory() -> OTTOMemory:
    """Get the global memory instance."""
    global _memory
    if _memory is None:
        _memory = OTTOMemory()
    return _memory


__all__ = [
    # Core classes
    "OTTOMemory",
    "Episode",
    "EpisodeQuery",
    "Outcome",
    "Context",
    "ContextDelta",
    "Identity",
    "Relationship",
    "TrailStrength",
    "MemoryTier",
    # Knowledge Graph
    "KnowledgePrim",
    "KnowledgeGraph",
    # Trail Decay
    "TrailDecayWorker",
    # Metrics
    "MemoryMetrics",
    "KnowledgeMetrics",
    "DecayMetrics",
    # Module functions
    "get_memory",
    # Constants
    "AUTO_APPROVE_THRESHOLD",
    "LEARNING_THRESHOLD",
    "COGNITIVE_TILE_SIZE",
    "MEMORY_SEED",
]
