"""
Tests for JSON Task Adapter
===========================

Tests the file-based task adapter for JSON files.
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from otto.integration.tasks import JsonTaskAdapter, create_json_task_adapter
from otto.integration.models import IntegrationConfig, IntegrationType, IntegrationStatus


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_tasks_dir(tmp_path):
    """Create a temporary directory for task files."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    return tasks_dir


@pytest.fixture
def sample_tasks_content():
    """Sample tasks JSON content."""
    now = datetime.now()
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    next_week = (now + timedelta(days=7)).strftime("%Y-%m-%d")

    return {
        "tasks": [
            {"due_date": yesterday, "priority": "high", "is_completed": False},
            {"due_date": tomorrow, "priority": "normal", "is_completed": False},
            {"due_date": next_week, "priority": "low", "is_completed": False},
            {"due_date": None, "priority": "urgent", "is_completed": False},
            {"due_date": yesterday, "priority": "normal", "is_completed": True},  # Completed, should be excluded
        ]
    }


@pytest.fixture
def sample_tasks_file(temp_tasks_dir, sample_tasks_content):
    """Create a sample tasks JSON file."""
    tasks_file = temp_tasks_dir / "todos.json"
    tasks_file.write_text(json.dumps(sample_tasks_content))
    return tasks_file


# =============================================================================
# Test: JsonTaskAdapter Initialization
# =============================================================================

class TestJsonTaskAdapterInit:
    """Tests for JsonTaskAdapter initialization."""

    @pytest.mark.asyncio
    async def test_init_with_file(self, sample_tasks_file):
        """Initialize with single JSON file."""
        adapter = create_json_task_adapter(str(sample_tasks_file))
        result = await adapter.initialize()

        assert result is True
        assert len(adapter._files) == 1

    @pytest.mark.asyncio
    async def test_init_with_directory(self, temp_tasks_dir, sample_tasks_content):
        """Initialize with directory containing JSON files."""
        # Create multiple files
        (temp_tasks_dir / "work.json").write_text(json.dumps(sample_tasks_content))
        (temp_tasks_dir / "personal.json").write_text(json.dumps(sample_tasks_content))

        adapter = create_json_task_adapter(str(temp_tasks_dir))
        result = await adapter.initialize()

        assert result is True
        assert len(adapter._files) == 2

    @pytest.mark.asyncio
    async def test_init_nonexistent_path(self, tmp_path):
        """Initialize with nonexistent path fails."""
        adapter = create_json_task_adapter(str(tmp_path / "nonexistent.json"))
        result = await adapter.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_init_empty_directory(self, temp_tasks_dir):
        """Initialize with empty directory succeeds but has no files."""
        adapter = create_json_task_adapter(str(temp_tasks_dir))
        result = await adapter.initialize()

        assert result is True
        assert len(adapter._files) == 0

    @pytest.mark.asyncio
    async def test_init_non_json_file(self, temp_tasks_dir):
        """Initialize with non-JSON file fails."""
        txt_file = temp_tasks_dir / "tasks.txt"
        txt_file.write_text("not json")

        adapter = create_json_task_adapter(str(txt_file))
        result = await adapter.initialize()

        assert result is False


# =============================================================================
# Test: JSON Format Support
# =============================================================================

class TestJSONFormatSupport:
    """Tests for different JSON format support."""

    @pytest.mark.asyncio
    async def test_standard_format(self, temp_tasks_dir):
        """Standard {"tasks": [...]} format."""
        content = {"tasks": [{"due_date": "2024-01-15", "priority": "high"}]}
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        assert context.total_tasks == 1

    @pytest.mark.asyncio
    async def test_array_format(self, temp_tasks_dir):
        """Direct array format."""
        content = [{"due_date": "2024-01-15", "priority": "high"}]
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        assert context.total_tasks == 1

    @pytest.mark.asyncio
    async def test_items_format(self, temp_tasks_dir):
        """{"items": [...]} format (alternative key)."""
        content = {"items": [{"due_date": "2024-01-15", "priority": "high"}]}
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        assert context.total_tasks == 1

    @pytest.mark.asyncio
    async def test_todos_format(self, temp_tasks_dir):
        """{"todos": [...]} format (alternative key)."""
        content = {"todos": [{"due_date": "2024-01-15", "priority": "high"}]}
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        assert context.total_tasks == 1


# =============================================================================
# Test: Context Calculation
# =============================================================================

