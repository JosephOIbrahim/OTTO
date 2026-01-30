"""
Prometheus-compatible metrics for Framework Orchestrator.

Provides production observability with:
- Counters: Total tasks, successes, failures, per-agent executions
- Histograms: Orchestration latency, per-agent latency (buckets for percentile calculation)
- Gauges: Active agents, open circuit breakers

Export format is Prometheus text exposition format for scraping.

Usage:
    metrics = OrchestratorMetrics()
    metrics.increment_task_total()
    metrics.observe_orchestration_latency(150.0)  # ms

    # Export for Prometheus scraping
    print(metrics.export_prometheus())
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class Counter:
    """Prometheus-style counter (only increases)."""

    name: str
    help: str
    labels: Tuple[str, ...] = ()
    _values: Dict[Tuple[str, ...], float] = field(default_factory=lambda: defaultdict(float))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, amount: float = 1.0, **label_values) -> None:
        """Increment counter by amount."""
        if amount < 0:
            raise ValueError("Counter can only increase")
        key = self._label_key(label_values)
        with self._lock:
            self._values[key] += amount

    def get(self, **label_values) -> float:
        """Get current counter value."""
        key = self._label_key(label_values)
        return self._values.get(key, 0.0)

    def _label_key(self, label_values: Dict) -> Tuple[str, ...]:
        """Create tuple key from label values."""
        if not self.labels:
            return ()
        return tuple(str(label_values.get(l, "")) for l in self.labels)

    def export(self) -> str:
        """Export in Prometheus text format."""
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        for key, value in self._values.items():
            if key:
                labels_str = ",".join(f'{l}="{v}"' for l, v in zip(self.labels, key))
                lines.append(f"{self.name}{{{labels_str}}} {value}")
            else:
                lines.append(f"{self.name} {value}")
        return "\n".join(lines)


@dataclass
class Histogram:
    """Prometheus-style histogram with fixed buckets."""

    name: str
    help: str
    buckets: Tuple[float, ...] = (10, 25, 50, 100, 250, 500, 1000, 2500, 5000)
    labels: Tuple[str, ...] = ()
    _bucket_counts: Dict[Tuple[str, ...], List[int]] = field(default_factory=lambda: defaultdict(list))
    _sum: Dict[Tuple[str, ...], float] = field(default_factory=lambda: defaultdict(float))
    _count: Dict[Tuple[str, ...], int] = field(default_factory=lambda: defaultdict(int))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        # Ensure buckets is a tuple and sorted
        self.buckets = tuple(sorted(self.buckets))

    def observe(self, value: float, **label_values) -> None:
        """Record an observation."""
        key = self._label_key(label_values)
        with self._lock:
            # Initialize bucket counts if needed
            if key not in self._bucket_counts:
                self._bucket_counts[key] = [0] * len(self.buckets)

            # Update bucket counts - only increment the first matching bucket
            # Export handles cumulative summing (Prometheus histogram semantics)
            for i, bucket in enumerate(self.buckets):
                if value <= bucket:
                    self._bucket_counts[key][i] += 1
                    break

            # Update sum and count
            self._sum[key] += value
            self._count[key] += 1

    def get_percentile(self, percentile: float, **label_values) -> Optional[float]:
        """Estimate percentile from histogram buckets."""
        key = self._label_key(label_values)
        if key not in self._count or self._count[key] == 0:
            return None

        target = self._count[key] * (percentile / 100.0)
        cumulative = 0

        for i, bucket in enumerate(self.buckets):
            cumulative = self._bucket_counts[key][i] if key in self._bucket_counts else 0
            if cumulative >= target:
                return bucket

        return self.buckets[-1] if self.buckets else None

    def _label_key(self, label_values: Dict) -> Tuple[str, ...]:
        """Create tuple key from label values."""
        if not self.labels:
            return ()
        return tuple(str(label_values.get(l, "")) for l in self.labels)

    def export(self) -> str:
        """Export in Prometheus text format."""
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]

        for key in set(self._count.keys()) | set(self._bucket_counts.keys()):
            label_prefix = ""
            if key:
                labels_str = ",".join(f'{l}="{v}"' for l, v in zip(self.labels, key))
                label_prefix = labels_str + ","

            # Export bucket counts
            bucket_counts = self._bucket_counts.get(key, [0] * len(self.buckets))
            cumulative = 0
            for i, bucket in enumerate(self.buckets):
                cumulative += bucket_counts[i] if i < len(bucket_counts) else 0
                if label_prefix:
                    lines.append(f'{self.name}_bucket{{{label_prefix}le="{bucket}"}} {cumulative}')
                else:
                    lines.append(f'{self.name}_bucket{{le="{bucket}"}} {cumulative}')

            # +Inf bucket
            total = self._count.get(key, 0)
            if label_prefix:
                lines.append(f'{self.name}_bucket{{{label_prefix}le="+Inf"}} {total}')
                lines.append(f'{self.name}_sum{{{label_prefix[:-1]}}} {self._sum.get(key, 0)}')
                lines.append(f'{self.name}_count{{{label_prefix[:-1]}}} {total}')
            else:
                lines.append(f'{self.name}_bucket{{le="+Inf"}} {total}')
                lines.append(f'{self.name}_sum {self._sum.get(key, 0)}')
                lines.append(f'{self.name}_count {total}')

        return "\n".join(lines)


@dataclass
class Gauge:
    """Prometheus-style gauge (can increase or decrease)."""

    name: str
    help: str
    labels: Tuple[str, ...] = ()
    _values: Dict[Tuple[str, ...], float] = field(default_factory=lambda: defaultdict(float))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, value: float, **label_values) -> None:
        """Set gauge to value."""
        key = self._label_key(label_values)
        with self._lock:
            self._values[key] = value

    def inc(self, amount: float = 1.0, **label_values) -> None:
        """Increment gauge by amount."""
        key = self._label_key(label_values)
        with self._lock:
            self._values[key] += amount

    def dec(self, amount: float = 1.0, **label_values) -> None:
        """Decrement gauge by amount."""
        key = self._label_key(label_values)
        with self._lock:
            self._values[key] -= amount

    def get(self, **label_values) -> float:
        """Get current gauge value."""
        key = self._label_key(label_values)
        return self._values.get(key, 0.0)

    def _label_key(self, label_values: Dict) -> Tuple[str, ...]:
        """Create tuple key from label values."""
        if not self.labels:
            return ()
        return tuple(str(label_values.get(l, "")) for l in self.labels)

    def export(self) -> str:
        """Export in Prometheus text format."""
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} gauge"]
        for key, value in self._values.items():
            if key:
                labels_str = ",".join(f'{l}="{v}"' for l, v in zip(self.labels, key))
                lines.append(f"{self.name}{{{labels_str}}} {value}")
            else:
                lines.append(f"{self.name} {value}")
        return "\n".join(lines)


class OrchestratorMetrics:
    """
    Prometheus-compatible metrics for production monitoring.

    Tracks:
    - Task throughput (total, succeeded, failed)
    - Per-agent execution metrics
    - Latency distributions
    - System resource gauges

    Thread-safe for concurrent access.
    """

    def __init__(self):
        # Counters
        self.tasks_total = Counter(
            name="fo_tasks_total",
            help="Total number of orchestration tasks received"
        )
        self.tasks_succeeded = Counter(
            name="fo_tasks_succeeded",
            help="Number of successfully completed tasks"
        )
        self.tasks_failed = Counter(
            name="fo_tasks_failed",
            help="Number of failed tasks"
        )
        self.agent_executions = Counter(
            name="fo_agent_executions_total",
            help="Total agent executions by agent name and status",
            labels=("agent_name", "status")
        )
        self.circuit_breaker_trips = Counter(
            name="fo_circuit_breaker_trips_total",
            help="Total circuit breaker trip events by agent",
            labels=("agent_name",)
        )
        self.retries_total = Counter(
            name="fo_retries_total",
            help="Total retry attempts by agent",
            labels=("agent_name",)
        )

        # Histograms (latency in milliseconds)
        self.orchestration_latency = Histogram(
            name="fo_orchestration_latency_ms",
            help="Full orchestration cycle latency in milliseconds",
            buckets=(50, 100, 250, 500, 1000, 2500, 5000, 10000)
        )
        self.agent_latency = Histogram(
            name="fo_agent_latency_ms",
            help="Per-agent execution latency in milliseconds",
            labels=("agent_name",),
            buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000)
        )

        # Gauges
        self.active_agents = Gauge(
            name="fo_active_agents",
            help="Number of currently executing agents"
        )
        self.circuit_breakers_open = Gauge(
            name="fo_circuit_breakers_open",
            help="Number of open circuit breakers"
        )
        self.queue_depth = Gauge(
            name="fo_queue_depth",
            help="Current queue depth by agent",
            labels=("agent_name",)
        )
        self.memory_usage_bytes = Gauge(
            name="fo_memory_usage_bytes",
            help="Estimated memory usage in bytes"
        )

        # Metadata
        self._start_time = time.time()

    # Convenience methods for common operations

    def increment_task_total(self) -> None:
        """Increment total tasks counter."""
        self.tasks_total.inc()

    def increment_task_succeeded(self) -> None:
        """Increment succeeded tasks counter."""
        self.tasks_succeeded.inc()

    def increment_task_failed(self) -> None:
        """Increment failed tasks counter."""
        self.tasks_failed.inc()

    def record_agent_execution(self, agent_name: str, status: str, latency_ms: float) -> None:
        """Record an agent execution with status and latency."""
        self.agent_executions.inc(agent_name=agent_name, status=status)
        self.agent_latency.observe(latency_ms, agent_name=agent_name)

    def observe_orchestration_latency(self, latency_ms: float) -> None:
        """Record orchestration cycle latency."""
        self.orchestration_latency.observe(latency_ms)

    def set_active_agents(self, count: int) -> None:
        """Set number of active agents."""
        self.active_agents.set(count)

    def set_circuit_breakers_open(self, count: int) -> None:
        """Set number of open circuit breakers."""
        self.circuit_breakers_open.set(count)

    def record_circuit_breaker_trip(self, agent_name: str) -> None:
        """Record a circuit breaker trip."""
        self.circuit_breaker_trips.inc(agent_name=agent_name)

    def record_retry(self, agent_name: str) -> None:
        """Record a retry attempt."""
        self.retries_total.inc(agent_name=agent_name)

    def set_queue_depth(self, agent_name: str, depth: int) -> None:
        """Set queue depth for an agent."""
        self.queue_depth.set(depth, agent_name=agent_name)

    def get_stats(self) -> Dict:
        """Get metrics as dictionary for internal use."""
        return {
            "tasks": {
                "total": self.tasks_total.get(),
                "succeeded": self.tasks_succeeded.get(),
                "failed": self.tasks_failed.get(),
            },
            "latency": {
                "orchestration_p50": self.orchestration_latency.get_percentile(50),
                "orchestration_p99": self.orchestration_latency.get_percentile(99),
            },
            "gauges": {
                "active_agents": self.active_agents.get(),
                "circuit_breakers_open": self.circuit_breakers_open.get(),
            },
            "uptime_seconds": time.time() - self._start_time,
        }

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text exposition format."""
        sections = [
            self.tasks_total.export(),
            self.tasks_succeeded.export(),
            self.tasks_failed.export(),
            self.agent_executions.export(),
            self.circuit_breaker_trips.export(),
            self.retries_total.export(),
            self.orchestration_latency.export(),
            self.agent_latency.export(),
            self.active_agents.export(),
            self.circuit_breakers_open.export(),
            self.queue_depth.export(),
            self.memory_usage_bytes.export(),
        ]

        # Add uptime metric
        uptime = time.time() - self._start_time
        sections.append(f"# HELP fo_uptime_seconds Time since metrics started")
        sections.append(f"# TYPE fo_uptime_seconds gauge")
        sections.append(f"fo_uptime_seconds {uptime}")

        return "\n\n".join(sections)

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        self.tasks_total = Counter(name="fo_tasks_total", help="Total tasks")
        self.tasks_succeeded = Counter(name="fo_tasks_succeeded", help="Succeeded tasks")
        self.tasks_failed = Counter(name="fo_tasks_failed", help="Failed tasks")
        self.agent_executions = Counter(
            name="fo_agent_executions_total",
            help="Agent executions",
            labels=("agent_name", "status")
        )
        self.circuit_breaker_trips = Counter(
            name="fo_circuit_breaker_trips_total",
            help="Circuit breaker trips",
            labels=("agent_name",)
        )
        self.retries_total = Counter(
            name="fo_retries_total",
            help="Retries",
            labels=("agent_name",)
        )
        self.orchestration_latency = Histogram(
            name="fo_orchestration_latency_ms",
            help="Orchestration latency",
            buckets=(50, 100, 250, 500, 1000, 2500, 5000, 10000)
        )
        self.agent_latency = Histogram(
            name="fo_agent_latency_ms",
            help="Agent latency",
            labels=("agent_name",),
            buckets=(10, 25, 50, 100, 250, 500, 1000, 2500, 5000)
        )
        self.active_agents = Gauge(name="fo_active_agents", help="Active agents")
        self.circuit_breakers_open = Gauge(name="fo_circuit_breakers_open", help="Open circuits")
        self.queue_depth = Gauge(name="fo_queue_depth", help="Queue depth", labels=("agent_name",))
        self.memory_usage_bytes = Gauge(name="fo_memory_usage_bytes", help="Memory usage")
        self._start_time = time.time()


# Global metrics instance (singleton pattern for easy access)
_global_metrics: Optional[OrchestratorMetrics] = None


def get_metrics() -> OrchestratorMetrics:
    """Get the global metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = OrchestratorMetrics()
    return _global_metrics


def reset_metrics() -> None:
    """Reset global metrics (for testing)."""
    global _global_metrics
    if _global_metrics:
        _global_metrics.reset()
    else:
        _global_metrics = OrchestratorMetrics()
