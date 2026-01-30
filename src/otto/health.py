"""
Health check system for Framework Orchestrator.

Provides:
- Health status reporting
- Readiness checks for load balancers
- Component status monitoring
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .resilience import CircuitBreaker


class HealthStatus(Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Complete health report for the orchestrator."""
    status: HealthStatus
    components: List[ComponentHealth]
    uptime_seconds: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'status': self.status.value,
            'uptime_seconds': round(self.uptime_seconds, 2),
            'timestamp': self.timestamp,
            'components': [
                {
                    'name': c.name,
                    'status': c.status.value,
                    'message': c.message,
                    'details': c.details
                }
                for c in self.components
            ]
        }

    @property
    def is_healthy(self) -> bool:
        """Check if overall status is healthy."""
        return self.status == HealthStatus.HEALTHY

    @property
    def is_ready(self) -> bool:
        """Check if system is ready to accept requests (healthy or degraded)."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)


class HealthChecker:
    """
    Health checker for Framework Orchestrator.

    Monitors:
    - Agent initialization status
    - Workspace writability
    - Circuit breaker states
    - Configuration validity

    Usage:
        checker = HealthChecker(orchestrator)
        report = checker.check_health()

        if report.is_ready:
            # Accept requests
            ...
    """

    def __init__(
        self,
        workspace: Path,
        agents: Optional[Dict[str, Any]] = None,
        circuit_breaker: Optional['CircuitBreaker'] = None,
        start_time: Optional[float] = None
    ):
        """
        Initialize health checker.

        Args:
            workspace: Workspace directory path
            agents: Dictionary of agents (name -> agent)
            circuit_breaker: Circuit breaker instance
            start_time: Process start time (defaults to now)
        """
        self.workspace = workspace
        self.agents = agents or {}
        self.circuit_breaker = circuit_breaker
        self.start_time = start_time or time.time()
        self._expected_agent_count = 7  # Default expected agent count

    def set_expected_agents(self, count: int) -> None:
        """Set expected number of agents."""
        self._expected_agent_count = count

    def check_health(self) -> HealthReport:
        """
        Perform full health check.

        Returns:
            HealthReport with overall status and component details
        """
        components = []

        # Check agents
        components.append(self._check_agents())

        # Check workspace
        components.append(self._check_workspace())

        # Check circuit breakers
        if self.circuit_breaker:
            components.append(self._check_circuit_breakers())

        # Determine overall status
        statuses = [c.status for c in components]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall = HealthStatus.UNHEALTHY
        else:
            overall = HealthStatus.DEGRADED

        uptime = time.time() - self.start_time

        return HealthReport(
            status=overall,
            components=components,
            uptime_seconds=uptime
        )

    def get_ready_status(self) -> bool:
        """
        Quick readiness check for load balancers.

        Returns:
            True if system is ready to accept requests
        """
        report = self.check_health()
        return report.is_ready

    def _check_agents(self) -> ComponentHealth:
        """Check agent initialization status."""
        agent_count = len(self.agents)
        expected = self._expected_agent_count

        if agent_count >= expected:
            return ComponentHealth(
                name='agents',
                status=HealthStatus.HEALTHY,
                message=f"{agent_count}/{expected} agents initialized",
                details={'count': agent_count, 'expected': expected}
            )
        elif agent_count > 0:
            return ComponentHealth(
                name='agents',
                status=HealthStatus.DEGRADED,
                message=f"Only {agent_count}/{expected} agents initialized",
                details={'count': agent_count, 'expected': expected}
            )
        else:
            return ComponentHealth(
                name='agents',
                status=HealthStatus.UNHEALTHY,
                message="No agents initialized",
                details={'count': 0, 'expected': expected}
            )

    def _check_workspace(self) -> ComponentHealth:
        """Check workspace directory status."""
        try:
            # Check if directory exists
            if not self.workspace.exists():
                return ComponentHealth(
                    name='workspace',
                    status=HealthStatus.UNHEALTHY,
                    message="Workspace directory does not exist",
                    details={'path': str(self.workspace)}
                )

            # Check if writable by creating a test file
            test_file = self.workspace / '.health_check'
            try:
                test_file.write_text('health_check')
                test_file.unlink()
            except Exception as e:
                return ComponentHealth(
                    name='workspace',
                    status=HealthStatus.UNHEALTHY,
                    message=f"Workspace not writable: {e}",
                    details={'path': str(self.workspace)}
                )

            return ComponentHealth(
                name='workspace',
                status=HealthStatus.HEALTHY,
                message="Workspace accessible and writable",
                details={'path': str(self.workspace)}
            )

        except Exception as e:
            return ComponentHealth(
                name='workspace',
                status=HealthStatus.UNHEALTHY,
                message=f"Workspace check failed: {e}",
                details={'path': str(self.workspace)}
            )

    def _check_circuit_breakers(self) -> ComponentHealth:
        """Check circuit breaker states."""
        if not self.circuit_breaker:
            return ComponentHealth(
                name='circuit_breakers',
                status=HealthStatus.HEALTHY,
                message="Circuit breakers not configured"
            )

        stats = self.circuit_breaker.get_all_stats()

        open_circuits = [
            name for name, s in stats.items()
            if s['state'] == 'open'
        ]

        half_open_circuits = [
            name for name, s in stats.items()
            if s['state'] == 'half_open'
        ]

        if open_circuits:
            return ComponentHealth(
                name='circuit_breakers',
                status=HealthStatus.DEGRADED,
                message=f"{len(open_circuits)} circuit(s) open",
                details={
                    'open': open_circuits,
                    'half_open': half_open_circuits,
                    'total': len(stats)
                }
            )
        elif half_open_circuits:
            return ComponentHealth(
                name='circuit_breakers',
                status=HealthStatus.DEGRADED,
                message=f"{len(half_open_circuits)} circuit(s) half-open",
                details={
                    'open': [],
                    'half_open': half_open_circuits,
                    'total': len(stats)
                }
            )
        else:
            return ComponentHealth(
                name='circuit_breakers',
                status=HealthStatus.HEALTHY,
                message="All circuits closed",
                details={
                    'open': [],
                    'half_open': [],
                    'total': len(stats)
                }
            )


def format_health_report(report: HealthReport) -> str:
    """
    Format health report for CLI output.

    Args:
        report: Health report to format

    Returns:
        Formatted string
    """
    lines = []

    # Status emoji
    status_emoji = {
        HealthStatus.HEALTHY: '+',
        HealthStatus.DEGRADED: '!',
        HealthStatus.UNHEALTHY: 'X'
    }

    lines.append(f"Health Status: {status_emoji[report.status]} {report.status.value.upper()}")
    lines.append(f"Uptime: {report.uptime_seconds:.1f}s")
    lines.append("")
    lines.append("Components:")

    for component in report.components:
        emoji = status_emoji[component.status]
        lines.append(f"  [{emoji}] {component.name}: {component.message}")

    return '\n'.join(lines)