class TestContextCalculation:
    """Tests for task context calculation."""

    @pytest.mark.asyncio
    async def test_counts_total_tasks(self, sample_tasks_file):
        """Context counts total active tasks."""
        adapter = create_json_task_adapter(str(sample_tasks_file))
        context = await adapter.get_context()

        # 4 incomplete tasks (1 completed is excluded)
        assert context.total_tasks == 4

    @pytest.mark.asyncio
    async def test_counts_overdue_tasks(self, sample_tasks_file):
        """Context counts overdue tasks."""
        adapter = create_json_task_adapter(str(sample_tasks_file))
        context = await adapter.get_context()

        # 1 task with yesterday's due date
        assert context.overdue_count >= 1

    @pytest.mark.asyncio
    async def test_counts_high_priority(self, sample_tasks_file):
        """Context counts high priority tasks."""
        adapter = create_json_task_adapter(str(sample_tasks_file))
        context = await adapter.get_context()

        # 1 high + 1 urgent
        assert context.high_priority_count >= 2

    @pytest.mark.asyncio
    async def test_excludes_completed_tasks(self, temp_tasks_dir):
        """Completed tasks are excluded from counts."""
        content = {
            "tasks": [
                {"due_date": "2024-01-15", "is_completed": True},
                {"due_date": "2024-01-16", "is_completed": True},
                {"due_date": "2024-01-17", "is_completed": False},
            ]
        }
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        # Only 1 incomplete task
        assert context.total_tasks == 1

    @pytest.mark.asyncio
    async def test_calculates_load_level_light(self, temp_tasks_dir):
        """Light load level with few tasks."""
        content = {"tasks": [{"priority": "normal"}, {"priority": "low"}]}
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        assert context.load_level == "light"

    @pytest.mark.asyncio
    async def test_calculates_load_level_overloaded(self, temp_tasks_dir):
        """Overloaded with many overdue tasks."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        content = {
            "tasks": [
                {"due_date": yesterday, "priority": "high"} for _ in range(10)
            ]
        }
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        # 5+ overdue = overloaded
        assert context.load_level == "overloaded"

    @pytest.mark.asyncio
    async def test_calculates_next_deadline(self, temp_tasks_dir):
        """Calculates hours until next deadline."""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        content = {"tasks": [{"due_date": tomorrow, "priority": "normal"}]}
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        # Should have a next deadline
        assert context.next_deadline_in_hours is not None
        assert context.next_deadline_in_hours > 0


# =============================================================================
# Test: Priority Normalization
# =============================================================================

class TestPriorityNormalization:
    """Tests for priority normalization."""

    @pytest.mark.asyncio
    async def test_string_priorities(self, temp_tasks_dir):
        """String priorities are normalized."""
        content = {
            "tasks": [
                {"priority": "low"},
                {"priority": "normal"},
                {"priority": "high"},
                {"priority": "urgent"},
            ]
        }
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        assert context.total_tasks == 4
        assert context.high_priority_count == 2  # high + urgent

    @pytest.mark.asyncio
    async def test_numeric_priorities(self, temp_tasks_dir):
        """Numeric priorities are normalized."""
        content = {
            "tasks": [
                {"priority": 1},  # low
                {"priority": 2},  # normal
                {"priority": 3},  # high
                {"priority": 4},  # urgent
            ]
        }
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        assert context.high_priority_count == 2  # 3 + 4

    @pytest.mark.asyncio
    async def test_todoist_priorities(self, temp_tasks_dir):
        """Todoist-style priorities (p1-p4, inverted)."""
        content = {
            "tasks": [
                {"priority": "p4"},  # low
                {"priority": "p3"},  # normal
                {"priority": "p2"},  # high
                {"priority": "p1"},  # urgent
            ]
        }
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        assert context.high_priority_count == 2  # p2 + p1

    @pytest.mark.asyncio
    async def test_missing_priority_defaults_normal(self, temp_tasks_dir):
        """Missing priority defaults to normal."""
        content = {"tasks": [{"due_date": "2024-01-15"}]}  # No priority
        (temp_tasks_dir / "tasks.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "tasks.json"))
        context = await adapter.get_context()

        # No high priority tasks
        assert context.high_priority_count == 0


# =============================================================================
# Test: Service Properties
# =============================================================================

class TestServiceProperties:
    """Tests for adapter service properties."""

    def test_service_name(self, sample_tasks_file):
        """Service name is 'json_tasks'."""
        adapter = create_json_task_adapter(str(sample_tasks_file))
        assert adapter.service_name == "json_tasks"

    def test_integration_type(self, sample_tasks_file):
        """Integration type is TASK_MANAGER."""
        adapter = create_json_task_adapter(str(sample_tasks_file))
        assert adapter.integration_type == IntegrationType.TASK_MANAGER

    def test_supports_write_false(self, sample_tasks_file):
        """Write is not supported in Phase 5.1."""
        adapter = create_json_task_adapter(str(sample_tasks_file))
        assert adapter.SUPPORTS_WRITE is False

    @pytest.mark.asyncio
    async def test_health_updates_on_success(self, sample_tasks_file):
        """Health status updates after successful fetch."""
        adapter = create_json_task_adapter(str(sample_tasks_file))
        await adapter.get_context()

        assert adapter.health.status == IntegrationStatus.HEALTHY


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_malformed_json_handled(self, temp_tasks_dir):
        """Malformed JSON doesn't crash adapter."""
        (temp_tasks_dir / "bad.json").write_text("not valid json {{{")

        adapter = create_json_task_adapter(str(temp_tasks_dir / "bad.json"))
        context = await adapter.get_context()

        # Should return empty context
        assert context.total_tasks == 0

    @pytest.mark.asyncio
    async def test_empty_tasks_array(self, temp_tasks_dir):
        """Empty tasks array returns empty context."""
        content = {"tasks": []}
        (temp_tasks_dir / "empty.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "empty.json"))
        context = await adapter.get_context()

        assert context.total_tasks == 0
        assert context.load_level == "light"

    @pytest.mark.asyncio
    async def test_unicode_content(self, temp_tasks_dir):
        """Unicode characters are handled."""
        content = {"tasks": [{"due_date": "2024-01-15", "title": "日本語タスク 🎯"}]}
        (temp_tasks_dir / "unicode.json").write_text(
            json.dumps(content, ensure_ascii=False),
            encoding="utf-8"
        )

        adapter = create_json_task_adapter(str(temp_tasks_dir / "unicode.json"))
        result = await adapter.initialize()

        assert result is True

    @pytest.mark.asyncio
    async def test_tasks_without_due_date(self, temp_tasks_dir):
        """Tasks without due dates are included."""
        content = {"tasks": [{"priority": "high"}, {"priority": "normal"}]}
        (temp_tasks_dir / "no_dates.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "no_dates.json"))
        context = await adapter.get_context()

        assert context.total_tasks == 2

    @pytest.mark.asyncio
    async def test_invalid_task_entries_skipped(self, temp_tasks_dir):
        """Non-dict task entries are skipped."""
        content = {"tasks": [{"priority": "high"}, "not a task", 123, None]}
        (temp_tasks_dir / "mixed.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "mixed.json"))
        context = await adapter.get_context()

        # Only the valid dict task
        assert context.total_tasks == 1


# =============================================================================
# Test: Multiple Files
# =============================================================================

class TestMultipleFiles:
    """Tests for handling multiple JSON files."""

    @pytest.mark.asyncio
    async def test_merges_tasks_from_multiple_files(self, temp_tasks_dir):
        """Tasks from multiple files are merged."""
        work_content = {"tasks": [{"priority": "high"}, {"priority": "high"}]}
        personal_content = {"tasks": [{"priority": "normal"}]}

        (temp_tasks_dir / "work.json").write_text(json.dumps(work_content))
        (temp_tasks_dir / "personal.json").write_text(json.dumps(personal_content))

        adapter = create_json_task_adapter(str(temp_tasks_dir))
        context = await adapter.get_context()

        assert context.total_tasks == 3
        assert context.high_priority_count == 2


# =============================================================================
# Test: Context Signals
# =============================================================================

class TestContextSignals:
    """Tests for context signals."""

    @pytest.mark.asyncio
    async def test_task_overload_signal(self, temp_tasks_dir):
        """Overloaded tasks trigger TASK_OVERLOAD signal."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        content = {"tasks": [{"due_date": yesterday} for _ in range(10)]}
        (temp_tasks_dir / "overdue.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "overdue.json"))
        context = await adapter.get_context()

        from otto.integration.models import ContextSignal
        signals = context.get_signals()

        assert ContextSignal.TASK_OVERLOAD in signals

    @pytest.mark.asyncio
    async def test_task_manageable_signal(self, temp_tasks_dir):
        """Light load triggers TASK_MANAGEABLE signal."""
        content = {"tasks": [{"priority": "normal"}]}
        (temp_tasks_dir / "light.json").write_text(json.dumps(content))

        adapter = create_json_task_adapter(str(temp_tasks_dir / "light.json"))
        context = await adapter.get_context()

        from otto.integration.models import ContextSignal
        signals = context.get_signals()

        assert ContextSignal.TASK_MANAGEABLE in signals


# =============================================================================
# Test: Factory Function
# =============================================================================

class TestFactoryFunction:
    """Tests for create_json_task_adapter factory."""

    def test_creates_adapter_with_correct_config(self, sample_tasks_file):
        """Factory creates properly configured adapter."""
        adapter = create_json_task_adapter(str(sample_tasks_file))

        assert isinstance(adapter, JsonTaskAdapter)
        assert adapter.config.service_name == "json_tasks"
        assert adapter.config.integration_type == IntegrationType.TASK_MANAGER
        assert adapter.config.settings["tasks_path"] == str(sample_tasks_file)
