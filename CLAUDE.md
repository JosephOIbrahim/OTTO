# OTTO OS v3.0 — CLAUDE.md

## Claude Code Instruction Set (Opus 4.6 + Claude Agent SDK)

**Version:** 3.0.0
**Date:** February 10, 2026
**Author:** Joe Ibrahim — Creative Director / Systems Architect
**Builder:** Claude Code (Opus 4.6) via Claude Agent SDK
**Model:** `claude-opus-4-6` — 1M context, agent teams, compaction, adaptive effort

---

## READ THIS FIRST — EVERY SESSION

This is the single source of truth for building OTTO OS v3.0. Read this document completely before starting any implementation work. No exceptions.

**Two targets, one cognitive architecture:**

| Target | Platform | Language | Dev Machine |
|--------|----------|----------|-------------|
| `otto-ios` | iPhone/iPad | Swift/SwiftUI | Mac Studio (macOS 26.3 + Xcode 26.3 + Claude Agent SDK) |
| `otto-cli` | Mac/Windows/Linux | Python 3.11+ | Windows Threadripper (WSL2) or Mac (native terminal) |

The cognitive engine is identical across platforms. The surface layer differs.

---

## WHAT OTTO IS

OTTO OS is a neurodivergent-native cognitive operating system. It is a productivity companion specifically designed for people whose brains work differently.

**Core philosophy:** Variable attention is a hardware feature, not a bug.

**Design principle:** Stealth accommodation. No clinical language. No guilt. No shame. Dignity-first computing.

**One-line summary:** The first operating system where neurodivergence is the native architecture — neurotypical users simply experience it as "finally, a computer that gets me."

---

# PART I: CONSTITUTIONAL LAYER (IMMUTABLE)

---

## 1. Constitutional Principles

**FROZEN. IMMUTABLE. NON-NEGOTIABLE. OVERRIDE EVERYTHING ELSE.**

```python
@dataclass(frozen=True)
class ConstitutionalPrinciples:
    safety_first: str = "User emotional and cognitive safety is paramount"
    ship_over_perfect: str = "Working code beats perfect plans"
    protect_momentum: str = "Never break flow state without consent"
    write_it_down: str = "If it's not persisted, it didn't happen"
    rest_is_productive: str = "Recovery is not laziness"
    one_at_a_time: str = "Focus is a finite resource"
    user_knows_best: str = "User sovereignty over all defaults"
    no_clinical_language: str = "Never use diagnostic labels in user-facing text"
    privacy_is_law: str = "Raw data never leaves the device"
    determinism_required: str = "Same input + same state = same output"
```

**Implementation requirement:** Code review ALL user-facing strings. Zero clinical language. Zero diagnostic framing.

```
NEVER: "Your ADHD...", "executive dysfunction", "neurodivergent deficit"
ALWAYS: "you seem tired", "that's a lot to hold", "good time for a break?"

NEVER: "just", "simply", "easy" (minimizes difficulty)
ALWAYS: Be honest about complexity

NEVER: guilt, shame, "you should have..."
ALWAYS: "Permission granted: rest is productive"
```

---

## 2. Safety Floors

```python
@dataclass(frozen=True)
class SafetyFloors:
    protector: float = 0.10   # Always ≥10% activation
    decomposer: float = 0.05  # Always ≥5% activation
    restorer: float = 0.05    # Always ≥5% activation
    # Sum = 0.20, leaving 0.80 for dynamic allocation
```

**Safety floors are constitutional. They cannot be lowered at runtime. They are checked BEFORE expert selection in the BOUND phase. This is not negotiable.**

---

## 3. Patent-Protected Innovations (5 Claims)

1. **LIVRPS** — Layered memory compositor with deterministic resolution order
2. **Safety Floors** — Immutable minimum expert activation (constitutional)
3. **Ambient Signal Fusion** — Raw data → categorical abstraction privacy boundary
4. **Pheromone Trails** — Distributed learning through persistent signal deposit/follow/decay
5. **Stealth Accommodation** — Neurodivergent-native design without clinical labeling

---

# PART II: COGNITIVE ARCHITECTURE

---

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    OTTO OS v3.0 COGNITIVE ENGINE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AMBIENT SIGNALS ──▶ LIVRPS COMPOSITOR ──▶ PRISM DETECTION       │
│                                                │                 │
│                                                ▼                 │
│                                          NEXUS ROUTER            │
│                                     (5-phase pipeline)           │
│                                                │                 │
│                                                ▼                 │
│                                        7 EXPERT MODES            │
│                                                │                 │
│                                                ▼                 │
│  LOCAL MEMORY ◀──────────────────── PHEROMONE TRAILS             │
│  (encrypted SQLite)                 (deposit/follow/decay)       │
│                                                                  │
│                          HTTPS (TLS 1.3)                         │
│                    Sends: message + routing context               │
│                    Never: raw health, identity, keys              │
│                                                                  │
│                        OPUS 4.6 SERVER                            │
│                   (effort controls, compaction,                   │
│                    structured outputs, 1M context)               │
└─────────────────────────────────────────────────────────────────┘
```

### Privacy Boundary (Patent Claim #3)

```
RAW (never leaves device)           →  CATEGORICAL (safe to process)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
47 open browser tabs                →  overwhelm: HIGH
stackoverflow.com visited 12x      →  stuck_signal: TECHNICAL
Typing speed: 45 → 28 WPM          →  energy: DECLINING
Calendar: "1:1 with Sarah 3pm"     →  commitment: MEETING_SOON
```

---

## 5. LIVRPS Cognitive Substrate

Inspired by Pixar USD composition arcs. Layers resolve in deterministic priority order (lowest → highest):

```
L — Learned      (accumulated from interactions, lowest priority)
I — Inherited    (from system defaults)
V — Volatile     (session-only, ephemeral)
R — Reactive     (real-time signal response)
P — Protective   (safety overrides)
S — Sovereign    (user explicit choice, HIGHEST priority)
```

**Resolution rule:** Highest active layer with that property wins. Always. This is deterministic.

### Python Implementation

```python
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime

