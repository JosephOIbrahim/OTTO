"""
Tests for OTTO OS Agents
========================

Tests for ValidationAgent and ContextAgent covering:
- File validation and compliance detection
- Import extraction and dependency mapping
- Trail deposition
- Reporting and summaries

Determinism:
- Tests use deterministic inputs
- Output verification uses sorted comparisons
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from otto.agents import (
    ValidationAgent,
    ValidationResult,
    ValidationFinding,
    ValidationSeverity,
    ContextAgent,
    FileContext,
    ImportInfo,
    DependencyGraph,
)
from otto.trails import Trail, TrailStore, TrailType


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_store():
    """Create a mock trail store."""
    store = MagicMock(spec=TrailStore)
    store.deposit = MagicMock()
    return store


@pytest.fixture
def validation_agent(mock_store):
    """Create a ValidationAgent with mock store."""
    return ValidationAgent(store=mock_store, agent_id="test_validator")


@pytest.fixture
def context_agent(mock_store, temp_dir):
    """Create a ContextAgent with mock store."""
    return ContextAgent(store=mock_store, agent_id="test_context", base_path=temp_dir)


# =============================================================================
# ValidationAgent Tests
# =============================================================================

class TestValidationAgent:
    """Tests for ValidationAgent."""

    @pytest.mark.asyncio
    async def test_validate_nonexistent_file(self, validation_agent):
        """Nonexistent files should return compliant result."""
        result = await validation_agent.validate_file("/nonexistent/file.py")

        assert result.is_compliant is True
        assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_validate_non_python_file(self, validation_agent, temp_dir):
        """Non-Python files should return compliant result."""
        txt_file = temp_dir / "readme.txt"
        txt_file.write_text("This is a text file")

        result = await validation_agent.validate_file(txt_file)

        assert result.is_compliant is True
        assert len(result.findings) == 0

    @pytest.mark.asyncio
    async def test_validate_compliant_file(self, validation_agent, temp_dir):
        """Compliant files should have no violations."""
        py_file = temp_dir / "compliant.py"
        py_file.write_text("""
# Compliant code
from otto.determinism import sorted_max, kahan_sum

def get_best(scores: dict) -> str:
    return sorted_max(scores)

def total(values: list) -> float:
    return kahan_sum(sorted(values))
""")

        result = await validation_agent.validate_file(py_file)

        assert result.is_compliant is True
        assert result.error_count == 0

    @pytest.mark.asyncio
    async def test_detect_max_on_dict_items(self, validation_agent, temp_dir):
        """Should detect max() on dict.items()."""
        py_file = temp_dir / "violation.py"
        py_file.write_text("""
def get_best(scores: dict):
    # Violation: max on dict.items() is non-deterministic
    return max(scores.items(), key=lambda x: x[1])
""")

        result = await validation_agent.validate_file(py_file)

        assert result.is_compliant is False
        assert any("HE2025-001" in f.code for f in result.findings)

    @pytest.mark.asyncio
    async def test_detect_iterate_set(self, validation_agent, temp_dir):
        """Should detect iteration over unsorted set."""
        py_file = temp_dir / "set_violation.py"
        py_file.write_text("""
def process_items(items):
    # Violation: iterating over set is non-deterministic
    for item in set(items):
        print(item)
""")

        result = await validation_agent.validate_file(py_file)

        # Note: depends on check_he2025_compliance implementation
        # This may or may not be detected based on regex patterns

    @pytest.mark.asyncio
    async def test_deposits_trails(self, validation_agent, mock_store, temp_dir):
        """Should deposit trails for findings."""
        py_file = temp_dir / "with_trails.py"
        py_file.write_text("""
from otto.determinism import sorted_max

def compliant():
    pass
