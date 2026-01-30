"""
Tests for resilience module (circuit breaker, timeout, retry).
"""

import asyncio
import pytest
import time

from otto.resilience import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    ResilientExecutor,
    TimeoutError,
    with_timeout,
    with_retry,
    RetryConfig,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_is_closed(self):
        """Circuit should start in closed state."""
        breaker = CircuitBreaker()
        assert breaker.get_state("test") == CircuitState.CLOSED

    def test_allows_requests_when_closed(self):
        """Should allow requests when circuit is closed."""
        breaker = CircuitBreaker()
        assert breaker.allow_request("test") is True

    def test_opens_after_threshold_failures(self):
        """Circuit should open after failure threshold is reached."""
        breaker = CircuitBreaker(failure_threshold=3)

        # Record failures
        for _ in range(3):
            breaker.record_failure("test")

        assert breaker.get_state("test") == CircuitState.OPEN

    def test_blocks_requests_when_open(self):
        """Should block requests when circuit is open."""
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.record_failure("test")

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            breaker.allow_request("test")

        assert exc_info.value.name == "test"

    def test_transitions_to_half_open_after_timeout(self):
        """Circuit should transition to half-open after reset timeout."""
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=0.1)
        breaker.record_failure("test")

        # Wait for reset timeout
        time.sleep(0.15)

        # Should allow request and transition to half-open
        assert breaker.allow_request("test") is True
        assert breaker.get_state("test") == CircuitState.HALF_OPEN

    def test_closes_after_success_in_half_open(self):
        """Circuit should close after success in half-open state."""
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=0.1)
        breaker.record_failure("test")

        time.sleep(0.15)
        breaker.allow_request("test")  # Transition to half-open
        breaker.record_success("test")

        assert breaker.get_state("test") == CircuitState.CLOSED

    def test_reopens_after_failure_in_half_open(self):
        """Circuit should reopen after failure in half-open state."""
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=0.1)
        breaker.record_failure("test")

        time.sleep(0.15)
        breaker.allow_request("test")  # Transition to half-open
        breaker.record_failure("test")

        assert breaker.get_state("test") == CircuitState.OPEN

    def test_independent_circuits(self):
        """Each named circuit should be independent."""
        breaker = CircuitBreaker(failure_threshold=2)

        breaker.record_failure("agent_a")
        breaker.record_failure("agent_a")

        assert breaker.get_state("agent_a") == CircuitState.OPEN
        assert breaker.get_state("agent_b") == CircuitState.CLOSED

    def test_reset_single_circuit(self):
        """Should reset a single circuit."""
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.record_failure("test")

        breaker.reset("test")

        assert breaker.get_state("test") == CircuitState.CLOSED

    def test_reset_all_circuits(self):
        """Should reset all circuits."""
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.record_failure("agent_a")
        breaker.record_failure("agent_b")

        breaker.reset()

        assert breaker.get_state("agent_a") == CircuitState.CLOSED
        assert breaker.get_state("agent_b") == CircuitState.CLOSED

    def test_get_stats(self):
        """Should return correct statistics."""
        breaker = CircuitBreaker()
        breaker.record_failure("test")
        breaker.record_success("test")
        breaker.record_success("test")

        stats = breaker.get_stats("test")

        assert stats['failures'] == 1
        assert stats['successes'] == 2
        assert stats['state'] == 'closed'


class TestTimeout:
    """Tests for timeout functionality."""

    @pytest.mark.asyncio
    async def test_completes_within_timeout(self):
        """Should complete if within timeout."""
        async def quick_task():
            await asyncio.sleep(0.01)
            return "done"

        result = await with_timeout(quick_task(), timeout=1.0)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self):
        """Should raise TimeoutError if operation exceeds timeout."""
        async def slow_task():
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(slow_task(), timeout=0.05, operation_name="slow_task")

        assert exc_info.value.operation == "slow_task"
        assert exc_info.value.timeout == 0.05


class TestRetry:
    """Tests for retry functionality."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        """Should return immediately if first attempt succeeds."""
        call_count = 0

        async def successful_task():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await with_retry(successful_task, max_attempts=3)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        """Should retry on failure and succeed eventually."""
        call_count = 0

        async def flaky_task():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Transient error")
            return "success"

        result = await with_retry(
            flaky_task,
            max_attempts=3,
            base_delay=0.01
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """Should raise last exception after max retries."""
        async def always_fails():
            raise ValueError("Permanent error")

        with pytest.raises(ValueError, match="Permanent error"):
            await with_retry(
                always_fails,
                max_attempts=3,
                base_delay=0.01
            )

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Should use exponential backoff between retries."""
        timestamps = []

        async def track_time():
            timestamps.append(time.time())
            if len(timestamps) < 3:
                raise ValueError("Retry")
            return "done"

        await with_retry(
            track_time,
            max_attempts=3,
            base_delay=0.1,
            exponential_base=2.0
        )

        # Check delays are roughly exponential
        # First retry should be ~0.1s, second ~0.2s
        if len(timestamps) >= 2:
            first_delay = timestamps[1] - timestamps[0]
            assert first_delay >= 0.05  # Allow some variance

        if len(timestamps) >= 3:
            second_delay = timestamps[2] - timestamps[1]
            assert second_delay >= 0.1  # Should be longer


class TestResilientExecutor:
    """Tests for ResilientExecutor class."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Should execute successfully."""
        executor = ResilientExecutor(default_timeout=1.0)

        async def task():
            return "result"

        result = await executor.execute("test", task)
        assert result == "result"

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Should handle timeout."""
        executor = ResilientExecutor(
            default_timeout=0.05,
            enable_retries=False
        )

        async def slow_task():
            await asyncio.sleep(1.0)
            return "done"

        with pytest.raises(TimeoutError):
            await executor.execute("test", slow_task)

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Should integrate with circuit breaker."""
        executor = ResilientExecutor(
            default_timeout=1.0,
            enable_retries=False
        )

        # Force circuit open
        for _ in range(5):
            try:
                async def failing_task():
                    raise ValueError("Error")
                await executor.execute("test", failing_task)
            except ValueError:
                pass

        # Circuit should now be open
        assert executor.circuit_breaker.get_state("test") == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_retry_integration(self):
        """Should retry on failure."""
        executor = ResilientExecutor(
            default_timeout=1.0,
            default_max_retries=3,
            retry_base_delay=0.01,
            enable_circuit_breaker=False  # Disable to test retry independently
        )

        call_count = 0

        async def flaky_task():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry me")
            return "success"

        result = await executor.execute("test", flaky_task)

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_disabled_features(self):
        """Should work with features disabled."""
        executor = ResilientExecutor(
            enable_circuit_breaker=False,
            enable_retries=False
        )

        async def task():
            return "done"

        result = await executor.execute("test", task)
        assert result == "done"
