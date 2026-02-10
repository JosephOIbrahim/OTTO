"""
OTTO Secure Services Layer
==========================

Provides secure, Deterministic service infrastructure:
- credentials: Secure credential management with OS keyring
- audit: Immutable audit log with hash chaining
- approval: Approval gate system for sensitive actions

Determinism:
- Fixed seeds for all operations
- Deterministic hashing (SHA-256)
- Sorted key iteration
- No runtime randomness in decision logic
"""

from .credentials import (
    CredentialManager,
    Credential,
    CredentialScope,
    CredentialError,
    CredentialNotFoundError,
    CredentialExpiredError,
    get_credential_manager,
)

from .audit import (
    AuditLog,
    AuditEntry,
    AuditAction,
    AuditSeverity,
    AuditVerificationError,
    get_audit_log,
    log_action,
)

from .approval import (
    ApprovalGate,
    ApprovalRequest,
    ApprovalDecision,
    ApprovalCategory,
    ApprovalPolicy,
    ApprovalError,
    ApprovalDeniedError,
    ApprovalTimeoutError,
    get_approval_gate,
    requires_approval,
)

__all__ = [
    # Credentials
    "CredentialManager",
    "Credential",
    "CredentialScope",
    "CredentialError",
    "CredentialNotFoundError",
    "CredentialExpiredError",
    "get_credential_manager",
    # Audit
    "AuditLog",
    "AuditEntry",
    "AuditAction",
    "AuditSeverity",
    "AuditVerificationError",
    "get_audit_log",
    "log_action",
    # Approval
    "ApprovalGate",
    "ApprovalRequest",
    "ApprovalDecision",
    "ApprovalCategory",
    "ApprovalPolicy",
    "ApprovalError",
    "ApprovalDeniedError",
    "ApprovalTimeoutError",
    "get_approval_gate",
    "requires_approval",
]
