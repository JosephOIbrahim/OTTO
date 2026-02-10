"""Service base types — protocol, signals, and registry.

Defines the OTTOService protocol that all ambient intelligence
services implement, and CategoricalSignal — the privacy-safe data
type that crosses the privacy boundary (Patent Claim #3).

Privacy boundary::

    RAW (inside service)              →  CATEGORICAL (safe to process)
    ════════════════════════════════════════════════════════════════
    47 open browser tabs              →  overwhelm: HIGH
    stackoverflow.com visited 12×     →  stuck_signal: TECHNICAL
    Typing speed: 45 → 28 WPM        →  energy: DECLINING
    Calendar: "1:1 with Sarah 3pm"    →  commitment: MEETING_SOON

Raw data stays inside the service.  Only CategoricalSignal objects
leave.  This is constitutional.

[He2025]: ServiceRegistry iterates services in sorted name order.
Signals returned in sorted (source, category, value) order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CategoricalSignal:
    """A privacy-safe categorical signal.

    This is what crosses the privacy boundary.  It contains NO raw
    data — only categorical abstractions safe for downstream
    processing (PRISM, NEXUS, API layer).

    Attributes:
        category: Signal category (e.g., ``"time_period"``,
            ``"energy"``, ``"overwhelm"``).
        value: Categorical value (e.g., ``"morning"``,
            ``"declining"``, ``"high"``).
        confidence: Confidence in this signal (0.0–1.0).
        source: Name of the service that produced it.
        timestamp: When the signal was produced.
    """

    category: str
    value: str
    confidence: float
    source: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


@runtime_checkable
class OTTOService(Protocol):
    """Protocol for ambient intelligence services.

    Every OS service implements this interface.  Services:

    1. Start/stop cleanly (idempotent)
    2. Produce CategoricalSignal objects (privacy-safe)
    3. Never expose raw data through ``get_signals()``

    The privacy boundary is enforced at the service level —
    services transform raw observations into categorical abstractions.
    """

    @property
    def name(self) -> str:
        """Unique service identifier."""
        ...

    @property
    def tier(self) -> int:
        """Service tier (1=core, 2=enrichment, 3=advanced)."""
        ...

    @property
    def running(self) -> bool:
        """Whether the service is currently running."""
        ...

    def start(self) -> None:
        """Start the service. Idempotent."""
        ...

    def stop(self) -> None:
        """Stop the service. Idempotent."""
        ...

    def get_signals(self) -> list[CategoricalSignal]:
        """Get current categorical signals.

        Returns ONLY privacy-safe categorical abstractions.
        Raw data never leaves the service.

        [He2025]: Signals returned in sorted order by
        ``(category, value)``.
        """
        ...


class ServiceRegistry:
    """Registry of all active services.

    Manages service lifecycle and collects signals from all
    registered services.

    [He2025]: Services are iterated in sorted name order.
    Signals returned in sorted ``(source, category, value)`` order.
    """

    def __init__(self) -> None:
        self._services: dict[str, OTTOService] = {}

    def register(self, service: OTTOService) -> None:
        """Register a service.

        Args:
            service: Any object satisfying the OTTOService protocol.
        """
        self._services[service.name] = service

    def start_all(self) -> None:
        """Start all registered services.

        [He2025]: Started in sorted name order.
        """
        for name in sorted(self._services.keys()):
            self._services[name].start()

    def stop_all(self) -> None:
        """Stop all registered services.

        [He2025]: Stopped in sorted name order.
        """
        for name in sorted(self._services.keys()):
            self._services[name].stop()

    def get_all_signals(self) -> list[CategoricalSignal]:
        """Collect signals from all running services.

        Only queries services whose ``running`` property is True.

        [He2025]: Services queried in sorted name order.
        Signals sorted by ``(source, category, value)``.

        Returns:
            Merged list of CategoricalSignals from all running
            services.
        """
        all_signals: list[CategoricalSignal] = []
        for name in sorted(self._services.keys()):
            service = self._services[name]
            if service.running:
                all_signals.extend(service.get_signals())

        return sorted(
            all_signals,
            key=lambda s: (s.source, s.category, s.value),
        )

    @property
    def services(self) -> list[OTTOService]:
        """All registered services, sorted by name."""
        return [
            self._services[name]
            for name in sorted(self._services.keys())
        ]

    def count(self) -> int:
        """Number of registered services."""
        return len(self._services)
