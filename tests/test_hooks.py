"""
Tests for the Hook System
==========================

Tests Hook base classes, registry, and trail-based hooks.

Focus areas:
- determinism (fixed execution order)
- Trail deposit/read integration
- Context injection formatting
- Collision detection
"""

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from otto.hooks.base import (
    Hook,
    HookContext,
    HookEvent,
    HookResult,
    HookRegistry,
)
from otto.hooks.auto_validate import (
    AutoValidateHook,
    check_he2025_compliance,
    validate_file,
    VIOLATION_PATTERNS,
    COMPLIANCE_PATTERNS,
)
from otto.hooks.trail_context import (
    TrailContextHook,
    WorkTrailHook,
    format_quality_trails,
)
from otto.trails import Trail, TrailStore, TrailType


# =============================================================================
# HookContext Tests
# =============================================================================

class TestHookContext:
    """Tests for HookContext dataclass."""

    def test_is_file_operation(self):
        """Should correctly identify file operations."""
        edit_ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            tool_name="Edit",
        )
        assert edit_ctx.is_file_operation()

        write_ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            tool_name="Write",
        )
        assert write_ctx.is_file_operation()

        bash_ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            tool_name="Bash",
        )
        assert not bash_ctx.is_file_operation()

    def test_get_target_path_from_file_path(self):
        """Should extract path from file_path field."""
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            file_path="src/test.py",
        )
        assert ctx.get_target_path() == "src/test.py"

    def test_get_target_path_from_tool_input(self):
        """Should extract path from tool_input."""
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_input={"file_path": "src/otto/test.py"},
        )
        assert ctx.get_target_path() == "src/otto/test.py"

    def test_get_target_path_prefers_file_path(self):
        """Should prefer file_path over tool_input."""
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            file_path="preferred.py",
            tool_input={"file_path": "other.py"},
        )
        assert ctx.get_target_path() == "preferred.py"


# =============================================================================
# HookRegistry Tests
# =============================================================================

class TestHookRegistry:
    """Tests for HookRegistry."""

    class TestHook(Hook):
        """Simple test hook."""

        def __init__(self, name: str, events: list, priority: int):
            self._name = name
            self._events = events
            self._priority = priority
            self.process_count = 0

        @property
        def name(self):
            return self._name

        @property
        def events(self):
            return self._events

        @property
        def priority(self):
            return self._priority

        def process(self, context):
            self.process_count += 1
            return HookResult(hook_name=self.name)

    def test_register_and_execute(self):
        """Should register and execute hooks."""
        registry = HookRegistry()
        hook = self.TestHook("test", [HookEvent.POST_TOOL_USE], 50)
        registry.register(hook)

        ctx = HookContext(event=HookEvent.POST_TOOL_USE)
        results = registry.execute(ctx)

        assert len(results) == 1
        assert results[0].hook_name == "test"
        assert hook.process_count == 1

    def test_execute_in_priority_order(self):
        """Should execute hooks in priority order."""
        registry = HookRegistry()
        execution_order = []

        class OrderTracker(Hook):
            def __init__(self, name, priority):
                self._name = name
                self._priority = priority

            @property
            def name(self):
                return self._name

            @property
            def events(self):
                return [HookEvent.POST_TOOL_USE]

            @property
            def priority(self):
                return self._priority

            def process(self, context):
                execution_order.append(self._name)
                return HookResult(hook_name=self.name)

        # Register in non-priority order
        registry.register(OrderTracker("third", 75))
        registry.register(OrderTracker("first", 25))
        registry.register(OrderTracker("second", 50))

        ctx = HookContext(event=HookEvent.POST_TOOL_USE)
        registry.execute(ctx)

        assert execution_order == ["first", "second", "third"]

    def test_halt_stops_execution(self):
        """Should stop execution when a hook returns halt=True."""
        registry = HookRegistry()

        class HaltingHook(Hook):
            @property
            def name(self):
                return "halter"

            @property
            def events(self):
                return [HookEvent.POST_TOOL_USE]

            @property
            def priority(self):
                return 50

            def process(self, context):
                return HookResult(hook_name=self.name, halt=True)

        after_hook = self.TestHook("after", [HookEvent.POST_TOOL_USE], 75)

        registry.register(HaltingHook())
        registry.register(after_hook)

        ctx = HookContext(event=HookEvent.POST_TOOL_USE)
        results = registry.execute(ctx)

        assert len(results) == 1
        assert after_hook.process_count == 0

    def test_context_injections_combined(self):
        """Should combine context injections from multiple hooks."""
        registry = HookRegistry()

        class InjectingHook(Hook):
            def __init__(self, name, injection):
                self._name = name
                self._injection = injection

            @property
            def name(self):
                return self._name

            @property
            def events(self):
                return [HookEvent.PRE_TOOL_USE]

            @property
            def priority(self):
                return 50

            def process(self, context):
                return HookResult(
                    hook_name=self.name,
                    context_injection=self._injection,
                )

        registry.register(InjectingHook("first", "Line 1"))
        registry.register(InjectingHook("second", "Line 2"))

        ctx = HookContext(event=HookEvent.PRE_TOOL_USE)
        results = registry.execute(ctx)

        combined = registry.get_context_injections(results)

        assert "Line 1" in combined
        assert "Line 2" in combined

    def test_deterministic_priority_tie_breaking(self):
        """Same priority hooks should execute in deterministic name order."""
        registry = HookRegistry()
        execution_order = []

        class NameTracker(Hook):
            def __init__(self, name):
                self._name = name

            @property
            def name(self):
                return self._name

            @property
            def events(self):
                return [HookEvent.POST_TOOL_USE]

            @property
            def priority(self):
                return 50  # All same priority

            def process(self, context):
                execution_order.append(self._name)
                return HookResult(hook_name=self.name)

        # Register in non-alphabetical order
        registry.register(NameTracker("zebra"))
        registry.register(NameTracker("alpha"))
        registry.register(NameTracker("mike"))

        ctx = HookContext(event=HookEvent.POST_TOOL_USE)
        registry.execute(ctx)

        # Should be sorted alphabetically
        assert execution_order == ["alpha", "mike", "zebra"]


