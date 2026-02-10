"""Pheromone trail subsystem — deposit, follow, decay (Patent Claim #4).

Distributed learning through persistent signal reinforcement.
Strong trails guide future routing; unused trails decay.

Components:
    Trail          — Frozen record of a single pheromone trail
    TrailManager   — Deposit, follow, query, and manage trails
    DecayEngine    — Half-life decay with Kahan-stable aggregation
"""

from otto.core.pheromones.decay import DecayEngine
from otto.core.pheromones.trails import Trail, TrailKey, TrailManager

__all__ = [
    "DecayEngine",
    "Trail",
    "TrailKey",
    "TrailManager",
]
