"""
Distributed tracing for Framework Orchestrator.

Implements OpenTelemetry-compatible tracing with:
- Trace context propagation through execution
- Span hierarchy (orchestration → routing → agent execution)
- Attribute recording for debugging
- Export to Jaeger/Zipkin format

References:
    [1] OpenTelemetry Authors. (2019-2025). "OpenTelemetry Specification"
        Cloud Native Computing Foundation (CNCF).
        https://opentelemetry.io/
        - W3C Trace Context propagation format
        - Span hierarchy and attribute conventions

    [2] Jaeger Authors. (2016-2025). "Jaeger: Open-Source Distributed Tracing"
        Cloud Native Computing Foundation (CNCF).
        https://www.jaegertracing.io/
        - Trace export format compatibility

Usage:
    tracer = DistributedTracer()

    # Start root span for orchestration
    with tracer.trace("orchestration", task_id="123") as span:
        span.set_attribute("task", "analyze code")

        # Child span for agent
        with tracer.trace("agent_execution", parent=span, agent_name="moe_router") as agent_span:
            # ... agent execution
            agent_span.set_attribute("status", "completed")

    # Export trace
    print(tracer.export_jaeger(span.trace_id))
"""

import time
import uuid
import json
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class SpanStatus(Enum):
    """Status of a span."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class TraceContext:
    """
    Distributed trace context that propagates through execution.

    Contains:
    - trace_id: Unique ID for the entire trace (shared across all spans)
    - span_id: Unique ID for this specific span
    - parent_span_id: ID of parent span (None for root)
    - baggage: Key-value pairs propagated through the trace
    """

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = field(default_factory=dict)

    @staticmethod
    def create() -> 'TraceContext':
        """Create a new root trace context."""
        return TraceContext(
            trace_id=uuid.uuid4().hex[:32],
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=None
        )

    def child_span(self) -> 'TraceContext':
        """Create a child span context."""
        return TraceContext(
            trace_id=self.trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=self.span_id,
            baggage=self.baggage.copy()
        )

    def with_baggage(self, key: str, value: str) -> 'TraceContext':
        """Return new context with added baggage item."""
        new_ctx = TraceContext(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            baggage={**self.baggage, key: value}
        )
        return new_ctx

    def to_header(self) -> str:
        """Export as W3C Trace Context header value."""
        return f"00-{self.trace_id}-{self.span_id}-01"

    @staticmethod
    def from_header(header: str) -> Optional['TraceContext']:
        """Parse from W3C Trace Context header."""
        try:
            parts = header.split("-")
            if len(parts) >= 3:
                return TraceContext(
                    trace_id=parts[1],
                    span_id=parts[2],
                    parent_span_id=None
                )
        except Exception as e:
            # Log parsing failures for debugging [He2025 production safety]
            logger.debug(f"Failed to parse trace context header '{header}': {e}")
        return None


@dataclass
class Span:
    """
    A single unit of work within a trace.

    Spans form a tree structure with parent-child relationships.
    Each span records:
    - Operation name
    - Start/end timestamps
    - Attributes (key-value metadata)
    - Events (timestamped annotations)
    - Status (ok/error)
    """

    name: str
    context: TraceContext
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: SpanStatus = SpanStatus.UNSET
    status_message: Optional[str] = None

    @property
    def trace_id(self) -> str:
        """Get the trace ID."""
        return self.context.trace_id

    @property
    def span_id(self) -> str:
        """Get the span ID."""
        return self.context.span_id

    @property
    def parent_span_id(self) -> Optional[str]:
        """Get the parent span ID."""
        return self.context.parent_span_id

    @property
    def duration_ms(self) -> Optional[float]:
        """Get duration in milliseconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on this span."""
        self.attributes[key] = value

    def set_attributes(self, attributes: Dict[str, Any]) -> None:
        """Set multiple attributes."""
        self.attributes.update(attributes)

    def add_event(self, name: str, attributes: Dict[str, Any] = None) -> None:
        """Add a timestamped event to this span."""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {}
        })

    def set_status(self, status: SpanStatus, message: str = None) -> None:
        """Set the span status."""
        self.status = status
        self.status_message = message

    def end(self, status: SpanStatus = None, error: str = None) -> None:
        """End this span."""
        self.end_time = time.time()
        if status:
            self.status = status
        elif error:
            self.status = SpanStatus.ERROR
            self.status_message = error
        elif self.status == SpanStatus.UNSET:
            self.status = SpanStatus.OK

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary for export."""
        return {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id,
            "operationName": self.name,
            "startTime": int(self.start_time * 1_000_000),  # microseconds
            "duration": int((self.duration_ms or 0) * 1000),  # microseconds
            "tags": [{"key": k, "value": str(v)} for k, v in self.attributes.items()],
            "logs": [
                {
                    "timestamp": int(e["timestamp"] * 1_000_000),
                    "fields": [{"key": k, "value": str(v)} for k, v in e["attributes"].items()]
                }
                for e in self.events
            ],
            "status": self.status.value,
            "statusMessage": self.status_message
        }


