# Framework Ottotor v5.0

**7-Agent async ottotion system implementing the USD Cognitive Substrate specification.**

## Overview

The Framework Ottotor provides a deterministic, reproducible cognitive routing system that implements V5 intervention experts with safety floors.

### Key Features

- **7 Agents**: ECHO Curator, Domain Intelligence, MoE Router, World Modeler, Code Generator, Determinism Guard, Self Reflector
- **V5 Intervention Experts**: protector, decomposer, restorer, redirector, acknowledger, guide, executor
- **Safety Floors**: Hard minimums (protector: 10%, decomposer: 5%, restorer: 5%)
- **5-Phase Routing**: ACTIVATE → WEIGHT → BOUND → SELECT → UPDATE
- **Determinism**: Batch-invariant execution
- **USD Payload Architecture**: Lazy-loadable framework modules

## Installation

```bash
# Clone/copy the Framework Ottotor directory
cp -r Framework_Ottotor ~/.framework-ottotor/core/

# Install dependencies
pip install -r requirements.txt
```

## Usage

### CLI Mode

```bash
# Single task
python framework_ottotor.py --task "Implement the feature"

# Interactive mode
python framework_ottotor.py

# Show agent info
python framework_ottotor.py --info
```

### Programmatic Usage

```python
from framework_ottotor import FrameworkOttotor, Mycelium

# Initialize
ottotor = FrameworkOttotor()

# Execute task
result = await ottotor.ottote(
    task="Debug the configuration",
    context={"seed": 42}
)

print(f"Agents executed: {result['agents_executed']}")
print(f"Master checksum: {result['master_checksum']}")
```

### Mycelium Weight Calibration

```python
from framework_ottotor import Mycelium

mycelium = Mycelium()

# Manual calibration (no automatic self-improvement)
mycelium.set_weight("executor", 0.4)  # Boost task execution
mycelium.save_weights()  # Persist to REFERENCES layer

# Check loading strategy
strategy = mycelium.get_loading_strategy()
print(f"Strategy: {strategy['strategy']}")  # fast/weighted/thorough
```

## Directory Structure

```
~/.framework-ottotor/
├── core/
│   ├── framework_ottotor.py    # Main ottotor
│   └── tests/                       # Test suite
├── domains/                         # Domain configs (JSON) - user-defined
│   ├── <your_domain>.json           # Add domain configs as needed
│   └── general.json                 # Fallback (auto-created if missing)
├── frameworks/                      # Payload modules
│   ├── adhd_moe/                   # Safety tier (always loaded)
│   ├── max_reflection/             # Weighted tier
│   ├── nova_oracle/                # Deferred tier
│   ├── echo_memory/                # Weighted tier
│   └── cortex_world/               # Deferred tier
├── principles.json                  # SPECIALIZES layer (never compressed)
└── mycelium_weights.json           # Calibrated weights (REFERENCES layer)
```

## Architecture

### Agent Responsibilities

| Agent | Framework | Purpose |
|-------|-----------|---------|
| ECHO Curator | ECHO 2.0 + LIVRPS | Memory management with USD composition semantics |
| Domain Intelligence | Phoenix v6 + PRISM | Multi-domain analysis with pluggable specialists |
| MoE Router | V5 Intervention Experts | 5-phase routing with safety floors |
| World Modeler | CORTEX | Context graph construction |
| Code Generator | MAX 3 + MNO v3 | Deterministic code generation |
| Determinism Guard | Batch-Invariance [He2025] | Reproducibility enforcement |
| Self Reflector | Resonance + RC^+xi | Meta-cognition and convergence tracking |

### V5 Expert Archetypes

| Priority | Expert | Triggers | Safety Floor |
|----------|--------|----------|--------------|
| 1 | Protector | frustrated, overwhelmed, safety | 10% |
| 2 | Decomposer | stuck, complex, break_down | 5% |
| 3 | Restorer | depleted, burnout, tired | 5% |
| 4 | Redirector | tangent, distracted, off_topic | 0% |
| 5 | Acknowledger | done, complete, milestone | 0% |
| 6 | Guide | exploring, what_if, curious | 0% |
| 7 | Executor | implement, code, do, execute | 0% |

### Design Decisions

1. **No Automatic Self-Improvement**: Weights are static, calibrated manually. This preserves:
   - Determinism (same signals → same routing)
   - Auditability (weights don't change unexpectedly)
   - Determinism

2. **Safety Floors are HARD**: Protector can never drop below 10% weight. This ensures safety experts are always available.

3. **5-Phase Routing**: Fixed execution order prevents batch-variance.

## Tests

```bash
cd ~/.framework-ottotor/core
pytest tests/test_ottotor.py -v --asyncio-mode=auto
```

**31/31 tests passing**

## Configuration

### Domain Configs

Create custom domain configs in `~/.framework-ottotor/domains/`:

```json
{
  "name": "my_domain",
  "specialists": {
    "specialist_name": {
      "keywords": ["keyword1", "keyword2"],
      "analysis_focus": ["focus_area"]
    }
  },
  "routing_keywords": ["domain_keyword"],
  "prism_perspectives": ["causal", "optimization", "risk"]
}
```

### Principles (SPECIALIZES Layer)

The principles layer is NEVER compressed. Create `~/.framework-ottotor/principles.json`:

```json
{
  "constitutional": {
    "principles": [
      {"id": "safety_first", "statement": "Safety first: Emotional safety before productivity"},
      {"id": "user_knows_best", "statement": "User signal trumps Claude's guess"}
    ]
  }
}
```

## References

- USD Cognitive Substrate: `~/.claude/substrate/cognitive_substrate_v4.usda`
- https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
- V5 Framework Synthesis: `V5_FRAMEWORK_SYNTHESIS.md`

---

*Framework Ottotor v5.0*
*Generated: 2026-01-21*
