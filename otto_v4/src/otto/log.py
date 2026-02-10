"""Structured logging for OTTO.

Thin wrapper around stdlib logging. One import, one function.

Usage:
    from otto.log import get_logger
    logger = get_logger(__name__)
    logger.warning("something went wrong: %s", err)
"""

from __future__ import annotations

import logging
import os

_configured = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``otto`` namespace.

    On first call, configures the root ``otto`` logger with a console
    handler.  Level defaults to WARNING; override with the
    ``OTTO_LOG_LEVEL`` environment variable (DEBUG, INFO, WARNING, ERROR).
    """
    global _configured
    if not _configured:
        _configure()
        _configured = True
    return logging.getLogger(name)


def _configure() -> None:
    """Set up the ``otto`` root logger once."""
    root = logging.getLogger("otto")
    if root.handlers:
        return  # already configured (e.g. by tests)

    level_name = os.environ.get("OTTO_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    root.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