class LayerName(IntEnum):
    LEARNED = 0
    INHERITED = 1
    VOLATILE = 2
    REACTIVE = 3
    PROTECTIVE = 4
    SOVEREIGN = 5  # Highest priority

@dataclass
class CognitiveProperty:
    name: str
    value: Any
    source_layer: LayerName
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class Layer:
    name: LayerName
    properties: dict[str, Any] = field(default_factory=dict)
    active: bool = True

class LIVRPSCompositor:
    def __init__(self):
        self.layers = {name: Layer(name=name) for name in LayerName}

    def resolve(self, property_name: str) -> Optional[CognitiveProperty]:
        """Resolve a property by checking layers highest-priority first."""
        for layer_name in sorted(LayerName, reverse=True):
            layer = self.layers[layer_name]
            if layer.active and property_name in layer.properties:
                return CognitiveProperty(
                    name=property_name,
                    value=layer.properties[property_name],
                    source_layer=layer_name,
                )
        return None

    def resolve_all(self) -> dict[str, CognitiveProperty]:
        """Resolve all properties. Deterministic: sorted iteration."""
        all_props = set()
        for layer_name in sorted(LayerName):
            layer = self.layers[layer_name]
            if layer.active:
                all_props.update(layer.properties.keys())
        return {
            prop: self.resolve(prop)
            for prop in sorted(all_props)
            if self.resolve(prop) is not None
        }
```

### Swift Implementation (iOS)

```swift
enum LayerName: Int, CaseIterable, Comparable, Codable {
    case learned = 0
    case inherited = 1
    case volatile = 2
    case reactive = 3
    case protective = 4
    case sovereign = 5

    static func < (lhs: LayerName, rhs: LayerName) -> Bool {
        lhs.rawValue < rhs.rawValue
    }
}

struct CognitiveProperty: Codable {
    let name: String
    let value: AnyCodable
    let sourceLayer: LayerName
    let timestamp: Date
}

struct Layer {
    let name: LayerName
    var properties: [String: AnyCodable] = [:]
    var active: Bool = true
}

final class LIVRPSCompositor {
    private var layers: [LayerName: Layer]

    init() {
        layers = Dictionary(uniqueKeysWithValues:
            LayerName.allCases.map { ($0, Layer(name: $0)) }
        )
    }

    func resolve(_ propertyName: String) -> CognitiveProperty? {
        for layerName in LayerName.allCases.sorted().reversed() {
            guard let layer = layers[layerName],
                  layer.active,
                  let value = layer.properties[propertyName] else { continue }
            return CognitiveProperty(
                name: propertyName,
                value: value,
                sourceLayer: layerName,
                timestamp: Date()
            )
        }
        return nil
    }
}
```

---

## 6. PRISM Signal Detection

Classifies user input into cognitive signals. Two-stage pipeline:

**Stage 1: Local (on device)** — Fast (<50ms), rule-based, no LLM required
**Stage 2: Server (Opus 4.6)** — Confirms local detection, handles nuance

### Signal Types (Universal)

```python
from enum import Enum, auto

class CognitiveSignal(Enum):
    # Primary cognitive states
    FRUSTRATED = auto()
    OVERWHELMED = auto()
    DEPLETED = auto()
    STUCK = auto()
    EXPLORING = auto()
    FOCUSED = auto()
    HYPERFOCUS = auto()
    CRASHED = auto()

    # Action signals (commitment tracking)
    COMMITMENT_OUTBOUND = auto()    # "I'll send that by Friday"
    COMMITMENT_INBOUND = auto()     # "Can you get me X by Tuesday?"
    MEETING_REQUEST = auto()        # "We should meet about this"
    TASK_IMPLIED = auto()           # "I need to update the docs"
    FOLLOW_UP_NEEDED = auto()       # "Let me get back to you"
    DECISION_MADE = auto()          # "Let's go with option B"

    # Ambient signals
    LOW_ENERGY = auto()
    HIGH_ENERGY = auto()
    CONTEXT_SWITCH = auto()
    EXTENDED_MEETINGS = auto()
    CRASH_ZONE_APPROACHING = auto()
```

### Pattern Matching (Local Detection)

```python
@dataclass
class DetectionPattern:
    regex: str
    signal_type: CognitiveSignal
    base_confidence: float

