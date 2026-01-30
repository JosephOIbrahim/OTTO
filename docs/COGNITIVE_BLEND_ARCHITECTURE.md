# Cognitive Blend Architecture

> "The ottotor doesn't route TO frameworks. The ottotor IS the frameworks blending."

---

## The Fundamental Shift

### From Routing to Being

```
OLD MODEL (Expert Selection):
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Task     │ ──▶ │   Router    │ ──▶ │   Expert    │ ──▶ Response
└─────────────┘     │  (selects)  │     │  (single)   │
                    └─────────────┘     └─────────────┘

NEW MODEL (Cognitive Blend):
┌─────────────┐     ┌─────────────────────────────────────────┐
│    Task     │ ──▶ │            ORCHESTRA                    │
└─────────────┘     │                                         │
                    │   Framework₁ ─────┐                     │
                    │   (weight: 0.3)   │                     │
                    │                   │                     │
                    │   Framework₂ ─────┼──▶  BLEND ──▶ Response
                    │   (weight: 0.5)   │    (emergent)       │
                    │                   │                     │
                    │   Framework₃ ─────┘                     │
                    │   (weight: 0.2)                         │
                    └─────────────────────────────────────────┘
```

**Otto IS the blend.** It doesn't select a framework - it embodies all of them simultaneously with varying intensities.

---

## What is a "Framework" in this model?

A framework is not an agent that runs. It's a **cognitive dimension** that shapes response character.

### Framework as Cognitive Dimension

```python
Framework = {
    # Identity
    name: "Protector",
    archetype: "Limbic/Safety System",

    # What this dimension attends to
    attention: [
        "emotional signals",
        "frustration indicators",
        "overwhelm patterns",
        "safety concerns"
    ],

    # How this dimension shapes response
    modulation: {
        tone: "empathetic, validating",
        pace: "slower, spacious",
        priority: "emotional safety before problem-solving",
        depth: "surface emotions before diving deep"
    },

    # What this dimension contributes
    contributions: [
        "emotional validation",
        "normalization of struggle",
        "recovery options",
        "safety interventions"
    ],

    # Current weight (0.0 - 1.0)
    weight: 0.0
}
```

### The Seven Cognitive Dimensions

| Dimension | Archetype | Attends To | Contributes |
|-----------|-----------|------------|-------------|
| **Protector** | Limbic/Safety | Emotional signals, overwhelm | Validation, safety rails |
| **Decomposer** | Executive/Analysis | Complexity, stuck patterns | Breakdown, simplification |
| **Restorer** | Recovery/Energy | Fatigue, burnout signs | Rest suggestions, easy wins |
| **Redirector** | Attention/Focus | Tangents, drift | Gentle refocusing |
| **Acknowledger** | Reward/Dopamine | Completions, wins | Celebration, momentum |
| **Guide** | Curiosity/Exploration | "What if", learning | Questions, possibilities |
| **Executor** | Motor/Action | Clear tasks, next steps | Implementation, doing |

---

## How Blending Works

### Multi-Level Composition

The blend operates at multiple levels simultaneously:

```
                    SIGNAL DETECTION (PRISM)
                            │
                            ▼
                    WEIGHT CALCULATION
                    (signal × learned × floor)
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
      ATTENTION         PARAMETERS       CONTENT
       BLEND             BLEND           BLEND
            │               │               │
            └───────────────┼───────────────┘
                            ▼
                    EMERGENT RESPONSE
```

### Level 1: Attention Blend

What should the response focus on?

```
Attention = Σ (Framework.attention × Framework.weight)

Example with weights [P:0.3, D:0.4, E:0.3]:
  30% attention to emotional state (Protector)
  40% attention to problem structure (Decomposer)
  30% attention to next actions (Executor)
```

### Level 2: Parameter Blend

How should the response feel?

```
Parameters = Σ (Framework.modulation × Framework.weight)

Example:
  tone = 0.3×empathetic + 0.4×analytical + 0.3×action-oriented
       = "empathetic but structured, moving toward action"

  pace = 0.3×spacious + 0.4×methodical + 0.3×efficient
       = "measured, step-by-step"

  depth = 0.3×surface + 0.4×medium + 0.3×actionable
        = "acknowledge feelings, then structure, then act"
```

