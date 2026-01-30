"""
Performance Benchmarks for OTTO OS
===================================

Critical path performance tests to ensure responsiveness.

Targets:
- Protocol encode/decode: < 1ms
- Context evaluation: < 5ms
- Full decision cycle: < 10ms

Run with:
    pytest tests/benchmarks/test_performance.py -v
"""

import pytest
import tempfile
import json
import timeit
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_message_payload() -> Dict[str, Any]:
    """Sample message payload for protocol benchmarks."""
    return {
        "state": {
            "energy_level": "high",
            "burnout_level": "GREEN",
            "momentum_phase": "building",
            "session_id": "test-123",
            "timestamp": datetime.now().isoformat(),
        },
        "context": {
            "calendar_busy": "moderate",
            "task_load": "manageable",
            "signals": ["focused", "productive"],
        }
    }


@pytest.fixture
def temp_notes_dir():
    """Create temp notes directory with files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        notes = Path(tmpdir)
        for i in range(50):
            (notes / f"note_{i:03d}.md").write_text(f"# Note {i}\n\nContent...")
        yield notes


@pytest.fixture
def temp_tasks_file():
    """Create temp tasks file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        tasks = {"tasks": [
            {"title": f"Task {i}", "completed": False, "priority": "medium"}
            for i in range(20)
        ]}
        json.dump(tasks, f)
        yield f.name
    Path(f.name).unlink(missing_ok=True)


# =============================================================================
# Protocol Performance Tests
# =============================================================================

class TestProtocolPerformance:
    """Performance tests for protocol operations."""

    def test_binary_encode_under_1ms(self, sample_message_payload):
        """Binary protocol encoding must be under 1ms."""
        from otto.protocol import BinaryProtocol, Message, MessageType

        proto = BinaryProtocol()
        msg = Message(type=MessageType.STATE_SYNC, payload=sample_message_payload)

        # Time 1000 iterations
        elapsed = timeit.timeit(lambda: proto.encode(msg), number=1000)
        avg_ms = (elapsed / 1000) * 1000

        print(f"\nBinary encode: {avg_ms:.4f}ms")
        assert avg_ms < 1.0, f"Encode too slow: {avg_ms}ms (target: <1ms)"

    def test_binary_decode_under_1ms(self, sample_message_payload):
        """Binary protocol decoding must be under 1ms."""
        from otto.protocol import BinaryProtocol, Message, MessageType

        proto = BinaryProtocol()
        msg = Message(type=MessageType.STATE_SYNC, payload=sample_message_payload)
        encoded = proto.encode(msg)

        elapsed = timeit.timeit(lambda: proto.decode(encoded), number=1000)
        avg_ms = (elapsed / 1000) * 1000

        print(f"\nBinary decode: {avg_ms:.4f}ms")
        assert avg_ms < 1.0, f"Decode too slow: {avg_ms}ms (target: <1ms)"

    def test_binary_roundtrip_under_2ms(self, sample_message_payload):
        """Full encode/decode cycle must be under 2ms."""
        from otto.protocol import BinaryProtocol, Message, MessageType

        proto = BinaryProtocol()
        msg = Message(type=MessageType.STATE_SYNC, payload=sample_message_payload)

        def roundtrip():
            encoded = proto.encode(msg)
            return proto.decode(encoded)

        elapsed = timeit.timeit(roundtrip, number=1000)
        avg_ms = (elapsed / 1000) * 1000

        print(f"\nBinary roundtrip: {avg_ms:.4f}ms")
        assert avg_ms < 2.0, f"Roundtrip too slow: {avg_ms}ms (target: <2ms)"

    def test_message_validation_under_1ms(self, sample_message_payload):
        """Message validation must be under 1ms."""
        from otto.protocol import Message, MessageType
        from otto.protocol.validator import ProtocolValidator

        validator = ProtocolValidator()
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload={"state": sample_message_payload}
        )

        elapsed = timeit.timeit(lambda: validator.validate_message(msg), number=1000)
        avg_ms = (elapsed / 1000) * 1000

        print(f"\nMessage validation: {avg_ms:.4f}ms")
        assert avg_ms < 1.0, f"Validation too slow: {avg_ms}ms (target: <1ms)"


