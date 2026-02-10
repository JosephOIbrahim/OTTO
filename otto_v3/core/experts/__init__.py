"""NEXUS expert routing — 5-phase cognitive routing pipeline.

Routes PRISM signals through 7 experts with safety floor enforcement
(Patent Claim #2). The pipeline is deterministic: same signals + same
state = same routing, always.

Experts:
    1. Protector  (floor 10%) — emotional safety, empathy-first
    2. Decomposer (floor  5%) — breaks down overwhelm, structures tasks
    3. Restorer   (floor  5%) — permission to rest, recovery-focused
    4. Redirector  (floor  0%) — refocuses from tangents
    5. Acknowledger(floor  0%) — celebrates wins, affirms progress
    6. Guide       (floor  0%) — Socratic discovery, strategic thinking
    7. Executor    (floor  0%) — direct implementation, stays out of way
"""

from otto_v3.core.experts.base import ExpertConfig, ExpertSelection, ExpertWeight
from otto_v3.core.experts.router import NEXUSRouter

__all__ = [
    "ExpertConfig",
    "ExpertSelection",
    "ExpertWeight",
    "NEXUSRouter",
]
