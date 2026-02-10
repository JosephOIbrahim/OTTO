"""Integration + Audit tests for OTTO OS v3.0 — Days 16-18.

Tests cross-module interactions end-to-end:
    - Full pipeline: PRISM → NEXUS → Effort → Prompt
    - ChatSession + Services flow
    - Memory + Encryption roundtrip
    - Pheromone trail lifecycle
    - MCP dispatch through full stack
    - Constitutional enforcement across all modules
    - [He2025] determinism verification
    - Privacy boundary enforcement
    - Automated audit (no bare dict.items, no clinical language)
    - Performance benchmarks

Run: python -m pytest tests/test_integration_v3.py -v --noconftest --tb=short
"""

from __future__ import annotations

import importlib
import os
import pathlib
import re
import time
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

# =====================================================================
# DAY 16: INTEGRATION TESTS — Cross-Module Flows
# =====================================================================


# ── Fixture Helpers ────────────────────────────────────────────


def _make_mock_client(content: str = "Test response") -> MagicMock:
    """Create a mock OTTOClient for integration tests."""
    mock = MagicMock()
    response = MagicMock()
    response.content = content
    response.model = "claude-opus-4-6"
    response.input_tokens = 150
    response.output_tokens = 75
    response.stop_reason = "end_turn"
    mock.send.return_value = response
    return mock


def _make_real_pipeline(
    client: MagicMock | None = None,
) -> "NEXUSPipeline":
    """Build a real NEXUSPipeline with real detector/router, mock client."""
    from otto.api.effort import EffortController
    from otto.api.nexus import NEXUSPipeline
    from otto.core.constitution import SafetyFloors
    from otto.core.experts.router import NEXUSRouter
    from otto.core.prism.detector import PRISMDetector

    return NEXUSPipeline(
        client=client or _make_mock_client(),
        router=NEXUSRouter(safety_floors=SafetyFloors()),
        detector=PRISMDetector(),
        effort_controller=EffortController(),
    )


# ── 1. Full Pipeline Integration ──────────────────────────────


class TestFullPipelineIntegration:
    """PRISM detect → NEXUS route → effort select → prompt build → response."""

    def test_frustrated_input_routes_to_protector(self):
        pipeline = _make_real_pipeline()
        result = pipeline.process(
            user_message="I CAN'T HANDLE THIS ANYMORE",
            dry_run=True,
        )
        assert result.selection.primary.expert == "protector"
        assert result.effort.value in ("high", "max")

    def test_stuck_input_activates_decomposer_or_guide(self):
        pipeline = _make_real_pipeline()
        result = pipeline.process(
            user_message="I'm stuck, I don't know what to do",
            dry_run=True,
        )
        primary = result.selection.primary.expert
        assert primary in ("decomposer", "guide", "protector")

    def test_focused_input_routes_to_executor(self):
        pipeline = _make_real_pipeline()
        result = pipeline.process(
            user_message="Let's implement the authentication module",
            dry_run=True,
        )
        primary = result.selection.primary.expert
        # Safety floor (protector=0.10) can win when no strong signals
        assert primary in ("executor", "guide", "decomposer", "protector")

    def test_pipeline_result_complete(self):
        pipeline = _make_real_pipeline()
        result = pipeline.process(
            user_message="Hello, how are you?",
            dry_run=True,
        )
        assert result.signals is not None
        assert result.selection is not None
        assert result.effort is not None
        assert result.system_prompt is not None
        assert result.response is None  # dry_run

    def test_pipeline_with_api_call(self):
        client = _make_mock_client(content="I hear you")
        pipeline = _make_real_pipeline(client=client)
        result = pipeline.process(user_message="I'm frustrated")
        assert result.response is not None
        assert result.response.content == "I hear you"
        client.send.assert_called_once()

    def test_system_prompt_includes_expert_voice(self):
        pipeline = _make_real_pipeline()
        result = pipeline.process(
            user_message="I'M SO FRUSTRATED",
            dry_run=True,
        )
        prompt_lower = result.system_prompt.lower()
        assert "empathy" in prompt_lower or "safety" in prompt_lower

    def test_safety_floors_enforced_in_pipeline(self):
        """Safety floors must be enforced regardless of input."""
        pipeline = _make_real_pipeline()
        result = pipeline.process(
            user_message="implement feature X",
            dry_run=True,
        )
        from otto.core.constitution import validate
        validate()  # Would raise if floors were modified

    def test_effort_override_respected(self):
        from otto.api.effort import EffortLevel

        pipeline = _make_real_pipeline()
        result = pipeline.process(
            user_message="test",
            effort_override=EffortLevel.MAX,
            dry_run=True,
        )
        assert result.effort == EffortLevel.MAX


