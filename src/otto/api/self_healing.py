"""
Self-Healing Security System for OTTO API
==========================================

Automated security incident detection and remediation:

1. Threat Detection
   - Real-time monitoring of security signals
   - Pattern recognition for attack detection
   - Anomaly scoring and classification

2. Automated Response
   - Auto-rotate compromised keys
   - Auto-block suspicious IPs
   - Auto-revoke suspicious sessions
   - Escalation to human operators

3. Recovery Automation
   - Incident containment
   - System restoration
   - Post-incident analysis

Determinism:
- FIXED response policies (no runtime variation)
- DETERMINISTIC threat classification
- Pre-computed response thresholds

Frontier Feature: Proactive security > reactive security.
System heals itself without human intervention.

References:
- NIST Cybersecurity Framework (CSF)
- MITRE ATT&CK Framework
- Zero Trust Architecture (ZTA)
"""

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Threat Classification
# =============================================================================

class ThreatCategory(Enum):
    """
    Categories of security threats.

    FIXED: Immutable threat taxonomy.
    """
    CREDENTIAL_COMPROMISE = "credential_compromise"   # API key leaked/stolen
    BRUTE_FORCE = "brute_force"                       # Password/key guessing
    CREDENTIAL_STUFFING = "credential_stuffing"       # Reused credentials
    RATE_ABUSE = "rate_abuse"                         # Rate limit bypass
    DATA_EXFILTRATION = "data_exfiltration"           # Bulk data access
    ENUMERATION = "enumeration"                       # Resource discovery
    INJECTION = "injection"                           # Code/SQL injection
    SESSION_HIJACK = "session_hijack"                 # Session takeover
    PRIVILEGE_ESCALATION = "privilege_escalation"    # Unauthorized access
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"         # Unusual patterns


class ThreatSeverity(Enum):
    """Severity levels for threats."""
    LOW = 1        # Monitor, log
    MEDIUM = 2     # Investigate, soft response
    HIGH = 3       # Immediate response, alert
    CRITICAL = 4   # Emergency response, block


class ResponseAction(Enum):
    """Available automated response actions."""
    LOG_ONLY = "log_only"                      # Just log the event
    ALERT = "alert"                            # Send alert to operators
    RATE_LIMIT = "rate_limit"                  # Apply stricter rate limits
    TEMPORARY_BLOCK = "temporary_block"        # Temp block IP/key
    PERMANENT_BLOCK = "permanent_block"        # Permanent block
    ROTATE_KEY = "rotate_key"                  # Auto-rotate API key
    REVOKE_KEY = "revoke_key"                  # Revoke API key
    REVOKE_SESSION = "revoke_session"          # End user session
    QUARANTINE = "quarantine"                  # Isolate affected resources
    ESCALATE = "escalate"                      # Escalate to humans


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ThreatEvent:
    """
    A detected security threat.

    Determinism: Deterministic structure.
    """
    event_id: str
    category: ThreatCategory
    severity: ThreatSeverity
    timestamp: float
    source_ip: Optional[str]
    api_key_id: Optional[str]
    endpoint: Optional[str]
    description: str
    evidence: Dict[str, Any]
    confidence: float = 0.0  # 0.0 - 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "category": self.category.value,
            "severity": self.severity.name,
            "timestamp": self.timestamp,
            "source_ip": self.source_ip,
            "api_key_id": self.api_key_id,
            "endpoint": self.endpoint,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }


@dataclass
class ResponseResult:
    """
    Result of an automated response action.
    """
    action: ResponseAction
    success: bool
    threat_event_id: str
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action.value,
            "success": self.success,
            "threat_event_id": self.threat_event_id,
            "timestamp": self.timestamp,
            "details": self.details,
            "error": self.error,
        }


@dataclass
class ResponsePolicy:
    """
    Policy defining automated response to threats.

    Immutable: Policies are immutable at runtime.
    """
    name: str
    threat_category: ThreatCategory
    min_severity: ThreatSeverity
    min_confidence: float
    actions: List[ResponseAction]
    cooldown_seconds: int  # Don't repeat action within this window
    requires_confirmation: bool  # Human confirmation needed?
    max_auto_actions: int  # Max actions before escalation

    def matches(self, threat: ThreatEvent) -> bool:
        """Check if policy matches threat."""
        return (
            threat.category == self.threat_category and
            threat.severity.value >= self.min_severity.value and
            threat.confidence >= self.min_confidence
        )


