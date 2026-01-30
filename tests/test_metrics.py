"""
Tests for metrics module.

Tests:
- Counter increment and label support
- Histogram observation and percentile calculation
- Gauge set/inc/dec operations
- OrchestratorMetrics convenience methods
- Prometheus export format
- Thread safety
"""

import time
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor

from otto.metrics import (
    Counter,
    Histogram,
    Gauge,
    OrchestratorMetrics,
    get_metrics,
    reset_metrics,
)


class TestCounter:
    """Test Counter metric type."""

    def test_basic_increment(self):
        """Should increment by 1 by default."""
        counter = Counter(name="test_counter", help="Test")
        counter.inc()
        assert counter.get() == 1.0

    def test_increment_by_amount(self):
        """Should increment by specified amount."""
        counter = Counter(name="test_counter", help="Test")
        counter.inc(5.0)
        assert counter.get() == 5.0

    def test_multiple_increments(self):
        """Should accumulate multiple increments."""
        counter = Counter(name="test_counter", help="Test")
        counter.inc(1.0)
        counter.inc(2.0)
        counter.inc(3.0)
        assert counter.get() == 6.0

    def test_negative_increment_raises(self):
        """Should raise ValueError for negative increment."""
        counter = Counter(name="test_counter", help="Test")
        with pytest.raises(ValueError, match="only increase"):
            counter.inc(-1.0)

    def test_labeled_counter(self):
        """Should track separate values per label combination."""
        counter = Counter(
            name="test_counter",
            help="Test",
            labels=("status", "agent")
        )
        counter.inc(1.0, status="success", agent="agent1")
        counter.inc(2.0, status="failure", agent="agent1")
        counter.inc(3.0, status="success", agent="agent2")

        assert counter.get(status="success", agent="agent1") == 1.0
        assert counter.get(status="failure", agent="agent1") == 2.0
        assert counter.get(status="success", agent="agent2") == 3.0
        assert counter.get(status="unknown", agent="unknown") == 0.0

    def test_export_format(self):
        """Should export in Prometheus format."""
        counter = Counter(name="my_counter", help="A test counter")
        counter.inc(42.0)

        export = counter.export()

        assert "# HELP my_counter A test counter" in export
        assert "# TYPE my_counter counter" in export
        assert "my_counter 42.0" in export

    def test_export_with_labels(self):
        """Should export labels correctly."""
        counter = Counter(
            name="my_counter",
            help="Test",
            labels=("method",)
        )
        counter.inc(5.0, method="GET")

        export = counter.export()

        assert 'my_counter{method="GET"} 5.0' in export


class TestHistogram:
    """Test Histogram metric type."""

    def test_observe_single_value(self):
        """Should record single observation."""
        hist = Histogram(
            name="test_hist",
            help="Test",
            buckets=(10, 50, 100)
        )
        hist.observe(25.0)

        # Value 25 should be counted in bucket 50 and 100
        assert hist._count[()] == 1
        assert hist._sum[()] == 25.0

    def test_observe_multiple_values(self):
        """Should record multiple observations."""
        hist = Histogram(
            name="test_hist",
            help="Test",
            buckets=(10, 50, 100)
        )
        hist.observe(5.0)
        hist.observe(25.0)
        hist.observe(75.0)

        assert hist._count[()] == 3
        assert hist._sum[()] == 105.0

    def test_bucket_counting(self):
        """Should count values in correct buckets."""
        hist = Histogram(
            name="test_hist",
            help="Test",
            buckets=(10, 50, 100)
        )
        # Value 5 -> bucket 10
        hist.observe(5.0)
        # Value 25 -> bucket 50
        hist.observe(25.0)
        # Value 75 -> bucket 100
        hist.observe(75.0)

        # Each bucket is cumulative in export but tracked separately
        assert hist._bucket_counts[()][0] == 1  # <=10
        assert hist._bucket_counts[()][1] == 1  # <=50
        assert hist._bucket_counts[()][2] == 1  # <=100

    def test_percentile_estimation(self):
        """Should estimate percentiles from buckets."""
        hist = Histogram(
            name="test_hist",
            help="Test",
            buckets=(10, 50, 100)
        )
        # All values below 10
        for _ in range(100):
            hist.observe(5.0)

        p50 = hist.get_percentile(50)
        assert p50 == 10  # All in first bucket

    def test_percentile_no_observations(self):
        """Should return None when no observations."""
        hist = Histogram(name="test_hist", help="Test")
        assert hist.get_percentile(50) is None

    def test_labeled_histogram(self):
        """Should track separate histograms per label."""
        hist = Histogram(
            name="test_hist",
            help="Test",
            labels=("agent",),
            buckets=(10, 50, 100)
        )
        hist.observe(25.0, agent="agent1")
        hist.observe(75.0, agent="agent2")

        assert hist._count[("agent1",)] == 1
        assert hist._count[("agent2",)] == 1
        assert hist._sum[("agent1",)] == 25.0
        assert hist._sum[("agent2",)] == 75.0

    def test_export_format(self):
        """Should export in Prometheus histogram format."""
        hist = Histogram(
            name="my_hist",
            help="Test histogram",
            buckets=(10, 50, 100)
        )
        hist.observe(25.0)
        hist.observe(75.0)

        export = hist.export()

        assert "# HELP my_hist Test histogram" in export
        assert "# TYPE my_hist histogram" in export
        assert 'my_hist_bucket{le="10"} 0' in export
        assert 'my_hist_bucket{le="50"} 1' in export
        assert 'my_hist_bucket{le="100"} 2' in export
        assert 'my_hist_bucket{le="+Inf"} 2' in export
        assert "my_hist_sum 100.0" in export
        assert "my_hist_count 2" in export


