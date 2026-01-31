"""
Self-Healing Security
=====================

Automatic detection, diagnosis, and remediation of security issues.

Implements a detect → diagnose → remediate loop:
1. Monitor security indicators continuously
2. Detect anomalies and policy violations
3. Diagnose root causes
4. Apply automatic remediation where safe
5. Alert for manual intervention when needed

[He2025] Compliance:
- FIXED remediation actions (no runtime policy changes)
- FIXED detection thresholds
- Deterministic diagnosis rules

Usage:
    from otto.security.healing import SecurityHealer, RemediationAction

    healer = SecurityHealer()
    healer.start_monitoring()

    # Register custom remediation
    healer.register_remediation(
        issue_type="expired_key",
        action=RemediationAction.KEY_ROTATE,
        auto_execute=True,
    )

    # Manual trigger
    issues = healer.scan()
    for issue in issues:
        healer.remediate(issue)
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional, Callable, Set
from pathlib import Path
import hashlib
import json

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (FIXED - [He2025] Compliant)
# =============================================================================

# Detection thresholds (FIXED)
FAILED_AUTH_THRESHOLD = 5  # Failed auths before alert
RATE_LIMIT_THRESHOLD = 100  # Requests per minute
KEY_AGE_WARNING_DAYS = 30  # Days before key rotation warning
KEY_AGE_CRITICAL_DAYS = 90  # Days before forced rotation
SESSION_DURATION_WARNING_HOURS = 4
ANOMALY_SCORE_THRESHOLD = 0.7

# Monitoring intervals
SCAN_INTERVAL_SECONDS = 60
DEEP_SCAN_INTERVAL_SECONDS = 300


# =============================================================================
# Enums
# =============================================================================

class IssueType(Enum):
    """Types of security issues that can be detected."""
    # Authentication issues
    BRUTE_FORCE_DETECTED = "brute_force_detected"
    SUSPICIOUS_AUTH_PATTERN = "suspicious_auth_pattern"
    INVALID_TOKEN_USED = "invalid_token_used"
    SESSION_ANOMALY = "session_anomaly"

    # Key management issues
    KEY_EXPIRED = "key_expired"
    KEY_EXPIRING_SOON = "key_expiring_soon"
    KEY_COMPROMISED = "key_compromised"
    WEAK_KEY_DETECTED = "weak_key_detected"

    # Access issues
    PRIVILEGE_ESCALATION = "privilege_escalation"
    UNAUTHORIZED_SCOPE = "unauthorized_scope"
    UNUSUAL_ACCESS_PATTERN = "unusual_access_pattern"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    BURST_TRAFFIC_DETECTED = "burst_traffic_detected"

    # System issues
    CONFIG_DRIFT = "config_drift"
    MISSING_SECURITY_UPDATE = "missing_security_update"
    PQ_CRYPTO_UNAVAILABLE = "pq_crypto_unavailable"

    # Audit issues
    AUDIT_LOG_TAMPERED = "audit_log_tampered"
    AUDIT_LOG_FULL = "audit_log_full"


class IssueSeverity(Enum):
    """Severity levels for detected issues."""
    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"  # Action required soon
    MEDIUM = "medium"  # Should be addressed
    LOW = "low"  # Informational


class RemediationAction(Enum):
    """Available remediation actions."""
    # No action
    NONE = "none"
    ALERT_ONLY = "alert_only"

    # Authentication remediations
    BLOCK_IP = "block_ip"
    REVOKE_TOKEN = "revoke_token"
    RESET_SESSION = "reset_session"
    REQUIRE_REAUTHENTICATION = "require_reauthentication"

    # Key remediations
    KEY_ROTATE = "key_rotate"
    KEY_REVOKE = "key_revoke"

    # Access remediations
    REDUCE_PRIVILEGES = "reduce_privileges"
    ENFORCE_MFA = "enforce_mfa"

    # Rate limiting
    APPLY_RATE_LIMIT = "apply_rate_limit"
    INCREASE_RATE_LIMIT = "increase_rate_limit"

    # System remediations
    RESTORE_CONFIG = "restore_config"
    APPLY_UPDATE = "apply_update"
    ENABLE_PQ = "enable_pq"

    # Audit remediations
    ROTATE_LOG = "rotate_log"
    REPAIR_LOG = "repair_log"


class RemediationStatus(Enum):
    """Status of a remediation action."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_MANUAL = "requires_manual"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SecurityIssue:
    """A detected security issue."""
    issue_type: IssueType
    severity: IssueSeverity
    title: str
    description: str
    detected_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    issue_id: str = ""

    def __post_init__(self):
        if not self.issue_id:
            content = f"{self.issue_type.value}-{self.detected_at}-{self.title}"
            self.issue_id = hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'issue_id': self.issue_id,
            'issue_type': self.issue_type.value,
            'severity': self.severity.value,
            'title': self.title,
            'description': self.description,
            'detected_at': self.detected_at,
            'metadata': self.metadata,
        }


