"""
Tests for health check module.

Tests:
- HealthStatus enum values
- ComponentHealth dataclass
- HealthReport serialization and properties
- HealthChecker component checks
- Health report formatting
"""

import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import os
import stat

from otto.health import (
    HealthStatus,
    ComponentHealth,
    HealthReport,
    HealthChecker,
    format_health_report,
)


class TestHealthStatus:
    """Test HealthStatus enum."""

    def test_enum_values(self):
        """Should have correct status values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_enum_members(self):
        """Should have exactly three members."""
        assert len(HealthStatus) == 3


class TestComponentHealth:
    """Test ComponentHealth dataclass."""

    def test_minimal_creation(self):
        """Should create with required fields only."""
        health = ComponentHealth(
            name='test',
            status=HealthStatus.HEALTHY
        )
        assert health.name == 'test'
        assert health.status == HealthStatus.HEALTHY
        assert health.message == ""
        assert health.details == {}

    def test_full_creation(self):
        """Should create with all fields."""
        health = ComponentHealth(
            name='agents',
            status=HealthStatus.DEGRADED,
            message='Only 3/7 agents initialized',
            details={'count': 3, 'expected': 7}
        )
        assert health.name == 'agents'
        assert health.status == HealthStatus.DEGRADED
        assert health.message == 'Only 3/7 agents initialized'
        assert health.details == {'count': 3, 'expected': 7}


class TestHealthReport:
    """Test HealthReport dataclass."""

    def test_creation(self):
        """Should create health report."""
        components = [
            ComponentHealth(name='test', status=HealthStatus.HEALTHY)
        ]
        report = HealthReport(
            status=HealthStatus.HEALTHY,
            components=components,
            uptime_seconds=100.5
        )
        assert report.status == HealthStatus.HEALTHY
        assert len(report.components) == 1
        assert report.uptime_seconds == 100.5
        assert report.timestamp > 0

    def test_to_dict(self):
        """Should serialize to dictionary."""
        components = [
            ComponentHealth(
                name='agents',
                status=HealthStatus.HEALTHY,
                message='All good',
                details={'count': 7}
            )
        ]
        report = HealthReport(
            status=HealthStatus.HEALTHY,
            components=components,
            uptime_seconds=123.456
        )

        data = report.to_dict()

        assert data['status'] == 'healthy'
        assert data['uptime_seconds'] == 123.46  # Rounded to 2 decimal places
        assert 'timestamp' in data
        assert len(data['components']) == 1
        assert data['components'][0]['name'] == 'agents'
        assert data['components'][0]['status'] == 'healthy'
        assert data['components'][0]['message'] == 'All good'
        assert data['components'][0]['details'] == {'count': 7}

    def test_is_healthy_true(self):
        """Should return True when status is HEALTHY."""
        report = HealthReport(
            status=HealthStatus.HEALTHY,
            components=[],
            uptime_seconds=0
        )
        assert report.is_healthy is True

    def test_is_healthy_false(self):
        """Should return False when status is not HEALTHY."""
        for status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]:
            report = HealthReport(
                status=status,
                components=[],
                uptime_seconds=0
            )
            assert report.is_healthy is False

    def test_is_ready_healthy(self):
        """Should be ready when HEALTHY."""
        report = HealthReport(
            status=HealthStatus.HEALTHY,
            components=[],
            uptime_seconds=0
        )
        assert report.is_ready is True

    def test_is_ready_degraded(self):
        """Should be ready when DEGRADED."""
        report = HealthReport(
            status=HealthStatus.DEGRADED,
            components=[],
            uptime_seconds=0
        )
        assert report.is_ready is True

    def test_is_ready_unhealthy(self):
        """Should not be ready when UNHEALTHY."""
        report = HealthReport(
            status=HealthStatus.UNHEALTHY,
            components=[],
            uptime_seconds=0
        )
        assert report.is_ready is False


class TestHealthChecker:
    """Test HealthChecker class."""

    def test_init_defaults(self):
        """Should initialize with defaults."""
        checker = HealthChecker(workspace=Path('/tmp'))

        assert checker.workspace == Path('/tmp')
        assert checker.agents == {}
        assert checker.circuit_breaker is None
        assert checker._expected_agent_count == 7

    def test_init_with_agents(self):
        """Should initialize with agents."""
        agents = {'agent1': MagicMock(), 'agent2': MagicMock()}
        checker = HealthChecker(
            workspace=Path('/tmp'),
            agents=agents
        )
        assert len(checker.agents) == 2

    def test_set_expected_agents(self):
        """Should allow setting expected agent count."""
        checker = HealthChecker(workspace=Path('/tmp'))
        checker.set_expected_agents(10)
        assert checker._expected_agent_count == 10


class TestHealthCheckerAgents:
    """Test HealthChecker agent checking."""

    def test_agents_healthy_all_present(self):
        """Should be healthy when all expected agents present."""
        agents = {f'agent{i}': MagicMock() for i in range(7)}
        checker = HealthChecker(workspace=Path('/tmp'), agents=agents)

        result = checker._check_agents()

        assert result.status == HealthStatus.HEALTHY
        assert '7/7' in result.message
        assert result.details['count'] == 7

    def test_agents_healthy_more_than_expected(self):
        """Should be healthy when more than expected agents present."""
        agents = {f'agent{i}': MagicMock() for i in range(10)}
        checker = HealthChecker(workspace=Path('/tmp'), agents=agents)

        result = checker._check_agents()

        assert result.status == HealthStatus.HEALTHY
        assert result.details['count'] == 10

    def test_agents_degraded_some_present(self):
        """Should be degraded when some but not all agents present."""
        agents = {f'agent{i}': MagicMock() for i in range(3)}
        checker = HealthChecker(workspace=Path('/tmp'), agents=agents)

        result = checker._check_agents()

        assert result.status == HealthStatus.DEGRADED
        assert 'Only 3/7' in result.message

    def test_agents_unhealthy_none_present(self):
        """Should be unhealthy when no agents present."""
        checker = HealthChecker(workspace=Path('/tmp'), agents={})

        result = checker._check_agents()

        assert result.status == HealthStatus.UNHEALTHY
        assert 'No agents' in result.message


class TestHealthCheckerWorkspace:
    """Test HealthChecker workspace checking."""

    def test_workspace_healthy(self):
        """Should be healthy when workspace exists and is writable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checker = HealthChecker(workspace=Path(tmpdir))

            result = checker._check_workspace()

            assert result.status == HealthStatus.HEALTHY
            assert 'writable' in result.message

    def test_workspace_unhealthy_not_exists(self):
        """Should be unhealthy when workspace does not exist."""
        checker = HealthChecker(workspace=Path('/nonexistent/path/12345'))

        result = checker._check_workspace()

        assert result.status == HealthStatus.UNHEALTHY
        assert 'does not exist' in result.message

    @pytest.mark.skipif(os.name == 'nt', reason="Permission tests unreliable on Windows")
    def test_workspace_unhealthy_not_writable(self):
        """Should be unhealthy when workspace is not writable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            readonly_path = Path(tmpdir) / 'readonly'
            readonly_path.mkdir()

            # Make directory read-only using chmod
            os.chmod(readonly_path, stat.S_IRUSR | stat.S_IXUSR)

            try:
                checker = HealthChecker(workspace=readonly_path)
                result = checker._check_workspace()

                assert result.status == HealthStatus.UNHEALTHY
                assert 'not writable' in result.message
            finally:
                # Restore permissions for cleanup
                os.chmod(readonly_path, stat.S_IRWXU)


class TestHealthCheckerCircuitBreakers:
    """Test HealthChecker circuit breaker checking."""

    def test_no_circuit_breaker(self):
        """Should be healthy when no circuit breaker configured."""
        checker = HealthChecker(workspace=Path('/tmp'))

        result = checker._check_circuit_breakers()

        assert result.status == HealthStatus.HEALTHY
        assert 'not configured' in result.message

    def test_all_circuits_closed(self):
        """Should be healthy when all circuits closed."""
        cb = MagicMock()
        cb.get_all_stats.return_value = {
            'agent1': {'state': 'closed'},
            'agent2': {'state': 'closed'}
        }
        checker = HealthChecker(workspace=Path('/tmp'), circuit_breaker=cb)

        result = checker._check_circuit_breakers()

        assert result.status == HealthStatus.HEALTHY
        assert 'All circuits closed' in result.message

    def test_circuits_half_open(self):
        """Should be degraded when circuits half-open."""
        cb = MagicMock()
        cb.get_all_stats.return_value = {
            'agent1': {'state': 'closed'},
            'agent2': {'state': 'half_open'}
        }
        checker = HealthChecker(workspace=Path('/tmp'), circuit_breaker=cb)

        result = checker._check_circuit_breakers()

        assert result.status == HealthStatus.DEGRADED
        assert 'half-open' in result.message
        assert 'agent2' in result.details['half_open']

    def test_circuits_open(self):
        """Should be degraded when circuits open."""
        cb = MagicMock()
        cb.get_all_stats.return_value = {
            'agent1': {'state': 'open'},
            'agent2': {'state': 'closed'}
        }
        checker = HealthChecker(workspace=Path('/tmp'), circuit_breaker=cb)

        result = checker._check_circuit_breakers()

        assert result.status == HealthStatus.DEGRADED
        assert 'open' in result.message
        assert 'agent1' in result.details['open']


class TestHealthCheckerFullCheck:
    """Test HealthChecker full health check."""

    def test_check_health_all_healthy(self):
        """Should be healthy when all components healthy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents = {f'agent{i}': MagicMock() for i in range(7)}
            checker = HealthChecker(
                workspace=Path(tmpdir),
                agents=agents
            )

            report = checker.check_health()

            assert report.status == HealthStatus.HEALTHY
            assert len(report.components) == 2  # agents + workspace (no circuit breaker)
            assert report.uptime_seconds >= 0

    def test_check_health_degraded(self):
        """Should be degraded when any component degraded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents = {f'agent{i}': MagicMock() for i in range(3)}  # Only 3 agents
            checker = HealthChecker(
                workspace=Path(tmpdir),
                agents=agents
            )

            report = checker.check_health()

            assert report.status == HealthStatus.DEGRADED

    def test_check_health_unhealthy(self):
        """Should be unhealthy when any component unhealthy."""
        checker = HealthChecker(
            workspace=Path('/nonexistent/path'),
            agents={f'agent{i}': MagicMock() for i in range(7)}
        )

        report = checker.check_health()

        assert report.status == HealthStatus.UNHEALTHY

    def test_get_ready_status(self):
        """Should return readiness status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents = {f'agent{i}': MagicMock() for i in range(7)}
            checker = HealthChecker(
                workspace=Path(tmpdir),
                agents=agents
            )

            assert checker.get_ready_status() is True

    def test_uptime_calculation(self):
        """Should calculate uptime correctly."""
        start = time.time() - 100  # Started 100 seconds ago
        checker = HealthChecker(
            workspace=Path('/tmp'),
            start_time=start
        )

        # Just verify uptime is reasonable (accounting for test execution time)
        report = checker.check_health()
        assert report.uptime_seconds >= 100
        assert report.uptime_seconds < 110