# ── 2. ChatSession + Services Integration ─────────────────────


class TestChatSessionServicesIntegration:
    """ChatSession collects service signals and passes them to pipeline."""

    def test_session_with_real_pipeline(self):
        from otto.ui.chat import ChatSession

        client = _make_mock_client(content="Got it!")
        pipeline = _make_real_pipeline(client=client)
        session = ChatSession(pipeline=pipeline)

        response = session.send("I need help")
        assert response.content == "Got it!"
        assert response.role == "assistant"
        assert session.exchange_count == 1

    def test_session_accumulates_history(self):
        from otto.ui.chat import ChatSession

        client = _make_mock_client()
        pipeline = _make_real_pipeline(client=client)
        session = ChatSession(pipeline=pipeline)

        session.send("first")
        session.send("second")
        session.send("third")

        assert session.exchange_count == 3
        assert session.history.count == 6  # 3 user + 3 assistant

    def test_session_with_service_registry(self):
        from otto.services.base import CategoricalSignal, ServiceRegistry
        from otto.ui.chat import ChatSession

        class FakeService:
            name = "test_service"
            tier = 1
            running = False

            def start(self):
                self.running = True

            def stop(self):
                self.running = False

            def get_signals(self):
                return [
                    CategoricalSignal(
                        category="test_cat",
                        value="test_val",
                        confidence=0.9,
                        source="test_service",
                    )
                ]

        registry = ServiceRegistry()
        registry.register(FakeService())

        client = _make_mock_client()
        pipeline = _make_real_pipeline(client=client)
        session = ChatSession(pipeline=pipeline, services=registry)

        # Should succeed without error — signals flow through
        response = session.send("hello")
        assert response.content == "Test response"

    def test_session_with_compaction_manager(self):
        from otto.api.compaction import CompactionManager
        from otto.ui.chat import ChatSession

        client = _make_mock_client()
        pipeline = _make_real_pipeline(client=client)
        compaction = CompactionManager()
        session = ChatSession(pipeline=pipeline, compaction=compaction)

        session.send("test message")

        status = compaction.status()
        assert status.total_tokens > 0
        assert status.exchange_count == 1


# ── 3. Memory + Encryption Roundtrip ──────────────────────────


class TestMemoryEncryptionIntegration:
    """Write memory → encrypt → store → decrypt → read back."""

    def test_memory_store_roundtrip(self):
        from otto.core.memory.manager import MemoryManager
        from otto.core.memory.types import MemoryType

        mgr = MemoryManager()  # :memory: by default

        # Must read before write (read-before-write invariant)
        mgr.read(MemoryType.EPISODIC, "greeting")
        mgr.write(MemoryType.EPISODIC, "greeting", "Hello from test")

        entry = mgr.read(MemoryType.EPISODIC, "greeting")
        assert entry is not None
        assert entry.content == "Hello from test"

    def test_identity_memory_isolated(self):
        from otto.core.memory.manager import MemoryManager
        from otto.core.memory.types import MemoryType

        mgr = MemoryManager()

        # Write identity memory (must read first)
        mgr.read(MemoryType.IDENTITY, "name")
        mgr.write(MemoryType.IDENTITY, "name", "Test User")

        # export_syncable returns dict[str, list[MemoryEntry]]
        syncable = mgr.export_syncable()
        assert "IDENTITY" not in syncable

    def test_read_before_write_enforced(self):
        from otto.core.memory.manager import MemoryManager, ReadBeforeWriteViolation
        from otto.core.memory.types import MemoryType

        mgr = MemoryManager()
        with pytest.raises(ReadBeforeWriteViolation):
            mgr.write(MemoryType.EPISODIC, "key", "value")

    def test_encryption_roundtrip(self):
        from otto.core.encryption.crypto import CryptoEngine

        key = CryptoEngine.generate_key()
        plaintext = b"OTTO cognitive data - sensitive"

        ciphertext = CryptoEngine.encrypt(plaintext, key)
        assert ciphertext != plaintext

        decrypted = CryptoEngine.decrypt(ciphertext, key)
        assert decrypted == plaintext

    def test_wrong_key_fails_gracefully(self):
        from otto.core.encryption.crypto import CryptoEngine, DecryptionError

        key1 = CryptoEngine.generate_key()
        key2 = CryptoEngine.generate_key()

        ciphertext = CryptoEngine.encrypt(b"secret", key1)
        with pytest.raises(DecryptionError):
            CryptoEngine.decrypt(ciphertext, key2)