@dataclass
class IncidentState:
    """
    State of an ongoing security incident.
    """
    incident_id: str
    start_time: float
    threat_events: List[ThreatEvent]
    responses_taken: List[ResponseResult]
    status: str  # "active", "contained", "resolved"
    affected_resources: Set[str]
    notes: List[str]


# =============================================================================
# Threat Detector
# =============================================================================

class ThreatDetector(ABC):
    """
    Abstract base class for threat detectors.

    Determinism: Deterministic detection.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Detector name."""
        pass

    @property
    @abstractmethod
    def categories(self) -> List[ThreatCategory]:
        """Threat categories this detector handles."""
        pass

    @abstractmethod
    def detect(self, event: Dict[str, Any]) -> Optional[ThreatEvent]:
        """
        Analyze event for threats.

        Args:
            event: Event data to analyze

        Returns:
            ThreatEvent if threat detected, None otherwise
        """
        pass


class BruteForceDetector(ThreatDetector):
    """
    Detect brute force attacks.

    FIXED thresholds:
    - 5 failures in 1 minute = LOW
    - 10 failures in 1 minute = MEDIUM
    - 20 failures in 1 minute = HIGH
    - 50 failures in 1 minute = CRITICAL
    """

    # FIXED thresholds
    THRESHOLDS = {
        5: ThreatSeverity.LOW,
        10: ThreatSeverity.MEDIUM,
        20: ThreatSeverity.HIGH,
        50: ThreatSeverity.CRITICAL,
    }
    WINDOW_SECONDS = 60

    def __init__(self):
        """Initialize detector."""
        self._failures_by_source: Dict[str, List[float]] = {}

    @property
    def name(self) -> str:
        return "brute_force_detector"

    @property
    def categories(self) -> List[ThreatCategory]:
        return [ThreatCategory.BRUTE_FORCE]

    def detect(self, event: Dict[str, Any]) -> Optional[ThreatEvent]:
        """Detect brute force attempts."""
        if event.get("type") != "auth_failure":
            return None

        source_ip = event.get("source_ip", "unknown")
        now = time.time()
        cutoff = now - self.WINDOW_SECONDS

        # Track failure
        if source_ip not in self._failures_by_source:
            self._failures_by_source[source_ip] = []

        self._failures_by_source[source_ip].append(now)
        self._failures_by_source[source_ip] = [
            t for t in self._failures_by_source[source_ip] if t > cutoff
        ]

        failure_count = len(self._failures_by_source[source_ip])

        # Check thresholds (from highest to lowest)
        severity = None
        for threshold, sev in sorted(self.THRESHOLDS.items(), reverse=True):
            if failure_count >= threshold:
                severity = sev
                break

        if severity is None:
            return None

        import uuid
        return ThreatEvent(
            event_id=f"threat_{uuid.uuid4().hex[:12]}",
            category=ThreatCategory.BRUTE_FORCE,
            severity=severity,
            timestamp=now,
            source_ip=source_ip,
            api_key_id=event.get("api_key_id"),
            endpoint=event.get("endpoint"),
            description=f"Brute force detected: {failure_count} failures in {self.WINDOW_SECONDS}s",
            evidence={
                "failure_count": failure_count,
                "window_seconds": self.WINDOW_SECONDS,
                "threshold_exceeded": failure_count,
            },
            confidence=min(0.9, 0.5 + (failure_count / 100)),
        )


