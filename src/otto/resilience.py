"""
Resilience patterns for Framework Orchestrator.

Implements:
- Circuit Breaker: Prevents cascading failures by stopping calls to failing services
- Timeout wrapper: Ensures operations don't hang indefinitely
- Retry with exponential backoff and jitter: Handles transient failures

These patterns work together to make the orchestrator production-ready.

ThinkingMachines Compliance:
    Jitter uses seeded random.Random() instance for reproducibility.
    When seed is provided, retry timing is deterministic.
    See: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/

References:
    [1] Nygard, M.T. (2007). "Release It! Design and Deploy Production-Ready Software"
        Pragmatic Bookshelf. ISBN: 978-0978739218
        - Circuit breaker pattern (Chapter 5: Stability Patterns)
        - Bulkhead pattern origin

    [2] Fowler, M. (2014). "CircuitBreaker"
        https://martinfowler.com/bliki/CircuitBreaker.html

    [3] AWS Architecture Blog. (2015). "Exponential Backoff And Jitter"
        https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
        - Jitter prevents thundering herd in distributed retries

    [4] He, Horace and Thinking Machines Lab. (2025). "Defeating Nondeterminism"
        https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
        - Seeded RNG for reproducible jitter
"""

import asyncio
import functools
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests flow through
    OPEN = "open"          # Failures exceeded threshold, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker."""
    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[float] = None
    state: CircuitState = CircuitState.CLOSED
    state_changed_at: float = field(default_factory=time.time)


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and blocking requests."""

    def __init__(self, name: str, time_until_reset: float):
        self.name = name
        self.time_until_reset = time_until_reset
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Will reset in {time_until_reset:.1f}s"
        )


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    The circuit has three states:
    - CLOSED: Normal operation, tracking failures
    - OPEN: Too many failures, blocking all requests
    - HALF_OPEN: Testing if service recovered with a single request

    Usage:
        breaker = CircuitBreaker()

        # Check before calling
        if breaker.allow_request("agent_name"):
            try:
                result = await agent.execute(...)
                breaker.record_success("agent_name")
            except Exception:
                breaker.record_failure("agent_name")
                raise

        # Or use as decorator
        @breaker.protect("agent_name")
        async def call_agent():
            ...
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        half_open_max_calls: int = 1
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            reset_timeout: Seconds to wait before trying half-open
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        self._circuits: Dict[str, CircuitStats] = {}
        self._half_open_calls: Dict[str, int] = {}

    def _get_circuit(self, name: str) -> CircuitStats:
        """Get or create circuit stats for a name."""
        if name not in self._circuits:
            self._circuits[name] = CircuitStats()
        return self._circuits[name]

    def allow_request(self, name: str) -> bool:
        """
        Check if a request is allowed for the named circuit.

        Args:
            name: Circuit identifier (e.g., agent name)

        Returns:
            True if request should proceed, False if blocked

        Raises:
            CircuitBreakerOpen: If circuit is open (with time until reset)
        """
        circuit = self._get_circuit(name)
        now = time.time()

        if circuit.state == CircuitState.CLOSED:
            return True

        if circuit.state == CircuitState.OPEN:
            # Check if reset timeout has elapsed
            time_in_open = now - circuit.state_changed_at
            if time_in_open >= self.reset_timeout:
                # Transition to half-open
                circuit.state = CircuitState.HALF_OPEN
                circuit.state_changed_at = now
                self._half_open_calls[name] = 0
                logger.info(f"Circuit '{name}' transitioned to HALF_OPEN")
                return True
            else:
                raise CircuitBreakerOpen(name, self.reset_timeout - time_in_open)

        if circuit.state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open state
            current_calls = self._half_open_calls.get(name, 0)
            if current_calls < self.half_open_max_calls:
                self._half_open_calls[name] = current_calls + 1
                return True
            else:
                # Wait for half-open call to complete
                raise CircuitBreakerOpen(name, 1.0)

        return False

    def record_success(self, name: str) -> None:
        """
        Record a successful call.

        Args:
            name: Circuit identifier
        """
        circuit = self._get_circuit(name)

        if circuit.state == CircuitState.HALF_OPEN:
            # Success in half-open -> close circuit
            circuit.state = CircuitState.CLOSED
            circuit.state_changed_at = time.time()
            circuit.failures = 0
            circuit.successes = 0
            self._half_open_calls.pop(name, None)
            logger.info(f"Circuit '{name}' CLOSED after successful recovery")

        circuit.successes += 1

    def record_failure(self, name: str) -> None:
        """
        Record a failed call.

        Args:
            name: Circuit identifier
        """
        circuit = self._get_circuit(name)
        circuit.failures += 1
        circuit.last_failure_time = time.time()

        if circuit.state == CircuitState.HALF_OPEN:
            # Failure in half-open -> back to open
            circuit.state = CircuitState.OPEN
            circuit.state_changed_at = time.time()
            self._half_open_calls.pop(name, None)
            logger.warning(f"Circuit '{name}' OPENED again after half-open failure")

        elif circuit.state == CircuitState.CLOSED:
            if circuit.failures >= self.failure_threshold:
                circuit.state = CircuitState.OPEN
                circuit.state_changed_at = time.time()
                logger.warning(
                    f"Circuit '{name}' OPENED after {circuit.failures} failures"
                )

    def get_state(self, name: str) -> CircuitState:
        """Get current state of a circuit."""
        return self._get_circuit(name).state

    def get_stats(self, name: str) -> Dict[str, Any]:
        """Get statistics for a circuit."""
        circuit = self._get_circuit(name)
        return {
            'state': circuit.state.value,
            'failures': circuit.failures,
            'successes': circuit.successes,
            'last_failure_time': circuit.last_failure_time,
            'state_changed_at': circuit.state_changed_at,
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuits."""
        return {name: self.get_stats(name) for name in self._circuits}

    def reset(self, name: Optional[str] = None) -> None:
        """
        Reset circuit(s) to closed state.

        Args:
            name: Specific circuit to reset, or None for all
        """
        if name is None:
            self._circuits.clear()
            self._half_open_calls.clear()
            logger.info("All circuits reset")
        elif name in self._circuits:
            self._circuits[name] = CircuitStats()
            self._half_open_calls.pop(name, None)
            logger.info(f"Circuit '{name}' reset")

    def protect(self, name: str):
        """
        Decorator to protect an async function with circuit breaker.

        Usage:
            @breaker.protect("my_service")
            async def call_service():
                ...
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                self.allow_request(name)  # May raise CircuitBreakerOpen
                try:
                    result = await func(*args, **kwargs)
                    self.record_success(name)
                    return result
                except asyncio.CancelledError:
                    # Don't count cancellation as failure [He2025]
                    raise
                except Exception as e:
                    # Log for observability before recording failure
                    logger.warning(f"Circuit breaker '{name}' recorded failure: {type(e).__name__}: {e}")
                    self.record_failure(name)
                    raise
            return wrapper
        return decorator


class TimeoutError(Exception):
    """Raised when an operation times out."""

    def __init__(self, operation: str, timeout: float):
        self.operation = operation
        self.timeout = timeout
        super().__init__(f"Operation '{operation}' timed out after {timeout}s")


async def with_timeout(
    coro,
    timeout: float,
    operation_name: str = "operation"
) -> Any:
    """
    Execute a coroutine with a timeout.

    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds
        operation_name: Name for error messages

    Returns:
        Result of the coroutine

    Raises:
        TimeoutError: If operation exceeds timeout
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(operation_name, timeout)


