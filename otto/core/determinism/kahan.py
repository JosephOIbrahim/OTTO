"""Kahan summation accumulator for numerically stable float addition.

Standard floating-point addition accumulates rounding error as O(n*eps).
Kahan's compensated summation bounds total error to O(eps) regardless
of the number of terms, by tracking a running compensation term.

This is required by [He2025] for all float accumulations in OTTO:
pheromone decay aggregation, expert weight sums, trail strengths, etc.

Reference: Kahan, W. (1965). "Pracniques: Further remarks on reducing
truncation errors." Communications of the ACM 8(1):40.
"""

from __future__ import annotations


class KahanAccumulator:
    """Numerically stable floating-point summation.

    Maintains a compensation term that captures the low-order bits
    lost during each addition, feeding them back into the next step.

    Usage::

        acc = KahanAccumulator()
        for value in many_small_floats:
            acc.add(value)
        result = acc.total()
    """

    __slots__ = ("_sum", "_compensation")

    def __init__(self) -> None:
        self._sum: float = 0.0
        self._compensation: float = 0.0

    def add(self, value: float) -> None:
        """Add a value with error compensation.

        The compensation term ``c`` tracks accumulated rounding error:
        ``y = value - c`` recovers bits lost in the previous step,
        ``t = sum + y`` performs the addition, then
        ``c = (t - sum) - y`` captures what was lost THIS step.
        """
        y = value - self._compensation
        t = self._sum + y
        self._compensation = (t - self._sum) - y
        self._sum = t

    def total(self) -> float:
        """Return the compensated sum."""
        return self._sum

    def reset(self) -> None:
        """Reset accumulator to zero."""
        self._sum = 0.0
        self._compensation = 0.0


def kahan_sum(values: list[float]) -> float:
    """Convenience: Kahan-sum a list of floats.

    Args:
        values: Floats to sum. Order matters for reproducibility
            but NOT for accuracy (unlike naive summation).

    Returns:
        Compensated sum.
    """
    acc = KahanAccumulator()
    for v in values:
        acc.add(v)
    return acc.total()
