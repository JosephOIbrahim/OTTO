"""
Centralized configuration for Framework Orchestrator.

All configuration values can be overridden via environment variables.
Pattern: FO_{SETTING_NAME}

Example:
    FO_AGENT_TIMEOUT=60 python -m framework_orchestrator --task "..."
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass


# Track configuration warnings for startup reporting
_config_warnings: list[str] = []


def _get_env_int(name: str, default: int, strict: bool = False) -> int:
    """
    Get integer from environment variable with default.

    Args:
        name: Environment variable name
        default: Default value if not set
        strict: If True, raise ConfigurationError on invalid value

    Returns:
        Integer value

    Raises:
        ConfigurationError: If strict=True and value is invalid
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        msg = f"Invalid integer for {name}: '{value}' (using default: {default})"
        if strict:
            raise ConfigurationError(msg)
        _config_warnings.append(msg)
        return default


def _get_env_float(name: str, default: float, strict: bool = False) -> float:
    """
    Get float from environment variable with default.

    Args:
        name: Environment variable name
        default: Default value if not set
        strict: If True, raise ConfigurationError on invalid value

    Returns:
        Float value

    Raises:
        ConfigurationError: If strict=True and value is invalid
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        msg = f"Invalid float for {name}: '{value}' (using default: {default})"
        if strict:
            raise ConfigurationError(msg)
        _config_warnings.append(msg)
        return default


def _get_env_bool(name: str, default: bool) -> bool:
    """Get boolean from environment variable with default."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ('true', '1', 'yes', 'on')


def _get_env_path(name: str, default: Path) -> Path:
    """Get path from environment variable with default."""
    value = os.environ.get(name)
    if value is None:
        return default
    return Path(value)