async def with_retry(
    func: Callable[[], Any],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    operation_name: str = "operation",
    jitter: float = 0.1,
    seed: Optional[int] = None
) -> Any:
    """
    Execute a function with retry, exponential backoff, and jitter.

    Jitter prevents thundering herd problem when multiple callers retry
    simultaneously after a shared failure.

    ThinkingMachines Compliance:
        When seed is provided, jitter is deterministic (reproducible).
        This enables batch-invariant retry behavior for testing.

    Args:
        func: Async function to call (no arguments)
        max_attempts: Maximum number of attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff
        retryable_exceptions: Tuple of exceptions to retry on
        operation_name: Name for logging
        jitter: Jitter factor (0.0-1.0) - adds random variance to delay
        seed: Random seed for reproducible jitter (None = use global random)

    Returns:
        Result of the function

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    # Create seeded RNG for reproducible jitter (ThinkingMachines compliance)
    if seed is not None:
        rng = random.Random(seed)
        logger.debug(f"{operation_name}: Using seeded RNG (seed={seed}) for deterministic jitter")
    else:
        rng = random.Random()  # Unseeded for true randomness in production

    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except retryable_exceptions as e:
            last_exception = e

            if attempt == max_attempts:
                logger.error(
                    f"{operation_name} failed after {max_attempts} attempts: {e}"
                )
                raise

            # Calculate delay with exponential backoff
            base_calculated = min(
                base_delay * (exponential_base ** (attempt - 1)),
                max_delay
            )

            # Add jitter to prevent thundering herd
            # Jitter range: [delay * (1 - jitter), delay * (1 + jitter)]
            # Uses seeded RNG when seed provided (ThinkingMachines compliance)
            jitter_amount = base_calculated * jitter
            delay = base_calculated + rng.uniform(-jitter_amount, jitter_amount)
            delay = max(0.0, delay)  # Ensure non-negative

            logger.warning(
                f"{operation_name} attempt {attempt}/{max_attempts} failed: {e}. "
                f"Retrying in {delay:.2f}s (jitter applied, seed={'set' if seed else 'random'})"
            )

            await asyncio.sleep(delay)

    # Should never reach here, but just in case
    raise last_exception


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    ThinkingMachines Compliance:
        Set seed for reproducible jitter timing in tests.
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    retryable_exceptions: tuple = (Exception,)
    jitter: float = 0.1  # 10% jitter by default to prevent thundering herd
    seed: Optional[int] = None  # Set for reproducible jitter (ThinkingMachines)


def with_retry_decorator(
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None
):
    """
    Decorator version of with_retry.

    Usage:
        @with_retry_decorator(RetryConfig(max_attempts=5))
        async def flaky_operation():
            ...

        # For reproducible behavior (ThinkingMachines compliance):
        @with_retry_decorator(RetryConfig(seed=42))
        async def deterministic_retry():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            name = operation_name or func.__name__

            async def call():
                return await func(*args, **kwargs)

            return await with_retry(
                call,
                max_attempts=config.max_attempts,
                base_delay=config.base_delay,
                max_delay=config.max_delay,
                exponential_base=config.exponential_base,
                retryable_exceptions=config.retryable_exceptions,
                operation_name=name,
                jitter=config.jitter,
                seed=config.seed
            )
        return wrapper
    return decorator