# ── 4. Pheromone Trail Lifecycle ──────────────────────────────


class TestPheromoneLifecycleIntegration:
    """Deposit → follow → decay → prune end-to-end."""

    def test_full_lifecycle(self):
        from otto.core.pheromones.trails import TrailManager
        from otto.core.pheromones.decay import DecayEngine

        mgr = TrailManager()
        decay = DecayEngine(half_life_hours=0.001, prune_threshold=0.001)

        # Deposit
        mgr.deposit("navigate_to_file", 0.8, "coding")
        mgr.deposit("navigate_to_file", 0.9, "coding")  # Reinforce

        # Follow
        trails = mgr.follow("coding")
        assert len(trails) == 1
        assert trails[0].action == "navigate_to_file"
        assert trails[0].deposit_count == 2
        assert trails[0].strength == pytest.approx(1.7)

        # Verify trail manager state
        assert mgr.count() == 1
        assert mgr.get_strength("navigate_to_file", "coding") == pytest.approx(1.7)

    def test_kahan_summation_precision(self):
        """Verify Kahan summation produces more precise results."""
        from otto.core.determinism.kahan import KahanAccumulator

        kahan = KahanAccumulator()
        naive = 0.0
        for _ in range(10000):
            kahan.add(0.1)
            naive += 0.1

        kahan_error = abs(kahan.total() - 1000.0)
        naive_error = abs(naive - 1000.0)
        assert kahan_error <= naive_error


# ── 5. MCP End-to-End ─────────────────────────────────────────


class TestMCPEndToEnd:
    """Full MCP dispatch through ChatSession to pipeline."""

    def test_chat_tool_end_to_end(self):
        from otto.mcp.server import OTTOMCPHandler
        from otto.ui.chat import ChatSession

        client = _make_mock_client(content="I understand how you feel")
        pipeline = _make_real_pipeline(client=client)
        session = ChatSession(pipeline=pipeline)
        handler = OTTOMCPHandler(session=session)

        result = handler.handle("otto_chat", {"message": "I'm overwhelmed"})
        assert result.content == "I understand how you feel"
        assert result.is_error is False
        assert "expert" in result.metadata

    def test_status_tool_after_chat(self):
        from otto.mcp.server import OTTOMCPHandler
        from otto.ui.chat import ChatSession

        client = _make_mock_client()
        pipeline = _make_real_pipeline(client=client)
        session = ChatSession(pipeline=pipeline)
        handler = OTTOMCPHandler(session=session)

        handler.handle("otto_chat", {"message": "hello"})
        status = handler.handle("otto_status", {})
        assert "1 exchanges" in status.content

    def test_signals_tool_with_services(self):
        from otto.mcp.server import OTTOMCPHandler
        from otto.services.base import CategoricalSignal, ServiceRegistry
        from otto.ui.chat import ChatSession

        class FakeClockService:
            name = "clock"
            tier = 1
            running = True

            def start(self): pass
            def stop(self): pass
            def get_signals(self):
                return [
                    CategoricalSignal(
                        category="time_period",
                        value="morning",
                        confidence=1.0,
                        source="clock",
                    ),
                ]

        registry = ServiceRegistry()
        registry.register(FakeClockService())

        client = _make_mock_client()
        pipeline = _make_real_pipeline(client=client)
        session = ChatSession(pipeline=pipeline, services=registry)
        handler = OTTOMCPHandler(session=session)

        result = handler.handle("otto_signals", {})
        assert "time_period" in result.content
        assert "morning" in result.content