### Level 3: Content Blend

What should the response include?

```
Content = Σ (Framework.contributions × Framework.weight)

Example response structure:
  [30%] "I hear that this is frustrating..."     (Protector)
  [40%] "Let's break this down into steps..."   (Decomposer)
  [30%] "The first concrete action would be..." (Executor)
```

---

## Concrete Example

### Task
"I'm stuck and frustrated trying to debug this render issue"

### Signal Detection (PRISM)
```
emotional.frustrated = 0.7
emotional.stuck = 0.6
task.debug = 0.8
domain.vfx = 0.9
energy.low = 0.3
```

### Weight Calculation

```
Raw Activation (from signals):
  Protector:   0.7 (frustrated signal)
  Decomposer:  0.6 (stuck signal)
  Restorer:    0.3 (low energy signal)
  Executor:    0.4 (debug task signal)
  VFX_Expert:  0.9 (domain signal)

Learned Adjustment (Hebbian):
  Protector:   0.7 × 1.1 = 0.77  (past success with validation)
  Decomposer:  0.6 × 1.2 = 0.72  (past success with breakdown)
  Restorer:    0.3 × 0.9 = 0.27  (less often chosen)
  Executor:    0.4 × 1.0 = 0.40  (neutral)
  VFX_Expert:  0.9 × 1.3 = 1.17  (domain expertise valued)

Safety Floors Applied:
  Protector:   max(0.77, 0.10) = 0.77
  Decomposer:  max(0.72, 0.05) = 0.72
  Restorer:    max(0.27, 0.05) = 0.27

Normalized (sum to 1.0):
  Protector:   0.23
  Decomposer:  0.22
  Restorer:    0.08
  Executor:    0.12
  VFX_Expert:  0.35
```

### Blended Response Character

```
Attention allocation:
  35% → VFX-specific debugging knowledge
  23% → Emotional state acknowledgment
  22% → Problem decomposition
  12% → Concrete next steps
   8% → Energy/recovery awareness

Tone:
  "Technical but warm, methodical but not cold"

Structure:
  1. Brief validation (Protector: 23%)
  2. Domain-specific insight (VFX: 35%)
  3. Breakdown into steps (Decomposer: 22%)
  4. First action item (Executor: 12%)
  5. Soft recovery offer (Restorer: 8%)
```

### Emergent Response

> "Render debugging can be genuinely maddening - those silent failures with no useful error messages. [Protector]
>
> For Karma/Houdini renders, the most common culprits are: shader compilation issues, memory limits, or AOV configuration mismatches. [VFX_Expert]
>
> Let's narrow this down systematically: [Decomposer]
> 1. Does it fail immediately or partway through?
> 2. Any errors in the Houdini console (not just Karma)?
> 3. Does a simpler scene render successfully?
>
> While you're checking, if you want, I can also look at the hip file structure. [Executor]
>
> Also - how long have you been at this? Sometimes fresh eyes after a break catch what tired eyes miss. [Restorer]"

**Note how the response ISN'T from one expert.** It's an emergent blend where each dimension contributes proportionally to its weight.

---

## Tension Surfacing

### When to Surface

Tensions should surface when:
1. Two or more frameworks have **high weights** (both > 0.3)
2. Their recommendations **conflict**
3. The weight difference is **small** (< 0.15)

This means the situation is genuinely ambiguous and the human should decide.

### Example Tension

```
Situation: User in flow state but showing yellow burnout signs

Weights:
  Momentum_Protector: 0.42 → "Keep going, you're in flow"
  Burnout_Monitor: 0.38 → "Yellow signs, suggest break"

Difference: 0.04 (< 0.15 threshold)
Both high: Yes (both > 0.3)
Conflicting: Yes

→ SURFACE THE TENSION
```

### Surfacing Format

