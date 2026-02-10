"""
OTTO OS Pheromone Trail System
==============================

Enables emergent learning through distributed trail signals.
Good paths get reinforced. Bad paths decay. The system learns by doing.

Core Thesis: Trails enable learning without centralized memory.

Usage:
    from otto.trails import Trail, TrailType, TrailStore

    # Create a store
    store = TrailStore()

    # Deposit a trail
    trail = Trail(
        trail_type=TrailType.QUALITY,
        path="src/otto/expert_router.py",
        signal="he2025_compliant",
        deposited_by="validation_agent",
    )
    store.deposit(trail)

    # Read trails for a file
    trails = store.read_trails("src/otto/expert_router.py")

    # Follow the strongest quality trail
    best = store.follow_strongest("src/otto/expert_router.py", TrailType.QUALITY)

Determinism:
- All queries return results in deterministic order
- Strength aggregations use sorted order before computation
- No race conditions through SQLite transactions
"""

from .models import Trail, TrailQuery, TrailType
from .store import (
    TrailStore,
    deposit,
    follow_strongest,
    get_store,
    read_trails,
)

__version__ = "0.1.0"

__all__ = [
    # Models
    "Trail",
    "TrailType",
    "TrailQuery",
    # Store
    "TrailStore",
    "get_store",
    # Convenience functions
    "deposit",
    "read_trails",
    "follow_strongest",
]
