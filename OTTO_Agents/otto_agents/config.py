"""Shared configuration for OTTO agents."""

from __future__ import annotations

import os
from pathlib import Path


def get_default_db_path() -> str:
    """Get OTTO database path. Respects OTTO_DB_PATH env var."""
    return os.getenv("OTTO_DB_PATH") or str(
        Path(os.path.expanduser("~/.otto/commitments.db"))
    )


# Root of the OTTO_OS project
OTTO_OS_ROOT = Path(__file__).resolve().parent.parent.parent

# Path to otto_v4 source
OTTO_V4_DIR = OTTO_OS_ROOT / "otto_v4"

# Path to otto_v4/src (for sys.path injection)
OTTO_V4_SRC = str(OTTO_V4_DIR / "src")