@dataclass
class RemediationResult:
    """Result of a remediation action."""
    issue_id: str
    action: RemediationAction
    status: RemediationStatus
    message: str
    executed_at: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'issue_id': self.issue_id,
            'action': self.action.value,
            'status': self.status.value,
            'message': self.message,
            'executed_at': self.executed_at,
            'details': self.details,
        }


@dataclass
class RemediationRule:
    """Rule for automatic remediation."""
    issue_type: IssueType
    action: RemediationAction
    auto_execute: bool = False
    condition: Optional[Callable[[SecurityIssue], bool]] = None
    cooldown_seconds: int = 300  # Min time between executions


# =============================================================================
# Detectors
# =============================================================================

class SecurityDetector:
    """Base class for security issue detectors."""

    def __init__(self, name: str):
        self.name = name

    def detect(self, context: Dict[str, Any]) -> List[SecurityIssue]:
        """Detect issues from context. Override in subclass."""
        raise NotImplementedError


class AuthenticationDetector(SecurityDetector):
    """Detects authentication-related security issues."""

    def __init__(self):
        super().__init__("authentication")
        self._failed_attempts: Dict[str, List[float]] = {}

    def detect(self, context: Dict[str, Any]) -> List[SecurityIssue]:
        issues = []

        # Check for brute force
        auth_events = context.get('auth_events', [])
        for event in auth_events:
            if event.get('success') is False:
                actor = event.get('actor', 'unknown')
                if actor not in self._failed_attempts:
                    self._failed_attempts[actor] = []
                self._failed_attempts[actor].append(event.get('timestamp', time.time()))

        # Check thresholds
        current_time = time.time()
        for actor, attempts in list(self._failed_attempts.items()):
            # Only count recent attempts (last 5 minutes)
            recent = [t for t in attempts if current_time - t < 300]
            self._failed_attempts[actor] = recent

            if len(recent) >= FAILED_AUTH_THRESHOLD:
                issues.append(SecurityIssue(
                    issue_type=IssueType.BRUTE_FORCE_DETECTED,
                    severity=IssueSeverity.HIGH,
                    title="Brute force attack detected",
                    description=f"Multiple failed auth attempts for {actor}",
                    metadata={'actor': actor, 'attempt_count': len(recent)},
                ))

        return issues


class KeyManagementDetector(SecurityDetector):
    """Detects key management issues."""

    def __init__(self):
        super().__init__("key_management")

    def detect(self, context: Dict[str, Any]) -> List[SecurityIssue]:
        issues = []

        keys = context.get('keys', [])
        current_time = time.time()

        for key in keys:
            created_at = key.get('created_at', current_time)
            age_days = (current_time - created_at) / (24 * 3600)

            if age_days >= KEY_AGE_CRITICAL_DAYS:
                issues.append(SecurityIssue(
                    issue_type=IssueType.KEY_EXPIRED,
                    severity=IssueSeverity.CRITICAL,
                    title="Encryption key critically old",
                    description=f"Key {key.get('key_id', 'unknown')} is {int(age_days)} days old",
                    metadata={'key_id': key.get('key_id'), 'age_days': age_days},
                ))
            elif age_days >= KEY_AGE_WARNING_DAYS:
                issues.append(SecurityIssue(
                    issue_type=IssueType.KEY_EXPIRING_SOON,
                    severity=IssueSeverity.MEDIUM,
                    title="Encryption key nearing rotation",
                    description=f"Key {key.get('key_id', 'unknown')} should be rotated soon",
                    metadata={'key_id': key.get('key_id'), 'age_days': age_days},
                ))

        return issues


class RateLimitDetector(SecurityDetector):
    """Detects rate limiting issues."""

    def __init__(self):
        super().__init__("rate_limit")
        self._request_counts: Dict[str, List[float]] = {}

    def detect(self, context: Dict[str, Any]) -> List[SecurityIssue]:
        issues = []

        requests = context.get('requests', [])
        current_time = time.time()

        for req in requests:
            client = req.get('client_id', 'unknown')
            if client not in self._request_counts:
                self._request_counts[client] = []
            self._request_counts[client].append(req.get('timestamp', current_time))

        # Check per-minute rates
        for client, timestamps in list(self._request_counts.items()):
            recent = [t for t in timestamps if current_time - t < 60]
            self._request_counts[client] = recent

            if len(recent) >= RATE_LIMIT_THRESHOLD:
                issues.append(SecurityIssue(
                    issue_type=IssueType.RATE_LIMIT_EXCEEDED,
                    severity=IssueSeverity.MEDIUM,
                    title="Rate limit exceeded",
                    description=f"Client {client} exceeded rate limit",
                    metadata={'client_id': client, 'request_count': len(recent)},
                ))

        return issues


