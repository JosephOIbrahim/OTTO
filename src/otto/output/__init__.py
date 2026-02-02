"""
OTTO OS Output Abstraction Layer
================================

Platform-agnostic output formatting for mobile builds.

Components:
- OutputFormatter: Abstract base for output formatting
- PlainFormatter: No colors, plain text
- JSONFormatter: Structured JSON output
- ANSIFormatter: Terminal with ANSI colors (desktop only)

[He2025] Compliance:
- Fixed format selection order
- Deterministic formatting (same state → same output)
- No runtime variation

Usage:
    from otto.output import get_formatter, set_formatter, PlainFormatter

    # Get current formatter
    formatter = get_formatter()
    output = formatter.format_state(state)

    # Use specific formatter
    set_formatter(PlainFormatter())
"""

from .formatter import (
    OutputFormatter,
    OutputFormat,
    PlainFormatter,
    JSONFormatter,
    StatusData,
    AlertData,
    get_formatter,
    set_formatter,
    reset_formatter,
)

__all__ = [
    "OutputFormatter",
    "OutputFormat",
    "PlainFormatter",
    "JSONFormatter",
    "StatusData",
    "AlertData",
    "get_formatter",
    "set_formatter",
    "reset_formatter",
]