class SpanStore:
    """
    Thread-safe storage for spans.

    Organizes spans by trace_id for efficient retrieval.
    Implements TTL-based cleanup to prevent memory leaks.
    """

    def __init__(self, max_traces: int = 1000, trace_ttl: float = 3600.0):
        """
        Initialize span store.

        Args:
            max_traces: Maximum number of traces to keep
            trace_ttl: Time-to-live for traces in seconds
        """
        self.max_traces = max_traces
        self.trace_ttl = trace_ttl
        self._traces: Dict[str, Dict[str, Span]] = {}
        self._trace_timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()

    def add_span(self, span: Span) -> None:
        """Add a span to the store."""
        with self._lock:
            trace_id = span.trace_id
            if trace_id not in self._traces:
                self._traces[trace_id] = {}
                self._trace_timestamps[trace_id] = time.time()
            self._traces[trace_id][span.span_id] = span

            # Cleanup old traces if needed
            self._cleanup_if_needed()

    def get_trace(self, trace_id: str) -> Optional[List[Span]]:
        """Get all spans for a trace."""
        with self._lock:
            if trace_id in self._traces:
                return list(self._traces[trace_id].values())
            return None

    def get_span(self, trace_id: str, span_id: str) -> Optional[Span]:
        """Get a specific span."""
        with self._lock:
            if trace_id in self._traces:
                return self._traces[trace_id].get(span_id)
            return None

    def _cleanup_if_needed(self) -> None:
        """Remove old traces if over capacity or TTL expired."""
        now = time.time()

        # Remove expired traces
        expired = [
            tid for tid, ts in self._trace_timestamps.items()
            if now - ts > self.trace_ttl
        ]
        for tid in expired:
            del self._traces[tid]
            del self._trace_timestamps[tid]

        # Remove oldest traces if over capacity
        while len(self._traces) > self.max_traces:
            oldest = min(self._trace_timestamps, key=self._trace_timestamps.get)
            del self._traces[oldest]
            del self._trace_timestamps[oldest]


