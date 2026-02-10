"""
OTTO OS Security Module
=======================

Comprehensive security systems for OTTO OS.

Components:
- Security Posture API: Real-time security scoring
- Merkle Audit Log: Tamper-evident event logging
- Self-Healing Security: Automatic issue detection and remediation
- HSM Interface: Hardware Security Module support

Determinism:
- FIXED security algorithms and thresholds
- Deterministic assessments (same state → same score)
- Bounded operations across all components

Usage:
    from otto.security import (
        # Posture assessment
        assess_posture, get_posture_summary,

        # Audit logging
        log_event, EventType, verify_log_integrity,

        # Self-healing
        scan_and_heal, get_security_status,

        # HSM
        HSMInterface, get_hsm,
    )

    # Check security posture
    posture = assess_posture()
    print(f"Grade: {posture.grade}, Score: {posture.score}")

    # Log security event
    log_event(EventType.AUTH_SUCCESS, "user@example.com", "User logged in")

    # Run security scan
    result = scan_and_heal()
"""

from .posture import (
    # Core types
    SecurityPosture,
    ComponentScore,
    SecurityIssue as PostureIssue,
    Severity as PostureSeverity,
    ComponentStatus,
    # Assessment
    SecurityAssessor,
    SecurityCheck,
    assess_posture,
    register_check,
    get_assessor,
    # API helpers
    get_posture_summary,
    get_posture_details,
)

from .audit import (
    # Core types
    AuditLog,
    AuditEvent,
    AuditCheckpoint,
    MerkleTree,
    MerkleProof,
    EventType,
    Severity as AuditSeverity,
    # Functions
    get_audit_log,
    log_event,
    verify_log_integrity,
    get_audit_summary,
    get_recent_events,
)

from .healing import (
    # Core types
    SecurityHealer,
    SecurityIssue as HealingIssue,
    IssueType,
    IssueSeverity,
    RemediationAction,
    RemediationResult,
    RemediationStatus,
    RemediationRule,
    # Detectors
    SecurityDetector,
    AuthenticationDetector,
    KeyManagementDetector,
    RateLimitDetector,
    AuditLogDetector,
    PQCryptoDetector,
    # Remediator
    Remediator,
    # Functions
    get_healer,
    scan_and_heal,
    get_security_status,
)

from .hsm import (
    # Core types
    HSMInterface,
    HSMConfig,
    HSMKeyInfo,
    HSMKeyType,
    HSMSlotInfo,
    HSMException,
    # Implementations
    MockHSM,
    PKCS11HSM,
    # Functions
    get_hsm,
    create_hsm,
    is_hsm_available,
)

from .keyring_provider import (
    # Core types
    KeyringProvider,
    KeyringBackend,
    Credential,
    # Implementations
    SystemKeyringProvider,
    MemoryKeyringProvider,
    NoOpKeyringProvider,
    # Manager
    KeyringManager,
    get_keyring,
    set_keyring,
    reset_keyring,
)

__all__ = [
    # Posture
    "SecurityPosture",
    "ComponentScore",
    "PostureIssue",
    "PostureSeverity",
    "ComponentStatus",
    "SecurityAssessor",
    "SecurityCheck",
    "assess_posture",
    "register_check",
    "get_assessor",
    "get_posture_summary",
    "get_posture_details",
    # Audit
    "AuditLog",
    "AuditEvent",
    "AuditCheckpoint",
    "MerkleTree",
    "MerkleProof",
    "EventType",
    "AuditSeverity",
    "get_audit_log",
    "log_event",
    "verify_log_integrity",
    "get_audit_summary",
    "get_recent_events",
    # Healing
    "SecurityHealer",
    "HealingIssue",
    "IssueType",
    "IssueSeverity",
    "RemediationAction",
    "RemediationResult",
    "RemediationStatus",
    "RemediationRule",
    "SecurityDetector",
    "AuthenticationDetector",
    "KeyManagementDetector",
    "RateLimitDetector",
    "AuditLogDetector",
    "PQCryptoDetector",
    "Remediator",
    "get_healer",
    "scan_and_heal",
    "get_security_status",
    # HSM
    "HSMInterface",
    "HSMConfig",
    "HSMKeyInfo",
    "HSMKeyType",
    "HSMSlotInfo",
    "HSMException",
    "MockHSM",
    "PKCS11HSM",
    "get_hsm",
    "create_hsm",
    "is_hsm_available",
    # Keyring
    "KeyringProvider",
    "KeyringBackend",
    "Credential",
    "SystemKeyringProvider",
    "MemoryKeyringProvider",
    "NoOpKeyringProvider",
    "KeyringManager",
    "get_keyring",
    "set_keyring",
    "reset_keyring",
]
