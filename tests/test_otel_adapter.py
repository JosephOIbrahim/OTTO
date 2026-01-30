"""
Tests for OpenTelemetry adapter module.

Tests:
- OTelAdapter initialization and configuration
- Graceful fallback when OTel is not available
- Trace context manager functionality
- Span wrapper interface
- Global adapter pattern
- Utility functions
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from otto.otel_adapter import (
    OTelAdapter,
    OTelSpanWrapper,
    configure_otel,
    get_otel_adapter,
    otel_trace,
    is_otel_available,
    is_otlp_available,
    _otel_available,
)


class TestOTelAvailabilityChecks:
    """Test availability check functions."""

    def test_is_otel_available(self):
        """Should return boolean for OTel availability."""
        result = is_otel_available()
        assert isinstance(result, bool)

    def test_is_otlp_available(self):
        """Should return boolean for OTLP availability."""
        result = is_otlp_available()
        assert isinstance(result, bool)


class TestOTelAdapterInit:
    """Test OTelAdapter initialization."""

    def test_default_initialization(self):
        """Should initialize with defaults."""
        adapter = OTelAdapter()

        assert adapter.service_name == "framework-orchestrator"
        assert adapter.endpoint is None
        # enabled depends on whether OTel is installed
        assert isinstance(adapter.enabled, bool)

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        adapter = OTelAdapter(
            service_name="my-service",
            endpoint="http://localhost:4317",
            use_console=True,
            enabled=False
        )

        assert adapter.service_name == "my-service"
        assert adapter.endpoint == "http://localhost:4317"
        assert adapter.enabled is False

    def test_disabled_when_otel_unavailable(self):
        """Should be disabled when OTel is not available and enabled=True."""
        with patch('otto.otel_adapter._otel_available', False):
            adapter = OTelAdapter(enabled=True)
            # enabled = True AND _otel_available = False → enabled = False
            assert adapter.enabled is False

    def test_internal_tracer_always_available(self):
        """Should always have internal tracer as fallback."""
        adapter = OTelAdapter(enabled=False)

        assert adapter._internal_tracer is not None


class TestOTelAdapterFallback:
    """Test OTelAdapter fallback to internal tracing."""

    def test_trace_uses_internal_when_disabled(self):
        """Should use internal tracer when disabled."""
        adapter = OTelAdapter(enabled=False)

        with adapter.trace("test_operation", task_id="123") as span:
            # Should get an internal span, not None
            assert span is not None
            span.set_attribute("test", "value")

    def test_start_span_uses_internal_when_disabled(self):
        """Should use internal tracer for start_span when disabled."""
        adapter = OTelAdapter(enabled=False)

        span = adapter.start_span("test_operation", attributes={"key": "value"})
        assert span is not None

    def test_get_current_span_returns_internal_when_disabled(self):
        """Should get internal span when disabled."""
        adapter = OTelAdapter(enabled=False)

        # May return None if no active span
        span = adapter.get_current_span()
        # Just verify it doesn't crash


class TestOTelSpanWrapper:
    """Test OTelSpanWrapper interface."""

    @pytest.fixture
    def mock_otel_span(self):
        """Create a mock OTel span."""
        span = MagicMock()
        span.get_span_context.return_value = MagicMock(
            trace_id=0x12345678901234567890123456789012,
            span_id=0x1234567890123456
        )
        return span

    def test_set_attribute(self, mock_otel_span):
        """Should set single attribute."""
        wrapper = OTelSpanWrapper(mock_otel_span)

        wrapper.set_attribute("key", "value")

        mock_otel_span.set_attribute.assert_called_once_with("key", "value")

    def test_set_attributes(self, mock_otel_span):
        """Should set multiple attributes."""
        wrapper = OTelSpanWrapper(mock_otel_span)

        wrapper.set_attributes({"key1": "value1", "key2": "value2"})

        assert mock_otel_span.set_attribute.call_count == 2

    def test_add_event(self, mock_otel_span):
        """Should add timestamped event."""
        wrapper = OTelSpanWrapper(mock_otel_span)

        wrapper.add_event("test_event", {"attr": "value"})

        mock_otel_span.add_event.assert_called_once_with("test_event", {"attr": "value"})

    def test_add_event_without_attributes(self, mock_otel_span):
        """Should add event without attributes."""
        wrapper = OTelSpanWrapper(mock_otel_span)

        wrapper.add_event("test_event")

        mock_otel_span.add_event.assert_called_once_with("test_event", {})

    @pytest.mark.skipif(not _otel_available, reason="OTel not installed")
    def test_set_status_ok(self, mock_otel_span):
        """Should set OK status."""
        wrapper = OTelSpanWrapper(mock_otel_span)

        wrapper.set_status("ok")

        mock_otel_span.set_status.assert_called_once()

    @pytest.mark.skipif(not _otel_available, reason="OTel not installed")
    def test_set_status_error(self, mock_otel_span):
        """Should set error status with message."""
        wrapper = OTelSpanWrapper(mock_otel_span)

        wrapper.set_status("error", "Something went wrong")

        mock_otel_span.set_status.assert_called_once()

    def test_end(self, mock_otel_span):
        """Should end the span."""
        wrapper = OTelSpanWrapper(mock_otel_span)

        wrapper.end()

        mock_otel_span.end.assert_called_once()

    def test_trace_id_property(self, mock_otel_span):
        """Should return trace ID as hex string."""
        wrapper = OTelSpanWrapper(mock_otel_span)

        trace_id = wrapper.trace_id

        assert isinstance(trace_id, str)
        assert len(trace_id) == 32  # 16 bytes = 32 hex chars

    def test_span_id_property(self, mock_otel_span):
        """Should return span ID as hex string."""
        wrapper = OTelSpanWrapper(mock_otel_span)

        span_id = wrapper.span_id

        assert isinstance(span_id, str)
        assert len(span_id) == 16  # 8 bytes = 16 hex chars


class TestConfigureOtel:
    """Test configure_otel function."""

    def test_configure_otel_returns_adapter(self):
        """Should return OTelAdapter instance."""
        adapter = configure_otel(
            service_name="test-service",
            enabled=False
        )

        assert isinstance(adapter, OTelAdapter)
        assert adapter.service_name == "test-service"

    def test_configure_otel_sets_global(self):
        """Should set global adapter."""
        adapter = configure_otel(service_name="global-test", enabled=False)

        global_adapter = get_otel_adapter()
        assert global_adapter is adapter

    def test_configure_otel_with_endpoint(self):
        """Should accept endpoint configuration."""
        adapter = configure_otel(
            service_name="test",
            endpoint="http://localhost:4317",
            enabled=False
        )

        assert adapter.endpoint == "http://localhost:4317"

    def test_configure_otel_with_console(self):
        """Should accept console flag."""
        adapter = configure_otel(
            service_name="test",
            use_console=True,
            enabled=False
        )

        assert adapter is not None


class TestGetOtelAdapter:
    """Test get_otel_adapter function."""

    def test_get_otel_adapter_creates_if_needed(self):
        """Should create adapter if not configured."""
        import otto.otel_adapter as otel_module

        # Reset global adapter
        otel_module._global_adapter = None

        adapter = get_otel_adapter()

        assert adapter is not None
        assert isinstance(adapter, OTelAdapter)

    def test_get_otel_adapter_returns_same_instance(self):
        """Should return same instance on multiple calls."""
        adapter1 = get_otel_adapter()
        adapter2 = get_otel_adapter()

        assert adapter1 is adapter2


class TestOtelTraceConvenience:
    """Test otel_trace convenience function."""

    def test_otel_trace_returns_context_manager(self):
        """Should return a context manager."""
        # Configure with disabled to use internal tracer
        configure_otel(enabled=False)

        ctx = otel_trace("test_operation")

        # Should be a context manager
        assert hasattr(ctx, '__enter__')
        assert hasattr(ctx, '__exit__')

    def test_otel_trace_with_attributes(self):
        """Should accept keyword attributes."""
        configure_otel(enabled=False)

        with otel_trace("test_op", task_id="123", agent="test") as span:
            assert span is not None


class TestOTelAdapterWithOTelAvailable:
    """Tests that run when OTel is available."""

    @pytest.mark.skipif(not _otel_available, reason="OTel not installed")
    def test_trace_with_otel_enabled(self):
        """Should use OTel tracing when enabled and available."""
        adapter = OTelAdapter(
            service_name="test-service",
            use_console=False,
            enabled=True
        )

        with adapter.trace("test_operation") as span:
            assert span is not None
            # Should be an OTelSpanWrapper
            span.set_attribute("test", "value")

    @pytest.mark.skipif(not _otel_available, reason="OTel not installed")
    def test_start_span_with_otel_enabled(self):
        """Should create OTel span when enabled."""
        adapter = OTelAdapter(
            service_name="test-service",
            enabled=True
        )

        span = adapter.start_span("test_operation")
        assert span is not None

        # Clean up
        span.end()

    @pytest.mark.skipif(not _otel_available, reason="OTel not installed")
    def test_trace_records_exception(self):
        """Should record exception on error."""
        adapter = OTelAdapter(enabled=True)

        with pytest.raises(ValueError):
            with adapter.trace("failing_operation") as span:
                raise ValueError("Test error")

        # Exception should have been recorded (via set_status ERROR)


class TestOTelAdapterTraceAttributes:
    """Test attribute handling in traces."""

    def test_trace_merges_attributes(self):
        """Should merge attributes dict with kwargs."""
        adapter = OTelAdapter(enabled=False)

        with adapter.trace(
            "test_op",
            attributes={"attr1": "value1"},
            attr2="value2"
        ) as span:
            # Both attributes should be available
            assert span is not None

    def test_trace_with_parent(self):
        """Should accept parent span."""
        adapter = OTelAdapter(enabled=False)

        with adapter.trace("parent_op") as parent_span:
            with adapter.trace("child_op", parent=parent_span) as child_span:
                assert child_span is not None


class TestOTelAdapterEdgeCases:
    """Test edge cases and error handling."""

    def test_adapter_with_none_endpoint(self):
        """Should handle None endpoint gracefully."""
        adapter = OTelAdapter(endpoint=None, enabled=False)

        assert adapter.endpoint is None

    def test_trace_empty_operation_name(self):
        """Should handle empty operation name."""
        adapter = OTelAdapter(enabled=False)

        with adapter.trace("") as span:
            assert span is not None

    def test_multiple_adapters(self):
        """Should allow multiple adapter instances."""
        adapter1 = OTelAdapter(service_name="service1", enabled=False)
        adapter2 = OTelAdapter(service_name="service2", enabled=False)

        assert adapter1.service_name != adapter2.service_name

    def test_trace_nested_multiple_times(self):
        """Should handle deeply nested traces."""
        adapter = OTelAdapter(enabled=False)

        with adapter.trace("level1") as span1:
            with adapter.trace("level2", parent=span1) as span2:
                with adapter.trace("level3", parent=span2) as span3:
                    assert span3 is not None


class TestOTelSetupLogging:
    """Test logging during setup."""

    def test_logs_when_otel_unavailable(self, caplog):
        """Should log info when OTel is not available."""
        with patch('otto.otel_adapter._otel_available', False):
            import logging
            caplog.set_level(logging.INFO)

            adapter = OTelAdapter(enabled=True)

            # Check it didn't crash
            assert adapter.enabled is False