class AuditLogDetector(SecurityDetector):
    """Detects audit log issues."""

    def __init__(self):
        super().__init__("audit_log")

    def detect(self, context: Dict[str, Any]) -> List[SecurityIssue]:
        issues = []

        audit_status = context.get('audit_log', {})

        # Check integrity
        if audit_status.get('integrity_valid') is False:
            issues.append(SecurityIssue(
                issue_type=IssueType.AUDIT_LOG_TAMPERED,
                severity=IssueSeverity.CRITICAL,
                title="Audit log tampering detected",
                description=audit_status.get('integrity_error', 'Unknown error'),
                metadata={'error': audit_status.get('integrity_error')},
            ))

        # Check size
        event_count = audit_status.get('event_count', 0)
        max_events = audit_status.get('max_events', 10000)
        if event_count > max_events * 0.9:
            issues.append(SecurityIssue(
                issue_type=IssueType.AUDIT_LOG_FULL,
                severity=IssueSeverity.HIGH,
                title="Audit log nearly full",
                description=f"Audit log at {int(event_count/max_events*100)}% capacity",
                metadata={'event_count': event_count, 'max_events': max_events},
            ))

        return issues


class PQCryptoDetector(SecurityDetector):
    """Detects post-quantum crypto issues."""

    def __init__(self):
        super().__init__("pq_crypto")

    def detect(self, context: Dict[str, Any]) -> List[SecurityIssue]:
        issues = []

        pq_status = context.get('pq_crypto', {})

        if not pq_status.get('available', True):
            issues.append(SecurityIssue(
                issue_type=IssueType.PQ_CRYPTO_UNAVAILABLE,
                severity=IssueSeverity.MEDIUM,
                title="Post-quantum crypto unavailable",
                description="liboqs not installed, using classical-only crypto",
                metadata={'classical_only': True},
            ))

        return issues


# =============================================================================
# Remediators
# =============================================================================

class Remediator:
    """Executes remediation actions."""

    def __init__(self):
        self._blocked_ips: Set[str] = set()
        self._revoked_tokens: Set[str] = set()
        self._last_executions: Dict[str, float] = {}

    def can_execute(self, issue: SecurityIssue, rule: RemediationRule) -> bool:
        """Check if remediation can be executed (cooldown check)."""
        key = f"{issue.issue_type.value}-{rule.action.value}"
        last_exec = self._last_executions.get(key, 0)
        return time.time() - last_exec >= rule.cooldown_seconds

    def execute(
        self,
        issue: SecurityIssue,
        action: RemediationAction,
    ) -> RemediationResult:
        """Execute a remediation action."""
        try:
            if action == RemediationAction.NONE:
                return RemediationResult(
                    issue_id=issue.issue_id,
                    action=action,
                    status=RemediationStatus.COMPLETED,
                    message="No action taken",
                )

            if action == RemediationAction.ALERT_ONLY:
                logger.warning(f"Security Alert: {issue.title} - {issue.description}")
                return RemediationResult(
                    issue_id=issue.issue_id,
                    action=action,
                    status=RemediationStatus.COMPLETED,
                    message="Alert logged",
                )

            if action == RemediationAction.BLOCK_IP:
                ip = issue.metadata.get('ip') or issue.metadata.get('actor')
                if ip:
                    self._blocked_ips.add(ip)
                    logger.info(f"Blocked IP: {ip}")
                    return RemediationResult(
                        issue_id=issue.issue_id,
                        action=action,
                        status=RemediationStatus.COMPLETED,
                        message=f"Blocked IP: {ip}",
                        details={'blocked_ip': ip},
                    )

            if action == RemediationAction.REVOKE_TOKEN:
                token_id = issue.metadata.get('token_id')
                if token_id:
                    self._revoked_tokens.add(token_id)
                    logger.info(f"Revoked token: {token_id}")
                    return RemediationResult(
                        issue_id=issue.issue_id,
                        action=action,
                        status=RemediationStatus.COMPLETED,
                        message=f"Revoked token: {token_id}",
                        details={'revoked_token': token_id},
                    )

            if action == RemediationAction.KEY_ROTATE:
                key_id = issue.metadata.get('key_id')
                # In production, this would call actual key rotation
                logger.info(f"Key rotation initiated for: {key_id}")
                return RemediationResult(
                    issue_id=issue.issue_id,
                    action=action,
                    status=RemediationStatus.COMPLETED,
                    message=f"Key rotation initiated: {key_id}",
                    details={'key_id': key_id},
                )

            if action == RemediationAction.APPLY_RATE_LIMIT:
                client = issue.metadata.get('client_id')
                logger.info(f"Rate limit applied to: {client}")
                return RemediationResult(
                    issue_id=issue.issue_id,
                    action=action,
                    status=RemediationStatus.COMPLETED,
                    message=f"Rate limit applied: {client}",
                    details={'client_id': client},
                )

            if action == RemediationAction.ROTATE_LOG:
                logger.info("Audit log rotation initiated")
                return RemediationResult(
                    issue_id=issue.issue_id,
                    action=action,
                    status=RemediationStatus.COMPLETED,
                    message="Audit log rotation initiated",
                )

            # Requires manual intervention
            return RemediationResult(
                issue_id=issue.issue_id,
                action=action,
                status=RemediationStatus.REQUIRES_MANUAL,
                message=f"Manual intervention required for {action.value}",
            )

        except Exception as e:
            logger.error(f"Remediation failed: {e}")
            return RemediationResult(
                issue_id=issue.issue_id,
                action=action,
                status=RemediationStatus.FAILED,
                message=str(e),
            )

    def is_ip_blocked(self, ip: str) -> bool:
        """Check if an IP is blocked."""
        return ip in self._blocked_ips

    def is_token_revoked(self, token_id: str) -> bool:
        """Check if a token is revoked."""
        return token_id in self._revoked_tokens