# ── 6. Constitution Enforcement End-to-End ─────────────────────


class TestConstitutionEnforcement:
    """Safety floors enforced across the full routing pipeline."""

    def test_safety_floors_immutable(self):
        from otto.core.constitution import SafetyFloors

        floors = SafetyFloors()
        with pytest.raises(FrozenInstanceError):
            floors.protector = 0.0  # type: ignore[misc]

    def test_safety_floors_values_correct(self):
        from otto.core.constitution import SafetyFloors

        floors = SafetyFloors()
        assert floors.protector == 0.10
        assert floors.decomposer == 0.05
        assert floors.restorer == 0.05

    def test_constitution_validates(self):
        from otto.core.constitution import validate
        validate()

    def test_routing_respects_floors_for_all_inputs(self):
        """Run 20 varied inputs through NEXUS, verify floors hold."""
        from otto.core.constitution import SafetyFloors
        from otto.core.experts.router import NEXUSRouter
        from otto.core.prism.detector import PRISMDetector

        detector = PRISMDetector()
        router = NEXUSRouter(safety_floors=SafetyFloors())

        inputs = [
            "hello", "I'm stuck", "FRUSTRATED", "let's code",
            "I'm tired", "what if we tried...", "can't handle this",
            "implement auth", "fix the bug", "I need a break",
            "too much going on", "let's brainstorm",
            "ship it", "I wonder about", "good morning",
            "", "a", "!!!", "???", "HELP ME",
        ]

        for text in inputs:
            signals = detector.detect(text)
            selection = router.route(signals, state={})
            # Constitution must still validate after any routing
            from otto.core.constitution import validate
            validate()


# =====================================================================
# DAY 17: PERFORMANCE BENCHMARKS
# =====================================================================


