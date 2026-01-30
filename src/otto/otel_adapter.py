"""
OpenTelemetry adapter for Framework Orchestrator.

Provides integration with OpenTelemetry for:
- Exporting traces to OTLP collectors
- Automatic instrumentation
- Metric export (future)

References:
    [1] OpenTelemetry Authors. (2019-2025). "OpenTelemetry Specification"
        Cloud Native Computing Foundation (CNCF).
        https://opentelemetry.io/
        https://github.com/open-telemetry/opentelemetry-specification
        - OTLP (OpenTelemetry Protocol) export
        - W3C Trace Context propagation

Usage:
    from otel_adapter import configure_otel, otel_trace

    # Configure OTLP export
    configure_otel(
        service_name="framework-orchestrator",
        endpoint="http://localhost:4317"
    )

    # Use tracing
    with otel_trace("orchestration", task_id="123") as span:
        span.set_attribute("agent.name", "moe_router")

Requirements:
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
"""

import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# OpenTelemetry imports with graceful fallback
_otel_available = False
try:
    from opentelemetry import trace as otel_trace_api
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.trace import Status, StatusCode

    _otel_available = True
except ImportError:
    logger.debug("OpenTelemetry not installed. Install with: pip install opentelemetry-api opentelemetry-sdk")

# Optional OTLP exporter
_otlp_available = False
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    _otlp_available = True
except ImportError:
    logger.debug("OTLP exporter not installed. Install with: pip install opentelemetry-exporter-otlp")


# Import our internal tracer for fallback
from .tracing import (
    DistributedTracer,
    Span as InternalSpan,
    SpanStatus as InternalSpanStatus,
    get_tracer as get_internal_tracer,
)


