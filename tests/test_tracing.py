"""
Tests for distributed tracing module.

Tests:
- SpanStatus enum
- TraceContext creation and propagation
- Span lifecycle and attributes
- SpanStore management
- DistributedTracer operations
- Jaeger/Zipkin export formats
- Context manager tracing
"""

import time
import json
import pytest
from unittest.mock import patch, MagicMock
import threading

from otto.tracing import (
    SpanStatus,
    TraceContext,
    Span,
    SpanStore,
    DistributedTracer,
    get_tracer,
    configure_tracer,
    trace,
)


class TestSpanStatus:
    """Test SpanStatus enum."""

    def test_status_values(self):
        """Should have correct status values."""
        assert SpanStatus.UNSET.value == "unset"
        assert SpanStatus.OK.value == "ok"
        assert SpanStatus.ERROR.value == "error"


class TestTraceContext:
    """Test TraceContext functionality."""

    def test_create(self):
        """Should create new root context."""
        ctx = TraceContext.create()

        assert len(ctx.trace_id) == 32
        assert len(ctx.span_id) == 16
        assert ctx.parent_span_id is None
        assert ctx.baggage == {}

    def test_child_span(self):
        """Should create child context with same trace_id."""
        parent = TraceContext.create()
        child = parent.child_span()

        assert child.trace_id == parent.trace_id
        assert child.span_id != parent.span_id
        assert child.parent_span_id == parent.span_id

    def test_child_inherits_baggage(self):
        """Should inherit baggage in child."""
        parent = TraceContext.create()
        parent.baggage["key"] = "value"

        child = parent.child_span()

        assert child.baggage["key"] == "value"

    def test_with_baggage(self):
        """Should create new context with added baggage."""
        ctx = TraceContext.create()
        new_ctx = ctx.with_baggage("user_id", "123")

        assert new_ctx.baggage["user_id"] == "123"
        assert "user_id" not in ctx.baggage  # Original unchanged

    def test_to_header(self):
        """Should export as W3C Trace Context header."""
        ctx = TraceContext(
            trace_id="abcd1234" * 4,
            span_id="efgh5678" * 2
        )

        header = ctx.to_header()

        assert header.startswith("00-")
        assert ctx.trace_id in header
        assert ctx.span_id in header

    def test_from_header(self):
        """Should parse W3C Trace Context header."""
        header = "00-abcd1234abcd1234abcd1234abcd1234-efgh5678efgh5678-01"

        ctx = TraceContext.from_header(header)

        assert ctx.trace_id == "abcd1234abcd1234abcd1234abcd1234"
        assert ctx.span_id == "efgh5678efgh5678"

    def test_from_header_invalid(self):
        """Should return None for invalid header."""
        ctx = TraceContext.from_header("invalid")

        assert ctx is None