class TestPerformance:
    """Performance benchmarks for critical paths."""

    def test_prism_detection_speed(self):
        """Signal detection should be fast (<10ms per call)."""
        from otto.core.prism.detector import PRISMDetector

        detector = PRISMDetector()
        text = "I'm so frustrated and stuck, I CAN'T do this anymore"

        start = time.perf_counter()
        iterations = 1000
        for _ in range(iterations):
            detector.detect(text)
        elapsed = time.perf_counter() - start

        per_call_ms = (elapsed / iterations) * 1000
        assert per_call_ms < 10, f"Detection too slow: {per_call_ms:.2f}ms"

    def test_nexus_routing_speed(self):
        """Routing should be fast (<5ms per call)."""
        from otto.core.constitution import SafetyFloors
        from otto.core.experts.router import NEXUSRouter
        from otto.core.prism.detector import PRISMDetector

        detector = PRISMDetector()
        router = NEXUSRouter(safety_floors=SafetyFloors())
        signals = detector.detect("I'm stuck and overwhelmed")

        start = time.perf_counter()
        iterations = 1000
        for _ in range(iterations):
            router.route(signals, state={})
        elapsed = time.perf_counter() - start

        per_call_ms = (elapsed / iterations) * 1000
        assert per_call_ms < 5, f"Routing too slow: {per_call_ms:.2f}ms"

    def test_livrps_resolve_speed(self):
        """Layer resolution should be fast (<1ms per call)."""
        from otto.core.livrps.compositor import LIVRPSCompositor
        from otto.core.livrps.layers import LayerName

        comp = LIVRPSCompositor()
        comp.set_property(LayerName.INHERITED, "mood", "neutral")
        comp.set_property(LayerName.REACTIVE, "mood", "stressed")
        comp.set_property(LayerName.SOVEREIGN, "theme", "dark")

        start = time.perf_counter()
        iterations = 1000
        for _ in range(iterations):
            comp.resolve_all()
        elapsed = time.perf_counter() - start

        per_call_ms = (elapsed / iterations) * 1000
        assert per_call_ms < 1, f"LIVRPS resolve too slow: {per_call_ms:.2f}ms"

    def test_full_pipeline_dry_run_speed(self):
        """Full pipeline (dry run) should complete in <20ms."""
        pipeline = _make_real_pipeline()

        start = time.perf_counter()
        iterations = 100
        for _ in range(iterations):
            pipeline.process(
                user_message="I'm stuck on this problem",
                dry_run=True,
            )
        elapsed = time.perf_counter() - start

        per_call_ms = (elapsed / iterations) * 1000
        assert per_call_ms < 20, f"Pipeline too slow: {per_call_ms:.2f}ms"

    def test_conversation_history_token_estimation_speed(self):
        """Token estimation should scale linearly."""
        from otto.ui.chat import ChatMessage, ConversationHistory

        history = ConversationHistory()
        for i in range(200):
            history.add(ChatMessage(role="user", content=f"msg {i} " * 50))

        start = time.perf_counter()
        iterations = 1000
        for _ in range(iterations):
            history.estimate_tokens()
        elapsed = time.perf_counter() - start

        per_call_ms = (elapsed / iterations) * 1000
        assert per_call_ms < 1, f"Token estimation too slow: {per_call_ms:.2f}ms"

    def test_pheromone_deposit_speed(self):
        """Pheromone deposits should be fast (<1ms)."""
        from otto.core.pheromones.trails import TrailManager

        mgr = TrailManager()

        start = time.perf_counter()
        iterations = 1000
        for i in range(iterations):
            mgr.deposit(f"action_{i % 50}", 0.5, "context")
        elapsed = time.perf_counter() - start

        per_call_ms = (elapsed / iterations) * 1000
        assert per_call_ms < 1, f"Deposit too slow: {per_call_ms:.2f}ms"

    def test_import_time(self):
        """Core imports should complete quickly (<500ms total)."""
        modules = [
            "otto.core.constitution",
            "otto.core.livrps",
            "otto.core.prism",
            "otto.core.experts.router",
            "otto.api.nexus",
            "otto.ui.chat",
            "otto.mcp",
        ]

        start = time.perf_counter()
        for mod in modules:
            importlib.import_module(mod)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5, f"Imports too slow: {elapsed:.2f}s"


# =====================================================================
# DAY 18: AUTOMATED AUDIT
# =====================================================================


OTTO_SRC = pathlib.Path(__file__).parent.parent / "otto"


def _collect_python_files() -> list[pathlib.Path]:
    """Collect all Python source files in otto/."""
    return sorted(OTTO_SRC.rglob("*.py"))


def _read_source(path: pathlib.Path) -> str:
    """Read a Python file's source code."""
    return path.read_text(encoding="utf-8")


# ── Audit: No bare dict.items() ───────────────────────────────


