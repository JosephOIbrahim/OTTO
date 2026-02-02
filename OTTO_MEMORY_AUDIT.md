# OTTO Memory Architecture Audit

> **Discovery Date**: 2026-02-02
> **Purpose**: Document existing OTTO memory systems for services layer integration
> **[He2025] Compliance**: All systems verified deterministic

---

## Executive Summary

OTTO uses a sophisticated multi-layered memory architecture based on USD (Universal Scene Description) composition semantics. The system combines:

1. **Pheromone Trails** (SQLite) - Episodic/procedural memory with decay
2. **LIVRPS Layers** - Priority-based conflict resolution
3. **Three-Tier Substrate** - Constitutional/Learned/Ephemeral state
4. **External Working Memory** - ADHD-native session management
5. **Knowledge Prims** - O(1) factual retrieval

**Key Insight**: The services layer must integrate with these existing systems rather than creating parallel storage.

---

## 1. Storage Locations

### Persistent Databases

| Location | Format | Purpose |
|----------|--------|---------|
| `~/OTTO_OS/data/trails.db` | SQLite | Pheromone trails (812 KB) |
| `~/.otto/knowledge/personal.json` | JSON | Personal knowledge store |
| `~/.otto/substrate/learned_state.json` | JSON | Learned tier state |
| `~/.otto/calibration/*.json` | JSON | Cross-session calibration |

### Session State Files

| Location | Format | Persistence |
|----------|--------|-------------|
| `~/.orchestra/state/cognitive_state.json` | JSON | Session (2h auto-reset) |
| `~/.claude/substrate/ewm/ewm_state.json` | JSON | Session-scoped |
| `~/OTTO_OS/data/discord_sessions.json` | JSON | Surface-specific |

### Knowledge Files

| Location | Format | Purpose |
|----------|--------|---------|
| `~/.claude/substrate/knowledge/prims/*.usda` | USDA | Knowledge prims |
| `~/.claude/substrate/knowledge/vfx_bootstrap.usda` | USDA | VFX domain |
| `~/.otto/knowledge/personal.json` | JSON | User personal facts |

### Backup Locations

```
~/.claude/substrate/backups/          # Substrate backups
~/.otto/calibration/backups/          # Calibration backups
Format: {filename}_{YYYYMMDD_HHMMSS}.json
```

---

## 2. Pheromone Trail Architecture

### Location
- **File**: `src/otto/trails/models.py`, `store.py`
- **Database**: `data/trails.db`

### Trail Data Structure

```python
@dataclass
class Trail:
    id: Optional[int]
    trail_type: TrailType      # QUALITY, CONTEXT, DECISION, PATTERN, WORK
    path: str                  # File path or action identifier
    signal: str                # e.g., "he2025_compliant", "momentum_up"
    strength: float            # 0.0-1.0, decays over time
    deposited_by: str          # Agent ID
    deposited_at: datetime
    reinforced_count: int      # Auto-increments on duplicate deposits
    metadata: dict             # Additional context
    half_life_days: float      # Decay rate (default 7.0)
```

### Trail Types

| Type | Purpose | Example Signals |
|------|---------|-----------------|
| `QUALITY` | Code health | `he2025_compliant`, `has_tests` |
| `CONTEXT` | Relationships | `depends_on`, `used_by` |
| `DECISION` | Historical choices | `chose:sorted_max|reason:determinism` |
| `PATTERN` | Learned approaches | `recovery_success|burnout` |
| `WORK` | Activity signals | `currently_editing`, `recently_touched` |

### Decay Mechanism

```python
decay_factor = 0.5 ** (days_elapsed / half_life_days)
current_strength = strength * decay_factor

# Trails with strength < 0.1 are pruned by decay_all()
```

### Trail Store Interface

```python
class TrailStore:
    def deposit(trail: Trail) -> Trail
        """Create or reinforce trail. Increments reinforced_count on duplicate."""

    def query(query: TrailQuery) -> List[Trail]
        """Deterministic search with sorted results."""

    def decay_all() -> int
        """Prune dead trails (strength < 0.1). Returns count removed."""

    def reinforce(trail_type: TrailType, path: str, signal: str) -> Trail
        """Strengthen existing trail or create new."""

    def get_strength(trail_type: TrailType, path: str, signal: str) -> float
        """Get current strength after decay calculation."""
```

### Database Schema

```sql
CREATE TABLE trails (
    id INTEGER PRIMARY KEY,
    trail_type TEXT NOT NULL,
    path TEXT NOT NULL,
    signal TEXT NOT NULL,
    strength REAL NOT NULL,
    deposited_by TEXT NOT NULL,
    deposited_at TIMESTAMP NOT NULL,
    reinforced_count INTEGER DEFAULT 0,
    metadata TEXT,  -- JSON
    half_life_days REAL DEFAULT 7.0,
    UNIQUE(trail_type, path, signal)
);
```