class TestSpan:
    """Test Span functionality."""

    def test_creation(self):
        """Should create span with context."""
        ctx = TraceContext.create()
        span = Span(name="test_operation", context=ctx)

        assert span.name == "test_operation"
        assert span.trace_id == ctx.trace_id
        assert span.span_id == ctx.span_id
        assert span.status == SpanStatus.UNSET

    def test_set_attribute(self):
        """Should set single attribute."""
        span = Span(name="op", context=TraceContext.create())

        span.set_attribute("key", "value")

        assert span.attributes["key"] == "value"

    def test_set_attributes(self):
        """Should set multiple attributes."""
        span = Span(name="op", context=TraceContext.create())

        span.set_attributes({"a": 1, "b": 2})

        assert span.attributes["a"] == 1
        assert span.attributes["b"] == 2

    def test_add_event(self):
        """Should add timestamped event."""
        span = Span(name="op", context=TraceContext.create())

        span.add_event("checkpoint", {"step": 1})

        assert len(span.events) == 1
        assert span.events[0]["name"] == "checkpoint"
        assert "timestamp" in span.events[0]

    def test_set_status(self):
        """Should set status and message."""
        span = Span(name="op", context=TraceContext.create())

        span.set_status(SpanStatus.ERROR, "Something failed")

        assert span.status == SpanStatus.ERROR
        assert span.status_message == "Something failed"

    def test_end(self):
        """Should record end time."""
        span = Span(name="op", context=TraceContext.create())

        span.end()

        assert span.end_time is not None
        assert span.status == SpanStatus.OK  # Default to OK

    def test_end_with_error(self):
        """Should set error status when ending with error."""
        span = Span(name="op", context=TraceContext.create())

        span.end(error="Failed")

        assert span.status == SpanStatus.ERROR
        assert span.status_message == "Failed"

    def test_duration_ms(self):
        """Should calculate duration in milliseconds."""
        span = Span(name="op", context=TraceContext.create())
        span.start_time = 1000.0
        span.end_time = 1000.5  # 500ms later

        assert span.duration_ms == 500.0

    def test_duration_ms_before_end(self):
        """Should return None before span ends."""
        span = Span(name="op", context=TraceContext.create())

        assert span.duration_ms is None

    def test_to_dict(self):
        """Should convert to dictionary."""
        span = Span(name="test", context=TraceContext.create())
        span.set_attribute("key", "value")
        span.end()

        d = span.to_dict()

        assert d["operationName"] == "test"
        assert d["traceId"] == span.trace_id
        assert "startTime" in d
        assert "duration" in d


class TestSpanStore:
    """Test SpanStore functionality."""

    def test_add_and_get_span(self):
        """Should store and retrieve span."""
        store = SpanStore()
        ctx = TraceContext.create()
        span = Span(name="op", context=ctx)

        store.add_span(span)
        retrieved = store.get_span(ctx.trace_id, ctx.span_id)

        assert retrieved == span

    def test_get_trace(self):
        """Should get all spans for a trace."""
        store = SpanStore()
        ctx = TraceContext.create()

        span1 = Span(name="op1", context=ctx)
        span2 = Span(name="op2", context=ctx.child_span())

        store.add_span(span1)
        store.add_span(span2)

        spans = store.get_trace(ctx.trace_id)

        assert len(spans) == 2

    def test_get_trace_nonexistent(self):
        """Should return None for unknown trace."""
        store = SpanStore()

        result = store.get_trace("nonexistent")

        assert result is None

    def test_cleanup_expired(self):
        """Should clean up expired traces."""
        store = SpanStore(trace_ttl=0.1)
        ctx = TraceContext.create()
        span = Span(name="op", context=ctx)

        store.add_span(span)

        # Wait for expiration
        import time
        time.sleep(0.2)

        # Add another span to trigger cleanup
        new_ctx = TraceContext.create()
        store.add_span(Span(name="new", context=new_ctx))

        # Old trace should be gone
        assert store.get_trace(ctx.trace_id) is None

    def test_cleanup_over_max(self):
        """Should clean up when over max_traces."""
        store = SpanStore(max_traces=3)

        for i in range(5):
            ctx = TraceContext.create()
            store.add_span(Span(name=f"op{i}", context=ctx))

        assert len(store._traces) <= 3


