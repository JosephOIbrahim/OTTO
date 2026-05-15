"""Tests for centralized model configuration (T1 foundation).

These guard:
- Default model IDs match Tier 1 design
- Env-var overrides work (rollback path)
- TEMPERATURE stays 0.0 (Patent P1 determinism regression guard)
"""
from __future__ import annotations

import importlib


def _reload_module():
    import otto.model_config as mc
    importlib.reload(mc)
    return mc


def test_detector_model_default(monkeypatch):
    monkeypatch.delenv("OTTO_DETECTOR_MODEL", raising=False)
    mc = _reload_module()
    assert mc.DETECTOR_MODEL == "claude-opus-4-7"


def test_agent_model_default(monkeypatch):
    monkeypatch.delenv("OTTO_AGENT_MODEL", raising=False)
    mc = _reload_module()
    assert mc.AGENT_MODEL == "claude-sonnet-4-6"


def test_response_gen_model_default(monkeypatch):
    monkeypatch.delenv("OTTO_RESPONSE_GEN_MODEL", raising=False)
    mc = _reload_module()
    assert mc.RESPONSE_GEN_MODEL == "claude-haiku-4-5-20251001"


def test_detector_model_env_override(monkeypatch):
    monkeypatch.setenv("OTTO_DETECTOR_MODEL", "claude-sonnet-4-5-20250929")
    mc = _reload_module()
    assert mc.DETECTOR_MODEL == "claude-sonnet-4-5-20250929"


def test_agent_model_env_override(monkeypatch):
    monkeypatch.setenv("OTTO_AGENT_MODEL", "claude-haiku-4-5-20251001")
    mc = _reload_module()
    assert mc.AGENT_MODEL == "claude-haiku-4-5-20251001"


def test_response_gen_model_env_override(monkeypatch):
    monkeypatch.setenv("OTTO_RESPONSE_GEN_MODEL", "claude-opus-4-7")
    mc = _reload_module()
    assert mc.RESPONSE_GEN_MODEL == "claude-opus-4-7"


def test_temperature_zero_for_determinism():
    # Patent P1: deterministic state evolution. Do not raise without
    # constitutional review.
    from otto.model_config import TEMPERATURE
    assert TEMPERATURE == 0.0