# =============================================================================
# AutoValidateHook Tests
# =============================================================================

class TestAutoValidateHook:
    """Tests for validation."""

    def test_detect_max_on_dict_items(self):
        """Should detect max() on dict.items()."""
        code = '''
def get_best(scores):
    return max(scores.items(), key=lambda x: x[1])
'''
        violations, _ = check_he2025_compliance(code)

        assert len(violations) == 1
        assert violations[0]["type"] == "max_on_dict_items"

    def test_detect_iterate_set(self):
        """Should detect iterating over set directly."""
        code = '''
def process(items):
    for item in set(items):
        print(item)
'''
        violations, _ = check_he2025_compliance(code)

        assert len(violations) == 1
        assert violations[0]["type"] == "iterate_set"

    def test_detect_unseeded_random(self):
        """Should detect unseeded random operations."""
        code = '''
import random

def pick_one(items):
    return random.choice(items)
'''
        violations, _ = check_he2025_compliance(code)

        assert len(violations) == 1
        assert violations[0]["type"] == "unseeded_random"

    def test_detect_compliance_patterns(self):
        """Should detect good compliance patterns."""
        code = '''
from otto.determinism import sorted_max, kahan_sum

def get_best(scores):
    return sorted_max(scores)

def total(values):
    return kahan_sum(values)
'''
        _, compliances = check_he2025_compliance(code)

        types = [c["type"] for c in compliances]
        assert "uses_sorted_max" in types
        assert "uses_kahan_sum" in types
        assert "imports_determinism" in types

    def test_no_false_positives_on_compliant_code(self):
        """Should not flag compliant code."""
        code = '''
from otto.determinism import sorted_max, kahan_sum, DETERMINISM_SEED
import random

random.seed(DETERMINISM_SEED)

def get_best(scores):
    return sorted_max(scores)

def process(items):
    for item in sorted(set(items)):
        print(item)
'''
        violations, compliances = check_he2025_compliance(code)

        # Only the sorted(set(...)) pattern should be flagged as good
        assert len(violations) == 0 or all(
            "sorted" in v.get("message", "").lower() for v in violations
        )

    @pytest.fixture
    def temp_py_file(self):
        """Create a temporary Python file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write('''
def bad_function(scores):
    return max(scores.items(), key=lambda x: x[1])
''')
            path = f.name
        yield path
        Path(path).unlink()

    def test_validate_file(self, temp_py_file):
        """Should validate a file from path."""
        result = validate_file(temp_py_file)

        assert not result["is_compliant"]
        assert len(result["violations"]) > 0


# =============================================================================
# TrailContextHook Tests
# =============================================================================

class TestTrailContextHook:
    """Tests for trail context injection."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create a TrailStore with temporary database."""
        return TrailStore(db_path=temp_db)

    def test_format_quality_trails_compliant(self):
        """Should format compliant quality trails."""
        trails = [
            Trail(
                path="test.py",
                signal="he2025_compliant",
                trail_type=TrailType.QUALITY,
            ),
        ]

        lines = format_quality_trails(trails)

        assert any("Determinism" in line for line in lines)

    def test_format_quality_trails_violation(self):
        """Should format violation trails."""
        trails = [
            Trail(
                path="test.py",
                signal="he2025_violation:max_on_dict:line42",
                trail_type=TrailType.QUALITY,
            ),
        ]

        lines = format_quality_trails(trails)

        assert any("Violation" in line for line in lines)
        assert any("42" in line for line in lines)

    def test_context_hook_injects_trails(self, store):
        """Should inject trail context before file operations."""
        # Deposit some trails
        store.deposit(Trail(
            path="src/otto/test.py",
            signal="he2025_compliant",
            trail_type=TrailType.QUALITY,
            deposited_by="test",
        ))
        store.deposit(Trail(
            path="src/otto/test.py",
            signal="depends_on:src/otto/utils.py",
            trail_type=TrailType.CONTEXT,
            deposited_by="test",
        ))

        hook = TrailContextHook(store=store)
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="Edit",
            tool_input={"file_path": "src/otto/test.py"},
        )

        result = hook.process(ctx)

        assert result.success
        assert result.trails_read > 0
        assert result.context_injection is not None
        assert "Determinism" in result.context_injection
        assert "utils.py" in result.context_injection

    def test_work_trail_hook_deposits_editing(self, store):
        """Should deposit work trail when editing starts."""
        hook = WorkTrailHook(store=store)
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="Edit",
            tool_input={"file_path": "src/otto/test.py"},
            session_id="test_session",
        )

        result = hook.process(ctx)

        assert result.success
        assert result.trails_deposited == 1

        trails = store.read_trails("src/otto/test.py")
        assert any(t.signal == "currently_editing" for t in trails)

    def test_work_trail_hook_updates_on_finish(self, store):
        """Should update work trail when editing finishes."""
        # First deposit currently_editing
        store.deposit(Trail(
            path="src/otto/test.py",
            signal="currently_editing",
            trail_type=TrailType.WORK,
            deposited_by="test_session",
        ))

        hook = WorkTrailHook(store=store)
        ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            tool_name="Edit",
            tool_input={"file_path": "src/otto/test.py"},
            session_id="test_session",
        )

        result = hook.process(ctx)

        assert result.success

        trails = store.read_trails("src/otto/test.py")
        assert any(t.signal == "recently_edited" for t in trails)


# =============================================================================
# Integration Tests
# =============================================================================

class TestHookIntegration:
    """Integration tests for the full hook system."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create a TrailStore with temporary database."""
        return TrailStore(db_path=temp_db)

    def test_full_edit_cycle(self, store):
        """Should handle a complete edit cycle with all hooks."""
        registry = HookRegistry()
        registry.register(AutoValidateHook(store=store))
        registry.register(TrailContextHook(store=store))
        registry.register(WorkTrailHook(store=store))

        path = "src/otto/test.py"

        # Pre-edit hook
        pre_ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name="Edit",
            tool_input={"file_path": path},
            session_id="test_session",
        )
        pre_results = registry.execute(pre_ctx)

        # Should have run context and work hooks
        assert len(pre_results) >= 2

        # Post-edit hook with some code
        post_ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            tool_name="Edit",
            tool_input={"file_path": path},
            tool_output='''
from otto.determinism import sorted_max

def get_best(scores):
    return sorted_max(scores)
''',
            session_id="test_session",
        )
        post_results = registry.execute(post_ctx)

        # Should have deposited trails
        total_deposited = sum(r.trails_deposited for r in post_results)
        assert total_deposited > 0

        # Check trails were created
        trails = store.read_trails(path)
        assert len(trails) > 0