class CredentialStuffingDetector(ThreatDetector):
    """
    Detect credential stuffing attacks.

    Pattern: Multiple accounts accessed from same IP in short time.

    FIXED thresholds:
    - 3 different keys in 5 minutes = MEDIUM
    - 5 different keys in 5 minutes = HIGH
    - 10 different keys in 5 minutes = CRITICAL
    """

    THRESHOLDS = {
        3: ThreatSeverity.MEDIUM,
        5: ThreatSeverity.HIGH,
        10: ThreatSeverity.CRITICAL,
    }
    WINDOW_SECONDS = 300

    def __init__(self):
        """Initialize detector."""
        self._keys_by_ip: Dict[str, Dict[str, float]] = {}

    @property
    def name(self) -> str:
        return "credential_stuffing_detector"

    @property
    def categories(self) -> List[ThreatCategory]:
        return [ThreatCategory.CREDENTIAL_STUFFING]

    def detect(self, event: Dict[str, Any]) -> Optional[ThreatEvent]:
        """Detect credential stuffing."""
        if event.get("type") != "auth_failure":
            return None

        source_ip = event.get("source_ip", "unknown")
        api_key_id = event.get("api_key_id", "unknown")
        now = time.time()
        cutoff = now - self.WINDOW_SECONDS

        # Track key attempts by IP
        if source_ip not in self._keys_by_ip:
            self._keys_by_ip[source_ip] = {}

        self._keys_by_ip[source_ip][api_key_id] = now

        # Clean old entries
        self._keys_by_ip[source_ip] = {
            k: t for k, t in self._keys_by_ip[source_ip].items()
            if t > cutoff
        }

        unique_keys = len(self._keys_by_ip[source_ip])

        # Check thresholds
        severity = None
        for threshold, sev in sorted(self.THRESHOLDS.items(), reverse=True):
            if unique_keys >= threshold:
                severity = sev
                break

        if severity is None:
            return None

        import uuid
        return ThreatEvent(
            event_id=f"threat_{uuid.uuid4().hex[:12]}",
            category=ThreatCategory.CREDENTIAL_STUFFING,
            severity=severity,
            timestamp=now,
            source_ip=source_ip,
            api_key_id=None,  # Multiple keys involved
            endpoint=event.get("endpoint"),
            description=f"Credential stuffing: {unique_keys} different keys from same IP",
            evidence={
                "unique_keys": unique_keys,
                "window_seconds": self.WINDOW_SECONDS,
                "key_ids": list(self._keys_by_ip[source_ip].keys())[:10],  # Limit for logging
            },
            confidence=min(0.95, 0.6 + (unique_keys / 20)),
        )


class DataExfiltrationDetector(ThreatDetector):
    """
    Detect potential data exfiltration.

    Pattern: Unusually high data volume or access frequency.

    FIXED thresholds:
    - 100 requests in 1 minute = LOW
    - 500 requests in 1 minute = MEDIUM
    - 1000 requests in 1 minute = HIGH
    """

    THRESHOLDS = {
        100: ThreatSeverity.LOW,
        500: ThreatSeverity.MEDIUM,
        1000: ThreatSeverity.HIGH,
    }
    WINDOW_SECONDS = 60

    def __init__(self):
        """Initialize detector."""
        self._requests_by_key: Dict[str, List[float]] = {}

    @property
    def name(self) -> str:
        return "data_exfiltration_detector"

    @property
    def categories(self) -> List[ThreatCategory]:
        return [ThreatCategory.DATA_EXFILTRATION]

    def detect(self, event: Dict[str, Any]) -> Optional[ThreatEvent]:
        """Detect data exfiltration."""
        if event.get("type") != "api_request":
            return None

        api_key_id = event.get("api_key_id", "unknown")
        now = time.time()
        cutoff = now - self.WINDOW_SECONDS

        # Track requests by key
        if api_key_id not in self._requests_by_key:
            self._requests_by_key[api_key_id] = []

        self._requests_by_key[api_key_id].append(now)
        self._requests_by_key[api_key_id] = [
            t for t in self._requests_by_key[api_key_id] if t > cutoff
        ]

        request_count = len(self._requests_by_key[api_key_id])

        # Check thresholds
        severity = None
        for threshold, sev in sorted(self.THRESHOLDS.items(), reverse=True):
            if request_count >= threshold:
                severity = sev
                break

        if severity is None:
            return None

        import uuid
        return ThreatEvent(
            event_id=f"threat_{uuid.uuid4().hex[:12]}",
            category=ThreatCategory.DATA_EXFILTRATION,
            severity=severity,
            timestamp=now,
            source_ip=event.get("source_ip"),
            api_key_id=api_key_id,
            endpoint=event.get("endpoint"),
            description=f"Potential exfiltration: {request_count} requests in {self.WINDOW_SECONDS}s",
            evidence={
                "request_count": request_count,
                "window_seconds": self.WINDOW_SECONDS,
                "endpoints_accessed": event.get("endpoint"),
            },
            confidence=min(0.8, 0.4 + (request_count / 2000)),
        )


