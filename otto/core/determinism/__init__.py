"""Determinism subsystem — Kahan summation and named seeds.

Provides the numerical and reproducibility primitives required by
[He2025] compliance: compensated float accumulation and fixed seed
constants for all pseudo-random operations.
"""

from otto.core.determinism.kahan import KahanAccumulator, kahan_sum
from otto.core.determinism.seeds import (
    ALL_SEEDS,
    BATCH_SEED,
    DECAY_SEED,
    DETERMINISM_SEED,
    ROUTING_SEED,
    TEST_SEED,
    TRAIL_SEED,
)

__all__ = [
    "ALL_SEEDS",
    "BATCH_SEED",
    "DECAY_SEED",
    "DETERMINISM_SEED",
    "KahanAccumulator",
    "ROUTING_SEED",
    "TEST_SEED",
    "TRAIL_SEED",
    "kahan_sum",
]
