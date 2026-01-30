"""
Structured logging setup for Framework Orchestrator.

Provides:
- JSON formatter for production use
- Text formatter for development
- Configurable handlers (console, file)
- Context injection (agent name, task hash, etc.)
- Correlation ID propagation for distributed tracing
"""

import contextvars
import json
import logging
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Context variable for correlation ID (thread-safe, async-safe)
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set or generate a correlation ID for the current context.

    Args:
        correlation_id: Optional ID to set. Generates UUID if None.

    Returns:
        The correlation ID that was set.
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())[:8]  # Short form for readability
    _correlation_id.set(correlation_id)
    return correlation_id


def clear_correlation_id() -> None:
    """Clear the correlation ID from context."""
    _correlation_id.set(None)


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for production environments.

    Produces structured JSON logs with:
    - ISO8601 timestamps with timezone
    - Log level
    - Logger name
    - Message
    - Extra context fields
    - Exception info (if present)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add correlation ID if present (for distributed tracing)
        correlation_id = get_correlation_id()
        if correlation_id:
            log_data['correlation_id'] = correlation_id

        # Add extra fields from record
        extra_fields = [
            'agent_name', 'task_hash', 'duration_ms', 'checksum',
            'iteration', 'phase', 'operation', 'circuit_state',
            'trace_id', 'span_id'  # For tracing integration
        ]
        for field in extra_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        # Add any custom extra fields
        if hasattr(record, 'extra') and isinstance(record.extra, dict):
            log_data.update(record.extra)

        # Add exception info
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info)
            }

        return json.dumps(log_data, default=str, sort_keys=True)


class TextFormatter(logging.Formatter):
    """
    Human-readable text formatter for development.

    Format: HH:MM:SS | LEVEL | [context] message
    """

    def __init__(self):
        super().__init__(
            fmt='%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text with context."""
        # Build context prefix
        context_parts = []

        # Add correlation ID first for easy visual tracking
        correlation_id = get_correlation_id()
        if correlation_id:
            context_parts.append(f"cid={correlation_id}")

        if hasattr(record, 'agent_name'):
            context_parts.append(f"agent={record.agent_name}")

        if hasattr(record, 'phase'):
            context_parts.append(f"phase={record.phase}")

        if hasattr(record, 'duration_ms'):
            context_parts.append(f"{record.duration_ms}ms")

        # Modify message to include context
        if context_parts:
            record.msg = f"[{' '.join(context_parts)}] {record.msg}"

        return super().format(record)


class ContextAdapter(logging.LoggerAdapter):
    """
    Logger adapter that injects context into all log messages.

    Usage:
        logger = ContextAdapter(logging.getLogger(__name__), {'agent_name': 'echo_curator'})
        logger.info("Processing task")  # Will include agent_name in structured output
    """

    def process(self, msg, kwargs):
        """Inject extra context into log record."""
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


def setup_logging(
    level: str = 'INFO',
    log_format: str = 'text',
    log_file: Optional[Path] = None,
    module_name: Optional[str] = None
) -> logging.Logger:
    """
    Configure logging for Framework Orchestrator.

    Args:
        level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        log_format: Output format ('text' or 'json')
        log_file: Optional file path for logging
        module_name: Module name for the logger (default: framework_orchestrator)

    Returns:
        Configured logger instance

    Usage:
        # Development (text output)
        logger = setup_logging(level='DEBUG', log_format='text')

        # Production (JSON output to file)
        logger = setup_logging(
            level='INFO',
            log_format='json',
            log_file=Path('/var/log/framework_orchestrator.log')
        )
    """
    # Get or create logger
    logger_name = module_name or 'framework_orchestrator'
    logger = logging.getLogger(logger_name)

    # Clear existing handlers
    logger.handlers.clear()

    # Set level
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Create formatter
    if log_format.lower() == 'json':
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str, context: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """
    Get a logger with optional context adapter.

    Args:
        name: Logger name (usually __name__)
        context: Optional context dict to inject into all logs

    Returns:
        Logger or ContextAdapter if context provided
    """
    logger = logging.getLogger(name)

    if context:
        return ContextAdapter(logger, context)

    return logger


def log_execution(
    logger: logging.Logger,
    agent_name: str,
    task_hash: str,
    duration_ms: float,
    checksum: str,
    status: str,
    error: Optional[str] = None
) -> None:
    """
    Log an agent execution with structured data.

    Args:
        logger: Logger instance
        agent_name: Name of the agent
        task_hash: Hash of the task
        duration_ms: Execution time in milliseconds
        checksum: Output checksum
        status: Execution status ('completed' or 'failed')
        error: Error message if failed
    """
    extra = {
        'agent_name': agent_name,
        'task_hash': task_hash,
        'duration_ms': round(duration_ms, 2),
        'checksum': checksum,
    }

    if status == 'completed':
        logger.info(
            f"Agent {agent_name} completed in {duration_ms:.2f}ms",
            extra=extra
        )
    else:
        extra['error'] = error
        logger.error(
            f"Agent {agent_name} failed: {error}",
            extra=extra
        )


def log_orchestration_start(
    logger: logging.Logger,
    iteration: int,
    task: str,
    active_agents: list
) -> None:
    """Log orchestration cycle start."""
    # Truncate task for logging
    task_preview = task[:100] + '...' if len(task) > 100 else task

    logger.info(
        f"Starting iteration {iteration}",
        extra={
            'iteration': iteration,
            'phase': 'start',
            'task_preview': task_preview,
            'agent_count': len(active_agents),
            'agents': active_agents
        }
    )


def log_orchestration_complete(
    logger: logging.Logger,
    iteration: int,
    duration_ms: float,
    agents_succeeded: int,
    agents_failed: int,
    master_checksum: str
) -> None:
    """Log orchestration cycle completion."""
    logger.info(
        f"Iteration {iteration} complete: {agents_succeeded}/{agents_succeeded + agents_failed} agents succeeded",
        extra={
            'iteration': iteration,
            'phase': 'complete',
            'duration_ms': round(duration_ms, 2),
            'agents_succeeded': agents_succeeded,
            'agents_failed': agents_failed,
            'master_checksum': master_checksum
        }
    )