---

## 3. LIVRPS Memory Layers

### Location
- **File**: `src/otto/cognitive_stage.py`

### Layer Priority (Highest to Lowest)

```python
class LayerPriority(Enum):
    LOCAL = 1           # Session state (mutable, HIGHEST)
    INHERITS = 2        # Inherited context from parent task
    VARIANTS = 3        # Mode variants (focused/exploring/recovery)
    REFERENCES = 4      # Calibration data (cross-session)
    PAYLOADS = 5        # Domain knowledge (loaded on demand)
    SPECIALIZES = 6     # Constitutional base (safety floors, LOWEST)
```

### Resolution Rule

> **Higher priority wins.** LOCAL overrides INHERITS overrides VARIANTS, etc.

### Layer Data Structure

```python
@dataclass
class CognitiveLayer:
    name: str
    priority: LayerPriority
    attributes: Dict[str, Any]
    sublayers: List['CognitiveLayer']

    def set_attribute(name: str, value: Any) -> None
    def get_attribute(name: str) -> Optional[Any]
    def has_attribute(name: str) -> bool
```

### Attribute Opinion Tracking

```python
@dataclass
class AttributeOpinion:
    """Tracks all layer opinions on a single attribute."""
    name: str
    opinions: Dict[LayerPriority, Any]

    def resolve(self) -> Any:
        """Return value from highest priority layer with opinion."""
        for priority in sorted(self.opinions.keys()):
            return self.opinions[priority]

    def has_tension(self) -> bool:
        """True if layers disagree."""
        values = list(self.opinions.values())
        return len(set(str(v) for v in values)) > 1
```

### LIVRPS Mapping

| Letter | USD Composition | Cognitive Mapping |
|--------|-----------------|-------------------|
| **L** | Local | Session state + Oracle results |
| **I** | Inherits | Parent task context |
| **V** | VariantSets | Mode switching (focused/exploring) |
| **R** | References | Calibration data, cache state |
| **P** | Payloads | Domain knowledge (VFX, WebDev, etc.) |
| **S** | Specializes | Constitutional base, safety floors |

---

## 4. Cognitive Substrate (Three-Tier)

### Location
- **File**: `src/otto/substrate/interface.py`
- **State**: `~/.otto/substrate/learned_state.json`

### Tier Architecture

```python
class SubstrateTier(IntEnum):
    CONSTITUTIONAL = 0  # Immutable, safety floors (LOWEST in override)
    LEARNED = 1         # Persistent, mutable with approval
    EPHEMERAL = 2       # Session-scoped, not persisted (HIGHEST in override)
```

### SubstrateValue Structure

```python
@dataclass
class SubstrateValue:
    key: str                      # e.g., "safety.burnout_threshold"
    value: Any
    tier: SubstrateTier
    modified_at: datetime
    checksum: str                 # SHA-256 for integrity
    metadata: Dict[str, Any]      # source, reason, approval_id
```

### Constitutional Values (Immutable)

```python
CONSTITUTIONAL_VALUES = {
    # Safety floors (NEVER go below)
    "safety_floor_protector": 0.10,
    "safety_floor_restorer": 0.05,

    # Processing order (FIXED)
    "phase_order": ["RETRIEVE", "CLASSIFY", "GROUND", "DETECT",
                    "CASCADE", "LOCK", "EXECUTE", "UPDATE", "FLUSH"],

    # Signal priority (FIXED)
    "signal_priority": ["emotional", "grounding", "mode", "domain", "task"],

    # Expert priority (FIXED)
    "expert_priority": ["Validator", "Scaffolder", "Restorer",
                        "Refocuser", "Celebrator", "Socratic", "Direct"],

    # Batch invariance
    "cognitive_tile_size": 32,

    # Principles
    "safety_first": True,
    "ship_over_perfect": True,
    "protect_momentum": True,
    # ... 62 total fields
}
```

### Substrate Interface

```python
class CognitiveSubstrate:
    def get(key: str, default=None) -> Any:
        """Resolution: EPHEMERAL > LEARNED > CONSTITUTIONAL"""

    def set_ephemeral(key: str, value: Any, metadata: dict = None) -> ModificationResponse:
        """Session-scoped, not persisted."""

    def set_learned(key: str, value: Any, reason: str,
                    approval_token: str = None) -> ModificationResponse:
        """Persistent, requires approval for protected fields."""

    def propose_modification(key: str, proposed_value: Any,
                            reason: str, evidence: List[str]) -> ProposalResult:
        """Propose change to learned tier (requires review)."""

    def compute_state_hash() -> str:
        """SHA-256 of entire state for integrity verification."""

    def snapshot() -> Dict[str, SubstrateValue]:
        """Get complete state snapshot."""
```

