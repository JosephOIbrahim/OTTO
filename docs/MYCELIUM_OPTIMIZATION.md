# Mycelium-Inspired Ottotion Optimization

## Design Decision: No Automatic Self-Improvement

**Self-improvement is INTENTIONALLY excluded** from the current implementation to maintain:

1. **Determinism**: Same signals → Same routing → Same behavior
2. **Auditability**: Weights don't change unexpectedly
3. **User Control**: Calibration is explicit, not automatic
4. **Determinism**: Batch-invariant execution

The Mycelium provides:
- Static weight storage (manually calibrated)
- Weight-based loading strategy calculation
- Persistence for cross-session calibration
- Outcome logging (for analysis only)

---

## The Biological Model (Inspiration, Not Implementation)

Mycelium networks (fungal root systems) inspire the loading strategy:

1. **Nutrient-Seeking**: Load high-weight payloads first
2. **Pathway Strengthening**: NOT implemented (manual calibration only)
3. **Atrophy**: NOT implemented (weights are static)
4. **No Central Control**: Distributed routing via trigger matching
5. **Redundancy**: Safety tier always available

## Applied to Framework Ottotion

### Current Problem

The ottotor loads ALL matching agents and runs them in parallel:

```
Task arrives → Match keywords → Load ALL matching agents → Execute ALL → Wait for ALL
```

**Issues**:
- Slow: Loads everything even when one expert is clearly correct
- Wasteful: All agents execute even when unnecessary

### Mycelium Solution: Weight-Guided Lazy Loading

```
Task arrives → Check Mycelium weights → Load WEIGHTED selection → Execute
              (NO automatic weight updates - determinism preserved)
```

**Key insight**: Pre-calibrated weights guide loading priorities without runtime mutation.

---

## Three-Tier Loading Architecture

### Tier 1: SAFETY (Always Loaded)

Safety-floor experts must ALWAYS be available. Like essential nutrients that mycelium needs regardless of environment:

```python
SAFETY_TIER = {
    "adhd_moe": ["protector", "decomposer", "restorer"]  # Safety floors
}
```

**Cost**: ~50ms (one payload, always loaded at startup)
**Rationale**: Safety floors are non-negotiable. Protector must respond to "help" immediately.

### Tier 2: WEIGHTED (Priority Loading)

Load based on Mycelium weight history. Like active growth zones where the mycelium is currently finding nutrients:

```python
def get_weighted_tier(task: str, weights: Dict[str, float]) -> List[str]:
    """Select payloads based on learned weights."""

    # Sort experts by weight
    sorted_experts = sorted(weights.items(), key=lambda x: -x[1])
    top_weight = sorted_experts[0][1]

    if top_weight > 0.5:
        # FAST PATH: High confidence, load only top expert's payload
        return [expert_to_payload(sorted_experts[0][0])]

    elif top_weight > 0.25:
        # MEDIUM PATH: Load top-3 experts' payloads
        return [expert_to_payload(e[0]) for e in sorted_experts[:3]]

    else:
        # THOROUGH PATH: Novel task, load all matching
        return get_all_matching_payloads(task)
```

**Cost**: 50-200ms depending on confidence
**Rationale**: High-confidence routing should be fast. Low-confidence should be thorough.

### Tier 3: DEFERRED (Lazy Loading)

Low-weight payloads stay dormant until needed. Like mycelium connections that haven't found nutrients - they exist but don't consume resources:

```python
DEFERRED_TIER = {
    # Only loaded if primary expert signals uncertainty or fails
    "nova_oracle": ["thought_leaders"],
    "max_reflection": ["rcxi_engine"],
    "cortex_world": ["world_model"]
}
```

**Cost**: 0ms until needed, then ~50ms per payload
**Rationale**: Don't load reflection engine for simple "implement" tasks.

---

## Weight Update Rules (Hebbian Learning)

### Strengthening (Successful Routing)

When an expert selection leads to task success:

```python
def strengthen_connection(expert: str, outcome: float, activation: float):
    """
    Hebbian update: strengthen connections that fire together successfully.

    w_new = w_old + alpha * (outcome - baseline) * activation

    Where:
        alpha = learning rate (0.1)
        outcome = success metric (0.0-1.0)
        baseline = neutral expectation (0.5)
        activation = how strongly expert was triggered (0.0-1.0)
    """
    delta = ALPHA * (outcome - 0.5) * activation
    weights[expert] = clamp(weights[expert] + delta, FLOOR, CEILING)
    normalize_weights()  # Homeostatic regulation
```

### Atrophy (Unused/Failed Routing)

When an expert is NOT selected or fails:

```python
def attenuate_connection(expert: str, decay_rate: float = 0.95):
    """
    Temporal decay: unused connections weaken over time.

    w_new = w_old * decay_rate

    With floor preservation for safety experts.
    """
    floor = SAFETY_FLOORS.get(expert, 0.0)
    weights[expert] = max(weights[expert] * decay_rate, floor)
    normalize_weights()
```

### Homeostatic Regulation

Prevent winner-take-all (one expert dominating):

```python
def normalize_weights():
    """
    Homeostatic normalization: weights sum to 1.0
    This prevents runaway specialization.
    """
    total = sum(weights.values())
    for expert in weights:
        weights[expert] /= total
```

---

## Performance Impact Analysis

| Scenario | Old (Load All) | New (Weighted) | Speedup |
|----------|---------------|----------------|---------|
| Repeated task type | ~400ms | ~100ms (fast path) | 4x |
| Moderate diversity | ~400ms | ~200ms (weighted) | 2x |
| Novel/complex task | ~400ms | ~400ms (thorough) | 1x |
| Average (mixed) | ~400ms | ~180ms | 2.2x |

### Fast Path Conditions

The fast path (100ms) triggers when:
1. Top expert weight > 0.5 (high confidence)
2. Task matches known pattern
3. No safety signals detected

### Safety Override

Regardless of weights, safety signals ALWAYS trigger full safety tier:
- "help", "stuck", "frustrated" → Load adhd_moe immediately
- "error", "broken" → Load full diagnostic chain

---

## Implementation Architecture

### 1. WeightedPayloadManager

```python
class WeightedPayloadManager:
    """Mycelium-inspired payload loading with resource optimization."""

    def __init__(self, mycelium: Mycelium):
        self.mycelium = mycelium
        self._loaded: Dict[str, Any] = {}
        self._load_safety_tier()  # Always available

    def _load_safety_tier(self):
        """Load safety-floor payloads at initialization."""
        self._loaded["adhd_moe"] = self._import_payload("adhd_moe")

    def get_loading_strategy(self, task: str) -> LoadingStrategy:
        """Determine which payloads to load based on Mycelium weights."""

        # Check for safety signals first (override weights)
        if self._has_safety_signals(task):
            return LoadingStrategy(
                tier="safety",
                payloads=["adhd_moe"],
                reason="Safety signals detected"
            )

        weights = self.mycelium.get_weights()
        sorted_experts = sorted(weights.items(), key=lambda x: -x[1])
        top_weight = sorted_experts[0][1]

        if top_weight > 0.5:
            return LoadingStrategy(
                tier="fast",
                payloads=[self._expert_to_payload(sorted_experts[0][0])],
                reason=f"High confidence ({top_weight:.2f}) in {sorted_experts[0][0]}"
            )
        elif top_weight > 0.25:
            return LoadingStrategy(
                tier="weighted",
                payloads=[self._expert_to_payload(e[0]) for e in sorted_experts[:3]],
                reason="Moderate confidence, loading top-3"
            )
        else:
            return LoadingStrategy(
                tier="thorough",
                payloads=self._get_all_matching(task),
                reason="Low confidence, comprehensive analysis"
            )

    def load_payloads(self, strategy: LoadingStrategy) -> Dict[str, Any]:
        """Load payloads according to strategy."""
        for payload_name in strategy.payloads:
            if payload_name not in self._loaded:
                self._loaded[payload_name] = self._import_payload(payload_name)
        return {p: self._loaded[p] for p in strategy.payloads}
```