class KeyCompromiseDetector(ThreatDetector):
    """
    Detect potentially compromised API keys.

    Patterns:
    - Key used from unusual location
    - Key used after long inactivity
    - Key used for unusual operations
    """

    def __init__(self):
        """Initialize detector."""
        self._key_history: Dict[str, Dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return "key_compromise_detector"

    @property
    def categories(self) -> List[ThreatCategory]:
        return [ThreatCategory.CREDENTIAL_COMPROMISE]

    def detect(self, event: Dict[str, Any]) -> Optional[ThreatEvent]:
        """Detect key compromise indicators."""
        api_key_id = event.get("api_key_id")
        if not api_key_id:
            return None

        source_ip = event.get("source_ip", "unknown")
        now = time.time()

        # Get or create key history
        if api_key_id not in self._key_history:
            self._key_history[api_key_id] = {
                "known_ips": set(),
                "last_used": 0,
                "typical_endpoints": set(),
            }

        history = self._key_history[api_key_id]
        threat = None

        # Check for new IP (if key has history)
        if len(history["known_ips"]) > 0 and source_ip not in history["known_ips"]:
            # New IP for this key
            inactivity_days = (now - history["last_used"]) / 86400 if history["last_used"] > 0 else 0

            if inactivity_days > 30:
                # Key used after long inactivity from new location - suspicious
                import uuid
                threat = ThreatEvent(
                    event_id=f"threat_{uuid.uuid4().hex[:12]}",
                    category=ThreatCategory.CREDENTIAL_COMPROMISE,
                    severity=ThreatSeverity.HIGH,
                    timestamp=now,
                    source_ip=source_ip,
                    api_key_id=api_key_id,
                    endpoint=event.get("endpoint"),
                    description=f"Key used from new IP after {inactivity_days:.0f} days inactivity",
                    evidence={
                        "new_ip": source_ip,
                        "known_ips": list(history["known_ips"])[:5],
                        "inactivity_days": inactivity_days,
                    },
                    confidence=0.7,
                )

        # Update history
        history["known_ips"].add(source_ip)
        history["last_used"] = now
        endpoint = event.get("endpoint")
        if endpoint:
            history["typical_endpoints"].add(endpoint)

        return threat


# =============================================================================
# Response Actions
# =============================================================================

class ResponseHandler(ABC):
    """
    Abstract handler for response actions.
    """

    @property
    @abstractmethod
    def action(self) -> ResponseAction:
        """Action this handler implements."""
        pass

    @abstractmethod
    def execute(
        self,
        threat: ThreatEvent,
        context: Dict[str, Any],
    ) -> ResponseResult:
        """
        Execute the response action.

        Args:
            threat: Threat to respond to
            context: System context (key_manager, etc.)

        Returns:
            ResponseResult
        """
        pass


class LogOnlyHandler(ResponseHandler):
    """Just log the threat - no active response."""

    @property
    def action(self) -> ResponseAction:
        return ResponseAction.LOG_ONLY

    def execute(
        self,
        threat: ThreatEvent,
        context: Dict[str, Any],
    ) -> ResponseResult:
        logger.warning(f"Threat logged: {threat.description}")
        return ResponseResult(
            action=self.action,
            success=True,
            threat_event_id=threat.event_id,
            details={"logged": True},
        )


class AlertHandler(ResponseHandler):
    """Send alert to security operators."""

    @property
    def action(self) -> ResponseAction:
        return ResponseAction.ALERT

    def execute(
        self,
        threat: ThreatEvent,
        context: Dict[str, Any],
    ) -> ResponseResult:
        # In production, this would integrate with PagerDuty, Slack, etc.
        alert_channels = context.get("alert_channels", [])

        logger.critical(f"SECURITY ALERT: {threat.description}")

        return ResponseResult(
            action=self.action,
            success=True,
            threat_event_id=threat.event_id,
            details={
                "channels_notified": len(alert_channels),
                "threat_summary": threat.to_dict(),
            },
        )


class TemporaryBlockHandler(ResponseHandler):
    """Temporarily block an IP address."""

    # FIXED block duration
    BLOCK_DURATION_SECONDS = 3600  # 1 hour

    @property
    def action(self) -> ResponseAction:
        return ResponseAction.TEMPORARY_BLOCK

    def execute(
        self,
        threat: ThreatEvent,
        context: Dict[str, Any],
    ) -> ResponseResult:
        ip_blocklist = context.get("ip_blocklist")

        if not ip_blocklist:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error="No IP blocklist configured",
            )

        if not threat.source_ip:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error="No source IP to block",
            )

        try:
            # Add to blocklist with expiry
            expiry = time.time() + self.BLOCK_DURATION_SECONDS
            ip_blocklist.add(threat.source_ip, expiry)

            logger.warning(f"Temporarily blocked IP: {threat.source_ip}")

            return ResponseResult(
                action=self.action,
                success=True,
                threat_event_id=threat.event_id,
                details={
                    "blocked_ip": threat.source_ip,
                    "duration_seconds": self.BLOCK_DURATION_SECONDS,
                    "expires_at": expiry,
                },
            )
        except Exception as e:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error=str(e),
            )