class ResilientExecutor:
    """
    Combines circuit breaker, timeout, and retry for resilient execution.

    Usage:
        executor = ResilientExecutor(config)

        result = await executor.execute(
            name="agent_name",
            func=lambda: agent.execute(task, context),
            timeout=30.0
        )
    """

    def __init__(
        self,
        circuit_breaker: Optional[CircuitBreaker] = None,
        default_timeout: float = 30.0,
        default_max_retries: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,
        enable_circuit_breaker: bool = True,
        enable_retries: bool = True,
        seed: Optional[int] = None
    ):
        """
        Initialize resilient executor.

        ThinkingMachines Compliance:
            When seed is provided, all retry jitter becomes deterministic.
            This enables reproducible failure recovery behavior.

        Args:
            circuit_breaker: Circuit breaker instance (creates new if None)
            default_timeout: Default timeout for operations
            default_max_retries: Default retry attempts
            retry_base_delay: Base delay for exponential backoff
            retry_max_delay: Maximum retry delay
            enable_circuit_breaker: Whether to use circuit breaker
            enable_retries: Whether to use retries
            seed: Random seed for reproducible jitter (ThinkingMachines compliance)
        """
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.default_timeout = default_timeout
        self.default_max_retries = default_max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay
        self.enable_circuit_breaker = enable_circuit_breaker
        self.enable_retries = enable_retries
        self.seed = seed

    async def execute(
        self,
        name: str,
        func: Callable[[], Any],
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None
    ) -> Any:
        """
        Execute a function with full resilience (circuit breaker + timeout + retry).

        Args:
            name: Operation name (for circuit breaker and logging)
            func: Async function to execute
            timeout: Timeout in seconds (uses default if None)
            max_retries: Number of retries (uses default if None)

        Returns:
            Result of the function

        Raises:
            CircuitBreakerOpen: If circuit is open
            TimeoutError: If operation times out
            Exception: Last exception if all retries fail
        """
        timeout = timeout or self.default_timeout
        max_retries = max_retries if max_retries is not None else self.default_max_retries

        # Check circuit breaker first
        if self.enable_circuit_breaker:
            self.circuit_breaker.allow_request(name)

        async def attempt():
            try:
                result = await with_timeout(func(), timeout, name)
                if self.enable_circuit_breaker:
                    self.circuit_breaker.record_success(name)
                return result
            except Exception as e:
                if self.enable_circuit_breaker:
                    self.circuit_breaker.record_failure(name)
                raise

        if self.enable_retries and max_retries > 1:
            return await with_retry(
                attempt,
                max_attempts=max_retries,
                base_delay=self.retry_base_delay,
                max_delay=self.retry_max_delay,
                operation_name=name,
                seed=self.seed  # ThinkingMachines: pass seed for reproducible jitter
            )
        else:
            return await attempt()