### 2. Routing Cache (Optional Speedup)

For truly fast ottotion, cache recent task→expert mappings:

```python
class RoutingCache:
    """Cache successful routes for similar tasks."""

    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, Tuple[str, float]] = {}
        self._ttl = ttl_seconds

    def get_cached_route(self, task_signature: str) -> Optional[str]:
        """Return cached expert if task signature seen recently."""
        if task_signature in self._cache:
            expert, timestamp = self._cache[task_signature]
            if time.time() - timestamp < self._ttl:
                return expert
        return None

    def cache_route(self, task_signature: str, expert: str):
        """Cache successful route for future similar tasks."""
        self._cache[task_signature] = (expert, time.time())
```

### 3. Task Signature Extraction

Normalize tasks to signatures for cache matching:

```python
def extract_task_signature(task: str) -> str:
    """Extract stable signature for task caching.

    Normalizes task to key features:
    - Detected triggers
    - Domain keywords
    - Task type indicators
    """
    task_lower = task.lower()

    # Extract trigger matches
    triggers = []
    for expert, config in EXPERTS.items():
        if any(t in task_lower for t in config["triggers"]):
            triggers.append(expert)

    # Sort for stability
    return f"experts:{','.join(sorted(triggers))}"
```

---

## Mycelium State Persistence

For cross-session learning, persist Mycelium weights:

```python
class Mycelium:
    """Extended with persistence for cross-session learning."""

    PERSISTENCE_PATH = Path.home() / ".framework-ottotor" / "mycelium_weights.json"

    def save_weights(self):
        """Persist weights to REFERENCES layer (cross-session)."""
        state = {
            "weights": self.expert_weights,
            "outcomes_count": len(self.outcomes),
            "last_updated": time.time()
        }
        self.PERSISTENCE_PATH.write_text(json.dumps(state, indent=2))

    def load_weights(self):
        """Load weights from REFERENCES layer."""
        if self.PERSISTENCE_PATH.exists():
            state = json.loads(self.PERSISTENCE_PATH.read_text())
            self.expert_weights = state.get("weights", self.expert_weights)
```

---

## Integration with V5 MoE Router

The WeightedPayloadManager integrates with the existing V5 MoE Router:

```python
class MoERouterAgent(BaseAgent):
    """V5 MoE Router with Mycelium weight integration."""

    def __init__(self, mycelium: Mycelium = None):
        super().__init__(...)
        self.mycelium = mycelium or Mycelium()

    def _weight(self, activation: Dict[str, float], context: Dict[str, Any]) -> Dict[str, float]:
        """Phase 2: Apply Mycelium-learned weights."""
        # Get weights from Mycelium (learned from history)
        weights = self.mycelium.get_weights()

        weighted = {}
        for expert in self.EXPERTS:
            weighted[expert] = activation.get(expert, 0.0) * weights.get(expert, 1/7)

        return weighted
```

---

## Summary: Mycelium Growth Patterns

| Pattern | Biological | Framework Application |
|---------|------------|----------------------|
| **Nutrient-seeking** | Grow toward food | Load high-weight payloads first |
| **Strengthening** | Thicken successful paths | Hebbian weight increase on success |
| **Atrophy** | Prune unused connections | Temporal decay on unused experts |
| **Homeostasis** | Balance nutrient flow | Normalize weights to sum=1.0 |
| **Redundancy** | Multiple paths | Safety tier always loaded |
| **Local rules** | No central brain | Each expert updates independently |

---

## Next Steps

1. **Implement WeightedPayloadManager** in framework_ottotor.py
2. **Add Hebbian update to Mycelium** (currently stubbed)
3. **Add weight persistence** for cross-session learning
4. **Add RoutingCache** for repeated task patterns
5. **Benchmark** against current implementation

---

*Generated: 2026-01-21*
*Document: Mycelium-Inspired Ottotion Optimization*