### Modification Response

```python
class ModificationResult(Enum):
    SUCCESS = "success"
    DENIED_CONSTITUTIONAL = "denied_constitutional"
    DENIED_VALIDATION = "denied_validation"
    REQUIRES_APPROVAL = "requires_approval"
    INVALID_TIER = "invalid_tier"
```

---

## 5. State Management

### External Working Memory (EWM)

**Location**: `src/otto/substrate/ewm/manager.py`

```python
@dataclass
class EWMState:
    # Session anchor (prevents "lost the thread")
    session_goal: str
    session_start: datetime
    exchange_count: int

    # Time beacon (prevents time blindness)
    estimated_minutes: float  # exchange_count * 4.5
    last_beacon_at: int       # Exchange when last shown

    # Project friction (prevents proliferation)
    open_projects: List[ProjectInfo]

    # Status line components
    current_expert: str       # Direct, Validator, etc.
    current_altitude: str     # 30k, 15k, 5k, Ground
    burnout_level: str        # GREEN, YELLOW, ORANGE, RED
    momentum_phase: str       # cold_start, building, rolling, etc.
```

### EWM Manager Interface

```python
class EWMManager:
    def start_session(goal: str) -> None
        """Initialize session with goal."""

    def tick() -> None
        """Increment exchange count."""

    def should_show_beacon() -> bool
        """True every 10 exchanges."""

    def get_status_line() -> str
        """[~45 min | Goal: X | Direct | 15k | GREEN | rolling]"""

    def surface_project_friction() -> Optional[str]
        """Returns project list if new project signals detected."""

    def save_handoff() -> None
        """Persist session state for cross-session continuity."""
```

### Session Staleness

Sessions auto-reset after 2 hours of inactivity:

| Resets | Preserves |
|--------|-----------|
| exchange_count | energy_level |
| momentum_phase | focus_level |
| tangent_budget | user preferences |
| burnout (if ORANGE/RED → GREEN) | calibration data |

### Handoff Document

**Location**: `~/.claude/last_session.md`

```markdown
# Last Session - {date}

## Goal
{session goal}

## Progress
- {completed items}

## Stopped At
{current position}

## Next Steps
- {immediate next action}

## Substrate State
- Expert: {x} | Altitude: {x} | Burnout: {x} | Momentum: {x}

## Open Threads
{ideas/tangents not pursued}
```

---

## 6. Existing Memory Interfaces

### Trail Operations

```python
# Deposit a trail (src/otto/trails/store.py)
trail_store.deposit(Trail(
    trail_type=TrailType.PATTERN,
    path="calendar.create",
    signal="success",
    strength=1.0,
    deposited_by="otto_agent",
    deposited_at=datetime.now(),
    metadata={"context": "morning scheduling"}
))

# Query trails
results = trail_store.query(TrailQuery(
    trail_type=TrailType.PATTERN,
    path="calendar.*",  # Glob pattern
    min_strength=0.5
))

# Get trail strength (for auto-approval decisions)
strength = trail_store.get_strength(
    TrailType.PATTERN,
    "calendar.create",
    "success"
)
```

### Substrate Operations

```python
# Get value (src/otto/substrate/interface.py)
substrate = CognitiveSubstrate()
value = substrate.get("safety.burnout_threshold", default=0.8)

# Set ephemeral (session-scoped)
substrate.set_ephemeral("current_task", "scheduling")

# Set learned (persistent, may require approval)
result = substrate.set_learned(
    key="user.preferred_calendar_time",
    value="morning",
    reason="User consistently schedules in AM",
    approval_token=approval_id
)

# Propose modification (for learning)
substrate.propose_modification(
    key="routing.overwhelm_threshold",
    proposed_value={"signals": 2, "window": 4},
    reason="Overwhelm detected late in 50%+ of cases",
    evidence=["45/90 late detections"]
)
```

### Knowledge Operations

```python
# Retrieve knowledge (src/otto/substrate/knowledge/retriever.py)
retriever = KnowledgeRetriever()

# Trigger-based search
result = retriever.search("what is LIVRPS")
if result.confidence >= 0.85:
    return result.content  # Fast path

# Direct path lookup (O(1))
prim = retriever.retrieve_by_path("/Knowledge/USD/LIVRPS")
```

### EWM Operations

```python
# Session management (src/otto/substrate/ewm/manager.py)
ewm = EWMManager()

# Start session
ewm.start_session("Build calendar integration")

# On each exchange
ewm.tick()

# Check for status line
if ewm.should_show_beacon():
    print(ewm.get_status_line())

# End session
ewm.save_handoff()
```