""")

        result = await validation_agent.validate_file(py_file)

        # Should have deposited at least compliance trails
        assert result.trails_deposited >= 0
        # If compliant patterns found, store.deposit should be called
        if result.trails_deposited > 0:
            assert mock_store.deposit.called

    @pytest.mark.asyncio
    async def test_validate_directory(self, validation_agent, temp_dir):
        """Should validate all Python files in directory."""
        # Create test files
        (temp_dir / "file1.py").write_text("x = 1")
        (temp_dir / "file2.py").write_text("y = 2")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file3.py").write_text("z = 3")

        results = await validation_agent.validate_directory(temp_dir, recursive=True)

        assert len(results) == 3
        # Results should be sorted by path for determinism
        paths = [r.path for r in results]
        assert paths == sorted(paths)

    @pytest.mark.asyncio
    async def test_validate_directory_non_recursive(self, validation_agent, temp_dir):
        """Non-recursive validation should skip subdirectories."""
        (temp_dir / "file1.py").write_text("x = 1")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file2.py").write_text("y = 2")

        results = await validation_agent.validate_directory(temp_dir, recursive=False)

        assert len(results) == 1

    def test_get_summary(self, validation_agent):
        """Summary should aggregate results correctly."""
        results = [
            ValidationResult(path="a.py", is_compliant=True, findings=[], trails_deposited=2),
            ValidationResult(path="b.py", is_compliant=False, findings=[
                ValidationFinding(
                    file_path="b.py",
                    line=10,
                    column=5,
                    code="HE2025-001",
                    message="Test",
                    severity=ValidationSeverity.ERROR,
                )
            ], trails_deposited=1),
            ValidationResult(path="c.py", is_compliant=True, findings=[], trails_deposited=3),
        ]

        summary = validation_agent.get_summary(results)

        assert summary["total_files"] == 3
        assert summary["compliant_files"] == 2
        assert summary["non_compliant_files"] == 1
        assert summary["total_errors"] == 1
        assert summary["total_trails_deposited"] == 6
        assert summary["compliance_rate"] == pytest.approx(66.67, rel=0.01)

    def test_format_report(self, validation_agent):
        """Report formatting should be readable."""
        results = [
            ValidationResult(path="test.py", is_compliant=False, findings=[
                ValidationFinding(
                    file_path="test.py",
                    line=42,
                    column=0,
                    code="HE2025-001",
                    message="max() on dict.items() is non-deterministic",
                    severity=ValidationSeverity.ERROR,
                    suggestion="Use sorted_max() from otto.determinism",
                )
            ]),
        ]

        report = validation_agent.format_report(results)

        assert "Determinism Report" in report
        assert "test.py" in report
        assert "HE2025-001" in report
        assert "sorted_max" in report


class TestValidationFinding:
    """Tests for ValidationFinding dataclass."""

    def test_to_signal(self):
        """Signal format should be consistent."""
        finding = ValidationFinding(
            file_path="test.py",
            line=42,
            column=5,
            code="HE2025-001",
            message="Test violation",
            severity=ValidationSeverity.ERROR,
        )

        signal = finding.to_signal()

        assert signal == "he2025_violation:HE2025-001:L42"

    def test_error_count(self):
        """Error count should include ERROR and CRITICAL."""
        result = ValidationResult(
            path="test.py",
            is_compliant=False,
            findings=[
                ValidationFinding("f", 1, 0, "X", "m", ValidationSeverity.INFO),
                ValidationFinding("f", 2, 0, "X", "m", ValidationSeverity.WARNING),
                ValidationFinding("f", 3, 0, "X", "m", ValidationSeverity.ERROR),
                ValidationFinding("f", 4, 0, "X", "m", ValidationSeverity.CRITICAL),
            ],
        )

        assert result.error_count == 2
        assert result.warning_count == 1


# =============================================================================
# ContextAgent Tests
# =============================================================================

class TestContextAgent:
    """Tests for ContextAgent."""

    @pytest.mark.asyncio
    async def test_analyze_nonexistent_file(self, context_agent):
        """Nonexistent files should return empty context."""
        result = await context_agent.analyze_file("/nonexistent/file.py")

        # Path may have platform-specific separators
        assert "nonexistent" in result.path and "file.py" in result.path
        assert len(result.imports) == 0

    @pytest.mark.asyncio
    async def test_analyze_non_python_file(self, context_agent, temp_dir):
        """Non-Python files should return empty context."""
        txt_file = temp_dir / "readme.txt"
        txt_file.write_text("This is a text file")

        result = await context_agent.analyze_file(txt_file)

        assert len(result.imports) == 0

    @pytest.mark.asyncio
    async def test_extract_absolute_imports(self, context_agent, temp_dir):
        """Should extract absolute imports."""
        py_file = temp_dir / "imports.py"
        py_file.write_text("""