# MUST be sorted by signal_type for determinism (inspired by [He2025])
PATTERNS: list[DetectionPattern] = sorted([
    DetectionPattern(r"(?i)(too much|overwhelm|can't handle)", CognitiveSignal.OVERWHELMED, 0.8),
    DetectionPattern(r"(?i)(stuck|blocked|don't know)", CognitiveSignal.STUCK, 0.7),
    DetectionPattern(r"(?i)(tired|exhausted|done)", CognitiveSignal.DEPLETED, 0.75),
    DetectionPattern(r"[A-Z]{3,}", CognitiveSignal.FRUSTRATED, 0.6),
    DetectionPattern(r"(?i)(what if|I wonder|could we)", CognitiveSignal.EXPLORING, 0.65),
    DetectionPattern(r"(?i)(I'll|I will|I can).*by\s+\w+day", CognitiveSignal.COMMITMENT_OUTBOUND, 0.7),
    DetectionPattern(r"(?i)(can you|could you|please).*by\s+\w+day", CognitiveSignal.COMMITMENT_INBOUND, 0.65),
], key=lambda p: p.signal_type.name)

@dataclass
class Signal:
    type: CognitiveSignal
    confidence: float
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

class PRISMDetector:
    def detect(self, text: str) -> list[Signal]:
        """Detect all signals. Returns sorted by confidence descending."""
        signals = []
        for pattern in PATTERNS:
            if re.search(pattern.regex, text):
                signals.append(Signal(
                    type=pattern.signal_type,
                    confidence=pattern.base_confidence,
                    source="local_pattern",
                ))
        return sorted(signals, key=lambda s: s.confidence, reverse=True)

    def detect_primary(self, text: str) -> Optional[Signal]:
        """Return highest-confidence signal."""
        signals = self.detect(text)
        return signals[0] if signals else None
```

---

## 7. Expert Routing (NEXUS) — 5-Phase Pipeline

### The 7 Experts

| Priority | Expert | Safety Floor | Trigger Signals | Voice |
|----------|--------|-------------|-----------------|-------|
| 1 | **Protector** | **10%** | frustrated, overwhelmed, crashed | Warm, validating, empathy-first |
| 2 | **Decomposer** | **5%** | stuck, overwhelmed, task_implied | Clear, structured, breaks things down |
| 3 | **Restorer** | **5%** | depleted, low_energy, crash_zone | Permission-giving, gentle, recovery-focused |
| 4 | Redirector | 0% | context_switch, tangents | Acknowledges, parks, refocuses |
| 5 | Acknowledger | 0% | high_energy, completions | Celebrates, affirms, brief |
| 6 | Guide | 0% | exploring, decision_made | Curious, strategic, Socratic |
| 7 | Executor | 0% | focused, task_implied | Direct, efficient, implementation-focused |

### 5-Phase Pipeline

```
Phase 1: ACTIVATE
  Input: detected signals + ambient state
  Output: list of experts that respond to these signals

Phase 2: WEIGHT
  Input: activated experts + current cognitive state (from LIVRPS)
  Output: weighted scores for each expert (0.0–1.0)

Phase 3: BOUND (CRITICAL — SAFETY)
  Input: weighted scores
  Output: bounded scores (safety floors applied)
  Rule: NO expert can score below its floor
        Protector >= 0.10, Decomposer >= 0.05, Restorer >= 0.05

Phase 4: SELECT
  Input: bounded scores
  Output: ExpertSelection (primary + supporting team)
  Rule: Primary = highest score
        Supporting = any with score > 0.20 (max 2)
        use_agent_team = true if supporting is non-empty

Phase 5: UPDATE
  Input: selection made
  Output: pheromone trail update
  Rule: Record pattern for future learning
```

**Invariant:** Same signals + same state = same routing. Always.

### Implementation

```python
@dataclass
class ExpertWeight:
    expert: str
    value: float

@dataclass
class ExpertSelection:
    primary: ExpertWeight
    supporting: list[ExpertWeight]
    use_agent_team: bool

    @classmethod
    def from_bounded_weights(cls, weights: list[ExpertWeight]) -> 'ExpertSelection':
        sorted_weights = sorted(weights, key=lambda w: w.value, reverse=True)
        primary = sorted_weights[0]
        supporting = [w for w in sorted_weights[1:] if w.value > 0.20][:2]
        return cls(
            primary=primary,
            supporting=supporting,
            use_agent_team=len(supporting) > 0,
        )

class NEXUSRouter:
    def __init__(self, safety_floors: SafetyFloors):
        self.safety_floors = safety_floors

    def route(self, signals: list[Signal], state: dict) -> ExpertSelection:
        # Phase 1: ACTIVATE
        activated = self._activate(signals)
        # Phase 2: WEIGHT
        weighted = self._weight(activated, state)
        # Phase 3: BOUND (safety floors — immutable)
        bounded = self._bound(weighted)
        # Phase 4: SELECT
        selection = ExpertSelection.from_bounded_weights(bounded)
        # Phase 5: UPDATE (pheromone trail deposit)
        self._update_trails(selection, signals)
        return selection

    def _bound(self, weights: list[ExpertWeight]) -> list[ExpertWeight]:
        """Apply safety floors. This is CONSTITUTIONAL."""
        floor_map = {
            "protector": self.safety_floors.protector,
            "decomposer": self.safety_floors.decomposer,
            "restorer": self.safety_floors.restorer,
        }
        return [
            ExpertWeight(
                expert=w.expert,
                value=max(w.value, floor_map.get(w.expert, 0.0)),
            )
            for w in sorted(weights, key=lambda w: w.expert)  # [He2025] sorted
        ]
