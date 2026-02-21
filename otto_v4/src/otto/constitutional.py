"""Constitutional layer for OTTO v5.0.

Safety floors and energy gates that can suppress output from any mode.
This layer sits ABOVE the specialist modes — it can veto anything
except the Protector (which always runs).

Wired live in Phase 1.1: CLI nudge, scheduler, and agent tools all
check should_suppress() before generating output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .log import get_logger
from .state import CognitiveState

_log = get_logger(__name__)

# Actions that can be suppressed
ActionType = Literal["nudge", "decompose", "redirect", "acknowledge"]

# The Protector is NEVER suppressed — this is constitutional
_UNSUPPRESSABLE = frozenset({"protector"})


@dataclass(frozen=True)
class Suppression:
    """Record of a suppressed action with the reason."""

    action: str
    reason: str


def should_suppress(
    state: CognitiveState,
    action: str,
    *,
    mode: str = "executor",
) -> Suppression | None:
    """Check if an action should be suppressed given current cognitive state.

    Parameters
    ----------
    state:
        Current cognitive state snapshot.
    action:
        The action being attempted (e.g. ``"nudge"``).
    mode:
        The mode attempting the action. The Protector mode is never
        suppressed.

    Returns
    -------
    Suppression | None
        A :class:`Suppression` if the action should be blocked,
        ``None`` if it should proceed.
    """
    # Constitutional: Protector is NEVER suppressed
    if mode in _UNSUPPRESSABLE:
        return None

    # RED burnout: suppress everything except protector
    if state.burnout == "RED":
        reason = "burnout is RED — OTTO is giving you space"
        _log.info("Suppressed %s: %s", action, reason)
        return Suppression(action=action, reason=reason)

    # ORANGE + low/depleted: don't pile on
    if state.burnout == "ORANGE" and state.energy in ("low", "depleted"):
        reason = f"burnout ORANGE + energy {state.energy} — backing off"
        _log.info("Suppressed %s: %s", action, reason)
        return Suppression(action=action, reason=reason)

    # Low effectiveness: nudges aren't helping, stop sending them
    if action == "nudge":
        if state.nudge_effectiveness < 0.1 and state.nudges_sent_today > 3:
            reason = (
                f"nudge effectiveness {state.nudge_effectiveness:.0%} "
                f"after {state.nudges_sent_today} sent — backing off"
            )
            _log.info("Suppressed %s: %s", action, reason)
            return Suppression(action=action, reason=reason)

    return None
