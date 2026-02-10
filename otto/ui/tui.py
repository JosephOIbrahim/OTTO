"""Terminal UI skeleton — Textual app structure.

Defines the TUI layout entry point.  Textual is an optional
dependency — if not installed, ``run()`` raises ImportError
with a helpful message.

The TUI wraps the platform-agnostic ChatSession and DashboardState
modules.  All logic lives in those modules; this is rendering only.
"""

from __future__ import annotations

from typing import Any


def run(**kwargs: Any) -> None:
    """Launch the OTTO TUI.

    Requires the ``textual`` package::

        pip install otto-os[tui]

    Raises:
        ImportError: If textual is not installed.
        NotImplementedError: TUI rendering is not yet wired up.
    """
    try:
        import textual  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "The TUI requires the 'textual' package. "
            "Install it with: pip install otto-os[tui]"
        ) from exc

    # TUI rendering will be implemented here.
    # The core components (ChatSession, DashboardState) are fully
    # functional and tested — visual rendering is the next step.
    raise NotImplementedError(
        "TUI rendering is not yet implemented. "
        "Use the MCP interface or import ChatSession directly."
    )