```

---

## 8. Memory & Pheromone Trails

### Memory Types

| Type | Contents | Persistence |
|------|----------|-------------|
| Episodic | What happened (conversations, events) | Encrypted SQLite |
| Procedural | What works (pheromone trails) | Encrypted SQLite |
| Contextual | Current state (session) | Encrypted SQLite |
| Identity | Who you are | Encrypted, NEVER synced |

### Pheromone Trail System (Patent Claim #4)

```python
@dataclass
class Trail:
    action: str
    strength: float
    deposit_count: int
    last_deposited: datetime
    context: str

class TrailManager:
    def deposit(self, action: str, strength: float, context: str) -> None:
        """Deposit pheromone. Strengthens successful patterns."""
        ...

    def follow(self, context: str) -> list[Trail]:
        """Follow trails. Returns sorted by strength descending."""
        ...

    def get_strength(self, action: str) -> float:
        """Get current trail strength."""
        ...

class DecayEngine:
    def decay_all(self, trails: list[Trail], half_life_hours: float = 168) -> None:
        """Decay all trails. Uses Kahan summation for numerical stability.
        Formula: strength *= 0.5 ^ (elapsed_hours / half_life_hours)
        Trails below threshold (0.001) are pruned."""
        ...
```

### Compaction (Native API)

Use Opus 4.6's native Compaction API (beta) for conversation management. Do NOT build custom summarization.

---

## 9. Encrypted Persistence

### Requirements

- **Algorithm:** AES-256-GCM
- **Key derivation:** Argon2id (memory-hard)
- **Key storage:** Platform keychain (iOS Keychain / OS credential store)
- **Recovery:** 32-character hex recovery key, shown once on setup
- **Scope:** ALL cognitive data encrypted at rest. No exceptions.
- **What's encrypted:** trails.db, session data, cognitive profiles
- **What's NOT encrypted:** Constitutional principles (public), .usda schemas (public)

---

## 10. Opus 4.6 API Integration

### CRITICAL CORRECTION FROM ORIGINAL BLUEPRINT

**Agent teams** are a Claude Code terminal feature, NOT a Messages API feature. OTTO's NEXUS routing spawns parallel Messages API calls and merges results with safety floor enforcement. This is BETTER for patent position — the orchestration logic is YOUR invention, not an API wrapper.

**Compaction API** exists in beta on Messages API. Use it directly. Do NOT build custom summarization.

**Effort controls** use the `effort` parameter (GA, no beta header needed). Replaces `budget_tokens`.

### What OTTO Uses (Messages API Features)

| Feature | Status | OTTO Usage |
|---------|--------|------------|
| Effort Controls (`effort` param) | **GA** | Cost controller: LOW→`low`, MED→`medium`, HIGH→`high`, MAX→`max` |
| Context Compaction | **Beta** | Long conversation management |
| 1M Context Window | **Beta** | Full cognitive substrate in context |
| 128k Output Tokens | **GA** | Large responses, code generation |
| Structured Outputs (`output_config.format`) | **GA** | Deterministic expert routing output |

### What OTTO Builds (Application Layer — Patent-Protected)

| Component | Why Not Native API | OTTO's Implementation |
|-----------|-------------------|----------------------|
| Expert routing (NEXUS) | No API for multi-expert merge | Multiple Messages API calls → merge with safety floors |
| Safety floor enforcement | No API concept of "minimum activation" | Frozen dataclass, checked BEFORE expert selection |
| Pheromone trails | No API for persistent learning | SQLite + Kahan summation decay |
| LIVRPS compositor | No API for layer resolution | Deterministic layer merge (patent) |
| PRISM signal detection | No API for input classification | Regex + pattern matching + LLM classification |

### Configuration

```python
class Opus46Config:
    MODEL = "claude-opus-4-6"
    MAX_OUTPUT_TOKENS = 128_000
    MAX_CONTEXT_TOKENS = 1_000_000
    INPUT_COST_PER_M = 5.0     # $5/M input tokens
    OUTPUT_COST_PER_M = 25.0   # $25/M output tokens

