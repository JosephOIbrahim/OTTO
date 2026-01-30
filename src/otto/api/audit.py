"""
Audit Logging for OTTO Public REST API
=======================================

Provides dedicated, append-only audit trail for API key lifecycle events.

ThinkingMachines [He2025] Compliance:
- DETERMINISTIC: Same event → same log structure
- FIXED FORMAT: No runtime variation in log format
- APPEND-ONLY: Immutable audit trail
- TRACEABLE: Full context for each event

Usage:
    from otto.api.audit import AuditLogger, AuditEvent

    audit = AuditLogger()
    audit.log(AuditEvent.KEY_CREATED, key_id="abc123", name="My Key")
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Audit Event Types (FIXED - No runtime additions)
# =============================================================================

class AuditEvent(Enum):
    """
    API audit event types.

    [He2025] Compliance: Fixed enumeration, no runtime additions.
    """
    # Key lifecycle
    KEY_CREATED = "key.created"
    KEY_VALIDATED = "key.validated"
    KEY_VALIDATION_FAILED = "key.validation_failed"
    KEY_ROTATED = "key.rotated"
    KEY_REVOKED = "key.revoked"
    KEY_DELETED = "key.deleted"
    KEY_EXPIRED = "key.expired"

    # Authentication
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILED = "auth.failed"
    AUTH_MISSING = "auth.missing"

    # Authorization
    SCOPE_GRANTED = "scope.granted"
    SCOPE_DENIED = "scope.denied"

    # Rate limiting
    RATE_LIMIT_HIT = "rate.limit_hit"
    RATE_LIMIT_EXCEEDED = "rate.limit_exceeded"

    # Sensitive data
    SENSITIVE_FILTERED = "sensitive.filtered"


# =============================================================================
# Audit Record (FIXED Structure)
# =============================================================================

@dataclass
class AuditRecord:
    """
    Immutable audit record.

    [He2025] Compliance: Fixed structure, deterministic serialization.
    """
    timestamp: float
    event: str
    key_id: Optional[str]
    details: Dict[str, Any]
    source_ip: Optional[str] = None
    request_id: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with FIXED field order."""
        return {
            "timestamp": self.timestamp,
            "iso_time": datetime.fromtimestamp(
                self.timestamp, tz=timezone.utc
            ).isoformat(),
            "event": self.event,
            "key_id": self.key_id,
            "source_ip": self.source_ip,
            "request_id": self.request_id,
            "user_agent": self.user_agent,
            "details": self.details,
        }

    def to_json(self) -> str:
        """
        Serialize to JSON with DETERMINISTIC ordering.

        [He2025] Compliance: sort_keys=True ensures same dict → same JSON.
        """
        return json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'))


# =============================================================================
# Audit Logger
# =============================================================================