class TestGauge:
    """Test Gauge metric type."""

    def test_set_value(self):
        """Should set gauge to value."""
        gauge = Gauge(name="test_gauge", help="Test")
        gauge.set(42.0)
        assert gauge.get() == 42.0

    def test_set_overwrites(self):
        """Should overwrite previous value."""
        gauge = Gauge(name="test_gauge", help="Test")
        gauge.set(10.0)
        gauge.set(20.0)
        assert gauge.get() == 20.0

    def test_increment(self):
        """Should increment gauge."""
        gauge = Gauge(name="test_gauge", help="Test")
        gauge.set(10.0)
        gauge.inc(5.0)
        assert gauge.get() == 15.0

    def test_decrement(self):
        """Should decrement gauge."""
        gauge = Gauge(name="test_gauge", help="Test")
        gauge.set(10.0)
        gauge.dec(3.0)
        assert gauge.get() == 7.0

    def test_negative_values(self):
        """Should allow negative values."""
        gauge = Gauge(name="test_gauge", help="Test")
        gauge.set(-5.0)
        assert gauge.get() == -5.0

        gauge.dec(10.0)
        assert gauge.get() == -15.0

    def test_labeled_gauge(self):
        """Should track separate values per label."""
        gauge = Gauge(
            name="test_gauge",
            help="Test",
            labels=("agent",)
        )
        gauge.set(10.0, agent="agent1")
        gauge.set(20.0, agent="agent2")

        assert gauge.get(agent="agent1") == 10.0
        assert gauge.get(agent="agent2") == 20.0

    def test_export_format(self):
        """Should export in Prometheus format."""
        gauge = Gauge(name="my_gauge", help="A test gauge")
        gauge.set(3.14)

        export = gauge.export()

        assert "# HELP my_gauge A test gauge" in export
        assert "# TYPE my_gauge gauge" in export
        assert "my_gauge 3.14" in export