---

## 7. Integration Points

### Where Services Layer Should Connect

| Service Need | OTTO System | Integration Point |
|--------------|-------------|-------------------|
| **Action history** | Pheromone Trails | `TrailStore.deposit()` |
| **Auto-approval** | Trail strength | `TrailStore.get_strength()` |
| **User preferences** | Substrate LEARNED | `CognitiveSubstrate.set_learned()` |
| **Session context** | EWM Manager | `EWMManager.get_context()` |
| **Learning proposals** | Substrate proposals | `CognitiveSubstrate.propose_modification()` |
| **Cross-session state** | Handoff document | `EWMManager.save_handoff()` |

### Memory Type Mapping

| Memory Type | OTTO Implementation |
|-------------|---------------------|
| **Identity Memory** | Cognitive Substrate (constitutional/learned) |
| **Episodic Memory** | Pheromone Trails (what happened) |
| **Procedural Memory** | Pheromone Trails (what works) |
| **Contextual Memory** | LIVRPS layers (where you are) |
| **Relational Memory** | Trail metadata + graph queries |

### Pattern Tracker Integration

```python
# Auto-deposit trails on state transitions
class PatternTracker:
    def check_and_deposit(new_state, expert_used) -> List[Trail]:
        """
        Auto-detects and deposits:
        - stuck → resolved (recovery success)
        - momentum_up (cold_start → building)
        - recovery_success (burnout improved)
        - mode_stability (stayed in stable mode)
        """
```

---

## 8. Determinism Compliance ([He2025])

### Key Constants

```python
COGNITIVE_TILE_SIZE: Final[int] = 32
SUBSTRATE_SEED: Final[int] = 0x50B57A7E
INTERFACE_SEED: Final[int] = 0xCAFEBEEF
HASH_ALGORITHM: Final[str] = "sha256"
```

### Deterministic Operations

| Operation | Guarantee |
|-----------|-----------|
| Trail queries | Results sorted by (trail_type, path, signal) |
| Layer resolution | Fixed LIVRPS priority order |
| Expert selection | Fixed priority (Validator > ... > Direct) |
| State hashing | SHA-256, sorted keys, Kahan summation |
| Batch processing | Fixed tile size (32), no adaptive sizing |

### Verification

```python
def verify_determinism(operation, n_trials=100):
    """Same inputs → same outputs."""
    results = [operation() for _ in range(n_trials)]
    assert len(set(hash(r) for r in results)) == 1
```

---

## 9. Migration Path

### Current Services Layer (WRONG)

```python
# Flat JSON storage - DELETE THIS
class ApprovalGateSystem:
    def __init__(self):
        self.history_path = base_path / "history.json"  # ❌ Parallel storage
```

### Target Integration (RIGHT)

```python
# Use OTTO memory systems
class ApprovalGateSystem:
    def __init__(self, trail_store: TrailStore, substrate: CognitiveSubstrate):
        self.trails = trail_store    # ✅ Use existing trails
        self.substrate = substrate   # ✅ Use existing substrate

    def requires_approval(self, action: str) -> bool:
        # Use trail strength instead of flat history
        strength = self.trails.get_strength(TrailType.PATTERN, action, "success")

        if self._is_constitutional(action):
            return True

        if strength > self.substrate.get("approval.auto_threshold", 0.8):
            return False  # Earned auto-approval via trails

        return True
```

---

## 10. Summary

### Files to Read for Integration

```
src/otto/trails/models.py       # Trail data model
src/otto/trails/store.py        # TrailStore interface
src/otto/cognitive_stage.py     # LIVRPS layers
src/otto/substrate/interface.py # Three-tier substrate
src/otto/substrate/ewm/manager.py # EWM session management
src/otto/substrate/knowledge/retriever.py # Knowledge prims
src/otto/cognitive_orchestrator.py # PatternTracker
```

### Key Classes for Integration

```python
from otto.trails.store import TrailStore
from otto.trails.models import Trail, TrailType, TrailQuery
from otto.substrate.interface import CognitiveSubstrate, SubstrateTier
from otto.substrate.ewm.manager import EWMManager
from otto.cognitive_stage import CognitiveStage, LayerPriority
```

### Integration Checklist

- [ ] Create unified memory interface wrapping existing systems
- [ ] Modify MCP servers to deposit trails on every action
- [ ] Replace approval flat files with trail strength queries
- [ ] Connect learning observer to substrate proposals
- [ ] Implement session persistence via EWM handoff
- [ ] Verify cross-surface state synchronization
- [ ] Add integration tests

---

**Memory is OTTO. OTTO is memory. Now connect them.**