# =============================================================================
# Cognitive State Performance Tests
# =============================================================================

class TestCognitiveStatePerformance:
    """Performance tests for cognitive state operations."""

    def test_state_creation_under_1ms(self):
        """CognitiveState creation must be under 1ms."""
        from otto.cognitive_state import CognitiveState, BurnoutLevel, EnergyLevel

        def create_state():
            return CognitiveState(
                burnout_level=BurnoutLevel.GREEN,
                energy_level=EnergyLevel.MEDIUM,
            )

        elapsed = timeit.timeit(create_state, number=1000)
        avg_ms = (elapsed / 1000) * 1000

        print(f"\nState creation: {avg_ms:.4f}ms")
        assert avg_ms < 1.0, f"State creation too slow: {avg_ms}ms (target: <1ms)"

    def test_state_serialization_under_1ms(self):
        """State to_dict/from_dict must be under 1ms each."""
        from otto.cognitive_state import CognitiveState, BurnoutLevel, EnergyLevel

        state = CognitiveState(
            burnout_level=BurnoutLevel.GREEN,
            energy_level=EnergyLevel.MEDIUM,
        )

        # to_dict
        elapsed = timeit.timeit(state.to_dict, number=1000)
        to_dict_ms = (elapsed / 1000) * 1000

        # from_dict
        data = state.to_dict()
        elapsed = timeit.timeit(lambda: CognitiveState.from_dict(data), number=1000)
        from_dict_ms = (elapsed / 1000) * 1000

        print(f"\nState to_dict: {to_dict_ms:.4f}ms")
        print(f"State from_dict: {from_dict_ms:.4f}ms")

        assert to_dict_ms < 1.0, f"to_dict too slow: {to_dict_ms}ms"
        assert from_dict_ms < 1.0, f"from_dict too slow: {from_dict_ms}ms"


# =============================================================================
# Integration Performance Tests
# =============================================================================

class TestIntegrationPerformance:
    """Performance tests for integration adapters."""

    @pytest.mark.asyncio
    async def test_notes_adapter_under_50ms(self, temp_notes_dir):
        """Notes adapter must handle 50 files in under 50ms."""
        from otto.integration import create_markdown_adapter
        import time

        adapter = create_markdown_adapter(str(temp_notes_dir))
        await adapter.initialize()

        start = time.perf_counter()
        for _ in range(10):
            await adapter.get_context()
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 10) * 1000
        print(f"\nNotes adapter (50 files): {avg_ms:.2f}ms")
        assert avg_ms < 50, f"Notes adapter too slow: {avg_ms}ms (target: <50ms)"

    @pytest.mark.asyncio
    async def test_tasks_adapter_under_10ms(self, temp_tasks_file):
        """Tasks adapter must parse 20 tasks in under 10ms."""
        from otto.integration import create_json_task_adapter
        import time

        adapter = create_json_task_adapter(temp_tasks_file)
        await adapter.initialize()

        start = time.perf_counter()
        for _ in range(100):
            await adapter.get_context()
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        print(f"\nTasks adapter (20 tasks): {avg_ms:.2f}ms")
        assert avg_ms < 10, f"Tasks adapter too slow: {avg_ms}ms (target: <10ms)"


# =============================================================================
# Coordinator Performance Tests
# =============================================================================