EFFORT_MAP = {
    "LOW": "low",        # Check-ins, energy queries (~$0.003)
    "MEDIUM": "medium",  # Standard routing (~$0.015)
    "HIGH": "high",      # Complex multi-expert (~$0.045)
    "MAX": "max",        # Deep analysis (~$0.08+)
}
```

---

## 11. Determinism (Inspired by [He2025])

OTTO applies [He2025] principles at the application layer (deterministic routing,
sorted iteration, Kahan summation), not at GPU kernel level.

From "Defeating Non-determinism in LLM Inference" (He, 2025):

| Principle | Implementation |
|-------------|---------------|
| Fixed evaluation order | NEXUS phases 1→2→3→4→5, never reorder |
| Sorted iteration | `sorted(dict.items())` everywhere, never bare `dict.items()` |
| Fixed seeds | Named seeds: DETERMINISM_SEED, ROUTING_SEED, TRAIL_SEED, etc. |
| Kahan summation | All float accumulations use Kahan (pheromone decay, expert weights) |
| Batch-invariant | Same batch of signals = same output regardless of batch size |
| Reproducible tests | Tests produce identical results across runs |

**Intentional exceptions (documented):**
- Retry jitter: Unseeded RNG prevents thundering herd
- Presentation variation: Unseeded for natural phrasing

### Kahan Accumulator

```python
class KahanAccumulator:
    """Numerically stable floating-point summation."""
    def __init__(self):
        self._sum = 0.0
        self._compensation = 0.0

    def add(self, value: float) -> None:
        y = value - self._compensation
        t = self._sum + y
        self._compensation = (t - self._sum) - y
        self._sum = t

    def total(self) -> float:
        return self._sum
```

---

# PART III: OS SERVICES

---

## 12. Service Interface (All Platforms)

```python
class OTTOService(Protocol):
    """Every OS service implements this interface."""
    name: str
    tier: int  # 1, 2, or 3

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def get_signals(self) -> list[CategoricalSignal]: ...
    # get_signals() returns ONLY categorical abstractions
    # Raw data stays inside the service — privacy boundary enforced here
