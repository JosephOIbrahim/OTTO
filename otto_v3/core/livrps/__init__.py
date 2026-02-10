"""LIVRPS cognitive substrate — Patent Claim #1.

Deterministic layered memory composition inspired by Pixar USD's
composition arcs. Layers resolve highest-priority-first, with sorted
iteration for determinism.

Layers (lowest → highest priority):
    L — Learned      (accumulated from interactions)
    I — Inherited    (system defaults)
    V — Volatile     (session-only, ephemeral)
    R — Reactive     (real-time signal response)
    P — Protective   (safety overrides)
    S — Sovereign    (user explicit choice, HIGHEST)
"""

from otto_v3.core.livrps.layers import Layer, LayerName, LayerStack
from otto_v3.core.livrps.properties import CognitiveProperty
from otto_v3.core.livrps.compositor import LIVRPSCompositor

__all__ = [
    "CognitiveProperty",
    "Layer",
    "LayerName",
    "LayerStack",
    "LIVRPSCompositor",
]