@dataclass
class OrchestratorConfig:
    """
    Configuration for Framework Orchestrator.

    All values have sensible defaults but can be overridden via environment variables.
    This allows different configurations for development, testing, and production.
    """

    # === Paths ===
    workspace: Path = field(default_factory=lambda: _get_env_path(
        'FO_WORKSPACE',
        Path.home() / 'Orchestra'
    ))

    @property
    def config_dir(self) -> Path:
        """Path to configuration directory."""
        return self.workspace / 'config'

    @property
    def state_dir(self) -> Path:
        """Path to runtime state directory."""
        return self.workspace / 'state'

    @property
    def domains_path(self) -> Path:
        """Path to domain configuration files."""
        custom = os.environ.get('FO_DOMAINS')
        if custom:
            return Path(custom)
        return self.config_dir / 'domains'

    @property
    def frameworks_path(self) -> Path:
        """Path to framework modules."""
        custom = os.environ.get('FO_FRAMEWORKS')
        if custom:
            return Path(custom)
        return self.config_dir / 'frameworks'

    @property
    def principles_path(self) -> Path:
        """Path to constitutional principles file."""
        custom = os.environ.get('FO_PRINCIPLES')
        if custom:
            return Path(custom)
        return self.config_dir / 'principles.json'

    @property
    def results_dir(self) -> Path:
        """Directory for agent result files."""
        custom = os.environ.get('FO_RESULTS_DIR')
        if custom:
            return Path(custom)
        return self.state_dir / 'results'

    @property
    def checkpoints_dir(self) -> Path:
        """Directory for checkpoint files."""
        custom = os.environ.get('FO_CHECKPOINTS_DIR')
        if custom:
            return Path(custom)
        return self.state_dir / 'checkpoints'

    @property
    def state_file(self) -> Path:
        """Path to orchestrator state file."""
        custom = os.environ.get('FO_STATE_FILE')
        if custom:
            return Path(custom)
        return self.state_dir / '.orchestrator-state.json'

    # === Timeouts (seconds) ===
    agent_timeout: float = field(default_factory=lambda: _get_env_float(
        'FO_AGENT_TIMEOUT', 30.0
    ))

    orchestration_timeout: float = field(default_factory=lambda: _get_env_float(
        'FO_ORCHESTRATION_TIMEOUT', 120.0
    ))

    shutdown_timeout: float = field(default_factory=lambda: _get_env_float(
        'FO_SHUTDOWN_TIMEOUT', 10.0
    ))

    shutdown_handler_timeout: float = field(default_factory=lambda: _get_env_float(
        'FO_SHUTDOWN_HANDLER_TIMEOUT', 5.0
    ))

    # === Retry Configuration ===
    max_retries: int = field(default_factory=lambda: _get_env_int(
        'FO_MAX_RETRIES', 3
    ))

    retry_base_delay: float = field(default_factory=lambda: _get_env_float(
        'FO_RETRY_BASE_DELAY', 1.0
    ))

    retry_max_delay: float = field(default_factory=lambda: _get_env_float(
        'FO_RETRY_MAX_DELAY', 30.0
    ))

    # === Circuit Breaker ===
    circuit_breaker_threshold: int = field(default_factory=lambda: _get_env_int(
        'FO_CB_THRESHOLD', 5
    ))

    circuit_breaker_reset_timeout: float = field(default_factory=lambda: _get_env_float(
        'FO_CB_RESET_TIMEOUT', 60.0
    ))

    # === Input Validation ===
    max_task_length: int = field(default_factory=lambda: _get_env_int(
        'FO_MAX_TASK_LENGTH', 10000
    ))

    # === Logging ===
    log_level: str = field(default_factory=lambda: os.environ.get(
        'FO_LOG_LEVEL', 'INFO'
    ).upper())

    log_format: str = field(default_factory=lambda: os.environ.get(
        'FO_LOG_FORMAT', 'text'  # 'text' or 'json'
    ).lower())

    log_file: Optional[Path] = field(default_factory=lambda: (
        Path(os.environ['FO_LOG_FILE']) if 'FO_LOG_FILE' in os.environ else None
    ))

    # === Agent Configuration ===
    max_parallel_agents: int = field(default_factory=lambda: _get_env_int(
        'FO_MAX_PARALLEL_AGENTS', 7
    ))

    # === Bulkhead Configuration ===
    max_concurrent_agents: int = field(default_factory=lambda: _get_env_int(
        'FO_MAX_CONCURRENT_AGENTS', 3
    ))

    agent_queue_size: int = field(default_factory=lambda: _get_env_int(
        'FO_AGENT_QUEUE_SIZE', 10
    ))

    bulkhead_timeout: float = field(default_factory=lambda: _get_env_float(
        'FO_BULKHEAD_TIMEOUT', 30.0
    ))

    # === Rate Limiting ===
    rate_limit_per_sec: float = field(default_factory=lambda: _get_env_float(
        'FO_RATE_LIMIT_PER_SEC', 100.0
    ))

    rate_limit_burst: int = field(default_factory=lambda: _get_env_int(
        'FO_RATE_LIMIT_BURST', 50
    ))

    rate_limit_adaptive: bool = field(default_factory=lambda: _get_env_bool(
        'FO_RATE_LIMIT_ADAPTIVE', False
    ))

    # === Fallback Configuration ===
    fallback_cache_retention: int = field(default_factory=lambda: _get_env_int(
        'FO_FALLBACK_CACHE_RETENTION', 3600
    ))

    fallback_enable_synthetic: bool = field(default_factory=lambda: _get_env_bool(
        'FO_FALLBACK_ENABLE_SYNTHETIC', True
    ))

    # === Idempotency Configuration ===
    idempotency_retention: int = field(default_factory=lambda: _get_env_int(
        'FO_IDEMPOTENCY_RETENTION', 3600
    ))

    idempotency_max_entries: int = field(default_factory=lambda: _get_env_int(
        'FO_IDEMPOTENCY_MAX_ENTRIES', 10000
    ))

    # === Checkpointing Configuration ===
    checkpoint_enabled: bool = field(default_factory=lambda: _get_env_bool(
        'FO_CHECKPOINT_ENABLED', True
    ))

    checkpoint_retention: int = field(default_factory=lambda: _get_env_int(
        'FO_CHECKPOINT_RETENTION', 86400  # 24 hours
    ))

    @property
    def checkpoint_dir(self) -> Path:
        """Path to checkpoint directory."""
        custom = os.environ.get('FO_CHECKPOINT_DIR')
        if custom:
            return Path(custom)
        return self.state_dir / 'checkpoints'

    # === Metrics Configuration ===
    metrics_enabled: bool = field(default_factory=lambda: _get_env_bool(
        'FO_METRICS_ENABLED', True
    ))

    # === Tracing Configuration ===
    tracing_enabled: bool = field(default_factory=lambda: _get_env_bool(
        'FO_TRACING_ENABLED', True
    ))

    tracing_sample_rate: float = field(default_factory=lambda: _get_env_float(
        'FO_TRACING_SAMPLE_RATE', 1.0
    ))

    # === Feature Flags ===
    enable_circuit_breaker: bool = field(default_factory=lambda: _get_env_bool(
        'FO_ENABLE_CIRCUIT_BREAKER', True
    ))

    enable_retries: bool = field(default_factory=lambda: _get_env_bool(
        'FO_ENABLE_RETRIES', True
    ))

    enable_health_check: bool = field(default_factory=lambda: _get_env_bool(
        'FO_ENABLE_HEALTH_CHECK', True
    ))

    enable_bulkhead: bool = field(default_factory=lambda: _get_env_bool(
        'FO_ENABLE_BULKHEAD', True
    ))

    enable_rate_limit: bool = field(default_factory=lambda: _get_env_bool(
        'FO_ENABLE_RATE_LIMIT', False  # Disabled by default
    ))

    enable_idempotency: bool = field(default_factory=lambda: _get_env_bool(
        'FO_ENABLE_IDEMPOTENCY', True
    ))

    enable_fallback: bool = field(default_factory=lambda: _get_env_bool(
        'FO_ENABLE_FALLBACK', True
    ))

    # === Reproducibility / ThinkingMachines Compliance ===
    # Per [He2025]: "Control every source of randomness"
    reproducibility_mode: bool = field(default_factory=lambda: _get_env_bool(
        'FO_REPRODUCIBILITY_MODE', False  # Disabled by default for production
    ))

    determinism_seed: int = field(default_factory=lambda: _get_env_int(
        'FO_DETERMINISM_SEED', 42  # Default seed when reproducibility_mode=True
    ))

    retry_jitter: float = field(default_factory=lambda: _get_env_float(
        'FO_RETRY_JITTER', 0.1  # 10% jitter by default; set to 0.0 for full determinism
    ))

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.domains_path.mkdir(parents=True, exist_ok=True)
        self.frameworks_path.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        if self.checkpoint_enabled:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """
        Validate configuration and return list of errors.

        Returns:
            Empty list if valid, list of error messages otherwise.
        """
        errors = []

        # Timeout validation
        if self.agent_timeout <= 0:
            errors.append(f"agent_timeout must be positive, got {self.agent_timeout}")
        if self.orchestration_timeout <= 0:
            errors.append(f"orchestration_timeout must be positive, got {self.orchestration_timeout}")
        if self.agent_timeout > self.orchestration_timeout:
            errors.append(
                f"agent_timeout ({self.agent_timeout}s) should not exceed "
                f"orchestration_timeout ({self.orchestration_timeout}s)"
            )

        # Retry validation
        if self.max_retries < 0:
            errors.append(f"max_retries must be non-negative, got {self.max_retries}")
        if self.retry_base_delay <= 0:
            errors.append(f"retry_base_delay must be positive, got {self.retry_base_delay}")

        # Circuit breaker validation
        if self.circuit_breaker_threshold < 1:
            errors.append(f"circuit_breaker_threshold must be >= 1, got {self.circuit_breaker_threshold}")

        # Input validation
        if self.max_task_length < 100:
            errors.append(f"max_task_length must be >= 100, got {self.max_task_length}")

        # Log level validation
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if self.log_level not in valid_levels:
            errors.append(f"log_level must be one of {valid_levels}, got {self.log_level}")

        # Log format validation
        if self.log_format not in ('text', 'json'):
            errors.append(f"log_format must be 'text' or 'json', got {self.log_format}")

        return errors

    def to_dict(self) -> dict:
        """Export configuration as dictionary (for logging/debugging)."""
        return {
            'workspace': str(self.workspace),
            'domains_path': str(self.domains_path),
            'frameworks_path': str(self.frameworks_path),
            'agent_timeout': self.agent_timeout,
            'orchestration_timeout': self.orchestration_timeout,
            'max_retries': self.max_retries,
            'circuit_breaker_threshold': self.circuit_breaker_threshold,
            'max_task_length': self.max_task_length,
            'log_level': self.log_level,
            'log_format': self.log_format,
            # Feature flags
            'enable_circuit_breaker': self.enable_circuit_breaker,
            'enable_retries': self.enable_retries,
            'enable_bulkhead': self.enable_bulkhead,
            'enable_rate_limit': self.enable_rate_limit,
            'enable_idempotency': self.enable_idempotency,
            'enable_fallback': self.enable_fallback,
            # Bulkhead
            'max_concurrent_agents': self.max_concurrent_agents,
            'agent_queue_size': self.agent_queue_size,
            # Rate limiting
            'rate_limit_per_sec': self.rate_limit_per_sec,
            'rate_limit_burst': self.rate_limit_burst,
            # Checkpointing
            'checkpoint_enabled': self.checkpoint_enabled,
            'checkpoint_dir': str(self.checkpoint_dir),
            # Metrics & Tracing
            'metrics_enabled': self.metrics_enabled,
            'tracing_enabled': self.tracing_enabled,
            # Reproducibility (ThinkingMachines compliance)
            'reproducibility_mode': self.reproducibility_mode,
            'determinism_seed': self.determinism_seed,
            'retry_jitter': self.retry_jitter,
        }


# Global default configuration instance
_default_config: Optional[OrchestratorConfig] = None


def get_config() -> OrchestratorConfig:
    """Get the global configuration instance (lazy initialization)."""
    global _default_config
    if _default_config is None:
        _default_config = OrchestratorConfig()
    return _default_config


def set_config(config: OrchestratorConfig) -> None:
    """Set the global configuration instance (for testing)."""
    global _default_config
    _default_config = config


def get_config_warnings() -> list[str]:
    """Get any configuration warnings that occurred during parsing."""
    return _config_warnings.copy()


def validate_config_strict() -> None:
    """
    Validate configuration and raise on any errors.

    Call this at startup to fail fast on misconfiguration.

    Raises:
        ConfigurationError: If any validation errors exist
    """
    config = get_config()
    errors = config.validate()

    # Also include any parsing warnings as errors in strict mode
    all_errors = errors + _config_warnings

    if all_errors:
        raise ConfigurationError(
            f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in all_errors)
        )
