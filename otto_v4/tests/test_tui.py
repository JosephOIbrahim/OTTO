"""Tests for OTTO TUI module."""
from __future__ import annotations

import pytest


def test_tui_module_structure():
    """TUI module must define OttoApp class."""
    try:
        from otto.tui import OttoApp
        assert hasattr(OttoApp, 'compose')
        assert hasattr(OttoApp, 'action_mark_done')
        assert hasattr(OttoApp, 'action_mark_parked')
    except ImportError:
        pytest.skip("textual not installed")
