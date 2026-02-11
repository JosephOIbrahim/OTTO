"""Mode protocol for OTTO's specialist modes.

Every mode implements four methods:
  - responds_to: does this mode activate for these signals?
  - weight: how strongly should this mode run? (0.0-1.0)
  - execute: primary mode action
  - augment: secondary support action (modify another mode's output)

Safety floors are enforced by NEXUS routing, not by modes themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from otto.signals import Signal
from otto.state import CognitiveState


@dataclass
class ModeResponse:
    """Output from a mode's execute() or augment() method.

    Attributes
    ----------
    text:
        Human-facing output text.
    suppress_others:
        If True, this mode's output replaces all other mode output.
        Only the Protector should set this.
    metadata:
        Arbitrary key-value data for downstream processing.
    """

    text: str
    suppress_others: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class Mode(Protocol):
    """Protocol all specialist modes must implement."""

    @property
    def name(self) -> str:
        """Unique mode identifier (e.g. 'protector', 'executor')."""
        ...

    @property
    def safety_floor(self) -> float:
        """Minimum weight this mode always receives (0.0 for optional modes)."""
        ...

    def responds_to(self, signals: list[Signal]) -> bool:
        """Return True if this mode activates for the given signals."""
        ...

    def weight(self, signals: list[Signal], state: CognitiveState) -> float:
        """Score this mode's relevance (0.0-1.0) given signals and state."""
        ...

    def execute(
        self, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        """Primary mode action. Returns the mode's response."""
        ...

    def augment(
        self, response: ModeResponse, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        """Modify another mode's response as a supporting mode.

        Default: return the response unchanged.
        """
        ...