class OTelAdapter:
    """
    Adapter that bridges Framework Orchestrator tracing to OpenTelemetry.

    When OpenTelemetry is available, exports spans to OTLP collectors.
    Falls back to internal tracing when not available.
    """

    def __init__(
        self,
        service_name: str = "framework-orchestrator",
        endpoint: Optional[str] = None,
        use_console: bool = False,
        enabled: bool = True
    ):
        """
        Initialize OpenTelemetry adapter.

        Args:
            service_name: Name of this service in traces
            endpoint: OTLP endpoint (e.g., "http://localhost:4317")
            use_console: Whether to also log spans to console
            enabled: Whether OTEL export is enabled
        """
        self.service_name = service_name
        self.endpoint = endpoint
        self.enabled = enabled and _otel_available
        self._tracer = None
        self._internal_tracer = get_internal_tracer()

        if self.enabled:
            self._setup_otel(use_console)
        else:
            if not _otel_available:
                logger.info("OpenTelemetry not available, using internal tracing")

    def _setup_otel(self, use_console: bool) -> None:
        """Configure OpenTelemetry provider and exporters."""
        # Create resource with service name
        resource = Resource.create({SERVICE_NAME: self.service_name})

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add OTLP exporter if endpoint provided
        if self.endpoint and _otlp_available:
            otlp_exporter = OTLPSpanExporter(endpoint=self.endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP exporter configured: {self.endpoint}")

        # Add console exporter if requested
        if use_console:
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Set as global provider
        otel_trace_api.set_tracer_provider(provider)

        # Get tracer
        self._tracer = otel_trace_api.get_tracer(
            self.service_name,
            "3.1.0"  # Version
        )

        logger.info(f"OpenTelemetry configured for {self.service_name}")

    @contextmanager
    def trace(
        self,
        operation_name: str,
        parent: Any = None,
        attributes: Dict[str, Any] = None,
        **kwargs
    ):
        """
        Context manager for tracing an operation.

        Uses OpenTelemetry when available, falls back to internal tracing.

        Args:
            operation_name: Name of the operation
            parent: Parent span (optional)
            attributes: Initial attributes
            **kwargs: Additional attributes

        Yields:
            Span object (OTel span or internal span)
        """
        all_attributes = {**(attributes or {}), **kwargs}

        if self.enabled and self._tracer:
            # Use OpenTelemetry
            with self._tracer.start_as_current_span(
                operation_name,
                attributes=all_attributes
            ) as span:
                try:
                    yield OTelSpanWrapper(span)
                    span.set_status(Status(StatusCode.OK))
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        else:
            # Fall back to internal tracer
            with self._internal_tracer.trace(
                operation_name,
                parent=parent,
                **all_attributes
            ) as span:
                yield span

    def start_span(
        self,
        operation_name: str,
        parent: Any = None,
        attributes: Dict[str, Any] = None
    ):
        """
        Start a new span (manual management).

        Args:
            operation_name: Name of the operation
            parent: Parent span
            attributes: Initial attributes

        Returns:
            Span wrapper
        """
        if self.enabled and self._tracer:
            span = self._tracer.start_span(
                operation_name,
                attributes=attributes
            )
            return OTelSpanWrapper(span)
        else:
            return self._internal_tracer.start_span(
                operation_name,
                parent=parent,
                attributes=attributes
            )

    def get_current_span(self):
        """Get the current active span."""
        if self.enabled and _otel_available:
            otel_span = otel_trace_api.get_current_span()
            if otel_span and otel_span.is_recording():
                return OTelSpanWrapper(otel_span)
        return self._internal_tracer.get_current_span()


class OTelSpanWrapper:
    """
    Wrapper to provide consistent interface between OTel spans and internal spans.
    """

    def __init__(self, otel_span):
        self._span = otel_span

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a single attribute."""
        self._span.set_attribute(key, value)

    def set_attributes(self, attributes: Dict[str, Any]) -> None:
        """Set multiple attributes."""
        for key, value in attributes.items():
            self._span.set_attribute(key, value)

    def add_event(self, name: str, attributes: Dict[str, Any] = None) -> None:
        """Add a timestamped event."""
        self._span.add_event(name, attributes or {})

    def set_status(self, status: str, message: str = None) -> None:
        """Set span status."""
        if not _otel_available:
            # OTel not installed, just log
            logger.debug(f"Span status: {status} - {message or ''}")
            return
        if status == "ok":
            self._span.set_status(Status(StatusCode.OK))
        elif status == "error":
            self._span.set_status(Status(StatusCode.ERROR, message or "Error"))

    def end(self) -> None:
        """End the span."""
        self._span.end()

    @property
    def trace_id(self) -> str:
        """Get trace ID as hex string."""
        ctx = self._span.get_span_context()
        return format(ctx.trace_id, '032x')

    @property
    def span_id(self) -> str:
        """Get span ID as hex string."""
        ctx = self._span.get_span_context()
        return format(ctx.span_id, '016x')


# Global adapter instance
_global_adapter: Optional[OTelAdapter] = None


def configure_otel(
    service_name: str = "framework-orchestrator",
    endpoint: Optional[str] = None,
    use_console: bool = False,
    enabled: bool = True
) -> OTelAdapter:
    """
    Configure OpenTelemetry adapter.

    Args:
        service_name: Name of this service
        endpoint: OTLP endpoint URL
        use_console: Whether to log spans to console
        enabled: Whether to enable OTEL export

    Returns:
        Configured adapter
    """
    global _global_adapter
    _global_adapter = OTelAdapter(
        service_name=service_name,
        endpoint=endpoint,
        use_console=use_console,
        enabled=enabled
    )
    return _global_adapter


def get_otel_adapter() -> OTelAdapter:
    """Get the global OTEL adapter, creating if needed."""
    global _global_adapter
    if _global_adapter is None:
        _global_adapter = OTelAdapter()
    return _global_adapter


def otel_trace(operation_name: str, **kwargs):
    """
    Convenience function for tracing.

    Usage:
        with otel_trace("operation", attr="value") as span:
            span.set_attribute("result", "success")
    """
    return get_otel_adapter().trace(operation_name, **kwargs)


def is_otel_available() -> bool:
    """Check if OpenTelemetry is available."""
    return _otel_available


def is_otlp_available() -> bool:
    """Check if OTLP exporter is available."""
    return _otlp_available

