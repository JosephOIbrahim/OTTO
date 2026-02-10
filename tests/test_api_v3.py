"""Tests for the Opus 4.6 API integration layer (Days 8-9).

Tests cover:
    - EffortLevel enum and EffortController logic
    - CostEstimate with gate thresholds
    - OTTOClient with mock Anthropic SDK
    - NEXUSPipeline (dry_run + full call)
    - CompactionManager token tracking
    - Expert voice constitutional checks
    - Determinism (100× same input → same result)
    - Import completeness

All tests use mock API clients — no real Anthropic API calls.
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass


# ─── Mock Anthropic SDK objects ───────────────────────────────────


@dataclass
class MockUsage:
    """Mimics anthropic.types.Usage."""

    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class MockContentBlock:
    """Mimics anthropic.types.ContentBlock."""

    type: str = "text"
    text: str = "Hello, I'm OTTO."


@dataclass
class MockMessage:
    """Mimics anthropic.types.Message."""

    content: list | None = None
    model: str = "claude-opus-4-6"
    usage: MockUsage | None = None
    stop_reason: str = "end_turn"

    def __post_init__(self) -> None:
        if self.content is None:
            self.content = [MockContentBlock()]
        if self.usage is None:
            self.usage = MockUsage()


class MockMessagesClient:
    """Mock for ``anthropic.Anthropic().messages``.

    Records the last ``create()`` call kwargs for assertion.
    """

    def __init__(self, response: MockMessage | None = None) -> None:
        self.last_kwargs: dict = {}
        self._response = response or MockMessage()

    def create(self, **kwargs: object) -> MockMessage:
        self.last_kwargs = dict(kwargs)
        return self._response


# ═══════════════════════════════════════════════════════════════════
# EffortLevel
# ═══════════════════════════════════════════════════════════════════

from otto.api.effort import EffortLevel, EffortController, CostEstimate


class TestEffortLevel:
    """Verify EffortLevel enum maps to correct API strings."""

    def test_low_value(self) -> None:
        assert EffortLevel.LOW.value == "low"

    def test_medium_value(self) -> None:
        assert EffortLevel.MEDIUM.value == "medium"

    def test_high_value(self) -> None:
        assert EffortLevel.HIGH.value == "high"

    def test_max_value(self) -> None:
        assert EffortLevel.MAX.value == "max"

    def test_all_levels_are_strings(self) -> None:
        for level in EffortLevel:
            assert isinstance(level.value, str)


# ═══════════════════════════════════════════════════════════════════
# EffortController
# ═══════════════════════════════════════════════════════════════════


class TestEffortControllerSelection:
    """Verify effort selection logic (first-match-wins rules)."""

    def setup_method(self) -> None:
        self.ctrl = EffortController()

    def test_protector_primary_gets_high(self) -> None:
        assert self.ctrl.select_effort("protector") == EffortLevel.HIGH

    def test_restorer_primary_gets_high(self) -> None:
        assert self.ctrl.select_effort("restorer") == EffortLevel.HIGH

    def test_agent_team_gets_high(self) -> None:
        result = self.ctrl.select_effort("executor", use_agent_team=True)
        assert result == EffortLevel.HIGH

    def test_many_signals_gets_medium(self) -> None:
        result = self.ctrl.select_effort("executor", signal_count=3)
        assert result == EffortLevel.MEDIUM

    def test_default_gets_low(self) -> None:
        assert self.ctrl.select_effort("executor") == EffortLevel.LOW

    def test_override_wins_over_all(self) -> None:
        result = self.ctrl.select_effort(
            "protector",
            use_agent_team=True,
            signal_count=5,
            override=EffortLevel.MAX,
        )
        assert result == EffortLevel.MAX

    def test_override_can_lower(self) -> None:
        result = self.ctrl.select_effort(
            "protector", override=EffortLevel.LOW,
        )
        assert result == EffortLevel.LOW

    def test_guide_default_low(self) -> None:
        assert self.ctrl.select_effort("guide") == EffortLevel.LOW

    def test_decomposer_with_team_gets_high(self) -> None:
        result = self.ctrl.select_effort("decomposer", use_agent_team=True)
        assert result == EffortLevel.HIGH


# ═══════════════════════════════════════════════════════════════════
# CostEstimate
# ═══════════════════════════════════════════════════════════════════


class TestCostEstimate:
    """Verify cost estimation and gate thresholds."""

    def setup_method(self) -> None:
        self.ctrl = EffortController(
            input_cost_per_m=5.0, output_cost_per_m=25.0,
        )

    def test_auto_gate_small_cost(self) -> None:
        # 1000/1M * $5 + 500/1M * $25 = $0.005 + $0.0125 = $0.0175
        est = self.ctrl.estimate_cost(1_000, 500)
        assert est.gate == "auto"
        assert est.estimated_usd == pytest.approx(0.0175)

    def test_warn_gate_medium_cost(self) -> None:
        # 10000/1M*5 + 3000/1M*25 = 0.05 + 0.075 = 0.125
        est = self.ctrl.estimate_cost(10_000, 3_000)
        assert est.gate == "warn"
        assert est.estimated_usd == pytest.approx(0.125)

    def test_confirm_gate_large_cost(self) -> None:
        # 50000/1M*5 + 10000/1M*25 = 0.25 + 0.25 = 0.50
        est = self.ctrl.estimate_cost(50_000, 10_000)
        assert est.gate == "confirm"
        assert est.estimated_usd == pytest.approx(0.50)

    def test_cost_estimate_is_frozen(self) -> None:
        est = self.ctrl.estimate_cost(100, 100)
        with pytest.raises(AttributeError):
            est.gate = "auto"  # type: ignore[misc]

    def test_tokens_preserved(self) -> None:
        est = self.ctrl.estimate_cost(42, 99)
        assert est.input_tokens == 42
        assert est.output_tokens == 99

    def test_zero_cost(self) -> None:
        est = self.ctrl.estimate_cost(0, 0)
        assert est.estimated_usd == 0.0
        assert est.gate == "auto"


# ═══════════════════════════════════════════════════════════════════
# ModelConfig + APIResponse
# ═══════════════════════════════════════════════════════════════════

from otto.api.client import ModelConfig, OPUS_46_CONFIG, APIResponse, OTTOClient


class TestModelConfig:
    """Verify model configuration defaults and immutability."""

    def test_defaults(self) -> None:
        cfg = ModelConfig()
        assert cfg.model == "claude-opus-4-6"
        assert cfg.max_output_tokens == 128_000
        assert cfg.max_context_tokens == 1_000_000
        assert cfg.input_cost_per_m == 5.0
        assert cfg.output_cost_per_m == 25.0

    def test_opus_46_preset(self) -> None:
        assert OPUS_46_CONFIG.model == "claude-opus-4-6"

    def test_frozen(self) -> None:
        cfg = ModelConfig()
        with pytest.raises(AttributeError):
            cfg.model = "other"  # type: ignore[misc]


class TestAPIResponse:
    """Verify API response is frozen and fields accessible."""

    def test_frozen(self) -> None:
        resp = APIResponse(
            content="hello", model="m",
            input_tokens=1, output_tokens=2,
            stop_reason="end_turn",
        )
        with pytest.raises(AttributeError):
            resp.content = "changed"  # type: ignore[misc]

    def test_fields(self) -> None:
        resp = APIResponse(
            content="text", model="opus",
            input_tokens=10, output_tokens=20,
            stop_reason="end_turn",
        )
        assert resp.content == "text"
        assert resp.model == "opus"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 20
        assert resp.stop_reason == "end_turn"


# ═══════════════════════════════════════════════════════════════════
# OTTOClient
# ═══════════════════════════════════════════════════════════════════


class TestOTTOClient:
    """Verify client wrapping, normalization, and kwarg passthrough."""

    def test_config_default(self) -> None:
        client = OTTOClient(raw_client=MockMessagesClient())
        assert client.config == OPUS_46_CONFIG

    def test_config_custom(self) -> None:
        cfg = ModelConfig(model="custom")
        client = OTTOClient(config=cfg, raw_client=MockMessagesClient())
        assert client.config.model == "custom"

    def test_send_basic(self) -> None:
        mock = MockMessagesClient()
        client = OTTOClient(raw_client=mock)
        resp = client.send(messages=[{"role": "user", "content": "hi"}])

        assert resp.content == "Hello, I'm OTTO."
        assert resp.model == "claude-opus-4-6"
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.stop_reason == "end_turn"

    def test_send_passes_model(self) -> None:
        mock = MockMessagesClient()
        client = OTTOClient(raw_client=mock)
        client.send(messages=[{"role": "user", "content": "hi"}])
        assert mock.last_kwargs["model"] == "claude-opus-4-6"

    def test_send_passes_system(self) -> None:
        mock = MockMessagesClient()
        client = OTTOClient(raw_client=mock)
        client.send(
            messages=[{"role": "user", "content": "hi"}],
            system="Be nice.",
        )
        assert mock.last_kwargs["system"] == "Be nice."

    def test_send_no_system_if_none(self) -> None:
        mock = MockMessagesClient()
        client = OTTOClient(raw_client=mock)
        client.send(messages=[{"role": "user", "content": "hi"}])
        assert "system" not in mock.last_kwargs

    def test_send_passes_effort(self) -> None:
        mock = MockMessagesClient()
        client = OTTOClient(raw_client=mock)
        client.send(
            messages=[{"role": "user", "content": "hi"}],
            effort="high",
        )
        assert mock.last_kwargs["effort"] == "high"

    def test_send_no_effort_if_none(self) -> None:
        mock = MockMessagesClient()
        client = OTTOClient(raw_client=mock)
        client.send(messages=[{"role": "user", "content": "hi"}])
        assert "effort" not in mock.last_kwargs

    def test_send_passes_max_tokens(self) -> None:
        mock = MockMessagesClient()
        client = OTTOClient(raw_client=mock)
        client.send(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=500,
        )
        assert mock.last_kwargs["max_tokens"] == 500

    def test_send_default_max_tokens(self) -> None:
        mock = MockMessagesClient()
        client = OTTOClient(raw_client=mock)
        client.send(messages=[{"role": "user", "content": "hi"}])
        assert mock.last_kwargs["max_tokens"] == 128_000

    def test_normalize_multi_block(self) -> None:
        """Multiple content blocks are concatenated."""
        mock_resp = MockMessage(
            content=[
                MockContentBlock(text="Part 1. "),
                MockContentBlock(text="Part 2."),
            ],
        )
        mock = MockMessagesClient(response=mock_resp)
        client = OTTOClient(raw_client=mock)
        resp = client.send(messages=[{"role": "user", "content": "hi"}])
        assert resp.content == "Part 1. Part 2."

    def test_normalize_empty_content(self) -> None:
        """Empty content list → empty string."""
        mock_resp = MockMessage(content=[])
        mock = MockMessagesClient(response=mock_resp)
        client = OTTOClient(raw_client=mock)
        resp = client.send(messages=[{"role": "user", "content": "hi"}])
        assert resp.content == ""

    def test_response_is_frozen(self) -> None:
        mock = MockMessagesClient()
        client = OTTOClient(raw_client=mock)
        resp = client.send(messages=[{"role": "user", "content": "hi"}])
        with pytest.raises(AttributeError):
            resp.content = "changed"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════
# Expert Voices
# ═══════════════════════════════════════════════════════════════════

from otto.api.nexus import (
    EXPERT_VOICES,
    build_system_prompt,
    NEXUSPipeline,
    PipelineResult,
    _BASE_SYSTEM_PREFIX,
)
from otto.core.experts.base import ExpertWeight, ExpertSelection


class TestExpertVoices:
    """Constitutional checks on expert voice descriptions."""

    def test_all_seven_experts_covered(self) -> None:
        expected = {
            "acknowledger", "decomposer", "executor", "guide",
            "protector", "redirector", "restorer",
        }
        assert set(EXPERT_VOICES.keys()) == expected

    def test_sorted_keys(self) -> None:
        keys = list(EXPERT_VOICES.keys())
        assert keys == sorted(keys), "EXPERT_VOICES must be sorted [He2025]"

    def test_no_clinical_language(self) -> None:
        """Constitutional: no clinical language in user-facing strings."""
        banned = [
            "adhd", "executive dysfunction", "neurodivergent deficit",
            "your adhd", "disorder", "diagnosis",
        ]
        for expert, voice in sorted(EXPERT_VOICES.items()):
            lower = voice.lower()
            for term in banned:
                assert term not in lower, (
                    f"Clinical language '{term}' found in {expert} voice"
                )

    def test_no_minimizing_language(self) -> None:
        """Constitutional: never use 'just' or 'simply' standalone."""
        for expert, voice in sorted(EXPERT_VOICES.items()):
            words = voice.lower().split()
            # Filter to standalone words (strip punctuation)
            clean_words = [
                w.strip(".,!?;:'\"()") for w in words
            ]
            assert "just" not in clean_words, (
                f"Minimizing word 'just' found in {expert} voice"
            )
            assert "simply" not in clean_words, (
                f"Minimizing word 'simply' found in {expert} voice"
            )

    def test_voices_are_non_empty(self) -> None:
        for expert, voice in sorted(EXPERT_VOICES.items()):
            assert len(voice) > 20, f"{expert} voice is too short"


# ═══════════════════════════════════════════════════════════════════
# build_system_prompt
# ═══════════════════════════════════════════════════════════════════


class TestBuildSystemPrompt:
    """Verify system prompt construction from expert selection."""

    def test_includes_base_prefix(self) -> None:
        selection = ExpertSelection(
            primary=ExpertWeight(expert="executor", value=0.5),
            supporting=(),
            use_agent_team=False,
        )
        prompt = build_system_prompt(selection)
        assert _BASE_SYSTEM_PREFIX in prompt

    def test_includes_primary_voice(self) -> None:
        selection = ExpertSelection(
            primary=ExpertWeight(expert="protector", value=0.8),
            supporting=(),
            use_agent_team=False,
        )
        prompt = build_system_prompt(selection)
        assert "PRIMARY MODE (protector)" in prompt
        assert "emotional and cognitive safety" in prompt

    def test_includes_supporting_voices(self) -> None:
        selection = ExpertSelection(
            primary=ExpertWeight(expert="protector", value=0.8),
            supporting=(
                ExpertWeight(expert="decomposer", value=0.3),
            ),
            use_agent_team=True,
        )
        prompt = build_system_prompt(selection)
        assert "SUPPORTING (decomposer)" in prompt

    def test_multiple_supporting(self) -> None:
        selection = ExpertSelection(
            primary=ExpertWeight(expert="protector", value=0.8),
            supporting=(
                ExpertWeight(expert="decomposer", value=0.3),
                ExpertWeight(expert="restorer", value=0.25),
            ),
            use_agent_team=True,
        )
        prompt = build_system_prompt(selection)
        assert "SUPPORTING (decomposer)" in prompt
        assert "SUPPORTING (restorer)" in prompt

    def test_unknown_expert_no_crash(self) -> None:
        selection = ExpertSelection(
            primary=ExpertWeight(expert="unknown_expert", value=0.5),
            supporting=(),
            use_agent_team=False,
        )
        prompt = build_system_prompt(selection)
        assert _BASE_SYSTEM_PREFIX in prompt

    def test_otto_identity_in_prefix(self) -> None:
        selection = ExpertSelection(
            primary=ExpertWeight(expert="executor", value=0.5),
            supporting=(),
            use_agent_team=False,
        )
        prompt = build_system_prompt(selection)
        assert "OTTO" in prompt
        assert "neurodivergent" in prompt


# ═══════════════════════════════════════════════════════════════════
# NEXUSPipeline
# ═══════════════════════════════════════════════════════════════════


class TestNEXUSPipeline:
    """Verify the full detect → route → call pipeline."""

    def setup_method(self) -> None:
        self.mock = MockMessagesClient()
        self.client = OTTOClient(raw_client=self.mock)
        self.pipeline = NEXUSPipeline(client=self.client)

    def test_dry_run_no_api_call(self) -> None:
        result = self.pipeline.process("hello", dry_run=True)
        assert result.response is None
        assert self.mock.last_kwargs == {}

    def test_dry_run_has_signals(self) -> None:
        result = self.pipeline.process(
            "I'm so stuck and blocked", dry_run=True,
        )
        assert len(result.signals) > 0

    def test_dry_run_has_selection(self) -> None:
        result = self.pipeline.process("hello", dry_run=True)
        assert result.selection is not None
        assert result.selection.primary is not None

    def test_dry_run_has_effort(self) -> None:
        result = self.pipeline.process("hello", dry_run=True)
        assert isinstance(result.effort, EffortLevel)

    def test_dry_run_has_system_prompt(self) -> None:
        result = self.pipeline.process("hello", dry_run=True)
        assert "OTTO" in result.system_prompt

    def test_frustrated_routes_to_protector(self) -> None:
        result = self.pipeline.process(
            "I CAN'T DO THIS ANYMORE", dry_run=True,
        )
        assert result.selection.primary.expert == "protector"

    def test_frustrated_gets_high_effort(self) -> None:
        result = self.pipeline.process(
            "I CAN'T DO THIS ANYMORE", dry_run=True,
        )
        assert result.effort == EffortLevel.HIGH

    def test_full_call_with_mock(self) -> None:
        result = self.pipeline.process("hello there")
        assert result.response is not None
        assert result.response.content == "Hello, I'm OTTO."
        assert result.response.model == "claude-opus-4-6"

    def test_full_call_passes_system_prompt(self) -> None:
        self.pipeline.process("hello there")
        assert "system" in self.mock.last_kwargs
        assert "OTTO" in self.mock.last_kwargs["system"]

    def test_full_call_passes_effort(self) -> None:
        self.pipeline.process("hello there")
        assert "effort" in self.mock.last_kwargs

    def test_conversation_history_included(self) -> None:
        history = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "response"},
        ]
        self.pipeline.process("second", conversation=history)
        msgs = self.mock.last_kwargs["messages"]
        assert len(msgs) == 3
        assert msgs[0]["content"] == "first"
        assert msgs[2]["content"] == "second"

    def test_effort_override(self) -> None:
        result = self.pipeline.process(
            "hello",
            effort_override=EffortLevel.MAX,
            dry_run=True,
        )
        assert result.effort == EffortLevel.MAX

    def test_state_affects_routing(self) -> None:
        """Burnout state should boost protector/restorer."""
        result = self.pipeline.process(
            "what should I do?",
            state={"burnout": "red"},
            dry_run=True,
        )
        # RED burnout boosts protector by 0.30 (STATE_BOOSTS)
        assert result.selection.primary.expert == "protector"


# ═══════════════════════════════════════════════════════════════════
# CompactionManager
# ═══════════════════════════════════════════════════════════════════

from otto.api.compaction import (
    CompactionConfig, CompactionManager, CompactionStatus,
)


class TestCompactionConfig:
    """Verify compaction config defaults and immutability."""

    def test_defaults(self) -> None:
        cfg = CompactionConfig()
        assert cfg.max_context_tokens == 1_000_000
        assert cfg.compaction_threshold == 0.80
        assert cfg.min_exchanges_before_compaction == 5

    def test_frozen(self) -> None:
        cfg = CompactionConfig()
        with pytest.raises(AttributeError):
            cfg.max_context_tokens = 500  # type: ignore[misc]


class TestCompactionManager:
    """Verify token tracking, threshold detection, and reset."""

    def test_initial_status(self) -> None:
        mgr = CompactionManager()
        status = mgr.status()
        assert status.total_tokens == 0.0
        assert status.exchange_count == 0
        assert status.should_compact is False
        assert status.utilization == 0.0

    def test_record_exchange_tracks_tokens(self) -> None:
        mgr = CompactionManager()
        status = mgr.record_exchange(100, 50)
        assert status.total_tokens == 150.0
        assert status.exchange_count == 1

    def test_multiple_exchanges_accumulate(self) -> None:
        mgr = CompactionManager()
        mgr.record_exchange(100, 50)
        status = mgr.record_exchange(200, 100)
        assert status.total_tokens == 450.0
        assert status.exchange_count == 2

    def test_compaction_triggers_at_threshold(self) -> None:
        cfg = CompactionConfig(
            max_context_tokens=1000,
            compaction_threshold=0.80,
            min_exchanges_before_compaction=2,
        )
        mgr = CompactionManager(config=cfg)
        mgr.record_exchange(300, 100)  # 400 total, 1 exchange
        status = mgr.record_exchange(300, 200)  # 900 total, >= 800 threshold
        assert status.should_compact is True

    def test_no_compact_before_min_exchanges(self) -> None:
        cfg = CompactionConfig(
            max_context_tokens=1000,
            compaction_threshold=0.80,
            min_exchanges_before_compaction=5,
        )
        mgr = CompactionManager(config=cfg)
        status = mgr.record_exchange(900, 100)  # 1000, but only 1 exchange
        assert status.should_compact is False

    def test_reset_clears_tokens(self) -> None:
        mgr = CompactionManager()
        mgr.record_exchange(50_000, 50_000)
        mgr.reset()
        status = mgr.status()
        assert status.total_tokens == 0.0
        assert status.exchange_count == 0

    def test_utilization_calculation(self) -> None:
        cfg = CompactionConfig(max_context_tokens=1000)
        mgr = CompactionManager(config=cfg)
        mgr.record_exchange(250, 250)
        status = mgr.status()
        assert status.utilization == pytest.approx(0.5)

    def test_threshold_tokens_value(self) -> None:
        cfg = CompactionConfig(
            max_context_tokens=1000, compaction_threshold=0.80,
        )
        mgr = CompactionManager(config=cfg)
        status = mgr.status()
        assert status.threshold_tokens == 800

    def test_kahan_stability_many_exchanges(self) -> None:
        """Many small exchanges accumulate precisely via Kahan."""
        mgr = CompactionManager()
        for _ in range(10_000):
            mgr.record_exchange(1, 0)
        status = mgr.status()
        assert status.total_tokens == 10_000.0  # Exact

    def test_status_frozen(self) -> None:
        mgr = CompactionManager()
        status = mgr.status()
        with pytest.raises(AttributeError):
            status.total_tokens = 999.0  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════
# Determinism
# ═══════════════════════════════════════════════════════════════════


class TestAPIDeterminism:
    """Same inputs must produce identical outputs [He2025]."""

    def test_same_input_same_pipeline_result_100x(self) -> None:
        """100 identical runs produce identical routing results."""
        mock = MockMessagesClient()
        client = OTTOClient(raw_client=mock)

        first: PipelineResult | None = None
        for _ in range(100):
            pipeline = NEXUSPipeline(client=client)
            result = pipeline.process(
                "I'm stuck and frustrated", dry_run=True,
            )

            if first is None:
                first = result
            else:
                assert (
                    result.selection.primary.expert
                    == first.selection.primary.expert
                )
                assert (
                    result.selection.primary.value
                    == first.selection.primary.value
                )
                assert result.effort == first.effort
                assert len(result.signals) == len(first.signals)
                for s1, s2 in zip(
                    sorted(result.signals, key=lambda s: s.type.name),
                    sorted(first.signals, key=lambda s: s.type.name),
                ):
                    assert s1.type == s2.type
                    assert s1.confidence == s2.confidence

    def test_effort_selection_deterministic(self) -> None:
        """Same routing params → same effort, 100 times."""
        ctrl = EffortController()
        first = ctrl.select_effort("protector", use_agent_team=True)
        for _ in range(100):
            assert ctrl.select_effort("protector", use_agent_team=True) == first


# ═══════════════════════════════════════════════════════════════════
# Import completeness
# ═══════════════════════════════════════════════════════════════════


class TestAPIImports:
    """Verify all public API exports are accessible."""

    def test_all_exports_importable(self) -> None:
        from otto.api import __all__
        import otto.api as api_module

        for name in __all__:
            assert hasattr(api_module, name), f"Missing export: {name}"

    def test_key_types_importable(self) -> None:
        from otto.api import (
            OTTOClient,
            APIResponse,
            ModelConfig,
            EffortLevel,
            EffortController,
            CostEstimate,
            NEXUSPipeline,
            PipelineResult,
            CompactionManager,
            CompactionConfig,
            CompactionStatus,
        )
        # All imported successfully — just verify they're real types
        assert OTTOClient is not None
        assert CompactionStatus is not None
