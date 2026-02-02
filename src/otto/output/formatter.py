"""
Output Formatter Abstraction
============================

Platform-agnostic output formatting to replace ANSI terminal colors.

Supports:
- Plain text (no formatting)
- JSON (structured data for APIs)
- ANSI colors (terminal only, loaded conditionally)

[He2025] Compliance:
- Fixed formatter selection order
- Deterministic output (same state → same formatted string)
- No runtime variation in formatting logic
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import logging
import os

logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """Available output formats."""
    PLAIN = "plain"      # No colors, plain text
    JSON = "json"        # Structured JSON
    ANSI = "ansi"        # Terminal with ANSI colors
    MARKDOWN = "markdown"  # Markdown formatting


@dataclass
class StatusData:
    """
    Status information for formatting.

    Attributes:
        burnout: Burnout level (GREEN, YELLOW, ORANGE, RED)
        momentum: Momentum phase (cold_start, building, rolling, etc.)
        energy: Energy level (high, medium, low, depleted)
        altitude: Current altitude (30000ft, 15000ft, 5000ft, Ground)
        expert: Active expert (Direct, Validator, etc.)
        goal: Session goal
        exchange_count: Number of exchanges
    """
    burnout: str = "GREEN"
    momentum: str = "cold_start"
    energy: str = "medium"
    altitude: str = "30000ft"
    expert: str = "Direct"
    goal: Optional[str] = None
    exchange_count: int = 0


@dataclass
class AlertData:
    """
    Alert information for formatting.

    Attributes:
        level: Alert level (info, warning, error, critical)
        message: Alert message
        timestamp: Optional timestamp
        source: Optional source of alert
    """
    level: str
    message: str
    timestamp: Optional[str] = None
    source: Optional[str] = None


class OutputFormatter(ABC):
    """
    Abstract base class for output formatters.

    Implementations must provide platform-specific formatting
    while maintaining consistent output semantics.
    """

    @property
    @abstractmethod
    def format_type(self) -> OutputFormat:
        """Return the format type."""
        pass

    @abstractmethod
    def format_status(self, status: StatusData) -> str:
        """
        Format status information.

        Args:
            status: StatusData with current state

        Returns:
            Formatted status string
        """
        pass

    @abstractmethod
    def format_alert(self, alert: AlertData) -> str:
        """
        Format an alert message.

        Args:
            alert: AlertData with alert information

        Returns:
            Formatted alert string
        """
        pass

    @abstractmethod
    def format_state(self, state: Dict[str, Any]) -> str:
        """
        Format cognitive state dictionary.

        Args:
            state: Full cognitive state dictionary

        Returns:
            Formatted state string
        """
        pass

    def format_status_line(self, status: StatusData) -> str:
        """
        Format a single-line status (for prompts, status bars).

        Default implementation uses format_status.
        """
        return self.format_status(status)

    def format_dashboard(
        self,
        status: StatusData,
        alerts: List[AlertData],
        state: Dict[str, Any]
    ) -> str:
        """
        Format full dashboard output.

        Default implementation combines status, alerts, and state.
        """
        parts = [self.format_status(status)]

        if alerts:
            parts.append("\nAlerts:")
            for alert in alerts:
                parts.append(self.format_alert(alert))

        parts.append("\nState:")
        parts.append(self.format_state(state))

        return "\n".join(parts)


class PlainFormatter(OutputFormatter):
    """
    Plain text formatter with no colors or styling.

    Safe for all platforms including mobile.
    """

    @property
    def format_type(self) -> OutputFormat:
        return OutputFormat.PLAIN

    def format_status(self, status: StatusData) -> str:
        """Format status as plain text."""
        time_estimate = f"~{(status.exchange_count * 4.5):.0f} min" if status.exchange_count else "start"

        parts = [
            f"[{time_estimate}",
        ]

        if status.goal:
            parts.append(f" | Goal: {status.goal}")

        parts.extend([
            f" | {status.expert}",
            f" | {status.altitude}",
            f" | {status.burnout}",
            f" | {status.momentum}]",
        ])

        return "".join(parts)

    def format_alert(self, alert: AlertData) -> str:
        """Format alert as plain text."""
        prefix = {
            "info": "[INFO]",
            "warning": "[WARN]",
            "error": "[ERROR]",
            "critical": "[CRITICAL]",
        }.get(alert.level.lower(), "[ALERT]")

        parts = [prefix, alert.message]

        if alert.timestamp:
            parts.insert(1, f"[{alert.timestamp}]")

        if alert.source:
            parts.append(f"(from: {alert.source})")

        return " ".join(parts)

    def format_state(self, state: Dict[str, Any]) -> str:
        """Format state as plain text key-value pairs."""
        lines = []
        for key, value in sorted(state.items()):
            if isinstance(value, dict):
                lines.append(f"  {key}:")
                for k, v in sorted(value.items()):
                    lines.append(f"    {k}: {v}")
            elif isinstance(value, list):
                lines.append(f"  {key}: [{', '.join(str(v) for v in value)}]")
            else:
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def format_status_line(self, status: StatusData) -> str:
        """Format compact single-line status."""
        return f"[{status.expert} | {status.altitude} | {status.burnout} | {status.momentum}]"


class JSONFormatter(OutputFormatter):
    """
    JSON formatter for structured output.

    Ideal for APIs, mobile apps, and programmatic access.
    """

    def __init__(self, indent: Optional[int] = None, sort_keys: bool = True):
        """
        Initialize JSON formatter.

        Args:
            indent: JSON indentation (None for compact)
            sort_keys: Sort keys for determinism
        """
        self._indent = indent
        self._sort_keys = sort_keys

    @property
    def format_type(self) -> OutputFormat:
        return OutputFormat.JSON

    def _to_json(self, data: Any) -> str:
        """Convert to JSON string with configured options."""
        return json.dumps(
            data,
            indent=self._indent,
            sort_keys=self._sort_keys,
            default=str  # Handle non-serializable types
        )

    def format_status(self, status: StatusData) -> str:
        """Format status as JSON."""
        return self._to_json({
            "type": "status",
            "burnout": status.burnout,
            "momentum": status.momentum,
            "energy": status.energy,
            "altitude": status.altitude,
            "expert": status.expert,
            "goal": status.goal,
            "exchange_count": status.exchange_count,
            "time_estimate_min": int(status.exchange_count * 4.5),
        })

    def format_alert(self, alert: AlertData) -> str:
        """Format alert as JSON."""
        return self._to_json({
            "type": "alert",
            "level": alert.level,
            "message": alert.message,
            "timestamp": alert.timestamp,
            "source": alert.source,
        })

    def format_state(self, state: Dict[str, Any]) -> str:
        """Format state as JSON."""
        return self._to_json({
            "type": "state",
            "data": state,
        })

    def format_status_line(self, status: StatusData) -> str:
        """Format compact JSON status."""
        return self._to_json({
            "expert": status.expert,
            "altitude": status.altitude,
            "burnout": status.burnout,
            "momentum": status.momentum,
        })

    def format_dashboard(
        self,
        status: StatusData,
        alerts: List[AlertData],
        state: Dict[str, Any]
    ) -> str:
        """Format full dashboard as single JSON object."""
        return self._to_json({
            "type": "dashboard",
            "status": {
                "burnout": status.burnout,
                "momentum": status.momentum,
                "energy": status.energy,
                "altitude": status.altitude,
                "expert": status.expert,
                "goal": status.goal,
                "exchange_count": status.exchange_count,
            },
            "alerts": [
                {
                    "level": a.level,
                    "message": a.message,
                    "timestamp": a.timestamp,
                    "source": a.source,
                }
                for a in alerts
            ],
            "state": state,
        })


# =============================================================================
# Global Instance
# =============================================================================

_formatter: Optional[OutputFormatter] = None


def get_formatter() -> OutputFormatter:
    """
    Get the global output formatter instance.

    Creates PlainFormatter by default. Use OTTO_OUTPUT_FORMAT env var
    to set default: 'plain', 'json', 'ansi'.
    """
    global _formatter
    if _formatter is None:
        _formatter = _create_default_formatter()
    return _formatter


def _create_default_formatter() -> OutputFormatter:
    """
    Create default formatter based on environment.

    [He2025] Fixed selection order: env var → plain
    """
    format_env = os.environ.get("OTTO_OUTPUT_FORMAT", "").lower()

    if format_env == "json":
        logger.debug("Using JSON formatter from environment")
        return JSONFormatter(indent=2)
    elif format_env == "ansi":
        # ANSI formatter would be loaded conditionally for desktop
        # For now, fall back to plain
        logger.debug("ANSI formatter requested but using plain (mobile-safe)")
        return PlainFormatter()
    else:
        logger.debug("Using plain formatter (default)")
        return PlainFormatter()


def set_formatter(formatter: OutputFormatter) -> None:
    """
    Set the global output formatter.

    Useful for testing or platform-specific configuration.
    """
    global _formatter
    _formatter = formatter


def reset_formatter() -> None:
    """Reset global formatter (for testing)."""
    global _formatter
    _formatter = None