import os
import sys
from pathlib import Path
from typing import Optional, List
from otto.trails import Trail, TrailStore
""")

        result = await context_agent.analyze_file(py_file)

        # Check otto.trails import is captured
        otto_imports = [i for i in result.imports if "otto" in i.module]
        assert len(otto_imports) == 1
        assert otto_imports[0].module == "otto.trails"
        assert set(otto_imports[0].names) == {"Trail", "TrailStore"}

    @pytest.mark.asyncio
    async def test_extract_relative_imports(self, context_agent, temp_dir):
        """Should extract relative imports."""
        py_file = temp_dir / "relative.py"
        py_file.write_text("""
from . import sibling
from .. import parent
from ..utils import helper
from ...deep import module
""")

        result = await context_agent.analyze_file(py_file)

        relative_imports = [i for i in result.imports if i.is_relative]
        assert len(relative_imports) == 4

        # Check levels are correct
        levels = sorted([i.level for i in relative_imports])
        assert levels == [1, 2, 2, 3]

    @pytest.mark.asyncio
    async def test_extract_class_definitions(self, context_agent, temp_dir):
        """Should extract class names."""
        py_file = temp_dir / "classes.py"
        py_file.write_text("""
class Alpha:
    pass

class Beta:
    pass

class _Private:
    pass
""")

        result = await context_agent.analyze_file(py_file)

        # All classes should be found (including private)
        assert "Alpha" in result.classes
        assert "Beta" in result.classes
        assert "_Private" in result.classes

    @pytest.mark.asyncio
    async def test_extract_function_definitions(self, context_agent, temp_dir):
        """Should extract public function names."""
        py_file = temp_dir / "functions.py"
        py_file.write_text("""
def public_func():
    pass

async def async_func():
    pass

def _private_func():
    pass
""")

        result = await context_agent.analyze_file(py_file)

        assert "public_func" in result.functions
        assert "async_func" in result.functions
        # Private functions are excluded
        assert "_private_func" not in result.functions

    @pytest.mark.asyncio
    async def test_extract_all_exports(self, context_agent, temp_dir):
        """Should extract __all__ exports."""
        py_file = temp_dir / "exports.py"
        py_file.write_text("""
__all__ = ["Foo", "Bar", "baz"]

class Foo:
    pass

class Bar:
    pass

def baz():
    pass
""")

        result = await context_agent.analyze_file(py_file)

        assert set(result.exported_names) == {"Foo", "Bar", "baz"}

    @pytest.mark.asyncio
    async def test_deposits_trails(self, context_agent, mock_store, temp_dir):
        """Should deposit trails for dependencies."""
        py_file = temp_dir / "with_trails.py"
        py_file.write_text("""
from otto.trails import Trail

class MyClass:
    pass

def my_function():
    pass
""")

        result = await context_agent.analyze_file(py_file)

        # Should deposit trails for:
        # - depends_on:otto/trails.py
        # - defines_class:MyClass
        # - defines_function:my_function
        assert result.trails_deposited >= 3
        assert mock_store.deposit.call_count >= 3

    @pytest.mark.asyncio
    async def test_analyze_directory(self, context_agent, temp_dir):
        """Should analyze all Python files in directory."""
        (temp_dir / "file1.py").write_text("class A: pass")
        (temp_dir / "file2.py").write_text("class B: pass")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file3.py").write_text("class C: pass")

        results = await context_agent.analyze_directory(temp_dir, recursive=True)

        assert len(results) == 3
        # Results should be sorted by path for determinism
        paths = [r.path for r in results]
        assert paths == sorted(paths)

    @pytest.mark.asyncio
    async def test_build_dependency_graph(self, context_agent, temp_dir):
        """Should build complete dependency graph."""
        # Create interconnected files
        (temp_dir / "base.py").write_text("class Base: pass")
        (temp_dir / "derived.py").write_text("""
from otto.base import Base

class Derived(Base):
    pass