```

### Tier 1: Core Services (Phase 1)

| Service | Signal | Platform |
|---------|--------|----------|
| System Clock | Time context (morning/evening, day type) | Both |
| Process Monitor | Active app / context switches | CLI: psutil, iOS: n/a |
| Git Watcher | Commit velocity, stuck detection | CLI only (gitpython) |
| File System Watcher | Activity patterns | CLI: watchdog, iOS: n/a |
| HealthKit | Heart rate, sleep, movement → energy | iOS only |
| Typing Cadence | Speed/rhythm → energy detection | iOS: Core ML |

### Tier 2: Enrichment (Phase 2)

| Service | Signal | Platform |
|---------|--------|----------|
| Calendar | Meeting density, free time | iOS: EventKit, CLI: Google Cal API |
| Discord | Social context | CLI only |

### Tier 3: Advanced (Phase 3)

| Service | Signal | Platform |
|---------|--------|----------|
| Proactive Engine | Crash zone prediction | Both |
| Cross-Surface Orchestration | Multi-device state sync | Future |

---

# PART IV: PLATFORM-SPECIFIC

---

## 13. iOS Project Structure (`otto-ios`)

**Target:** Mac Studio + Xcode 26.3 + Claude Agent SDK

```
otto-ios/
├── OTTO.xcodeproj
├── CLAUDE.md                          # This file
├── OTTO/
│   ├── App/
│   │   ├── OTTOApp.swift
│   │   └── ContentView.swift
│   ├── Core/
│   │   ├── Constitution/
│   │   │   └── Constitution.swift     # FROZEN. Immutable.
│   │   ├── LIVRPS/
│   │   │   ├── LayerName.swift
│   │   │   ├── LIVRPSCompositor.swift
│   │   │   └── CognitiveProperty.swift
│   │   ├── PRISM/
│   │   │   ├── CognitiveSignal.swift
│   │   │   ├── PRISMDetector.swift
│   │   │   └── L0DDictionary.swift
│   │   ├── Experts/
│   │   │   ├── ExpertRouter.swift
│   │   │   ├── ExpertProtocol.swift
│   │   │   ├── ProtectorExpert.swift    # Floor 10%
│   │   │   ├── DecomposerExpert.swift   # Floor 5%
│   │   │   ├── RestorerExpert.swift     # Floor 5%
│   │   │   ├── RedirectorExpert.swift
│   │   │   ├── AcknowledgerExpert.swift
│   │   │   ├── GuideExpert.swift
│   │   │   └── ExecutorExpert.swift
│   │   ├── Memory/
│   │   │   ├── OTTOMemory.swift
│   │   │   ├── EpisodicStore.swift
│   │   │   ├── ProceduralStore.swift
│   │   │   ├── ContextualStore.swift
│   │   │   └── IdentityStore.swift      # NEVER synced
│   │   ├── Pheromones/
│   │   │   ├── TrailManager.swift
│   │   │   ├── TrailTypes.swift
│   │   │   └── DecayEngine.swift        # Kahan summation
│   │   ├── Encryption/
│   │   │   ├── CryptoManager.swift      # AES-256-GCM via CryptoKit
│   │   │   ├── KeyDerivation.swift      # Argon2id
│   │   │   ├── KeychainManager.swift
│   │   │   └── RecoveryKeyManager.swift
│   │   └── Determinism/
│   │       ├── Seeds.swift
│   │       └── KahanAccumulator.swift
│   ├── Intelligence/
│   │   ├── HealthKitManager.swift
│   │   ├── TypingCadenceAnalyzer.swift
│   │   ├── TimeContextEngine.swift
│   │   └── ProactiveEngine.swift
│   ├── API/
│   │   ├── AnthropicClient.swift
│   │   ├── NEXUSPipeline.swift
│   │   ├── EffortController.swift
│   │   └── CompactionManager.swift
│   ├── UI/
│   │   ├── ChatView.swift
│   │   ├── DashboardView.swift
│   │   ├── OnboardingView.swift
│   │   └── Components/
│   └── Extensions/
│       ├── Widgets/
│       ├── SiriIntents/
│       └── ShareExtension/
└── Tests/
```

### iOS Build Phases

| Phase | Weeks | Content |
|-------|-------|---------|
| Phase 1: Core Engine | 1–3 | Constitution, LIVRPS, PRISM, NEXUS, encryption, memory |
| Phase 2: Intelligence | 4–5 | HealthKit, typing cadence, time patterns, dashboard |
| Phase 2.5: Opus 4.6 | 5–6 | Agent teams, effort controller, compaction, 1M context |
| Phase 3: Extensions | 6–7 | Widgets, Siri Shortcuts, Share extension, StoreKit |
| Phase 4: Polish | 8 | TestFlight, App Store assets, compliance audit, submission |

---

## 14. CLI Project Structure (`otto-cli`)

**Target:** Windows (WSL2) + Mac + Linux

```
otto-cli/
├── pyproject.toml                    # Python 3.11+
├── README.md
├── CLAUDE.md                         # This file
├── otto/
│   ├── __init__.py                   # version = "3.0.0-dev"
│   ├── __main__.py                   # Entry point: python -m otto
│   ├── core/
│   │   ├── __init__.py
│   │   ├── constitution.py           # Frozen. Immutable. First file built.
│   │   ├── livrps/
│   │   │   ├── __init__.py
│   │   │   ├── layers.py
│   │   │   ├── compositor.py
│   │   │   └── properties.py
│   │   ├── prism/
│   │   │   ├── __init__.py
│   │   │   ├── detector.py
│   │   │   ├── signals.py
│   │   │   └── patterns.py
│   │   ├── experts/
│   │   │   ├── __init__.py
│   │   │   ├── router.py            # NEXUS 5-phase pipeline
│   │   │   ├── protector.py         # 10% floor
│   │   │   ├── decomposer.py        # 5% floor
│   │   │   ├── restorer.py          # 5% floor
│   │   │   ├── redirector.py
│   │   │   ├── acknowledger.py
│   │   │   ├── guide.py
│   │   │   └── executor.py
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── manager.py           # Read-before-write invariant
│   │   │   ├── episodic.py
│   │   │   └── procedural.py
│   │   ├── encryption/
│   │   │   ├── __init__.py
│   │   │   ├── crypto.py            # AES-256-GCM + Argon2id
│   │   │   └── keystore.py
│   │   ├── pheromones/
│   │   │   ├── __init__.py
│   │   │   ├── trails.py
│   │   │   └── decay.py             # Kahan summation decay
│   │   └── determinism/
│   │       ├── __init__.py
│   │       ├── seeds.py
│   │       └── kahan.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── client.py                # Anthropic SDK wrapper
│   │   ├── nexus.py                 # NEXUS pipeline (uses client.py)
│   │   ├── effort.py                # Effort controller
│   │   └── compaction.py            # Native Compaction API wrapper
│   ├── services/
│   │   ├── __init__.py
│   │   ├── base.py                  # OTTOService protocol
│   │   ├── clock.py                 # Temporal awareness
│   │   ├── process.py               # Active app detection (psutil)
│   │   ├── git.py                   # Commit velocity (gitpython)
│   │   ├── filesystem.py            # File watcher (watchdog)
│   │   └── discord.py               # Discord integration
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── tui.py                   # Terminal UI (textual)
│   │   ├── chat.py
│   │   ├── dashboard.py
│   │   └── styles.py
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py                # MCP server implementation
│   │   └── tools.py                 # OTTO MCP tools
│   └── platform/
│       ├── __init__.py
│       ├── mac.py
│       └── windows.py               # WSL2-specific
├── tests/
│   ├── __init__.py
│   ├── test_constitution.py
│   ├── test_livrps.py
│   ├── test_prism.py
│   ├── test_routing.py
│   ├── test_memory.py
│   ├── test_pheromones.py
│   ├── test_encryption.py
│   ├── test_determinism.py
│   └── test_integration.py
└── scripts/
    ├── install.sh                   # Mac install
    └── install_wsl.sh               # WSL2 install
```

---

# PART V: DEVELOPMENT APPROACH

---

## 15. Using Agent Teams (For BUILDING OTTO)

Agent teams are a Claude Code feature for parallelizing development work. Use them when building OTTO, not inside OTTO's runtime.

```
GOOD: "Implement the LIVRPS compositor, write tests, and update CLAUDE.md"
      → 3 teammates: code / tests / docs (parallel, independent)

GOOD: "Review the v0.7.0 codebase for migration candidates"
      → 3 teammates: core/ review, surfaces/ review, tests/ review

BAD:  "Implement NEXUS routing" (sequential, dependencies between steps)
      → Single session or subagents
