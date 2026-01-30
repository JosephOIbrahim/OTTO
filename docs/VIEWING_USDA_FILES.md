# Viewing Otto .usda Files

## Overview

Otto exports cognitive state sessions to `.usda` (USD ASCII) files
that can be viewed and analyzed using standard USD tools.

## Exported Files Location

```
Otto/
├── state/
│   └── exports/
│       └── *.usda        # Exported session files
├── src/otto/
│   └── schema/
│       ├── cognitive.usda    # Schema definition
│       └── constitutional.usda # Safety floors schema
```

## Viewing with usdview

### Prerequisites

Install USD tools (requires Python <3.14):

```bash
# Create a Python 3.13 environment
conda create -n usd python=3.13
conda activate usd

# Install USD
pip install usd-core

# Or with NVIDIA's distribution (includes usdview)
pip install nvidia-pyindex
pip install usd-viewer
```

### Opening a Session File

```bash
# Using usdview (if available)
usdview Otto/state/exports/dogfood_b1cef6ac.usda

# Or using Python
python -c "
from pxr import Usd
stage = Usd.Stage.Open('Otto/state/exports/dogfood_b1cef6ac.usda')
for prim in stage.Traverse():
    print(prim.GetPath())
"
```

### What You'll See

The stage hierarchy:

```
/CognitiveRoot
├── /session        (LOCAL - highest priority, current state)
├── /inherited      (INHERITS - parent context)
├── /variants       (VARIANTS - mode-specific values)
├── /calibration    (REFERENCES - learned preferences)
├── /domain         (PAYLOADS - domain knowledge)
└── /constitutional (SPECIALIZES - safety floors)
```

## Understanding the .usda Format

### Session Layer (Priority 1)

Contains current session state - mutable:

```usda
def Xform "session" (doc = "Priority: LOCAL (1)") {
    custom string burnout_level = "green"
    custom string momentum_phase = "cold_start"
    custom string energy_level = "medium"
    custom string mode = "focused"
    custom int altitude = 30000
}
```

### Constitutional Layer (Priority 6)

Contains safety floors - immutable:

```usda
def Xform "constitutional" (doc = "Priority: SPECIALIZES (6)") {
    custom double safety_floor_protector = 0.1
    custom int working_memory_limit = 3
    custom int body_check_interval = 20
    custom string max_depth_depleted = "minimal"
}
```

## Analyzing Sessions

### Comparing Two Sessions

```python
from pxr import Usd, Sdf

# Load two session exports
stage1 = Usd.Stage.Open('session_1.usda')
stage2 = Usd.Stage.Open('session_2.usda')

# Compare attributes
for prim_path in ['/CognitiveRoot/session']:
    prim1 = stage1.GetPrimAtPath(prim_path)
    prim2 = stage2.GetPrimAtPath(prim_path)

    for attr in prim1.GetAttributes():
        val1 = attr.Get()
        attr2 = prim2.GetAttribute(attr.GetName())
        val2 = attr2.Get() if attr2 else None

        if val1 != val2:
            print(f"{attr.GetName()}: {val1} -> {val2}")
```

### Extracting Metrics

```python
from pxr import Usd

stage = Usd.Stage.Open('session.usda')
session = stage.GetPrimAtPath('/CognitiveRoot/session')

# Get attributes
burnout = session.GetAttribute('burnout_level').Get()
energy = session.GetAttribute('energy_level').Get()
mode = session.GetAttribute('mode').Get()

print(f"Burnout: {burnout}")
print(f"Energy: {energy}")
print(f"Mode: {mode}")
```

## Session Export Example

Here's what a typical session export looks like:

```usda
#usda 1.0
(
    doc = "Cognitive Stage - Otto Cognitive Architecture"
    metersPerUnit = 1
    upAxis = "Y"
)

def Xform "CognitiveRoot"
{
    def Xform "session" (
        doc = "Priority: LOCAL (1)"
    )
    {
        custom string burnout_level = "green"
        custom string momentum_phase = "building"
        custom string energy_level = "medium"
        custom string mode = "focused"
        custom int altitude = 30000
        custom string focus_level = "moderate"
        custom string urgency = "moderate"
        custom int exchange_count = 15
        custom double epistemic_tension = 0.1
        custom string paradigm = "cortex"
    }

    def Xform "constitutional" (
        doc = "Priority: SPECIALIZES (6)"
    )
    {
        custom double safety_floor_protector = 0.1
        custom double safety_floor_restorer = 0.05
        custom int working_memory_limit = 3
        custom int max_agent_depth = 3
        custom int max_parallel_agents = 3
        custom int body_check_interval = 20
        custom int tangent_budget_default = 5
        custom string max_depth_depleted = "minimal"
        custom string max_depth_low_energy = "standard"
        custom string max_depth_red_burnout = "minimal"
        custom string max_depth_orange_burnout = "standard"
    }
}
```

## Integration with VFX Tools

The .usda format is standard Pixar USD ASCII. These files can be:

1. **Opened in Houdini** - File > Import > USD
2. **Viewed in Maya** - USD plugin required
3. **Analyzed in usdcat** - `usdcat session.usda`
4. **Diffed with usddiff** - `usddiff session1.usda session2.usda`

This enables treating cognitive state as a first-class scene description,
amenable to all standard USD tooling.

## Why USD for Cognitive State?

1. **LIVRPS composition** - Priority resolution is built-in
2. **Layered overrides** - Session > Calibration > Constitutional
3. **Queryable** - Can inspect any attribute's opinion stack
4. **Debuggable** - Human-readable ASCII format
5. **Standard** - Works with existing VFX toolchains