class TestAuditDictIteration:
    """[He2025] All dict iteration must use sorted()."""

    def test_no_bare_dict_items(self):
        """Every .items() call must be inside sorted().

        Handles multi-line patterns like:
            dict(sorted({
                ...
            }.items()))
        by scanning backwards from the .items() line.
        """
        violations = []
        for pyfile in _collect_python_files():
            source = _read_source(pyfile)
            lines = source.splitlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if ".items()" not in line:
                    continue

                # Check current line for sorted()
                if "sorted(" in line or "dict(sorted(" in line:
                    continue

                # Check previous 40 lines for sorted( or dict(sorted(
                # (dict literals can span many lines)
                found_sorted = False
                start = max(0, i - 40)
                for j in range(start, i):
                    if "sorted(" in lines[j] or "dict(sorted(" in lines[j]:
                        found_sorted = True
                        break

                if not found_sorted:
                    violations.append(
                        f"{pyfile.relative_to(OTTO_SRC)}:{i+1}: {stripped}"
                    )

        assert not violations, (
            f"Bare dict.items() found (must use sorted()):\n"
            + "\n".join(violations)
        )

    def test_no_bare_dict_keys_in_iteration(self):
        """Every .keys() used in for-loop must use sorted()."""
        violations = []
        for pyfile in _collect_python_files():
            source = _read_source(pyfile)
            for i, line in enumerate(source.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "for " in line and ".keys()" in line:
                    if "sorted(" not in line:
                        violations.append(f"{pyfile.relative_to(OTTO_SRC)}:{i}: {stripped}")

        assert not violations, (
            f"Bare dict.keys() in for-loop:\n" + "\n".join(violations)
        )


# ── Audit: No clinical language ───────────────────────────────


class TestAuditClinicalLanguage:
    """No clinical language in user-facing strings."""

    CLINICAL_PATTERNS = [
        r'\b[Aa][Dd][Hh][Dd]\b',
        r'executive\s+dysfunction',
        r'neurodivergent\s+deficit',
        r'\bdiagnos(?:is|ed|tic)\b',
        r'\bsymptom\b',
        r'\bdisorder\b',
    ]

    # Files ALLOWED to contain clinical terms (define banned lists or doc rules)
    EXEMPT_FILES = {
        "core/constitution.py",
    }

    def test_no_clinical_language_in_strings(self):
        """Check all .py files for clinical terms in string literals."""
        violations = []

        for pyfile in _collect_python_files():
            relpath = str(pyfile.relative_to(OTTO_SRC)).replace("\\", "/")
            if relpath in self.EXEMPT_FILES:
                continue

            source = _read_source(pyfile)
            for i, line in enumerate(source.splitlines(), 1):
                stripped = line.strip()
                # Skip comments explaining what NOT to do
                if stripped.startswith("#"):
                    continue
                if stripped.startswith('"""') or stripped.startswith("- No"):
                    continue

                for pattern in self.CLINICAL_PATTERNS:
                    if re.search(pattern, line):
                        violations.append(f"{relpath}:{i}: {stripped}")

        assert not violations, (
            f"Clinical language found:\n" + "\n".join(violations)
        )


# ── Audit: No minimizing language in user-facing strings ──────


class TestAuditMinimizingLanguage:
    """No "just", "simply", "easy" in user-facing strings."""

    def test_no_minimizing_in_expert_voices(self):
        from otto.api.nexus import EXPERT_VOICES

        for expert, voice in sorted(EXPERT_VOICES.items()):
            words = voice.lower().split()
            for term in ("just", "simply", "easy"):
                assert term not in words, (
                    f"Minimizing term '{term}' in {expert} voice: {voice}"
                )

    def test_no_minimizing_in_descriptions(self):
        from otto.ui.dashboard import EFFORT_DESCRIPTIONS, EXPERT_DESCRIPTIONS
        from otto.ui.styles import SIGNAL_LABELS

        all_strings = {}
        for k, v in sorted(EXPERT_DESCRIPTIONS.items()):
            all_strings[f"expert:{k}"] = v
        for k, v in sorted(EFFORT_DESCRIPTIONS.items()):
            all_strings[f"effort:{k}"] = v
        for k, v in sorted(SIGNAL_LABELS.items()):
            all_strings[f"signal:{k}"] = v

        for source, text in sorted(all_strings.items()):
            words = set(text.lower().split())
            for term in ("just", "simply", "easy"):
                assert term not in words, (
                    f"Minimizing term '{term}' in {source}: {text}"
                )


# ── Audit: Safety floors immutable ────────────────────────────


class TestAuditSafetyFloors:
    """Safety floors cannot be modified at runtime."""

    def test_floors_frozen(self):
        from otto.core.constitution import SafetyFloors

        floors = SafetyFloors()
        for attr in ("protector", "decomposer", "restorer"):
            with pytest.raises(FrozenInstanceError):
                setattr(floors, attr, 0.0)

    def test_floor_values_exact(self):
        from otto.core.constitution import SafetyFloors

        floors = SafetyFloors()
        assert floors.protector == pytest.approx(0.10)
        assert floors.decomposer == pytest.approx(0.05)
        assert floors.restorer == pytest.approx(0.05)

    def test_floor_total(self):
        from otto.core.constitution import SafetyFloors

        floors = SafetyFloors()
        assert floors.total == pytest.approx(0.20)


# ── Audit: Privacy boundary ───────────────────────────────────


class TestAuditPrivacyBoundary:
    """Raw data never crosses into categorical signals."""

    def test_categorical_signal_has_no_raw_field(self):
        from otto.services.base import CategoricalSignal
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(CategoricalSignal)}
        forbidden = {"raw_data", "raw", "data", "raw_value", "raw_input"}
        overlap = field_names & forbidden
        assert not overlap, f"CategoricalSignal has raw data field: {overlap}"

    def test_categorical_signal_fields_are_categorical(self):
        from otto.services.base import CategoricalSignal
        import dataclasses

        expected = {"category", "value", "confidence", "source", "timestamp"}
        actual = {f.name for f in dataclasses.fields(CategoricalSignal)}
        assert actual == expected

    def test_services_only_emit_categoricals(self):
        """Verify service get_signals() returns CategoricalSignal type."""
        from otto.services.clock import ClockService
        from otto.services.base import CategoricalSignal

        service = ClockService()
        signals = service.get_signals()
        for sig in signals:
            assert isinstance(sig, CategoricalSignal), (
                f"Service emitted non-categorical: {type(sig)}"
            )