```

### Model Selection for Development

| Task | Model | Effort | Why |
|------|-------|--------|-----|
| Architecture decisions | Opus 4.6 | max | Needs deepest reasoning |
| Module implementation | Opus 4.6 | high | Standard complex work |
| Test writing | Sonnet 4.5 | medium | Pattern-based, fast |
| Quick fixes / formatting | Sonnet 4.5 | low | Speed over depth |
| Agent team leads | Opus 4.6 | high | Coordination requires judgment |
| Agent team workers | Sonnet 4.5 | medium | Execution-focused |

### Claude Code Session Pattern

```
1. Read CLAUDE.md (always, every session — this file)
2. Assess task:
   - Parallelizable? → Agent team (2-3 teammates)
   - Sequential? → Single session with subagents
   - Simple? → Direct execution
3. Run existing tests (verify baseline)
4. Implement
5. Run full test suite
6. Commit (conventional commits)
7. Report: shipped / next / blockers
```

### Environment Setup

```bash
# Enable agent teams
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# Execution sequence
# 1. Place CLAUDE.md in repo root
# 2. git checkout -b v3-refactor
# 3. Set env var above
# 4. Open Claude Code
# 5. Paste the day's task card
# 6. Let it run
```

---

## 16. Implementation Rules

### Red Flags (Stop Immediately)

- ✗ Safety floor values changing
- ✗ Clinical language in user-facing strings
- ✗ Bare `dict.items()` (must use `sorted()`)
- ✗ Tests being "adjusted" to pass (fix the code, not the tests)
- ✗ Raw data crossing privacy boundary into categorical signals

### Green Flags

- ✓ Tests pass before moving on
- ✓ `sorted()` around all dict iteration
- ✓ Privacy boundary respected (raw → categorical only)
- ✓ Conventional commit messages
- ✓ Constitution unchanged after Day 1

---

# PART VI: SPRINT TASK CARDS

Paste one card per Claude Code session. Each builds on the previous.

---

## DAY 1: Foundation (Constitution + Project Setup)

```
Read CLAUDE.md first.

TODAY'S TASK: Set up project and implement constitutional layer.

1. Initialize project structure (pyproject.toml or Xcode project)
2. Implement constitution module:
   - ConstitutionalPrinciples (frozen dataclass)
   - SafetyFloors (frozen dataclass)
   - validate() function that asserts floors haven't been modified
3. Write test_constitution.py:
   - Test: principles are frozen (cannot modify)
   - Test: safety floors are frozen
   - Test: protector floor == 0.10
   - Test: decomposer floor == 0.05
   - Test: restorer floor == 0.05
   - Test: validate() passes on correct values
   - Test: validate() raises on incorrect values
4. Run tests. ALL must pass.
5. Commit: "feat: constitutional principles and safety floors (immutable)"
6. Report: what shipped / what's next / blockers
```

---

## DAY 2: LIVRPS Compositor

```
Read CLAUDE.md first.

TODAY'S TASK: Implement LIVRPS memory compositor.

1. Implement layers module:
   - LayerName enum (L=0 through S=5)
   - Layer dataclass with properties dict and active flag
   - LayerStack ordered collection
2. Implement properties module:
   - CognitiveProperty with value, source_layer, timestamp
3. Implement compositor:
   - resolve(property_name) → highest active layer wins
   - resolve_all() → deterministic sorted output
   - Must use sorted iteration for [He2025]
4. Write tests:
   - S overrides all others
   - P overrides L/I/V/R but not S
   - Empty/inactive layers skipped
   - resolve_all deterministic (run 100×, compare)
   - Same input → same resolution
5. Run ALL tests. All must pass.
6. Commit: "feat: LIVRPS memory compositor with deterministic layer resolution"
7. Report.
```

---

## DAY 3: PRISM Signal Detection

```
Read CLAUDE.md first.

TODAY'S TASK: Implement PRISM signal detection.

1. Implement signal types enum (all CognitiveSignal values)
2. Implement pattern definitions (sorted by signal_type for He2025)
3. Implement detector:
   - detect(text) → list of signals sorted by confidence
   - detect_primary(text) → highest confidence or None
   - Fixed evaluation order, sorted output
4. Write tests:
   - Known frustrated text → FRUSTRATED signal
   - Known stuck text → STUCK signal
   - Caps detection works
   - Multiple signals detected and sorted correctly
   - Empty text → empty list
   - Deterministic (same text → same signals, 100×)
5. Run ALL tests.
6. Commit: "feat: PRISM signal detection with pattern matching"
7. Report.
```

---

## DAY 4: Expert Routing (NEXUS) — Biggest Day

```
Read CLAUDE.md first.

TODAY'S TASK: Implement NEXUS 5-phase expert routing pipeline.

This is the largest module. Consider splitting across a full day.

1. Implement expert base class/protocol
2. Implement all 7 expert stubs (protector through executor)
3. Implement NEXUS router:
   - Phase 1: ACTIVATE (signal → expert mapping)
   - Phase 2: WEIGHT (expert scoring based on signal + state)
   - Phase 3: BOUND (safety floor enforcement — CONSTITUTIONAL)
   - Phase 4: SELECT (primary + supporting, agent team flag)
   - Phase 5: UPDATE (pheromone trail deposit)