class DistributedTracer:
    """
    Traces orchestrator execution across agents.

    Provides:
    - Automatic span hierarchy
    - Context propagation
    - Multiple export formats (Jaeger, Zipkin)
    - Sampling support

    Thread-safe for concurrent tracing.
    """

    def __init__(
        self,
        service_name: str = "framework-orchestrator",
        sample_rate: float = 1.0,
        enabled: bool = True
    ):
        """
        Initialize tracer.

        Args:
            service_name: Name of this service in traces
            sample_rate: Fraction of traces to sample (0.0 - 1.0)
            enabled: Whether tracing is enabled
        """
        self.service_name = service_name
        self.sample_rate = sample_rate
        self.enabled = enabled
        self._span_store = SpanStore()
        self._current_span: Dict[int, Span] = {}  # thread_id -> current span
        self._lock = threading.Lock()

    def _should_sample(self) -> bool:
        """Determine if this trace should be sampled.

        ThinkingMachines [He2025] Compliance:
            Uses seeded RNG for reproducible sampling decisions.
        """
        if self.sample_rate >= 1.0:
            return True
        # Use seeded RNG for batch-invariance compliance
        if not hasattr(self, '_sample_rng'):
            import random
            self._sample_rng = random.Random(42)
        return self._sample_rng.random() < self.sample_rate

    def start_span(
        self,
        operation_name: str,
        parent: Optional[Span] = None,
        context: Optional[TraceContext] = None,
        attributes: Dict[str, Any] = None
    ) -> Span:
        """
        Start a new span.

        Args:
            operation_name: Name of the operation
            parent: Parent span (creates child relationship)
            context: Explicit trace context (creates child if has parent_span_id)
            attributes: Initial attributes for the span

        Returns:
            New span instance
        """
        if not self.enabled:
            # Return a no-op span
            return Span(
                name=operation_name,
                context=TraceContext.create()
            )

        # Determine trace context
        if parent:
            ctx = parent.context.child_span()
        elif context:
            ctx = context.child_span() if context.parent_span_id else context
        else:
            ctx = TraceContext.create()

        # Check sampling
        if not parent and not self._should_sample():
            self.enabled = False  # Disable for this trace

        span = Span(
            name=operation_name,
            context=ctx,
            attributes=attributes or {}
        )

        # Add service name
        span.set_attribute("service.name", self.service_name)

        # Store span
        self._span_store.add_span(span)

        # Track current span for thread
        thread_id = threading.get_ident()
        with self._lock:
            self._current_span[thread_id] = span

        return span

    def end_span(self, span: Span, status: SpanStatus = None, error: str = None) -> None:
        """End a span."""
        span.end(status=status, error=error)

        # Update storage
        self._span_store.add_span(span)

        # Clear current span if this is it
        thread_id = threading.get_ident()
        with self._lock:
            if self._current_span.get(thread_id) == span:
                del self._current_span[thread_id]

    @contextmanager
    def trace(
        self,
        operation_name: str,
        parent: Optional[Span] = None,
        **attributes
    ):
        """
        Context manager for tracing an operation.

        Usage:
            with tracer.trace("operation", key="value") as span:
                # ... do work
                span.set_attribute("result", "success")
        """
        span = self.start_span(operation_name, parent=parent, attributes=attributes)
        try:
            yield span
            span.set_status(SpanStatus.OK)
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            span.add_event("exception", {"message": str(e), "type": type(e).__name__})
            raise
        finally:
            self.end_span(span)

    def get_current_span(self) -> Optional[Span]:
        """Get the current span for this thread."""
        thread_id = threading.get_ident()
        with self._lock:
            return self._current_span.get(thread_id)

    def get_trace(self, trace_id: str) -> Optional[List[Span]]:
        """Get all spans for a trace."""
        return self._span_store.get_trace(trace_id)

    def export_jaeger(self, trace_id: str) -> str:
        """
        Export trace in Jaeger JSON format.

        Compatible with Jaeger UI for visualization.
        """
        spans = self.get_trace(trace_id)
        if not spans:
            return json.dumps({"data": []})

        jaeger_spans = []
        for span in spans:
            jaeger_span = {
                "traceID": span.trace_id,
                "spanID": span.span_id,
                "operationName": span.name,
                "references": [],
                "startTime": int(span.start_time * 1_000_000),
                "duration": int((span.duration_ms or 0) * 1000),
                "tags": [
                    {"key": k, "type": "string", "value": str(v)}
                    for k, v in span.attributes.items()
                ],
                "logs": [
                    {
                        "timestamp": int(e["timestamp"] * 1_000_000),
                        "fields": [
                            {"key": k, "type": "string", "value": str(v)}
                            for k, v in e.get("attributes", {}).items()
                        ]
                    }
                    for e in span.events
                ],
                "processID": "p1",
                "warnings": None
            }

            # Add parent reference
            if span.parent_span_id:
                jaeger_span["references"].append({
                    "refType": "CHILD_OF",
                    "traceID": span.trace_id,
                    "spanID": span.parent_span_id
                })

            jaeger_spans.append(jaeger_span)

        return json.dumps({
            "data": [{
                "traceID": trace_id,
                "spans": jaeger_spans,
                "processes": {
                    "p1": {
                        "serviceName": self.service_name,
                        "tags": []
                    }
                },
                "warnings": None
            }]
        }, indent=2)

    def export_zipkin(self, trace_id: str) -> str:
        """
        Export trace in Zipkin JSON format.

        Compatible with Zipkin UI for visualization.
        """
        spans = self.get_trace(trace_id)
        if not spans:
            return json.dumps([])

        zipkin_spans = []
        for span in spans:
            zipkin_span = {
                "traceId": span.trace_id,
                "id": span.span_id,
                "name": span.name,
                "timestamp": int(span.start_time * 1_000_000),
                "duration": int((span.duration_ms or 0) * 1000),
                "localEndpoint": {
                    "serviceName": self.service_name
                },
                "tags": {k: str(v) for k, v in span.attributes.items()},
                "annotations": [
                    {
                        "timestamp": int(e["timestamp"] * 1_000_000),
                        "value": e["name"]
                    }
                    for e in span.events
                ]
            }

            if span.parent_span_id:
                zipkin_span["parentId"] = span.parent_span_id

            zipkin_spans.append(zipkin_span)

        return json.dumps(zipkin_spans, indent=2)


# Global tracer instance
_global_tracer: Optional[DistributedTracer] = None


def get_tracer() -> DistributedTracer:
    """Get the global tracer instance."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = DistributedTracer()
    return _global_tracer


def configure_tracer(
    service_name: str = "framework-orchestrator",
    sample_rate: float = 1.0,
    enabled: bool = True
) -> DistributedTracer:
    """Configure and return the global tracer."""
    global _global_tracer
    _global_tracer = DistributedTracer(
        service_name=service_name,
        sample_rate=sample_rate,
        enabled=enabled
    )
    return _global_tracer


# Convenience function for quick tracing
def trace(operation_name: str, parent: Optional[Span] = None, **attributes):
    """
    Quick context manager for tracing.

    Usage:
        with trace("my_operation", task_id="123") as span:
            # ... do work
    """
    return get_tracer().trace(operation_name, parent=parent, **attributes)