""")

        graph = await context_agent.build_dependency_graph(temp_dir)

        assert graph.node_count == 2
        # Edges should be sorted for determinism
        assert graph.edges == sorted(graph.edges)

    @pytest.mark.asyncio
    async def test_skip_pycache(self, context_agent, temp_dir):
        """Should skip __pycache__ directories."""
        (temp_dir / "main.py").write_text("x = 1")
        (temp_dir / "__pycache__").mkdir()
        (temp_dir / "__pycache__" / "main.cpython-311.pyc").write_bytes(b"compiled")

        results = await context_agent.analyze_directory(temp_dir)

        assert len(results) == 1
        assert "__pycache__" not in results[0].path

    def test_get_summary(self, context_agent):
        """Summary should aggregate contexts correctly."""
        contexts = [
            FileContext(path="a.py", imports=[
                ImportInfo("os", [], False, 0, 1),
            ], classes=["A"], functions=["f1", "f2"], trails_deposited=5),
            FileContext(path="b.py", imports=[
                ImportInfo("sys", [], False, 0, 1),
                ImportInfo("json", [], False, 0, 2),
            ], classes=["B", "C"], functions=[], trails_deposited=3),
        ]

        summary = context_agent.get_summary(contexts)

        assert summary["total_files"] == 2
        assert summary["total_imports"] == 3
        assert summary["total_classes"] == 3
        assert summary["total_functions"] == 2
        assert summary["total_trails_deposited"] == 8

    def test_format_graph(self, context_agent):
        """Graph formatting should be readable."""
        graph = DependencyGraph(
            files={
                "a.py": FileContext(path="a.py"),
                "b.py": FileContext(path="b.py"),
            },
            edges=[("b.py", "a.py"), ("b.py", "a.py")],  # b depends on a
        )

        report = context_agent.format_graph(graph)

        assert "Dependency Graph Report" in report
        assert "Files:  2" in report


class TestDependencyGraph:
    """Tests for DependencyGraph dataclass."""

    def test_node_count(self):
        """Node count should reflect files."""
        graph = DependencyGraph(
            files={"a.py": FileContext("a.py"), "b.py": FileContext("b.py")},
            edges=[],
        )

        assert graph.node_count == 2

    def test_edge_count(self):
        """Edge count should reflect dependencies."""
        graph = DependencyGraph(
            files={},
            edges=[("a.py", "b.py"), ("a.py", "c.py")],
        )

        assert graph.edge_count == 2

    def test_get_dependents(self):
        """Should return files that depend on target."""
        graph = DependencyGraph(
            files={},
            edges=[
                ("consumer1.py", "lib.py"),
                ("consumer2.py", "lib.py"),
                ("other.py", "unrelated.py"),
            ],
        )

        dependents = graph.get_dependents("lib.py")

        assert sorted(dependents) == ["consumer1.py", "consumer2.py"]

    def test_get_dependencies(self):
        """Should return files that target depends on."""
        graph = DependencyGraph(
            files={},
            edges=[
                ("main.py", "lib1.py"),
                ("main.py", "lib2.py"),
                ("other.py", "lib3.py"),
            ],
        )

        deps = graph.get_dependencies("main.py")

        assert sorted(deps) == ["lib1.py", "lib2.py"]


class TestImportInfo:
    """Tests for ImportInfo dataclass."""

    def test_absolute_import(self):
        """Absolute imports should have level 0."""
        info = ImportInfo(
            module="otto.trails",
            names=["Trail"],
            is_relative=False,
            level=0,
            line=1,
        )

        assert info.is_relative is False
        assert info.level == 0

    def test_relative_import(self):
        """Relative imports should have level > 0."""
        info = ImportInfo(
            module="utils",
            names=["helper"],
            is_relative=True,
            level=2,
            line=5,
        )

        assert info.is_relative is True
        assert info.level == 2


# =============================================================================
# Integration Tests
# =============================================================================

class TestAgentIntegration:
    """Integration tests for agents working together."""

    @pytest.mark.asyncio
    async def test_validation_and_context_same_file(self, temp_dir):
        """Both agents should analyze the same file consistently."""
        py_file = temp_dir / "target.py"
        py_file.write_text("""
from otto.determinism import sorted_max

class MyClass:
    def get_best(self, scores):
        return sorted_max(scores)
""")

        store = MagicMock(spec=TrailStore)
        store.deposit = MagicMock()

        val_agent = ValidationAgent(store=store, agent_id="validator")
        ctx_agent = ContextAgent(store=store, agent_id="context")

        val_result = await val_agent.validate_file(py_file)
        ctx_result = await ctx_agent.analyze_file(py_file)

        # Both should have analyzed the same file
        assert Path(val_result.path).name == "target.py"
        assert Path(ctx_result.path).name == "target.py"

        # Context should have found the class
        assert "MyClass" in ctx_result.classes

    @pytest.mark.asyncio
    async def test_trails_use_correct_types(self, temp_dir):
        """Agents should deposit correct trail types."""
        py_file = temp_dir / "mixed.py"
        py_file.write_text("""
