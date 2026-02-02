# Storage Abstraction Layer

**Status:** FUTURE USE (not currently integrated with memory backbone)

---

## Overview

This module provides a general-purpose storage abstraction layer. It was designed for:
- Swapping storage backends without changing application code
- Supporting multiple storage roots (otto, claude, backup)
- Future cloud storage integration

## Current State

**NOT INTEGRATED** with OTTOMemory. The memory backbone uses direct file I/O.

| Component | Uses Storage Module |
|-----------|---------------------|
| OTTOMemory | ❌ Direct file I/O |
| TrailStore | ❌ Direct SQLite |
| Substrate | ❌ Direct JSON |
| Services | ❌ Direct file I/O |

## Decision Record

**Date:** 2026-02-02
**Decision:** Keep as "future use", do not integrate now
**Rationale:**
1. Memory backbone is working correctly
2. Refactoring would add risk with no immediate benefit
3. Cloud storage might need this in the future

## Architecture

```
StorageManager (singleton)
    │
    └── StorageProvider (abstract)
            │
            ├── LocalStorageProvider ← Currently only implementation
            │
            └── CloudStorageProvider (FUTURE)
```

## Usage (if adopted in future)

```python
from otto.storage import get_storage

storage = get_storage()

# Read/write JSON
data = storage.read_json("state/cognitive_state.json")
storage.write_json("state/cognitive_state.json", data)

# Multiple roots
storage.read_json("state.json", root_type="otto")   # ~/.otto/
storage.read_json("state.json", root_type="claude") # ~/.claude/

# Atomic writes with backup
storage.write_json("state.json", data, backup=True)
```

## When to Integrate

Consider integrating storage module when:
- Cloud storage backend needed
- Cross-machine sync required
- Backup strategy becomes complex
- Multiple storage backends needed

---

*Last reviewed: 2026-02-02*