class TestOrchestratorMetrics:
    """Test OrchestratorMetrics class."""

    def test_initialization(self):
        """Should initialize all metric types."""
        metrics = OrchestratorMetrics()

        assert metrics.tasks_total is not None
        assert metrics.tasks_succeeded is not None
        assert metrics.tasks_failed is not None
        assert metrics.agent_executions is not None
        assert metrics.orchestration_latency is not None
        assert metrics.agent_latency is not None
        assert metrics.active_agents is not None

    def test_increment_task_total(self):
        """Should increment task total."""
        metrics = OrchestratorMetrics()
        metrics.increment_task_total()
        metrics.increment_task_total()
        assert metrics.tasks_total.get() == 2.0

    def test_increment_task_succeeded(self):
        """Should increment succeeded tasks."""
        metrics = OrchestratorMetrics()
        metrics.increment_task_succeeded()
        assert metrics.tasks_succeeded.get() == 1.0

    def test_increment_task_failed(self):
        """Should increment failed tasks."""
        metrics = OrchestratorMetrics()
        metrics.increment_task_failed()
        assert metrics.tasks_failed.get() == 1.0

    def test_record_agent_execution(self):
        """Should record agent execution with status and latency."""
        metrics = OrchestratorMetrics()
        metrics.record_agent_execution("echo_curator", "success", 150.0)

        assert metrics.agent_executions.get(agent_name="echo_curator", status="success") == 1.0

    def test_observe_orchestration_latency(self):
        """Should observe orchestration latency."""
        metrics = OrchestratorMetrics()
        metrics.observe_orchestration_latency(250.0)
        metrics.observe_orchestration_latency(500.0)

        assert metrics.orchestration_latency._count[()] == 2
        assert metrics.orchestration_latency._sum[()] == 750.0

    def test_set_active_agents(self):
        """Should set active agents gauge."""
        metrics = OrchestratorMetrics()
        metrics.set_active_agents(3)
        assert metrics.active_agents.get() == 3.0

    def test_set_circuit_breakers_open(self):
        """Should set circuit breakers open gauge."""
        metrics = OrchestratorMetrics()
        metrics.set_circuit_breakers_open(2)
        assert metrics.circuit_breakers_open.get() == 2.0

    def test_record_circuit_breaker_trip(self):
        """Should record circuit breaker trip."""
        metrics = OrchestratorMetrics()
        metrics.record_circuit_breaker_trip("agent1")
        metrics.record_circuit_breaker_trip("agent1")

        assert metrics.circuit_breaker_trips.get(agent_name="agent1") == 2.0

    def test_record_retry(self):
        """Should record retry attempt."""
        metrics = OrchestratorMetrics()
        metrics.record_retry("agent1")

        assert metrics.retries_total.get(agent_name="agent1") == 1.0

    def test_set_queue_depth(self):
        """Should set queue depth per agent."""
        metrics = OrchestratorMetrics()
        metrics.set_queue_depth("agent1", 5)
        metrics.set_queue_depth("agent2", 10)

        assert metrics.queue_depth.get(agent_name="agent1") == 5.0
        assert metrics.queue_depth.get(agent_name="agent2") == 10.0

    def test_get_stats(self):
        """Should return stats dictionary."""
        metrics = OrchestratorMetrics()
        metrics.increment_task_total()
        metrics.increment_task_succeeded()
        metrics.set_active_agents(7)

        stats = metrics.get_stats()

        assert stats["tasks"]["total"] == 1.0
        assert stats["tasks"]["succeeded"] == 1.0
        assert stats["tasks"]["failed"] == 0.0
        assert stats["gauges"]["active_agents"] == 7.0
        assert "uptime_seconds" in stats

    def test_export_prometheus(self):
        """Should export all metrics in Prometheus format."""
        metrics = OrchestratorMetrics()
        metrics.increment_task_total()
        metrics.set_active_agents(3)

        export = metrics.export_prometheus()

        # Check for key metric sections
        assert "fo_tasks_total" in export
        assert "fo_tasks_succeeded" in export
        assert "fo_tasks_failed" in export
        assert "fo_active_agents" in export
        assert "fo_uptime_seconds" in export

    def test_reset(self):
        """Should reset all metrics."""
        metrics = OrchestratorMetrics()
        metrics.increment_task_total()
        metrics.increment_task_total()

        metrics.reset()

        assert metrics.tasks_total.get() == 0.0


class TestGlobalMetrics:
    """Test global metrics singleton."""

    def test_get_metrics_singleton(self):
        """Should return same instance."""
        reset_metrics()
        metrics1 = get_metrics()
        metrics2 = get_metrics()
        assert metrics1 is metrics2

    def test_reset_metrics(self):
        """Should reset the global instance."""
        reset_metrics()
        metrics = get_metrics()
        metrics.increment_task_total()

        reset_metrics()

        assert get_metrics().tasks_total.get() == 0.0


class TestThreadSafety:
    """Test thread safety of metrics."""

    def test_counter_thread_safety(self):
        """Counter should be thread-safe."""
        counter = Counter(name="test", help="Test")

        def increment():
            for _ in range(1000):
                counter.inc()

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter.get() == 10000.0

    def test_gauge_thread_safety(self):
        """Gauge should be thread-safe."""
        gauge = Gauge(name="test", help="Test")

        def modify():
            for _ in range(1000):
                gauge.inc()
                gauge.dec()

        threads = [threading.Thread(target=modify) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should end up at 0 (equal inc and dec)
        assert gauge.get() == 0.0

    def test_histogram_thread_safety(self):
        """Histogram should be thread-safe."""
        hist = Histogram(name="test", help="Test", buckets=(10, 50, 100))

        def observe():
            for i in range(100):
                hist.observe(float(i))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(observe) for _ in range(10)]
            for f in futures:
                f.result()

        assert hist._count[()] == 1000