class TestCoordinatorPerformance:
    """Performance tests for agent coordinator."""

    def test_decision_making_under_10ms(self):
        """Coordinator decision making must be under 10ms."""
        from otto.agents.context_aware_coordinator import create_context_aware_coordinator
        from otto.agent_coordinator import TaskProfile

        coordinator = create_context_aware_coordinator()
        task = TaskProfile(
            description="Test task",
            estimated_complexity="moderate",
            parallelizable=False,
            requires_focus=True,
            file_count=5,
            domain="general",
        )

        elapsed = timeit.timeit(lambda: coordinator.decide(task), number=100)
        avg_ms = (elapsed / 100) * 1000

        print(f"\nDecision making: {avg_ms:.4f}ms")
        assert avg_ms < 10.0, f"Decision too slow: {avg_ms}ms (target: <10ms)"

    def test_cognitive_budget_under_1ms(self):
        """Cognitive budget calculation must be under 1ms."""
        from otto.agents.context_aware_coordinator import EnhancedCognitiveContext

        context = EnhancedCognitiveContext(
            energy_level="medium",
            burnout_level="YELLOW",
            momentum_phase="building",
            active_agents=1,
            working_memory_used=2,
            in_flow_state=False,
            mode="focused",
            calendar_busy_level="moderate",
            task_load_level="manageable",
            has_approaching_deadline=True,
        )

        elapsed = timeit.timeit(context.cognitive_budget, number=1000)
        avg_ms = (elapsed / 1000) * 1000

        print(f"\nCognitive budget calc: {avg_ms:.4f}ms")
        assert avg_ms < 1.0, f"Budget calc too slow: {avg_ms}ms (target: <1ms)"

    def test_context_gathering_under_5ms(self):
        """Full context gathering must be under 5ms."""
        from otto.agents.context_aware_coordinator import create_context_aware_coordinator

        coordinator = create_context_aware_coordinator()

        elapsed = timeit.timeit(coordinator.get_cognitive_context, number=100)
        avg_ms = (elapsed / 100) * 1000

        print(f"\nContext gathering: {avg_ms:.4f}ms")
        assert avg_ms < 5.0, f"Context gathering too slow: {avg_ms}ms (target: <5ms)"


# =============================================================================
# Protection Performance Tests
# =============================================================================

class TestProtectionPerformance:
    """Performance tests for protection engine."""

    def test_protection_check_under_5ms(self):
        """Protection check must be under 5ms."""
        from otto.protection import ProtectionEngine
        from otto.cognitive_state import CognitiveState, BurnoutLevel, EnergyLevel
        from otto.profile_loader import ResolvedProfile

        profile = ResolvedProfile()
        engine = ProtectionEngine(profile)
        state = CognitiveState(
            burnout_level=BurnoutLevel.YELLOW,
            energy_level=EnergyLevel.MEDIUM,
        )

        elapsed = timeit.timeit(lambda: engine.check(state), number=100)
        avg_ms = (elapsed / 100) * 1000

        print(f"\nProtection check: {avg_ms:.4f}ms")
        assert avg_ms < 5.0, f"Protection check too slow: {avg_ms}ms (target: <5ms)"


# =============================================================================
# Calibration Performance Tests
# =============================================================================

class TestCalibrationPerformance:
    """Performance tests for calibration engine."""

    def test_calibration_lookup_under_5ms(self):
        """Calibration recommendation must be under 5ms."""
        from otto.protection import CalibrationEngine
        import tempfile
        from pathlib import Path

        # Use temp directory to avoid polluting real config
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = CalibrationEngine(otto_dir=Path(tmpdir))

            # Record some data first
            for i in range(10):
                engine.record_override(
                    trigger=f"test_trigger_{i % 3}",
                    current_firmness=0.5,
                )

            elapsed = timeit.timeit(
                lambda: engine.get_recommended_firmness(0.5), number=100
            )
            avg_ms = (elapsed / 100) * 1000

            print(f"\nCalibration lookup: {avg_ms:.4f}ms")
            assert avg_ms < 5.0, f"Calibration too slow: {avg_ms}ms (target: <5ms)"


# =============================================================================
# End-to-End Performance Tests
# =============================================================================

