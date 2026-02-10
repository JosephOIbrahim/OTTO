"""Named seed constants for Determinism.

Every pseudo-random operation in OTTO uses a named seed from this
module.  This ensures that any stochastic behavior is reproducible
when the same seed is used, and that different subsystems don't
accidentally share entropy streams.

Intentional exceptions (documented, unseeded):
  - Cryptographic nonces (os.urandom — MUST be unpredictable)
  - Retry jitter (prevents thundering herd)
  - Presentation variation (natural language phrasing)
"""

from __future__ import annotations

# ---- System-wide seeds (fixed, never change) ----

DETERMINISM_SEED: int = 42       # General-purpose determinism
ROUTING_SEED: int = 137          # NEXUS expert routing
TRAIL_SEED: int = 271            # Pheromone trail operations
DECAY_SEED: int = 314            # Decay engine calculations
BATCH_SEED: int = 577            # Batch-invariant processing
TEST_SEED: int = 12345           # Test reproducibility

# Sorted tuple of all seeds for validation
ALL_SEEDS: tuple[tuple[str, int], ...] = tuple(sorted([
    ("BATCH_SEED", BATCH_SEED),
    ("DECAY_SEED", DECAY_SEED),
    ("DETERMINISM_SEED", DETERMINISM_SEED),
    ("ROUTING_SEED", ROUTING_SEED),
    ("TEST_SEED", TEST_SEED),
    ("TRAIL_SEED", TRAIL_SEED),
], key=lambda pair: pair[0]))