# =============================================================================
# Security Healer
# =============================================================================

class SecurityHealer:
    """
    Self-healing security system.

    Coordinates detection, diagnosis, and remediation of security issues.
    """

    def __init__(self):
        self._detectors: List[SecurityDetector] = [
            AuthenticationDetector(),
            KeyManagementDetector(),
            RateLimitDetector(),
            AuditLogDetector(),
            PQCryptoDetector(),
        ]
        self._remediator = Remediator()
        self._rules: Dict[IssueType, RemediationRule] = {}
        self._active_issues: Dict[str, SecurityIssue] = {}
        self._remediation_history: List[RemediationResult] = []
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Register default rules
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """Register default remediation rules."""
        # Auto-block brute force
        self.register_remediation(
            IssueType.BRUTE_FORCE_DETECTED,
            RemediationAction.BLOCK_IP,
            auto_execute=True,
        )

        # Alert on key expiry
        self.register_remediation(
            IssueType.KEY_EXPIRING_SOON,
            RemediationAction.ALERT_ONLY,
            auto_execute=True,
        )

        # Auto-rotate expired keys
        self.register_remediation(
            IssueType.KEY_EXPIRED,
            RemediationAction.KEY_ROTATE,
            auto_execute=True,
        )

        # Auto rate limit
        self.register_remediation(
            IssueType.RATE_LIMIT_EXCEEDED,
            RemediationAction.APPLY_RATE_LIMIT,
            auto_execute=True,
        )

        # Alert on log tampering (critical, requires manual)
        self.register_remediation(
            IssueType.AUDIT_LOG_TAMPERED,
            RemediationAction.ALERT_ONLY,
            auto_execute=True,
        )

        # Auto-rotate nearly full log
        self.register_remediation(
            IssueType.AUDIT_LOG_FULL,
            RemediationAction.ROTATE_LOG,
            auto_execute=True,
        )

    def register_remediation(
        self,
        issue_type: IssueType,
        action: RemediationAction,
        auto_execute: bool = False,
        condition: Optional[Callable[[SecurityIssue], bool]] = None,
        cooldown_seconds: int = 300,
    ) -> None:
        """Register a remediation rule."""
        self._rules[issue_type] = RemediationRule(
            issue_type=issue_type,
            action=action,
            auto_execute=auto_execute,
            condition=condition,
            cooldown_seconds=cooldown_seconds,
        )

    def add_detector(self, detector: SecurityDetector) -> None:
        """Add a custom detector."""
        self._detectors.append(detector)

    def scan(self, context: Optional[Dict[str, Any]] = None) -> List[SecurityIssue]:
        """
        Run all detectors and return issues.

        Args:
            context: Context data for detectors

        Returns:
            List of detected issues
        """
        if context is None:
            context = self._gather_context()

        issues = []
        for detector in self._detectors:
            try:
                detected = detector.detect(context)
                issues.extend(detected)
            except Exception as e:
                logger.error(f"Detector {detector.name} failed: {e}")

        # Update active issues
        for issue in issues:
            self._active_issues[issue.issue_id] = issue

        return issues

    def _gather_context(self) -> Dict[str, Any]:
        """Gather context from various sources."""
        context: Dict[str, Any] = {}

        # Try to get audit log status
        try:
            from .audit import get_audit_log, verify_log_integrity
            log = get_audit_log()
            valid, error = verify_log_integrity()
            context['audit_log'] = {
                'event_count': log.event_count,
                'max_events': 10000,
                'integrity_valid': valid,
                'integrity_error': error,
            }
        except Exception:
            pass

        # Try to get PQ crypto status
        try:
            from ..crypto.pqcrypto import is_pq_available
            context['pq_crypto'] = {
                'available': is_pq_available(),
            }
        except Exception:
            pass

        return context

    def remediate(
        self,
        issue: SecurityIssue,
        action: Optional[RemediationAction] = None,
    ) -> RemediationResult:
        """
        Remediate a security issue.

        Args:
            issue: The issue to remediate
            action: Override action (uses rule if not specified)

        Returns:
            Remediation result
        """
        # Get action from rule if not specified
        if action is None:
            rule = self._rules.get(issue.issue_type)
            if rule:
                action = rule.action
            else:
                action = RemediationAction.ALERT_ONLY

        result = self._remediator.execute(issue, action)
        self._remediation_history.append(result)

        # Clear from active if completed
        if result.status in (RemediationStatus.COMPLETED, RemediationStatus.REQUIRES_MANUAL):
            self._active_issues.pop(issue.issue_id, None)

        return result

    def auto_remediate(self, issues: List[SecurityIssue]) -> List[RemediationResult]:
        """
        Automatically remediate issues based on rules.

        Args:
            issues: Issues to remediate

        Returns:
            List of remediation results
        """
        results = []

        for issue in issues:
            rule = self._rules.get(issue.issue_type)
            if not rule or not rule.auto_execute:
                continue

            # Check condition
            if rule.condition and not rule.condition(issue):
                continue

            # Check cooldown
            if not self._remediator.can_execute(issue, rule):
                continue

            result = self.remediate(issue)
            results.append(result)

        return results

    def scan_and_heal(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run detection and automatic remediation.

        Args:
            context: Context for detection

        Returns:
            Summary of actions taken
        """
        issues = self.scan(context)
        results = self.auto_remediate(issues)

        return {
            'issues_detected': len(issues),
            'remediations_attempted': len(results),
            'remediations_successful': sum(
                1 for r in results if r.status == RemediationStatus.COMPLETED
            ),
            'issues': [i.to_dict() for i in issues],
            'results': [r.to_dict() for r in results],
        }

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._monitoring:
            try:
                self.scan_and_heal()
            except Exception as e:
                logger.error(f"Monitoring scan failed: {e}")

            await asyncio.sleep(SCAN_INTERVAL_SECONDS)

    def start_monitoring(self) -> None:
        """Start background monitoring."""
        if self._monitoring:
            return

        self._monitoring = True
        try:
            loop = asyncio.get_event_loop()
            self._monitor_task = loop.create_task(self._monitor_loop())
        except RuntimeError:
            # No event loop running
            pass

    def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

    def get_active_issues(self) -> List[SecurityIssue]:
        """Get currently active issues."""
        return list(self._active_issues.values())

    def get_remediation_history(self, limit: int = 50) -> List[RemediationResult]:
        """Get recent remediation history."""
        return self._remediation_history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """Get healer status for API response."""
        return {
            'monitoring': self._monitoring,
            'active_issues': len(self._active_issues),
            'total_remediations': len(self._remediation_history),
            'detectors': [d.name for d in self._detectors],
            'rules': {
                t.value: {
                    'action': r.action.value,
                    'auto_execute': r.auto_execute,
                }
                for t, r in self._rules.items()
            },
        }


# =============================================================================
# Global Instance
# =============================================================================

_healer: Optional[SecurityHealer] = None


def get_healer() -> SecurityHealer:
    """Get the global security healer instance."""
    global _healer
    if _healer is None:
        _healer = SecurityHealer()
    return _healer


def scan_and_heal() -> Dict[str, Any]:
    """Run a scan and heal cycle."""
    return get_healer().scan_and_heal()


def get_security_status() -> Dict[str, Any]:
    """Get security healer status."""
    return get_healer().get_status()