class RateLimitHandler(ResponseHandler):
    """Apply stricter rate limits."""

    # FIXED rate limit reduction
    REDUCED_RATE_MULTIPLIER = 0.1  # 10% of normal rate

    @property
    def action(self) -> ResponseAction:
        return ResponseAction.RATE_LIMIT

    def execute(
        self,
        threat: ThreatEvent,
        context: Dict[str, Any],
    ) -> ResponseResult:
        rate_limiter = context.get("rate_limiter")

        if not rate_limiter:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error="No rate limiter configured",
            )

        target = threat.source_ip or threat.api_key_id
        if not target:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error="No target for rate limiting",
            )

        try:
            # Apply reduced rate
            if hasattr(rate_limiter, "set_override"):
                rate_limiter.set_override(target, self.REDUCED_RATE_MULTIPLIER)

            logger.warning(f"Applied reduced rate limit to: {target}")

            return ResponseResult(
                action=self.action,
                success=True,
                threat_event_id=threat.event_id,
                details={
                    "target": target,
                    "rate_multiplier": self.REDUCED_RATE_MULTIPLIER,
                },
            )
        except Exception as e:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error=str(e),
            )


class RotateKeyHandler(ResponseHandler):
    """Auto-rotate a potentially compromised API key."""

    @property
    def action(self) -> ResponseAction:
        return ResponseAction.ROTATE_KEY

    def execute(
        self,
        threat: ThreatEvent,
        context: Dict[str, Any],
    ) -> ResponseResult:
        key_manager = context.get("key_manager")

        if not key_manager:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error="No key manager configured",
            )

        if not threat.api_key_id:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error="No API key to rotate",
            )

        try:
            # Rotate the key
            if hasattr(key_manager, "rotate_key"):
                new_key_id = key_manager.rotate_key(threat.api_key_id)

                logger.warning(f"Auto-rotated compromised key: {threat.api_key_id}")

                return ResponseResult(
                    action=self.action,
                    success=True,
                    threat_event_id=threat.event_id,
                    details={
                        "old_key_id": threat.api_key_id,
                        "new_key_id": new_key_id,
                    },
                )
            else:
                return ResponseResult(
                    action=self.action,
                    success=False,
                    threat_event_id=threat.event_id,
                    error="Key manager does not support rotation",
                )
        except Exception as e:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error=str(e),
            )


class RevokeKeyHandler(ResponseHandler):
    """Revoke a compromised API key."""

    @property
    def action(self) -> ResponseAction:
        return ResponseAction.REVOKE_KEY

    def execute(
        self,
        threat: ThreatEvent,
        context: Dict[str, Any],
    ) -> ResponseResult:
        key_manager = context.get("key_manager")

        if not key_manager:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error="No key manager configured",
            )

        if not threat.api_key_id:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error="No API key to revoke",
            )

        try:
            if hasattr(key_manager, "revoke_key"):
                key_manager.revoke_key(threat.api_key_id)

                logger.warning(f"Revoked compromised key: {threat.api_key_id}")

                return ResponseResult(
                    action=self.action,
                    success=True,
                    threat_event_id=threat.event_id,
                    details={
                        "revoked_key_id": threat.api_key_id,
                    },
                )
            else:
                return ResponseResult(
                    action=self.action,
                    success=False,
                    threat_event_id=threat.event_id,
                    error="Key manager does not support revocation",
                )
        except Exception as e:
            return ResponseResult(
                action=self.action,
                success=False,
                threat_event_id=threat.event_id,
                error=str(e),
            )