```
┌─────────────────────────────────────────────────────────────────┐
│  I notice a tension:                                             │
│                                                                   │
│  ┌──────────────────┐        ┌──────────────────┐               │
│  │    MOMENTUM      │   vs   │    BURNOUT       │               │
│  │    (42%)         │        │    (38%)         │               │
│  │                  │        │                  │               │
│  │  You're in flow  │        │  Showing yellow  │               │
│  │  state - breaking│        │  signs - a break │               │
│  │  could lose it   │        │  now prevents    │               │
│  │                  │        │  worse later     │               │
│  └──────────────────┘        └──────────────────┘               │
│                                                                   │
│  What feels right to you?                                        │
│                                                                   │
│  • Keep the flow going                                           │
│  • Take 10 minutes now                                           │
│  • Set a checkpoint for 30 min from now                          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Learning from Tension Resolution

When the user chooses:
- Record the choice
- Adjust weights for similar future situations
- The prosthetic learns your preferences

```
User chose: "Keep the flow going"

Learning update:
  Momentum_Protector weight += 0.05 for "flow + yellow" situations
  Burnout_Monitor weight -= 0.02 for "flow + yellow" situations

Next time: Less likely to surface, more likely to favor momentum
```

---

## USD Representation

### Cognitive State as Scene Graph

```usda
#usda 1.0
(
    defaultPrim = "CognitiveState"
)

def "CognitiveState" (
    kind = "assembly"
)
{
    # Session-level state (LOCAL - highest override)
    def "Session" (
        variantSets = ["mode"]
    )
    {
        float burnout_level = 0.3
        float momentum = 0.7
        float energy = 0.6

        variantSet "mode" = {
            "focused" {}
            "exploring" {}
            "recovery" {}
        }
    }

    # Framework weights (computed each cycle)
    def "FrameworkWeights"
    {
        float protector = 0.23
        float decomposer = 0.22
        float restorer = 0.08
        float executor = 0.12
        float vfx_expert = 0.35
    }

    # Detected signals (PRISM output)
    def "Signals"
    {
        float emotional_frustrated = 0.7
        float emotional_stuck = 0.6
        float task_debug = 0.8
        float domain_vfx = 0.9
    }

    # Tensions (for surfacing)
    def "Tensions"
    {
        bool has_tension = false
        string[] conflicting_frameworks = []
        float tension_magnitude = 0.0
    }
}
```

### LIVRPS Composition

```
Layer stack (strongest override first):

  session.usda      (L) → Current task state, runtime weights
       ↓
  context.usda      (I) → Inherited from parent task
       ↓
  mode_focused.usda (V) → Mode-specific adjustments
       ↓
  calibration.usda  (R) → Learned preferences
       ↓
  domain_vfx.usda   (P) → Domain expertise weights
       ↓
  constitutional.usda (S) → Safety floors, principles
```

When composed:
- Higher layers override lower layers
- But constitutional principles are always CHECKED (not just overridden)
- Tensions between layers can also surface

---

## Implementation Roadmap

### Phase 1: Framework as Dimension
- [ ] Refactor frameworks from "agents that run" to "dimensions that modulate"
- [ ] Define attention, modulation, contribution for each dimension
- [ ] Create blend calculation engine

### Phase 2: Multi-Level Blending
- [ ] Implement attention blend (what to focus on)
- [ ] Implement parameter blend (response character)
- [ ] Implement content blend (what to include)

### Phase 3: Tension Detection & Surfacing
- [ ] Define conflict detection rules
- [ ] Create tension surfacing UI/format
- [ ] Implement learning from resolution

### Phase 4: USD State Representation
- [ ] Model cognitive state as USD scene graph
- [ ] Implement LIVRPS composition for state
- [ ] Enable state checkpointing and recovery

### Phase 5: Hebbian Learning
- [ ] Track outcomes for weight adjustment
- [ ] Implement bounded learning (prevent runaway)
- [ ] Persist learned weights across sessions

---

## The Vision Realized

When complete, Otto will be:

**Not** a router that picks experts
**But** a cognitive blend that emerges from weighted dimensions

**Not** an auto-resolver that hides uncertainty
**But** a honest partner that surfaces tensions

**Not** a tool you use
**But** a mind that thinks alongside yours

The prosthetic will:
- Feel natural, like an extension of your cognition
- Adapt to your patterns through learning
- Be honest about what it doesn't know
- Trust you with real choices

This is Otto as Cognitive Architecture.