class TestDistributedTracer:
    """Test DistributedTracer functionality."""

    def test_initialization(self):
        """Should initialize with defaults."""
        tracer = DistributedTracer()

        assert tracer.service_name == "framework-orchestrator"
        assert tracer.sample_rate == 1.0
        assert tracer.enabled is True

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        tracer = DistributedTracer(
            service_name="test-service",
            sample_rate=0.5,
            enabled=False
        )

        assert tracer.service_name == "test-service"
        assert tracer.sample_rate == 0.5
        assert tracer.enabled is False

    def test_start_span(self):
        """Should create and start a span."""
        tracer = DistributedTracer()

        span = tracer.start_span("test_operation")

        assert span.name == "test_operation"
        assert span.trace_id is not None

    def test_start_span_with_parent(self):
        """Should create child span."""
        tracer = DistributedTracer()

        parent = tracer.start_span("parent")
        child = tracer.start_span("child", parent=parent)

        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.span_id

    def test_start_span_with_attributes(self):
        """Should accept initial attributes."""
        tracer = DistributedTracer()

        span = tracer.start_span("op", attributes={"key": "value"})

        assert span.attributes["key"] == "value"

    def test_end_span(self):
        """Should end a span."""
        tracer = DistributedTracer()

        span = tracer.start_span("op")
        tracer.end_span(span)

        assert span.end_time is not None

    def test_trace_context_manager(self):
        """Should work as context manager."""
        tracer = DistributedTracer()

        with tracer.trace("operation", attr="value") as span:
            span.set_attribute("inside", True)

        assert span.end_time is not None
        assert span.status == SpanStatus.OK

    def test_trace_context_manager_error(self):
        """Should handle exceptions in context manager."""
        tracer = DistributedTracer()

        with pytest.raises(ValueError):
            with tracer.trace("failing_op") as span:
                raise ValueError("test error")

        assert span.status == SpanStatus.ERROR

    def test_get_current_span(self):
        """Should track current span for thread."""
        tracer = DistributedTracer()

        span = tracer.start_span("op")
        current = tracer.get_current_span()

        assert current == span

        tracer.end_span(span)

    def test_get_trace(self):
        """Should retrieve trace spans."""
        tracer = DistributedTracer()

        with tracer.trace("op1") as span1:
            with tracer.trace("op2", parent=span1) as span2:
                pass

        spans = tracer.get_trace(span1.trace_id)

        assert len(spans) >= 2


class TestDistributedTracerExport:
    """Test export functionality."""

    def test_export_jaeger(self):
        """Should export in Jaeger format."""
        tracer = DistributedTracer(service_name="test-service")

        with tracer.trace("operation", key="value") as span:
            span.add_event("checkpoint")

        json_str = tracer.export_jaeger(span.trace_id)
        data = json.loads(json_str)

        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["traceID"] == span.trace_id

    def test_export_zipkin(self):
        """Should export in Zipkin format."""
        tracer = DistributedTracer(service_name="test-service")

        with tracer.trace("operation") as span:
            pass

        json_str = tracer.export_zipkin(span.trace_id)
        data = json.loads(json_str)

        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["traceId"] == span.trace_id

    def test_export_nonexistent_trace(self):
        """Should handle nonexistent trace."""
        tracer = DistributedTracer()

        jaeger = tracer.export_jaeger("nonexistent")
        zipkin = tracer.export_zipkin("nonexistent")

        assert json.loads(jaeger) == {"data": []}
        assert json.loads(zipkin) == []


class TestDistributedTracerSampling:
    """Test sampling functionality."""

    def test_full_sample_rate(self):
        """Should always sample at rate 1.0."""
        tracer = DistributedTracer(sample_rate=1.0)

        assert tracer._should_sample() is True

    def test_zero_sample_rate(self):
        """Should never sample at rate 0.0."""
        tracer = DistributedTracer(sample_rate=0.0)

        # Multiple checks to be sure
        samples = [tracer._should_sample() for _ in range(10)]
        assert all(s is False for s in samples)


class TestGlobalTracer:
    """Test global tracer functions."""

    def test_get_tracer(self):
        """Should return global tracer."""
        tracer = get_tracer()

        assert isinstance(tracer, DistributedTracer)

    def test_configure_tracer(self):
        """Should configure global tracer."""
        tracer = configure_tracer(
            service_name="configured-service",
            sample_rate=0.5
        )

        assert tracer.service_name == "configured-service"
        assert get_tracer() == tracer

    def test_trace_convenience(self):
        """Should work as convenience function."""
        configure_tracer()  # Reset to default

        with trace("quick_op", attr="val") as span:
            pass

        assert span.end_time is not None


class TestTracerThreadSafety:
    """Test thread safety."""

    def test_concurrent_spans(self):
        """Should handle concurrent spans from different threads."""
        tracer = DistributedTracer()
        spans = []
        errors = []

        def create_span(n):
            try:
                span = tracer.start_span(f"thread_{n}")
                time.sleep(0.01)
                tracer.end_span(span)
                spans.append(span)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_span, args=(i,))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(spans) == 10