4. Implement ExpertSelection dataclass with from_bounded_weights
5. Write tests:
   - Safety floors ALWAYS applied (100 random inputs, protector ≥ 0.10)
   - FRUSTRATED → Protector primary
   - STUCK → Decomposer or Guide primary
   - DEPLETED → Restorer primary
   - FOCUSED → Executor primary
   - Same signals + same state → same selection (determinism)
   - Supporting experts filtered by > 0.20 threshold
   - Agent team flag set correctly
6. Run ALL tests.
7. Commit: "feat: NEXUS 5-phase expert routing with safety floor enforcement"
8. Report.
```

---

## DAY 5: Memory Manager

```
Read CLAUDE.md first.

TODAY'S TASK: Implement memory management system.

1. Implement memory types (episodic, procedural, contextual, identity)
2. Implement memory manager with read-before-write invariant
3. Implement SQLite backend (will be encrypted in Day 6)
4. Write tests:
   - Store and retrieve episodic memory
   - Store and retrieve procedural memory
   - Read-before-write enforced
   - Identity memory isolation
5. Run ALL tests.
6. Commit: "feat: memory management with episodic and procedural stores"
7. Report.
```

---

## DAY 6: Encryption

```
Read CLAUDE.md first.

TODAY'S TASK: Implement encryption layer.

1. Implement crypto module (AES-256-GCM)
2. Implement key derivation (Argon2id)
3. Implement keystore (setup, unlock, recovery)
4. Write tests:
   - Encrypt → decrypt roundtrip preserves data
   - Wrong key → graceful failure
   - Key derivation is deterministic
   - Recovery key works
   - Plaintext never written to disk
5. Run ALL tests.
6. Commit: "feat: AES-256-GCM encryption with Argon2id key derivation"
7. Report.
```

---

## DAY 7: Pheromone Trails

```
Read CLAUDE.md first.

TODAY'S TASK: Implement pheromone trail system.

1. Implement Kahan accumulator
2. Implement named seed constants
3. Implement trail manager (deposit, follow, get_strength)
4. Implement decay engine (Kahan summation, half-life, pruning)
5. Write tests:
   - Deposit increases strength
   - Multiple deposits accumulate correctly
   - Decay reduces strength over time
   - Kahan vs naive sum shows precision difference (10,000 iterations)
   - Trails below threshold pruned
   - follow() returns sorted by strength desc
   - Deterministic decay
6. Run ALL tests.
7. Commit: "feat: pheromone trails with Kahan summation decay"
8. Report.
```

---

## DAYS 8-9: API Layer

```
Read CLAUDE.md first.

2-DAY TASK: Implement Anthropic API integration.

DAY 8:
1. Implement API client wrapper (Anthropic SDK)
2. Implement effort controller (LOW/MEDIUM/HIGH/MAX → API effort param)
3. Write tests for effort mapping and client initialization

DAY 9:
1. Implement NEXUS pipeline (API calls with expert routing context)
2. Implement compaction manager (native Compaction API)
3. Write integration tests (mock API responses)
4. Run ALL tests.
5. Commit: "feat: Opus 4.6 API integration with effort controls and compaction"
6. Report.
```

---

## DAYS 10-12: OS Services

```
Read CLAUDE.md first.

3-DAY TASK: Implement ambient intelligence services.

DAY 10: Service base + clock + process monitor
DAY 11: Git watcher + file system watcher
DAY 12: Platform-specific (iOS: HealthKit | CLI: psutil/watchdog)

Each day:
1. Implement services following OTTOService protocol
2. Ensure privacy boundary: raw → categorical only
3. Write tests
4. Run ALL tests.
5. Commit with conventional message
6. Report.
```

---

## DAYS 13-15: User Interface

```
Read CLAUDE.md first.

3-DAY TASK: Implement user interface.

DAY 13: Chat interface (core conversation)
DAY 14: Dashboard (cognitive state visualization)
DAY 15: Platform extensions (iOS: widgets/Siri | CLI: TUI/MCP)

Each day:
1. Implement UI components
2. Verify no clinical language in ANY string
3. Write tests
4. Run ALL tests.
5. Commit.
6. Report.
```

---

## DAYS 16-18: Integration & Polish

```
Read CLAUDE.md first.

DAY 16: Full integration testing (all modules together)
DAY 17: Performance profiling + optimization
DAY 18: Migration from v0.7.0 data (if applicable) + final audit

Final audit checklist:
□ All tests pass
□ No clinical language in user-facing strings
□ No bare dict.items()
□ Safety floors verified immutable
□ Privacy boundary verified (grep for raw data leaks)
□ Encryption verified (no plaintext cognitive data on disk)
□ Determinism verified (repeated test runs identical)
□ Conventional commit history clean
```

---

# PART VII: REFERENCES

| Item | Location |
|------|----------|
| Main codebase | `otto-cli/` or `otto-ios/` |
| Cognitive substrate (Desktop) | `~/.claude/substrate/cognitive_substrate_v5_desktop.usda` |
| Cognitive substrate (CLI) | `~/.claude/substrate/cognitive_substrate_v5.usda` |
| Compliance doc | `THINKINGMACHINES_COMPLIANCE.md` |
| Trail persistence | `data/trails.db` (encrypted → `data/trails.db.enc`) |

---

*Same vehicle. Same highway. New engine. Let's build it.*
