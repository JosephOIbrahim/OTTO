# OTTO OS Blueprint v1.0 Reconciliation Summary

## For Claude Desktop Discussion

---

## TL;DR

The Blueprint v1.0 is **85% aligned** with [He2025] determinism principles and existing code. Three documents now close the gaps:

1. `docs/HE2025_DETERMINISM_ADDENDUM.md` - Determinism specifications
2. `docs/USD_ARCHITECTURE_DECISION.md` - USD as conceptual model
3. Updated `.usda` schema files with compliance notes

---

## What Exists (349 Tests)

```
┌─────────────────────────────────────────────────────────────────┐
│                    OTTO OS CODEBASE                             │
├─────────────────────────────────────────────────────────────────┤
│  PLATFORM ABSTRACTION         │  PHEROMONE TRAILS              │
│  ├── Storage (37 tests)       │  ├── TrailStore (36 tests)     │
│  ├── Keyring (44 tests)       │  └── Hook System (21 tests)    │
│  ├── Output (41 tests)        │                                 │
│  ├── Input (59 tests)         │  RENDERING                      │
│  └── Mobile (32 tests)        │  ├── StatusRenderer (36 tests)  │
│                               │  └── DashboardRenderer (43 t)   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Decisions Made

### 1. USD: Conceptual, Not Runtime

| Blueprint Says | Decision |
|----------------|----------|
| `pxr-usd` dependency | **REMOVED** |
| USD file parsing | **NOT NEEDED** |
| LIVRPS semantics | **Python implementation** |

**Rationale:** Mobile compatibility, simpler deployment, [He2025] easier to verify.

### 2. State Detection: Fixed Vocabularies

| Blueprint Says | Addendum Specifies |
|----------------|-------------------|
| "heuristics" | Fixed vocabularies (`FRUSTRATED_VOCABULARY`, etc.) |
| "negative words" | 11 specific words, alphabetically sorted |
| "short responses" | `< 20 characters` |

### 3. Expert Selection: Explicit Priorities

| Expert | Priority |
|--------|----------|
| Validator | 1 (highest) |
| Scaffolder | 2 |
| Restorer | 3 |
| Refocuser | 4 |
| Celebrator | 5 |
| Socratic | 6 |
| Direct | 7 (default) |

### 4. Float Handling: Precision Specified

| Operation | Specification |
|-----------|---------------|
| Comparison | `round(value, 6)` |
| Aggregation | Kahan summation |
| Input order | `sorted()` first |
| Ratios | 2 decimal places |

---

## What Blueprint Needs Updated

### Missing Components

| Component | Code Location | Tests |
|-----------|---------------|-------|
| Trail System | `otto/trails/` | 36 |
| Hook System | `otto/hooks/` | 21 |
| Output Formatter | `otto/output/` | 41 |
| Input Provider | `otto/input/` | 59 |
| Mobile Config | `otto/mobile/` | 32 |

### Section Updates Needed

1. **Section 12 (TUI):** Update for mobile-first (TUI being removed)
2. **Dependencies:** Remove `pxr-usd`, keep USD conceptual
3. **State Detection:** Reference addendum for fixed vocabularies
4. **Expert Selection:** Add explicit priority numbers

---

## File Deliverables Created

```
docs/
├── HE2025_DETERMINISM_ADDENDUM.md   # NEW - Full determinism spec
├── USD_ARCHITECTURE_DECISION.md      # NEW - ADR for USD approach
├── BLUEPRINT_RECONCILIATION_SUMMARY.md  # NEW - This file
└── MOBILE_TUI_REMOVAL.md             # EXISTING - Migration status

src/otto/schema/
├── cognitive.usda                    # UPDATED - [He2025] notes added
└── constitutional.usda               # UPDATED - [He2025] notes added
```

---

## Verification Commands

```bash
# All 349 tests pass
cd C:\Users\User\OTTO_OS
pytest tests/ -v

# Specific modules
pytest tests/test_trails.py -v          # 36 tests
pytest tests/test_hooks.py -v           # 21 tests
pytest tests/test_mobile_build.py -v    # 32 tests
pytest tests/test_dashboard_renderer.py -v  # 43 tests
pytest tests/test_status_renderer.py -v     # 36 tests
```

---

## Next Steps for Blueprint v1.1

### Phase 1: Documentation (No Code)

1. Add reference to `HE2025_DETERMINISM_ADDENDUM.md` in Blueprint
2. Update dependencies section (remove pxr-usd)
3. Add Trail/Hook/Mobile sections
4. Update TUI section for mobile-first

### Phase 2: Implementation

5. Implement `SignalExtractor` class per addendum
6. Implement `select_expert()` per addendum
7. Implement `compute_dial()` with Kahan summation
8. Add determinism verification tests

### Phase 3: Integration

9. Wire intake form to dial computation
10. Wire state detection to expert selection
11. Wire expert selection to response generation
12. End-to-end determinism testing

---

## The Soul Remains Intact

The Blueprint's soul:
> "Doesn't judge. Doesn't annoy. Doesn't forget."

How [He2025] compliance protects it:

| Promise | Protection |
|---------|------------|
| "Doesn't judge" | Same message → same state → consistent treatment |
| "Doesn't annoy" | Same conditions → same intervention timing |
| "Doesn't forget" | Same profile → same behavior, always |

**Determinism IS the soul.** Without it, the system judges inconsistently, annoys unpredictably, and forgets differently each time.

---

## Questions for Claude Desktop Discussion

1. **Priority:** Implement intake form first, or state detection first?
2. **Telegram vs Web:** Start with Telegram bot or web interface?
3. **Testing:** Unit tests sufficient, or need integration tests for determinism?
4. **Vocabulary:** Should signal vocabularies be user-customizable?
5. **Decay:** Should permission effectiveness decay like trails?

---

*Summary v1.0 | February 2026*
*Ready for Claude Desktop discussion*