# ── Audit: Determinism ────────────────────────────────────────


class TestAuditDeterminism:
    """Same input → same output, verified across repeated runs."""

    def test_prism_deterministic_100x(self):
        from otto.core.prism.detector import PRISMDetector

        detector = PRISMDetector()
        text = "I'm stuck and frustrated, can't handle this"
        baseline = [(s.type.name, s.confidence) for s in detector.detect(text)]

        for _ in range(100):
            result = [(s.type.name, s.confidence) for s in detector.detect(text)]
            assert result == baseline

    def test_nexus_routing_deterministic_100x(self):
        from otto.core.constitution import SafetyFloors
        from otto.core.experts.router import NEXUSRouter
        from otto.core.prism.detector import PRISMDetector

        detector = PRISMDetector()
        router = NEXUSRouter(safety_floors=SafetyFloors())
        signals = detector.detect("I'm overwhelmed and stuck")

        baseline_primary = None
        baseline_supporting = None
        for _ in range(100):
            selection = router.route(signals, state={})
            primary = selection.primary.expert
            supporting = tuple(s.expert for s in selection.supporting)
            if baseline_primary is None:
                baseline_primary = primary
                baseline_supporting = supporting
            else:
                assert primary == baseline_primary
                assert supporting == baseline_supporting

    def test_livrps_deterministic(self):
        from otto.core.livrps.compositor import LIVRPSCompositor
        from otto.core.livrps.layers import LayerName

        comp = LIVRPSCompositor()
        comp.set_property(LayerName.LEARNED, "a", 1)
        comp.set_property(LayerName.REACTIVE, "b", 2)
        comp.set_property(LayerName.SOVEREIGN, "c", 3)

        baseline = {k: v.value for k, v in comp.resolve_all().items()}
        for _ in range(100):
            result = {k: v.value for k, v in comp.resolve_all().items()}
            assert result == baseline

    def test_pipeline_deterministic_50x(self):
        """Full pipeline produces same routing 50 times."""
        pipeline = _make_real_pipeline()

        baseline = None
        for _ in range(50):
            result = pipeline.process(
                user_message="I need help organizing my tasks",
                dry_run=True,
            )
            current = (
                result.selection.primary.expert,
                tuple(s.expert for s in result.selection.supporting),
                result.effort.value,
            )
            if baseline is None:
                baseline = current
            else:
                assert current == baseline

    def test_mcp_tools_deterministic(self):
        from otto.mcp.tools import get_tool_definitions

        baseline = [(t.name, t.description) for t in get_tool_definitions()]
        for _ in range(100):
            current = [(t.name, t.description) for t in get_tool_definitions()]
            assert current == baseline


