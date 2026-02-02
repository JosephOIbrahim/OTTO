# OTTO Memory Backbone Architecture

> "Memory IS OTTO. OTTO IS memory."

**Version:** 1.0.0
**Updated:** 2026-02-02
**Status:** COMPLETE (per Phase 1 Audit)

---

## Overview

OTTOMemory is the central nervous system of OTTO. All services, surfaces, and subsystems connect through this unified interface.

```
┌─────────────────────────────────────────────────────────────┐
│                      OTTOMemory                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │  Episodic   │ │ Procedural  │ │ Contextual  │           │
│  │  (events)   │ │  (trails)   │ │  (state)    │           │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘           │
│         │               │               │                   │
│         └───────────────┴───────────────┘                   │
│                         │                                   │
│              ┌──────────┴──────────┐                       │
│              │   Memory Interface  │                       │
│              └──────────┬──────────┘                       │
└─────────────────────────┼───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
   │Services │      │Surfaces │      │Substrate│
   │  (MCP)  │      │         │      │         │
   └─────────┘      └─────────┘      └─────────┘
```

---

## Key Components

### OTTOMemory (Unified Interface)

**Location:** `src/otto/memory/interface.py`

The singleton interface that wraps all memory subsystems:

```python
from otto.memory import get_memory, Episode, Outcome

memory = get_memory()

# Episodic memory
memory.record_episode(Episode(...))
episodes = memory.query_episodes(event_type="service.calendar.create")

# Procedural memory (trails)
memory.deposit_trail(action="calendar.create", outcome=Outcome.SUCCESS)
trust = memory.follow_trail("calendar.create")
```

### Pheromone Trails

**Location:** `src/otto/trails/`
**Storage:** `data/trails.db` (SQLite)

Trails implement procedural memory through decay-based strength:

- **Deposit:** Successful actions strengthen trails
- **Follow:** Query trail strength for trust decisions
- **Decay:** 7-day half-life keeps trails responsive

```python
# Trail strengthens with use
for _ in range(10):
    memory.deposit_trail("calendar.create", Outcome.SUCCESS)

# High strength enables auto-approval
trust = memory.follow_trail("calendar.create")
if trust.strength >= AUTO_APPROVE_THRESHOLD:
    # Auto-approve this action type
```

### LIVRPS Composition

**Location:** `src/otto/core/livrps.py`

State composition uses USD-inspired priority resolution:

```
L (Local)      → Session state, oracle results (HIGHEST)
I (Inherits)   → Inherited context from parent
V (Variants)   → Mode switching (focused/exploring/recovery)
R (References) → Calibration data, preferences
P (Payloads)   → Domain knowledge
S (Specializes)→ Constitutional base (LOWEST)
```

### Cognitive Substrate

**Location:** `src/otto/substrate/interface.py`

Three-tier architecture for learned state:

| Tier | Persistence | Mutability |
|------|-------------|------------|
| CONSTITUTIONAL | Immutable | Never changes |
| LEARNED | Cross-session | Approval-gated |
| EPHEMERAL | Session-only | Freely mutable |

---

## Integration Points

### Services → Memory (via MCPServer)

All MCP servers inherit memory via `MCPServer._log_tool_invocation()`:

```python
# base_mcp.py:526-551
def _log_tool_invocation(self, tool, arguments, success, error):
    memory = self._get_memory()
    episode = Episode(...)
    memory.record_episode(episode)
    memory.deposit_trail(action=..., outcome=...)
```

| MCP Server | Memory Inherited |
|------------|------------------|
| calendar_mcp.py | ✅ |
| email_mcp.py | ✅ |
| tasks_mcp.py | ✅ |
| notion_mcp.py | ✅ |
| repos_mcp.py | ✅ |

### Surfaces → Memory

Surfaces connect via `get_memory()`:

```python
# surfaces/base.py
from ..memory import get_memory

class BaseSurface:
    def __init__(self):
        self._memory = get_memory()
```

### Approval → Trails (Bidirectional)

The approval system reads AND writes to trails:

```python
# approval.py:466 - Deposits trails on decisions
memory.deposit_trail(action=trail_action, outcome=outcome)

# approval.py:519 - Queries trail strength for trust
trail_strength = memory.follow_trail(f"{action}:{actor}")
if trail_strength.strength >= AUTO_APPROVE_THRESHOLD:
    return True  # Auto-approved via trails
```

---

## Storage Strategy

### Current Implementation

Memory uses direct file I/O for storage:

| Component | Storage | Format |
|-----------|---------|--------|
| Trails | `data/trails.db` | SQLite |
| Episodes | (via trails) | SQLite |
| Substrate | `~/.otto/substrate/` | JSON |
| Sessions | `~/.orchestra/state/` | JSON |

### Storage Abstraction (FUTURE USE)

**Location:** `src/otto/storage/`

A general-purpose storage abstraction exists but is NOT currently used by memory:

```python
from otto.storage import get_storage

storage = get_storage()
data = storage.read_json("state/cognitive_state.json")
```

**Decision (2026-02-02):** Keep as "future use" for potential cloud storage backends.
**Rationale:** Memory is working with direct I/O. No benefit to refactoring now.

---

## [He2025] Determinism Compliance

| Requirement | Implementation |
|-------------|----------------|
| Fixed evaluation order | LIVRPS priority is fixed |
| Sorted iteration | All queries sort by key |
| Deterministic trails | Trail queries sorted by (path, type, signal) |
| Fixed constants | COGNITIVE_TILE_SIZE=32, seeds fixed |
| Kahan summation | Float aggregation uses Kahan |

---

## Constants

```python
AUTO_APPROVE_THRESHOLD = 0.8   # Trail strength for auto-approval
LEARNING_THRESHOLD = 0.7       # Trail strength for learning
COGNITIVE_TILE_SIZE = 32       # Fixed batch size
MEMORY_SEED = 0xAE0717E5       # Determinism seed
```

---

## Cross-Surface State

The core value proposition: **Actions in one surface are visible in all others.**

```
CLI ──────┐
          │
Telegram ─┼──► OTTOMemory ──► Unified State
          │
Discord ──┘
```

Example workflow:
1. User approves calendar action in CLI
2. Trail strengthens globally
3. Same action auto-approved in Telegram (trust built)
4. Discord status shows CLI's action history

---

## Files Reference

```
src/otto/memory/
├── __init__.py          # Public exports
├── interface.py         # OTTOMemory class (1,528 lines)

src/otto/trails/
├── models.py            # Trail data structures
├── store.py             # SQLite backend

src/otto/core/
├── livrps.py            # LIVRPS composition (494 lines)

src/otto/substrate/
├── interface.py         # Three-tier substrate (730+ lines)

src/otto/storage/        # FUTURE USE
├── provider.py          # Abstract base
├── local.py             # Local filesystem
├── manager.py           # Singleton manager
```

---

*Architecture document for OTTO OS v0.7.0*