class TestEndToEndPerformance:
    """End-to-end performance tests."""

    def test_full_decision_cycle_under_20ms(self):
        """Complete decision cycle must be under 20ms."""
        from otto.agents.context_aware_coordinator import create_context_aware_coordinator
        from otto.agent_coordinator import TaskProfile
        from otto.protection import ProtectionEngine
        from otto.profile_loader import ResolvedProfile

        profile = ResolvedProfile()
        protection = ProtectionEngine(profile)
        coordinator = create_context_aware_coordinator(
            protection_engine=protection,
        )

        task = TaskProfile(
            description="Complex refactoring",
            estimated_complexity="complex",
            parallelizable=True,
            requires_focus=True,
            file_count=10,
            domain="implementation",
        )

        def full_cycle():
            context = coordinator.get_cognitive_context()
            decision = coordinator.decide(task)
            return context, decision

        elapsed = timeit.timeit(full_cycle, number=100)
        avg_ms = (elapsed / 100) * 1000

        print(f"\nFull decision cycle: {avg_ms:.4f}ms")
        assert avg_ms < 20.0, f"Full cycle too slow: {avg_ms}ms (target: <20ms)"


# =============================================================================
# Performance Summary
# =============================================================================

class TestPerformanceSummary:
    """Generate performance summary."""

    def test_performance_report(self, sample_message_payload):
        """Generate comprehensive performance report."""
        from otto.protocol import BinaryProtocol, Message, MessageType
        from otto.protocol.validator import ProtocolValidator
        from otto.cognitive_state import CognitiveState, BurnoutLevel, EnergyLevel
        from otto.agents.context_aware_coordinator import (
            create_context_aware_coordinator,
            EnhancedCognitiveContext,
        )
        from otto.agent_coordinator import TaskProfile
        from otto.protection import ProtectionEngine
        from otto.profile_loader import ResolvedProfile

        results = {}

        # Protocol
        proto = BinaryProtocol()
        msg = Message(type=MessageType.STATE_SYNC, payload=sample_message_payload)
        encoded = proto.encode(msg)

        results["protocol_encode"] = timeit.timeit(
            lambda: proto.encode(msg), number=1000
        ) / 1000 * 1000

        results["protocol_decode"] = timeit.timeit(
            lambda: proto.decode(encoded), number=1000
        ) / 1000 * 1000

        # Validation
        validator = ProtocolValidator()
        msg_valid = Message(type=MessageType.STATE_SYNC, payload={"state": {}})
        results["validation"] = timeit.timeit(
            lambda: validator.validate_message(msg_valid), number=1000
        ) / 1000 * 1000

        # Cognitive state
        state = CognitiveState(
            burnout_level=BurnoutLevel.GREEN,
            energy_level=EnergyLevel.MEDIUM,
        )
        results["state_to_dict"] = timeit.timeit(state.to_dict, number=1000) / 1000 * 1000

        # Coordinator
        coordinator = create_context_aware_coordinator()
        task = TaskProfile(
            description="Test",
            estimated_complexity="simple",
            parallelizable=False,
            requires_focus=False,
            file_count=1,
            domain="general",
        )
        results["decision"] = timeit.timeit(
            lambda: coordinator.decide(task), number=100
        ) / 100 * 1000

        # Protection
        profile = ResolvedProfile()
        protection = ProtectionEngine(profile)
        results["protection"] = timeit.timeit(
            lambda: protection.check(state), number=100
        ) / 100 * 1000

        # Print report
        print("\n" + "=" * 60)
        print("OTTO OS PERFORMANCE REPORT")
        print("=" * 60)
        print(f"\n{'Operation':<30} {'Time (ms)':<15} {'Target':<10} {'Status'}")
        print("-" * 60)

        targets = {
            "protocol_encode": 1.0,
            "protocol_decode": 1.0,
            "validation": 1.0,
            "state_to_dict": 1.0,
            "decision": 10.0,
            "protection": 5.0,
        }

        all_pass = True
        for op, time_ms in results.items():
            target = targets.get(op, 10.0)
            status = "PASS" if time_ms < target else "FAIL"
            if time_ms >= target:
                all_pass = False
            print(f"{op:<30} {time_ms:>10.4f}ms    <{target}ms     {status}")

        print("-" * 60)
        print(f"Overall: {'ALL TARGETS MET' if all_pass else 'SOME TARGETS MISSED'}")
        print("=" * 60)

        assert all_pass, "Some performance targets were not met"