class TestFormatHealthReport:
    """Test health report formatting."""

    def test_format_healthy(self):
        """Should format healthy report."""
        report = HealthReport(
            status=HealthStatus.HEALTHY,
            components=[
                ComponentHealth(
                    name='agents',
                    status=HealthStatus.HEALTHY,
                    message='7/7 agents initialized'
                ),
                ComponentHealth(
                    name='workspace',
                    status=HealthStatus.HEALTHY,
                    message='Workspace accessible'
                )
            ],
            uptime_seconds=123.4
        )

        output = format_health_report(report)

        assert 'HEALTHY' in output
        assert '123.4s' in output
        assert 'agents' in output
        assert 'workspace' in output

    def test_format_degraded(self):
        """Should format degraded report with warning indicator."""
        report = HealthReport(
            status=HealthStatus.DEGRADED,
            components=[
                ComponentHealth(
                    name='agents',
                    status=HealthStatus.DEGRADED,
                    message='Only 3/7 agents'
                )
            ],
            uptime_seconds=50.0
        )

        output = format_health_report(report)

        assert 'DEGRADED' in output
        assert '[!]' in output  # Warning indicator

    def test_format_unhealthy(self):
        """Should format unhealthy report with error indicator."""
        report = HealthReport(
            status=HealthStatus.UNHEALTHY,
            components=[
                ComponentHealth(
                    name='workspace',
                    status=HealthStatus.UNHEALTHY,
                    message='Directory not found'
                )
            ],
            uptime_seconds=0
        )

        output = format_health_report(report)

        assert 'UNHEALTHY' in output
        assert '[X]' in output  # Error indicator
