"""Plasticity layer for OTTO v5.0.

Amplifies trail deposit strength during crisis states so OTTO learns
faster from recovery patterns.  The plasticity window opens when the
user enters RED burnout or CRASHED+ORANGE, and closes after 3 stable
exchanges.

This layer affects LEARNING RATE only, never routing order.

Usage:
    window = PlasticityWindow()
    window.update(state)
    deposit_strength = window.adjust_strength(1.0)  # -> 2.0 if open
"""

from __future__ import annotations

from dataclasses import dataclass

from .log import get_logger
from .state import CognitiveState

_log = get_logger(__name__)

# Number of stable exchanges before the window closes
_STABILITY_THRESHOLD = 3

# Trail deposit multiplier during open window
_AMPLIFICATION = 2.0


@dataclass
class PlasticityWindow:
    """Tracks whether the plasticity window is open.

    The window opens during crisis states (RED burnout or
    CRASHED+ORANGE) and closes after ``_STABILITY_THRESHOLD``
    consecutive exchanges where the crisis has resolved.

    While open, trail deposits are amplified by ``_AMPLIFICATION``
    so OTTO learns faster from what works during recovery.
    """

    is_open: bool = False
    stable_count: int = 0

    @property
    def amplification(self) -> float:
        """Current amplification factor (1.0 when closed)."""
        return _AMPLIFICATION if self.is_open else 1.0

    @staticmethod
    def _is_crisis(state: CognitiveState) -> bool:
        """Check if the current state is a crisis state."""
        if state.burnout == "RED":
            return True
        if state.momentum == "crashed" and state.burnout == "ORANGE":
            return True
        return False

    def update(self, state: CognitiveState) -> None:
        """Update plasticity window based on current cognitive state.

        Call this once per exchange (interaction cycle).
        """
        crisis = self._is_crisis(state)

        if self.is_open:
            if crisis:
                # Still in crisis -- reset stability counter
                self.stable_count = 0
            else:
                # Crisis resolved this exchange
                self.stable_count += 1
                if self.stable_count >= _STABILITY_THRESHOLD:
                    self.is_open = False
                    self.stable_count = 0
                    _log.info(
                        "Plasticity window closed after %d stable exchanges",
                        _STABILITY_THRESHOLD,
                    )
        elif crisis:
            # Entering crisis -- open the window
            self.is_open = True
            self.stable_count = 0
            _log.info(
                "Plasticity window opened: burnout=%s momentum=%s",
                state.burnout,
                state.momentum,
            )

    def adjust_strength(self, base_strength: float) -> float:
        """Adjust trail deposit strength based on plasticity state.

        Parameters
        ----------
        base_strength:
            The base deposit strength (typically 1.0 for success,
            0.3 for park, etc.)

        Returns
        -------
        float
            Amplified strength if window is open, base otherwise.
        """
        return base_strength * self.amplification
