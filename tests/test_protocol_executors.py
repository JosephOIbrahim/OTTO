"""
Tests for Agent Executors
==========================

Tests for the default agent executor implementations.
"""

import pytest
import tempfile
from pathlib import Path

from otto.protocol.agent_executors import (
    explore_executor,
    implement_executor,
    review_executor,
    research_executor,
    general_executor,
    get_executor,
    list_executors,
    EXECUTOR_REGISTRY,
)


class TestExploreExecutor:
    """Tests for explore_executor."""

    @pytest.mark.asyncio
    async def test_returns_required_keys(self):
        """Executor returns all required keys."""
        result = await explore_executor("Find patterns", {})

        assert "findings" in result
        assert "files_read" in result
        assert "patterns" in result
        assert "summary" in result
        assert "duration_seconds" in result

    @pytest.mark.asyncio
    async def test_findings_is_list(self):
        """Findings is a list."""
        result = await explore_executor("Find patterns", {})
        assert isinstance(result["findings"], list)

    @pytest.mark.asyncio
    async def test_reads_specified_files(self):
        """Reads files specified in context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def hello(): pass\n# TODO: implement")

            result = await explore_executor(
                "Find patterns",
                {"files": [str(test_file)], "patterns": ["TODO"]}
            )

            assert str(test_file) in result["files_read"]
            # Should find the TODO pattern
            assert len(result["findings"]) > 0

    @pytest.mark.asyncio
    async def test_handles_missing_files(self):
        """Handles missing files gracefully."""
        result = await explore_executor(
            "Find patterns",
            {"files": ["/nonexistent/file.py"]}
        )

        # Should not crash, just empty results
        assert result["files_read"] == []


class TestImplementExecutor:
    """Tests for implement_executor."""

    @pytest.mark.asyncio
    async def test_returns_required_keys(self):
        """Executor returns all required keys."""
        result = await implement_executor("Create a function", {})

        assert "code" in result
        assert "files_modified" in result
        assert "approach" in result
        assert "notes" in result
        assert "requires_human_review" in result
        assert "duration_seconds" in result

    @pytest.mark.asyncio
    async def test_marks_for_human_review(self):
        """Implementation requires human review."""
        result = await implement_executor("Create a function", {})
        assert result["requires_human_review"] is True

    @pytest.mark.asyncio
    async def test_respects_language_context(self):
        """Uses language from context."""
        result = await implement_executor(
            "Create a function",
            {"language": "typescript"}
        )

        assert "typescript" in result["approach"].lower()


class TestReviewExecutor:
    """Tests for review_executor."""

    @pytest.mark.asyncio
    async def test_returns_required_keys(self):
        """Executor returns all required keys."""
        result = await review_executor("Review this code", {})

        assert "issues" in result
        assert "suggestions" in result
        assert "files_reviewed" in result
        assert "summary" in result
        assert "duration_seconds" in result

    @pytest.mark.asyncio
    async def test_finds_todos(self):
        """Finds TODO comments in files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("# TODO: fix this\n# FIXME: also this")

            result = await review_executor(
                "Review code",
                {"files": [str(test_file)]}
            )

            assert str(test_file) in result["files_reviewed"]
            # Should find TODO and FIXME
            assert len(result["suggestions"]) >= 2

    @pytest.mark.asyncio
    async def test_detects_large_files(self):
        """Detects overly large files as issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "large.py"
            # Create a file with 600 lines
            test_file.write_text("\n".join([f"line {i}" for i in range(600)]))

            result = await review_executor(
                "Review code",
                {"files": [str(test_file)]}
            )

            # Should flag as complexity issue
            complexity_issues = [i for i in result["issues"] if i["type"] == "complexity"]
            assert len(complexity_issues) > 0


class TestResearchExecutor:
    """Tests for research_executor."""

    @pytest.mark.asyncio
    async def test_returns_required_keys(self):
        """Executor returns all required keys."""
        result = await research_executor("Research topic X", {})

        assert "findings" in result
        assert "sources" in result
        assert "synthesis" in result
        assert "questions" in result
        assert "duration_seconds" in result

    @pytest.mark.asyncio
    async def test_generates_followup_questions(self):
        """Generates follow-up questions."""
        result = await research_executor("Research topic X", {})
        assert len(result["questions"]) > 0


class TestGeneralExecutor:
    """Tests for general_executor."""

    @pytest.mark.asyncio
    async def test_returns_required_keys(self):
        """Executor returns all required keys."""
        result = await general_executor("Do something", {})

        assert "result" in result
        assert "actions" in result
        assert "status" in result
        assert "duration_seconds" in result

    @pytest.mark.asyncio
    async def test_completes_successfully(self):
        """Task completes with success status."""
        result = await general_executor("Do something", {})
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_includes_context_keys(self):
        """Includes context keys in result."""
        result = await general_executor(
            "Do something",
            {"key1": "value1", "key2": "value2"}
        )

        assert "key1" in result["context_keys"]
        assert "key2" in result["context_keys"]


class TestExecutorRegistry:
    """Tests for executor registry."""

    def test_registry_has_all_executors(self):
        """Registry contains all default executors."""
        assert "explore" in EXECUTOR_REGISTRY
        assert "implement" in EXECUTOR_REGISTRY
        assert "review" in EXECUTOR_REGISTRY
        assert "research" in EXECUTOR_REGISTRY
        assert "general" in EXECUTOR_REGISTRY

    def test_get_executor_returns_function(self):
        """get_executor returns executor function."""
        executor = get_executor("explore")
        assert callable(executor)
        assert executor == explore_executor

    def test_get_executor_unknown_returns_none(self):
        """get_executor returns None for unknown type."""
        executor = get_executor("unknown_type")
        assert executor is None

    def test_list_executors(self):
        """list_executors returns all executor types."""
        executors = list_executors()
        assert "explore" in executors
        assert "implement" in executors
        assert "review" in executors
        assert "research" in executors
        assert "general" in executors


class TestExecutorIntegration:
    """Integration tests for executors with agent bridge."""

    @pytest.mark.asyncio
    async def test_explore_executor_with_bridge(self):
        """Explore executor works with agent bridge."""
        from otto.protocol import create_protocol_router

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def example(): pass")

            # Create router without decision engine so agents actually spawn
            # (With decision engine, it may choose to work directly)
            # Pass False to explicitly disable (None = auto-create)
            router = create_protocol_router(
                otto_dir=Path(tmpdir),
                decision_engine=False,  # Explicitly disable
                register_default_executors=True
            )

            # Spawn explore agent
            response = await router.route({
                "jsonrpc": "2.0",
                "method": "otto.agent.spawn",
                "params": {
                    "task": "Find functions",
                    "agent_type": "explore",
                    "context": {
                        "files": [str(test_file)],
                        "patterns": ["def"]
                    }
                },
                "id": 1
            })

            assert response["result"]["status"] == "spawned"

            # Wait for executor to run
            import asyncio
            await asyncio.sleep(0.2)

            # Check agent status
            agent_id = response["result"]["agent_id"]
            status_response = await router.route({
                "jsonrpc": "2.0",
                "method": "otto.agent.status",
                "params": {"agent_id": agent_id},
                "id": 2
            })

            # Should be completed
            assert status_response["result"]["status"] == "completed"
            assert "findings" in status_response["result"]["result"]

    @pytest.mark.asyncio
    async def test_review_executor_with_bridge(self):
        """Review executor works with agent bridge."""
        from otto.protocol import create_protocol_router

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file with TODO
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("# TODO: implement this\ndef stub(): pass")

            # Create router without decision engine so agents actually spawn
            router = create_protocol_router(
                otto_dir=Path(tmpdir),
                decision_engine=False,  # Explicitly disable
                register_default_executors=True
            )

            # Spawn review agent
            response = await router.route({
                "jsonrpc": "2.0",
                "method": "otto.agent.spawn",
                "params": {
                    "task": "Review code quality",
                    "agent_type": "review",
                    "context": {
                        "files": [str(test_file)]
                    }
                },
                "id": 1
            })

            assert response["result"]["status"] == "spawned"

            # Wait for executor to run
            import asyncio
            await asyncio.sleep(0.2)

            # Check agent status
            agent_id = response["result"]["agent_id"]
            status_response = await router.route({
                "jsonrpc": "2.0",
                "method": "otto.agent.status",
                "params": {"agent_id": agent_id},
                "id": 2
            })

            # Should be completed with suggestions
            assert status_response["result"]["status"] == "completed"
            assert "suggestions" in status_response["result"]["result"]