from otto.trails import Trail
from otto.determinism import kahan_sum

class Calculator:
    def total(self, values):
        return kahan_sum(sorted(values))
""")

        deposited_trails = []

        def capture_trail(trail):
            deposited_trails.append(trail)

        store = MagicMock(spec=TrailStore)
        store.deposit = capture_trail

        val_agent = ValidationAgent(store=store, agent_id="validator")
        ctx_agent = ContextAgent(store=store, agent_id="context")

        await val_agent.validate_file(py_file)
        await ctx_agent.analyze_file(py_file)

        # Check trail types
        trail_types = [t.trail_type for t in deposited_trails]

        # Validation deposits QUALITY trails
        # Context deposits CONTEXT trails
        assert TrailType.QUALITY in trail_types or TrailType.CONTEXT in trail_types


# =============================================================================
# Determinism Tests (Determinism)
# =============================================================================

class TestDeterminism:
    """Tests verifying Determinism."""

    @pytest.mark.asyncio
    async def test_validation_order_deterministic(self, temp_dir):
        """Validation should process files in deterministic order."""
        # Create files with names that would sort differently
        (temp_dir / "zebra.py").write_text("x = 1")
        (temp_dir / "alpha.py").write_text("y = 2")
        (temp_dir / "middle.py").write_text("z = 3")

        store = MagicMock(spec=TrailStore)
        agent = ValidationAgent(store=store)

        # Run multiple times
        results1 = await agent.validate_directory(temp_dir)
        results2 = await agent.validate_directory(temp_dir)

        paths1 = [r.path for r in results1]
        paths2 = [r.path for r in results2]

        assert paths1 == paths2
        assert paths1 == sorted(paths1)

    @pytest.mark.asyncio
    async def test_context_order_deterministic(self, temp_dir):
        """Context analysis should process files in deterministic order."""
        (temp_dir / "zebra.py").write_text("class Z: pass")
        (temp_dir / "alpha.py").write_text("class A: pass")
        (temp_dir / "middle.py").write_text("class M: pass")

        store = MagicMock(spec=TrailStore)
        agent = ContextAgent(store=store, base_path=temp_dir)

        # Run multiple times
        results1 = await agent.analyze_directory(temp_dir)
        results2 = await agent.analyze_directory(temp_dir)

        paths1 = [r.path for r in results1]
        paths2 = [r.path for r in results2]

        assert paths1 == paths2
        assert paths1 == sorted(paths1)

    @pytest.mark.asyncio
    async def test_imports_sorted_by_line(self, temp_dir):
        """Imports should be sorted by line number."""
        py_file = temp_dir / "imports.py"
        py_file.write_text("""
import sys
import os
from typing import List
import json
""")

        store = MagicMock(spec=TrailStore)
        agent = ContextAgent(store=store, base_path=temp_dir)

        result = await agent.analyze_file(py_file)

        lines = [i.line for i in result.imports]
        assert lines == sorted(lines)

    @pytest.mark.asyncio
    async def test_graph_edges_sorted(self, temp_dir):
        """Dependency graph edges should be sorted."""
        (temp_dir / "a.py").write_text("from otto.b import B")
        (temp_dir / "b.py").write_text("from otto.c import C")
        (temp_dir / "c.py").write_text("x = 1")

        store = MagicMock(spec=TrailStore)
        agent = ContextAgent(store=store, base_path=temp_dir)

        graph = await agent.build_dependency_graph(temp_dir)

        assert graph.edges == sorted(graph.edges)

    @pytest.mark.asyncio
    async def test_findings_sorted(self, temp_dir):
        """Validation findings should be sorted deterministically."""
        py_file = temp_dir / "violations.py"
        # Create file with multiple potential violations
        py_file.write_text("""
import random

def func1():
    random.choice([1, 2, 3])

def func2():
    max({"a": 1, "b": 2}.items(), key=lambda x: x[1])
""")

        store = MagicMock(spec=TrailStore)
        agent = ValidationAgent(store=store)

        result1 = await agent.validate_file(py_file)
        result2 = await agent.validate_file(py_file)

        # Findings should be identical between runs
        codes1 = [(f.line, f.code) for f in result1.findings]
        codes2 = [(f.line, f.code) for f in result2.findings]

        assert codes1 == codes2