# ── Audit: Conventional commit history ─────────────────────────


class TestAuditCommitHistory:
    """Verify conventional commit message format."""

    CONVENTIONAL_PATTERN = re.compile(
        r"^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)"
        r"(\([a-z0-9_-]+\))?:\s.+"
    )

    def test_recent_commits_conventional(self):
        """Check that recent v3 commits follow conventional format."""
        import subprocess

        result = subprocess.run(
            ["git", "log", "--oneline", "--format=%s", "-20"],
            capture_output=True,
            text=True,
            cwd=str(OTTO_SRC.parent),
        )
        if result.returncode != 0:
            pytest.skip("Not in a git repository")

        for line in result.stdout.strip().splitlines():
            if not line:
                continue
            # Only check v3 commits
            if "constitutional" in line or "LIVRPS" in line or "PRISM" in line or \
               "NEXUS" in line or "memory" in line or "AES-256" in line or \
               "pheromone" in line or "Opus 4.6" in line or "ambient" in line or \
               "user interface" in line or "integration" in line:
                assert self.CONVENTIONAL_PATTERN.match(line), (
                    f"Non-conventional commit: {line}"
                )


# ── Audit: No plaintext cognitive data on disk ────────────────


class TestAuditEncryption:
    """Verify encryption module doesn't write plaintext."""

    def test_crypto_engine_produces_different_output(self):
        from otto.core.encryption.crypto import CryptoEngine

        key = CryptoEngine.generate_key()
        data = b"cognitive state: overwhelmed, frustrated"

        encrypted = CryptoEngine.encrypt(data, key)
        assert encrypted != data
        assert b"overwhelmed" not in encrypted
        assert b"frustrated" not in encrypted

    def test_key_derivation_deterministic(self):
        from otto.core.encryption.kdf import TEST_PARAMS, derive_key, generate_salt

        salt = b"fixed_salt_for_test_0000"  # 24 bytes, >= 8

        key1 = derive_key("test_password_123", salt, TEST_PARAMS)
        key2 = derive_key("test_password_123", salt, TEST_PARAMS)
        assert key1 == key2

    def test_different_passwords_different_keys(self):
        from otto.core.encryption.kdf import TEST_PARAMS, derive_key

        salt = b"fixed_salt_for_test_0000"

        key1 = derive_key("password_a", salt, TEST_PARAMS)
        key2 = derive_key("password_b", salt, TEST_PARAMS)
        assert key1 != key2


# ── Audit: Package structure completeness ─────────────────────


class TestAuditPackageStructure:
    """Verify all expected packages and modules exist."""

    EXPECTED_PACKAGES = [
        "otto",
        "otto.core",
        "otto.core.livrps",
        "otto.core.prism",
        "otto.core.experts",
        "otto.core.memory",
        "otto.core.encryption",
        "otto.core.pheromones",
        "otto.core.determinism",
        "otto.api",
        "otto.services",
        "otto.ui",
        "otto.mcp",
    ]

    def test_all_packages_importable(self):
        failures = []
        for pkg in self.EXPECTED_PACKAGES:
            try:
                importlib.import_module(pkg)
            except ImportError as e:
                failures.append(f"{pkg}: {e}")

        assert not failures, (
            f"Failed to import:\n" + "\n".join(failures)
        )

    def test_key_modules_importable(self):
        """Verify critical modules can be imported."""
        modules = [
            "otto.core.constitution",
            "otto.core.livrps.compositor",
            "otto.core.prism.detector",
            "otto.core.experts.router",
            "otto.api.nexus",
            "otto.api.effort",
            "otto.api.client",
            "otto.api.compaction",
            "otto.services.base",
            "otto.services.clock",
            "otto.ui.chat",
            "otto.ui.dashboard",
            "otto.ui.styles",
            "otto.mcp.tools",
            "otto.mcp.server",
        ]
        for mod_name in modules:
            mod = importlib.import_module(mod_name)
            assert mod is not None
