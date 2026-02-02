# USD Architecture Decision Record

## Decision: USD as Conceptual Model, Not Runtime Dependency

**Date:** February 2026
**Status:** ACCEPTED
**Deciders:** Architecture Review

---

## Context

The OTTO OS Blueprint references USD (Universal Scene Description) in two ways:

1. **Conceptual:** Using LIVRPS composition semantics as a mental model for cognitive state priority resolution
2. **Runtime:** Potentially using `pxr-usd` (Pixar's OpenUSD library) as a dependency

The Blueprint v1.0 lists `pxr-usd` as a dependency:

```toml
dependencies = [
    "pxr-usd",              # USD (OpenUSD)
    ...
]
```

This document records the decision on which approach to use.

---

## Decision

**Use USD as a CONCEPTUAL model only. Do NOT add `pxr-usd` as a runtime dependency.**

---

## Rationale

### 1. Mobile Compatibility

The existing codebase has 292 tests for mobile abstraction. Mobile builds explicitly exclude heavy dependencies:

```python
MOBILE_EXCLUDED_DEPENDENCIES = {
    "rich",
    "prompt_toolkit",
}
```

Adding `pxr-usd` would contradict this architecture:
- `pxr-usd` is ~500MB (C++ library with Python bindings)
- Not available on iOS/Android
- Would require native compilation per platform

### 2. Existing Implementation Works

The current implementation uses USD semantics without the runtime:

| Component | Approach |
|-----------|----------|
| `.usda` files | Schema documentation, not parsed |
| LIVRPS priority | Implemented in Python |
| Layer resolution | Python dict merging |
| Variant sets | Python enums |

349 tests pass with this approach.

### 3. The Pattern, Not the Parser

USD's value to OTTO OS is the **composition semantics**, not the file format:

- **LIVRPS priority order** → Implemented as Python priority resolution
- **Layer stacking** → Implemented as dict merging (session > calibration > constitutional)
- **Variant sets** → Implemented as Python enums (cognitive_mode variants)
- **Specializes (safety floors)** → Implemented as minimum value enforcement

We get the conceptual benefit without the operational cost.

### 4. Simpler Deployment

Without `pxr-usd`:
- `pip install otto-os` works on any platform
- No native compilation required
- Smaller package size
- Fewer dependency conflicts

### 5. [He2025] Determinism

USD file parsing introduces potential non-determinism:
- File I/O timing
- Layer composition order edge cases
- Attribute resolution caching

Pure Python LIVRPS implementation is easier to verify for [He2025] compliance.

---

## Consequences

### Positive

1. Mobile builds remain lightweight
2. Simpler installation and deployment
3. Easier [He2025] compliance verification
4. Full control over composition behavior

### Negative

1. Can't interchange `.usda` files with DCC apps (Houdini, Maya)
2. Must maintain our own LIVRPS implementation
3. `.usda` files are documentation, not machine-parsed

### Neutral

1. Developers familiar with USD will recognize the patterns
2. Documentation can reference USD concepts
3. Future migration to `pxr-usd` remains possible

---

## Implementation

### Current State

```
OTTO_OS/
├── src/otto/schema/
│   ├── cognitive.usda       # Schema documentation (not parsed)
│   └── constitutional.usda  # Safety floors documentation (not parsed)
```

### LIVRPS Implementation (Conceptual)

```python
# otto/core/livrps.py

def resolve_livrps(layers: dict[str, dict]) -> dict:
    """
    Resolve cognitive state using LIVRPS priority.

    Layer priority (highest to lowest):
    - L (Local/Session): Current session state
    - I (Inherits): Inherited context
    - V (Variants): Mode-specific values
    - R (References): Calibration data
    - P (Payloads): Domain knowledge
    - S (Specializes): Constitutional base

    First layer with a value wins.
    Safety floors from S are always enforced.
    """
    result = {}

    # Apply in LIVRPS order (L highest priority)
    for layer_name in ["local", "inherits", "variants", "references", "payloads", "specializes"]:
        layer = layers.get(layer_name, {})
        for key, value in layer.items():
            if key not in result:
                result[key] = value

    # Enforce safety floors (never overridden)
    safety_floors = layers.get("specializes", {}).get("safety_floors", {})
    for key, floor in safety_floors.items():
        if key in result and result[key] < floor:
            result[key] = floor

    return result
```

### .usda Files as Documentation

The `.usda` files serve as:
1. **Schema definition** - What fields exist and their types
2. **Default values** - Starting values for each field
3. **Allowed tokens** - Valid values for string enums
4. **Documentation** - Docstrings explaining each field

They are **human-readable specifications**, not runtime-parsed data.

---

## Alternatives Considered

### Alternative 1: Full pxr-usd Integration

**Rejected because:**
- Mobile incompatibility
- Heavy dependency (~500MB)
- Over-engineering for current needs

### Alternative 2: USD-lite Python Library

**Considered but deferred:**
- Libraries like `usd-core` exist but still heavy
- Could revisit if DCC interchange becomes needed
- Current approach sufficient for cognitive state management

### Alternative 3: Custom USD Parser

**Rejected because:**
- Significant development effort
- Would need to maintain parser
- No actual need to parse `.usda` at runtime

---

## References

- [He2025] Determinism requirements: `docs/HE2025_DETERMINISM_ADDENDUM.md`
- Mobile architecture: `docs/MOBILE_TUI_REMOVAL.md`
- Blueprint v1.0: `BLUEPRINT.md`
- USD specification: https://openusd.org/release/spec.html

---

## Review

This decision should be reviewed if:
1. DCC application interchange becomes a requirement
2. A lightweight mobile-compatible USD library emerges
3. Performance of Python LIVRPS becomes insufficient

---

*ADR-001 | February 2026*