class AuditLogger:
    """
    Dedicated audit logger for API events.

    Features:
    - Append-only file output
    - JSONL format (one record per line)
    - Deterministic serialization
    - Optional structured logging integration

    [He2025] Compliance:
    - Fixed log format (no runtime variation)
    - Deterministic: same event + context → same output
    - Append-only: never modifies existing records
    """

    DEFAULT_AUDIT_DIR = Path.home() / ".otto" / "audit"
    DEFAULT_AUDIT_FILE = "api_audit.jsonl"

    def __init__(
        self,
        audit_dir: Optional[Path] = None,
        audit_file: str = DEFAULT_AUDIT_FILE,
        enabled: bool = True,
        also_log: bool = True,
    ):
        """
        Initialize audit logger.

        Args:
            audit_dir: Directory for audit files (default: ~/.otto/audit)
            audit_file: Audit file name (default: api_audit.jsonl)
            enabled: Whether to write to file (can disable for testing)
            also_log: Also log via standard logger
        """
        self._audit_dir = audit_dir or self.DEFAULT_AUDIT_DIR
        self._audit_file = audit_file
        self._enabled = enabled
        self._also_log = also_log
        self._file_path: Optional[Path] = None

        if self._enabled:
            self._ensure_audit_dir()

    def _ensure_audit_dir(self) -> None:
        """Create audit directory if needed."""
        try:
            self._audit_dir.mkdir(parents=True, exist_ok=True)
            self._file_path = self._audit_dir / self._audit_file
        except OSError as e:
            logger.warning(f"Could not create audit directory: {e}")
            self._enabled = False

    def log(
        self,
        event: AuditEvent,
        key_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        request_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        **details: Any,
    ) -> AuditRecord:
        """
        Log an audit event.

        Args:
            event: Event type
            key_id: API key ID (never the full key)
            source_ip: Client IP address
            request_id: Request correlation ID
            user_agent: Client user agent
            **details: Additional event-specific details

        Returns:
            The created AuditRecord
        """
        record = AuditRecord(
            timestamp=time.time(),
            event=event.value,
            key_id=key_id,
            source_ip=source_ip,
            request_id=request_id,
            user_agent=user_agent,
            details=details,
        )

        # Write to file (append-only)
        if self._enabled and self._file_path:
            try:
                with open(self._file_path, "a", encoding="utf-8") as f:
                    f.write(record.to_json() + "\n")
            except OSError as e:
                logger.error(f"Failed to write audit record: {e}")

        # Also log via standard logger
        if self._also_log:
            log_level = self._get_log_level(event)
            log_message = self._format_log_message(record)
            logger.log(log_level, log_message)

        return record

    def _get_log_level(self, event: AuditEvent) -> int:
        """
        Get appropriate log level for event type.

        [He2025] Compliance: Fixed mapping, no runtime variation.
        """
        # Security-sensitive events at WARNING
        if event in (
            AuditEvent.AUTH_FAILED,
            AuditEvent.AUTH_MISSING,
            AuditEvent.SCOPE_DENIED,
            AuditEvent.RATE_LIMIT_EXCEEDED,
            AuditEvent.KEY_VALIDATION_FAILED,
        ):
            return logging.WARNING

        # Destructive operations at INFO
        if event in (
            AuditEvent.KEY_REVOKED,
            AuditEvent.KEY_DELETED,
        ):
            return logging.INFO

        # Normal operations at DEBUG
        return logging.DEBUG

    def _format_log_message(self, record: AuditRecord) -> str:
        """
        Format audit record for standard logging.

        [He2025] Compliance: Fixed format template.
        """
        parts = [f"AUDIT:{record.event}"]

        if record.key_id:
            parts.append(f"key={record.key_id}")
        if record.source_ip:
            parts.append(f"ip={record.source_ip}")
        if record.request_id:
            parts.append(f"req={record.request_id}")

        if record.details:
            # Only include non-sensitive details
            safe_details = {
                k: v for k, v in record.details.items()
                if not k.startswith("_") and k not in ("key", "secret", "password")
            }
            if safe_details:
                parts.append(f"details={safe_details}")

        return " ".join(parts)

    # =========================================================================
    # Convenience methods for common events
    # =========================================================================

    def key_created(
        self,
        key_id: str,
        name: str,
        scopes: list,
        environment: str = "live",
        **kwargs,
    ) -> AuditRecord:
        """Log key creation event."""
        return self.log(
            AuditEvent.KEY_CREATED,
            key_id=key_id,
            name=name,
            scopes=scopes,
            environment=environment,
            **kwargs,
        )

    def key_validated(
        self,
        key_id: str,
        **kwargs,
    ) -> AuditRecord:
        """Log successful key validation."""
        return self.log(
            AuditEvent.KEY_VALIDATED,
            key_id=key_id,
            **kwargs,
        )

    def key_validation_failed(
        self,
        key_id: Optional[str],
        reason: str,
        **kwargs,
    ) -> AuditRecord:
        """Log failed key validation."""
        return self.log(
            AuditEvent.KEY_VALIDATION_FAILED,
            key_id=key_id,
            reason=reason,
            **kwargs,
        )

    def key_revoked(
        self,
        key_id: str,
        revoked_by: Optional[str] = None,
        **kwargs,
    ) -> AuditRecord:
        """Log key revocation."""
        return self.log(
            AuditEvent.KEY_REVOKED,
            key_id=key_id,
            revoked_by=revoked_by,
            **kwargs,
        )

    def key_deleted(
        self,
        key_id: str,
        deleted_by: Optional[str] = None,
        **kwargs,
    ) -> AuditRecord:
        """Log key deletion."""
        return self.log(
            AuditEvent.KEY_DELETED,
            key_id=key_id,
            deleted_by=deleted_by,
            **kwargs,
        )

    def auth_success(
        self,
        key_id: str,
        endpoint: str,
        **kwargs,
    ) -> AuditRecord:
        """Log successful authentication."""
        return self.log(
            AuditEvent.AUTH_SUCCESS,
            key_id=key_id,
            endpoint=endpoint,
            **kwargs,
        )

    def auth_failed(
        self,
        key_id: Optional[str],
        reason: str,
        endpoint: str,
        **kwargs,
    ) -> AuditRecord:
        """Log failed authentication."""
        return self.log(
            AuditEvent.AUTH_FAILED,
            key_id=key_id,
            reason=reason,
            endpoint=endpoint,
            **kwargs,
        )

    def scope_denied(
        self,
        key_id: str,
        required_scope: str,
        endpoint: str,
        **kwargs,
    ) -> AuditRecord:
        """Log scope denial."""
        return self.log(
            AuditEvent.SCOPE_DENIED,
            key_id=key_id,
            required_scope=required_scope,
            endpoint=endpoint,
            **kwargs,
        )

    def rate_limit_exceeded(
        self,
        key_id: str,
        endpoint: str,
        limit: int,
        window_seconds: int,
        **kwargs,
    ) -> AuditRecord:
        """Log rate limit exceeded."""
        return self.log(
            AuditEvent.RATE_LIMIT_EXCEEDED,
            key_id=key_id,
            endpoint=endpoint,
            limit=limit,
            window_seconds=window_seconds,
            **kwargs,
        )


# =============================================================================
# Global Audit Logger
# =============================================================================

_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def reset_audit_logger() -> None:
    """Reset global audit logger (for testing)."""
    global _audit_logger
    _audit_logger = None


__all__ = [
    "AuditEvent",
    "AuditRecord",
    "AuditLogger",
    "get_audit_logger",
    "reset_audit_logger",
]