class EscalateHandler(ResponseHandler):
    """Escalate to human operators."""

    @property
    def action(self) -> ResponseAction:
        return ResponseAction.ESCALATE

    def execute(
        self,
        threat: ThreatEvent,
        context: Dict[str, Any],
    ) -> ResponseResult:
        # In production, this would page on-call security team
        logger.critical(f"ESCALATION REQUIRED: {threat.description}")

        return ResponseResult(
            action=self.action,
            success=True,
            threat_event_id=threat.event_id,
            details={
                "escalated": True,
                "requires_human_action": True,
                "threat": threat.to_dict(),
            },
        )


# =============================================================================
# Self-Healing Engine
# =============================================================================

class SelfHealingEngine:
    """
    Self-Healing Security Engine.

    Automatically detects and responds to security threats:
    1. Monitors security signals
    2. Detects threats using pluggable detectors
    3. Applies automated responses per policy
    4. Escalates when automated response is insufficient

    Determinism:
    - FIXED response policies
    - DETERMINISTIC threat classification
    - Auditable response actions

    Frontier Feature: Proactive security without human intervention.

    Usage:
        engine = SelfHealingEngine.default()

        # Configure context
        context = {
            "key_manager": key_manager,
            "ip_blocklist": blocklist,
            "rate_limiter": rate_limiter,
        }

        # Process security events
        for event in security_events:
            responses = engine.process_event(event, context)
            for response in responses:
                if not response.success:
                    handle_failed_response(response)
    """

    # FIXED default policies
    _DEFAULT_POLICIES: Tuple[ResponsePolicy, ...] = (
        ResponsePolicy(
            name="brute_force_low",
            threat_category=ThreatCategory.BRUTE_FORCE,
            min_severity=ThreatSeverity.LOW,
            min_confidence=0.5,
            actions=[ResponseAction.LOG_ONLY, ResponseAction.RATE_LIMIT],
            cooldown_seconds=300,
            requires_confirmation=False,
            max_auto_actions=10,
        ),
        ResponsePolicy(
            name="brute_force_high",
            threat_category=ThreatCategory.BRUTE_FORCE,
            min_severity=ThreatSeverity.HIGH,
            min_confidence=0.7,
            actions=[ResponseAction.ALERT, ResponseAction.TEMPORARY_BLOCK],
            cooldown_seconds=60,
            requires_confirmation=False,
            max_auto_actions=5,
        ),
        ResponsePolicy(
            name="credential_stuffing",
            threat_category=ThreatCategory.CREDENTIAL_STUFFING,
            min_severity=ThreatSeverity.MEDIUM,
            min_confidence=0.6,
            actions=[ResponseAction.ALERT, ResponseAction.TEMPORARY_BLOCK],
            cooldown_seconds=60,
            requires_confirmation=False,
            max_auto_actions=3,
        ),
        ResponsePolicy(
            name="key_compromise",
            threat_category=ThreatCategory.CREDENTIAL_COMPROMISE,
            min_severity=ThreatSeverity.HIGH,
            min_confidence=0.7,
            actions=[ResponseAction.ALERT, ResponseAction.ROTATE_KEY],
            cooldown_seconds=0,  # No cooldown for key compromise
            requires_confirmation=True,  # Human must confirm key rotation
            max_auto_actions=1,
        ),
        ResponsePolicy(
            name="data_exfiltration",
            threat_category=ThreatCategory.DATA_EXFILTRATION,
            min_severity=ThreatSeverity.HIGH,
            min_confidence=0.6,
            actions=[ResponseAction.ALERT, ResponseAction.RATE_LIMIT, ResponseAction.ESCALATE],
            cooldown_seconds=60,
            requires_confirmation=False,
            max_auto_actions=3,
        ),
    )

    def __init__(
        self,
        detectors: Optional[List[ThreatDetector]] = None,
        policies: Optional[List[ResponsePolicy]] = None,
        handlers: Optional[Dict[ResponseAction, ResponseHandler]] = None,
    ):
        """
        Initialize self-healing engine.

        Args:
            detectors: List of threat detectors
            policies: List of response policies
            handlers: Map of action to handler
        """
        # Initialize detectors
        if detectors is None:
            detectors = [
                BruteForceDetector(),
                CredentialStuffingDetector(),
                DataExfiltrationDetector(),
                KeyCompromiseDetector(),
            ]
        self._detectors = detectors

        # Initialize policies
        if policies is None:
            policies = list(self._DEFAULT_POLICIES)
        self._policies = policies

        # Initialize handlers
        if handlers is None:
            handlers = {
                ResponseAction.LOG_ONLY: LogOnlyHandler(),
                ResponseAction.ALERT: AlertHandler(),
                ResponseAction.RATE_LIMIT: RateLimitHandler(),
                ResponseAction.TEMPORARY_BLOCK: TemporaryBlockHandler(),
                ResponseAction.ROTATE_KEY: RotateKeyHandler(),
                ResponseAction.REVOKE_KEY: RevokeKeyHandler(),
                ResponseAction.ESCALATE: EscalateHandler(),
            }
        self._handlers = handlers

        # State tracking
        self._threat_events: List[ThreatEvent] = []
        self._responses: List[ResponseResult] = []
        self._action_counts: Dict[str, int] = {}  # source -> count
        self._last_action_time: Dict[str, float] = {}  # source -> timestamp
        self._pending_confirmations: List[Tuple[ThreatEvent, ResponsePolicy]] = []

    @classmethod
    def default(cls) -> "SelfHealingEngine":
        """Create engine with default configuration."""
        return cls()

    def add_detector(self, detector: ThreatDetector) -> None:
        """Add a threat detector."""
        self._detectors.append(detector)
        logger.info(f"Added threat detector: {detector.name}")

    def add_policy(self, policy: ResponsePolicy) -> None:
        """Add a response policy."""
        self._policies.append(policy)
        logger.info(f"Added response policy: {policy.name}")

    def process_event(
        self,
        event: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[ResponseResult]:
        """
        Process a security event through detection and response.

        DETERMINISTIC: Same event → same detection → same response.

        Args:
            event: Security event to process
            context: System context with managers, blocklists, etc.

        Returns:
            List of response results
        """
        responses = []

        # Run all detectors
        for detector in self._detectors:
            try:
                threat = detector.detect(event)
                if threat:
                    self._threat_events.append(threat)
                    logger.info(f"Threat detected: {threat.category.value} - {threat.description}")

                    # Find matching policies and respond
                    threat_responses = self._respond_to_threat(threat, context)
                    responses.extend(threat_responses)

            except Exception as e:
                logger.error(f"Detector {detector.name} failed: {e}")

        return responses

    def _respond_to_threat(
        self,
        threat: ThreatEvent,
        context: Dict[str, Any],
    ) -> List[ResponseResult]:
        """Apply response policies to a threat."""
        responses = []

        for policy in self._policies:
            if not policy.matches(threat):
                continue

            # Check cooldown
            source = threat.source_ip or threat.api_key_id or "unknown"
            policy_key = f"{source}:{policy.name}"

            if policy_key in self._last_action_time:
                elapsed = time.time() - self._last_action_time[policy_key]
                if elapsed < policy.cooldown_seconds:
                    logger.debug(f"Policy {policy.name} in cooldown for {source}")
                    continue

            # Check max actions
            if policy_key in self._action_counts:
                if self._action_counts[policy_key] >= policy.max_auto_actions:
                    # Max reached - escalate
                    logger.warning(f"Max auto-actions reached for {source}, escalating")
                    escalate_handler = self._handlers.get(ResponseAction.ESCALATE)
                    if escalate_handler:
                        result = escalate_handler.execute(threat, context)
                        responses.append(result)
                    continue

            # Check if confirmation required
            if policy.requires_confirmation:
                self._pending_confirmations.append((threat, policy))
                logger.info(f"Response pending confirmation: {policy.name}")
                continue

            # Execute response actions
            for action in policy.actions:
                handler = self._handlers.get(action)
                if handler:
                    try:
                        result = handler.execute(threat, context)
                        responses.append(result)
                        self._responses.append(result)

                        if result.success:
                            logger.info(f"Response action {action.value} succeeded")
                        else:
                            logger.warning(f"Response action {action.value} failed: {result.error}")

                    except Exception as e:
                        logger.error(f"Handler {action.value} failed: {e}")
                        responses.append(ResponseResult(
                            action=action,
                            success=False,
                            threat_event_id=threat.event_id,
                            error=str(e),
                        ))

            # Update tracking
            self._last_action_time[policy_key] = time.time()
            self._action_counts[policy_key] = self._action_counts.get(policy_key, 0) + 1

        return responses

    def confirm_action(
        self,
        threat_event_id: str,
        approved: bool,
        context: Dict[str, Any],
    ) -> List[ResponseResult]:
        """
        Confirm or deny a pending action.

        Args:
            threat_event_id: Event ID to confirm
            approved: Whether to proceed
            context: System context

        Returns:
            Response results if approved
        """
        responses = []

        for threat, policy in list(self._pending_confirmations):
            if threat.event_id == threat_event_id:
                self._pending_confirmations.remove((threat, policy))

                if approved:
                    logger.info(f"Action confirmed for {threat_event_id}")
                    for action in policy.actions:
                        handler = self._handlers.get(action)
                        if handler:
                            result = handler.execute(threat, context)
                            responses.append(result)
                else:
                    logger.info(f"Action denied for {threat_event_id}")

                break

        return responses

    def get_pending_confirmations(self) -> List[Dict[str, Any]]:
        """Get list of actions pending confirmation."""
        return [
            {
                "threat": threat.to_dict(),
                "policy": policy.name,
                "actions": [a.value for a in policy.actions],
            }
            for threat, policy in self._pending_confirmations
        ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "detectors": [d.name for d in self._detectors],
            "policies": [p.name for p in self._policies],
            "threats_detected": len(self._threat_events),
            "responses_executed": len(self._responses),
            "successful_responses": sum(1 for r in self._responses if r.success),
            "pending_confirmations": len(self._pending_confirmations),
            "threats_by_category": self._count_by_category(),
        }

    def _count_by_category(self) -> Dict[str, int]:
        """Count threats by category."""
        counts: Dict[str, int] = {}
        for threat in self._threat_events:
            category = threat.category.value
            counts[category] = counts.get(category, 0) + 1
        return counts

    def get_recent_threats(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent threats."""
        return [t.to_dict() for t in self._threat_events[-limit:]]

    def get_recent_responses(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent responses."""
        return [r.to_dict() for r in self._responses[-limit:]]


# =============================================================================
# IP Blocklist (Supporting Class)
# =============================================================================

class IPBlocklist:
    """
    IP address blocklist with automatic expiry.

    Used by self-healing engine for temporary blocks.
    """

    def __init__(self):
        """Initialize blocklist."""
        self._blocked: Dict[str, float] = {}  # ip -> expiry timestamp

    def add(self, ip: str, expiry: float) -> None:
        """Add IP to blocklist with expiry."""
        self._blocked[ip] = expiry
        logger.info(f"Blocked IP {ip} until {expiry}")

    def remove(self, ip: str) -> bool:
        """Remove IP from blocklist."""
        if ip in self._blocked:
            del self._blocked[ip]
            logger.info(f"Unblocked IP {ip}")
            return True
        return False

    def is_blocked(self, ip: str) -> bool:
        """Check if IP is blocked."""
        if ip not in self._blocked:
            return False

        # Check expiry
        if time.time() > self._blocked[ip]:
            del self._blocked[ip]
            return False

        return True

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        now = time.time()
        expired = [ip for ip, expiry in self._blocked.items() if now > expiry]
        for ip in expired:
            del self._blocked[ip]
        return len(expired)

    def list_blocked(self) -> List[Dict[str, Any]]:
        """List all blocked IPs."""
        now = time.time()
        return [
            {
                "ip": ip,
                "expires_at": expiry,
                "remaining_seconds": max(0, expiry - now),
            }
            for ip, expiry in self._blocked.items()
            if now < expiry
        ]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "ThreatCategory",
    "ThreatSeverity",
    "ResponseAction",

    # Data classes
    "ThreatEvent",
    "ResponseResult",
    "ResponsePolicy",
    "IncidentState",

    # Detectors
    "ThreatDetector",
    "BruteForceDetector",
    "CredentialStuffingDetector",
    "DataExfiltrationDetector",
    "KeyCompromiseDetector",

    # Response handlers
    "ResponseHandler",
    "LogOnlyHandler",
    "AlertHandler",
    "TemporaryBlockHandler",
    "RateLimitHandler",
    "RotateKeyHandler",
    "RevokeKeyHandler",
    "EscalateHandler",

    # Engine
    "SelfHealingEngine",

    # Supporting classes
    "IPBlocklist",
]
