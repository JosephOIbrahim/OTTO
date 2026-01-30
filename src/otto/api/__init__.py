"""
OTTO OS Public REST API
=======================

Versioned REST API for third-party integrations.

Architecture:
    /api/v1/*  →  REST Router  →  JSON-RPC Handler
                    │
              Middleware Chain:
              1. Security Headers (response wrapper)
              2. Authentication (API Key)
              3. Rate Limiting
              4. Scope Validation
              5. Sensitive Data Filter

Usage:
    from otto.api import APIKeyManager, APIScope, APIResponse

    # Create an API key
    manager = APIKeyManager()
    key, metadata = manager.create(
        name="My Integration",
        scopes={APIScope.READ_STATUS, APIScope.READ_STATE},
    )

    # Validate a key
    result = manager.validate(key)
    if result.valid:
        print(f"Key valid: {result.key.name}")

Version: v1.0.0
"""

__version__ = "2.0.0"  # Frontier Security Update
__api_version__ = "v1"
__frontier_version__ = "1.0.0"  # Frontier security features version

# Scopes
from .scopes import (
    APIScope,
    SENSITIVE_FIELDS,
    expand_scopes,
    has_scope,
    can_access_field,
    filter_state_by_scope,
    parse_scope,
    parse_scopes,
)

# API Keys
from .api_keys import (
    APIKey,
    APIKeyManager,
    APIKeyValidationResult,
    APIKeyError,
    APIKeyNotFoundError,
    APIKeyInvalidError,
    APIKeyExpiredError,
    APIKeyRevokedError,
    generate_api_key,
    hash_api_key,
    parse_api_key,
    validate_key_format,
    get_manager,
    reset_manager,
)

# Response
from .response import (
    API_VERSION,
    APIResponse,
    APIResponseMeta,
    APIError,
    success,
    error,
    not_found,
    unauthorized,
    forbidden,
    rate_limited,
    invalid_params,
    internal_error,
)

# Errors
from .errors import (
    APIErrorCode,
    APIException,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    MethodNotAllowedError,
    RateLimitedError,
    InternalServerError,
    jsonrpc_error_to_api,
    api_code_to_http_status,
)

# Middleware
from .middleware import (
    APIRequestContext,
    Middleware,
    MiddlewareChain,
    SecurityHeadersMiddleware,
    CORSMiddleware,
    ReplayProtectionMiddleware,
    AuthenticationMiddleware,
    RateLimitMiddleware,
    ScopeValidationMiddleware,
    InputValidationMiddleware,
    SensitiveDataFilterMiddleware,
    EndpointRateLimit,
    EndpointScope,
    create_api_middleware,
)

# Schemas
from .schemas import (
    STATE_UPDATE_SCHEMA,
    AGENT_SPAWN_SCHEMA,
    AGENT_ABORT_SCHEMA,
    SESSION_START_SCHEMA,
    SESSION_END_SCHEMA,
    PROTECTION_CHECK_SCHEMA,
    INTEGRATION_SYNC_SCHEMA,
    ENDPOINT_SCHEMAS,
    get_schema_for_endpoint,
)

# REST Router
from .rest_router import (
    Route,
    ROUTES,
    RESTRouter,
    create_rest_router,
)

# OpenAPI
from .openapi import generate_openapi_spec

# Audit Logging
from .audit import (
    AuditEvent,
    AuditRecord,
    AuditLogger,
    get_audit_logger,
    reset_audit_logger,
)

# TLS Configuration
from .tls import (
    TLSConfig,
    HSTSConfig,
    CertificateInfo,
    TLSConfigError,
    get_certificate_info,
    generate_self_signed_cert,
    create_development_tls,
    create_production_tls,
    CertificateExpiryLevel,
    CertificateHealthStatus,
    CertificateMonitor,
    ACMEProvider,
    ACMEConfig,
)

# Rate Limit Backends
from .rate_limit_backend import (
    RateLimitState,
    RateLimitBackend,
    InMemoryRateLimitBackend,
    RedisRateLimitBackend,
    create_rate_limit_backend,
)

# Security Framework
from .security import (
    AlgorithmCategory,
    AlgorithmStatus,
    AlgorithmSpec,
    AlgorithmRegistry,
    InvariantSeverity,
    InvariantResult,
    SecurityInvariant,
    TLSVersionInvariant,
    CipherSuiteInvariant,
    APIKeyHashInvariant,
    RateLimitInvariant,
    SecurityHeadersInvariant,
    InvariantVerifier,
    CTLogOperator,
    CTLogInfo,
    CTMonitor,
    AnomalyType,
    AnomalySeverity,
    AnomalyEvent,
    AnomalyDetector,
    RateSpikeDetector,
    AuthFailureDetector,
    AnomalyDetectionEngine,
)

# =============================================================================
# FRONTIER SECURITY FEATURES (v2.0.0)
# =============================================================================

# Post-Quantum Cryptography + HSM
from .frontier_crypto import (
    # Enums
    NISTSecurityLevel,
    HybridMode,
    # Key Exchange
    KeyExchangeResult,
    KeyPair,
    HybridKeyExchange,
    # Signatures
    HybridSignature,
    HybridSigner,
    # HSM
    HSMSlotInfo,
    HSMKeyHandle,
    HSMInterface,
    PKCS11HSM,
    SoftwareHSM,
    # Utilities
    create_hybrid_key_exchange,
    create_hsm,
    get_pq_capabilities,
    # Availability flags
    HAS_CRYPTOGRAPHY,
    HAS_LIBOQS,
    HAS_PKCS11,
)

# Security Posture
from .security_posture import (
    # Enums
    PostureStatus,
    ComponentHealth,
    RecommendationPriority,
    # Data classes
    ComponentAssessment,
    SecurityRecommendation,
    PostureReport,
    # Assessors
    ComponentAssessor,
    CryptographyAssessor,
    AuthenticationAssessor,
    NetworkAssessor,
    AnomalyDetectionAssessor,
    AuditAssessor,
    # Engine
    RecommendationGenerator,
    SecurityPostureEngine,
    # API
    SecurityPostureAPI,
)

# Threshold Signatures
from .threshold_signatures import (
    # Data classes
    Share,
    ThresholdKeyPair,
    PartialSignature,
    CombinedSignature,
    # Secret sharing
    ShamirSecretSharing,
    # Threshold signatures
    ThresholdSignatureScheme,
    # API key management
    ThresholdAPIKeyManager,
    # Key ceremony
    KeyCeremonyState,
    KeyCeremony,
    KeyCeremonyManager,
)

# Self-Healing Security
from .self_healing import (
    # Enums
    ThreatCategory,
    ThreatSeverity,
    ResponseAction,
    # Data classes
    ThreatEvent,
    ResponseResult,
    ResponsePolicy,
    IncidentState,
    # Detectors
    ThreatDetector,
    BruteForceDetector,
    CredentialStuffingDetector,
    DataExfiltrationDetector,
    KeyCompromiseDetector,
    # Response handlers
    ResponseHandler,
    LogOnlyHandler,
    AlertHandler,
    TemporaryBlockHandler,
    RateLimitHandler,
    RotateKeyHandler,
    RevokeKeyHandler,
    EscalateHandler,
    # Engine
    SelfHealingEngine,
    # Supporting classes
    IPBlocklist,
)

# Merkle Audit Trail
from .merkle_audit import (
    # Hash functions
    hash_leaf,
    hash_node,
    # Data classes
    AuditEntry,
    InclusionProof,
    ConsistencyProof,
    SignedTreeHead,
    # Merkle tree
    MerkleTree,
    # Audit logger
    MerkleAuditLog,
    AuditEventType,
    # API
    AuditLogAPI,
    # Convenience
    create_audit_log,
)


__all__ = [
    # Version
    "__version__",
    "__api_version__",
    "API_VERSION",

    # Scopes
    "APIScope",
    "SENSITIVE_FIELDS",
    "expand_scopes",
    "has_scope",
    "can_access_field",
    "filter_state_by_scope",
    "parse_scope",
    "parse_scopes",

    # API Keys
    "APIKey",
    "APIKeyManager",
    "APIKeyValidationResult",
    "APIKeyError",
    "APIKeyNotFoundError",
    "APIKeyInvalidError",
    "APIKeyExpiredError",
    "APIKeyRevokedError",
    "generate_api_key",
    "hash_api_key",
    "parse_api_key",
    "validate_key_format",
    "get_manager",
    "reset_manager",

    # Response
    "APIResponse",
    "APIResponseMeta",
    "APIError",
    "success",
    "error",
    "not_found",
    "unauthorized",
    "forbidden",
    "rate_limited",
    "invalid_params",
    "internal_error",

    # Errors
    "APIErrorCode",
    "APIException",
    "BadRequestError",
    "UnauthorizedError",
    "ForbiddenError",
    "NotFoundError",
    "MethodNotAllowedError",
    "RateLimitedError",
    "InternalServerError",
    "jsonrpc_error_to_api",
    "api_code_to_http_status",

    # Middleware
    "APIRequestContext",
    "Middleware",
    "MiddlewareChain",
    "SecurityHeadersMiddleware",
    "CORSMiddleware",
    "ReplayProtectionMiddleware",
    "AuthenticationMiddleware",
    "RateLimitMiddleware",
    "ScopeValidationMiddleware",
    "InputValidationMiddleware",
    "SensitiveDataFilterMiddleware",
    "EndpointRateLimit",
    "EndpointScope",
    "create_api_middleware",

    # Schemas
    "STATE_UPDATE_SCHEMA",
    "AGENT_SPAWN_SCHEMA",
    "AGENT_ABORT_SCHEMA",
    "SESSION_START_SCHEMA",
    "SESSION_END_SCHEMA",
    "PROTECTION_CHECK_SCHEMA",
    "INTEGRATION_SYNC_SCHEMA",
    "ENDPOINT_SCHEMAS",
    "get_schema_for_endpoint",

    # REST Router
    "Route",
    "ROUTES",
    "RESTRouter",
    "create_rest_router",

    # OpenAPI
    "generate_openapi_spec",

    # Audit Logging
    "AuditEvent",
    "AuditRecord",
    "AuditLogger",
    "get_audit_logger",
    "reset_audit_logger",

    # TLS Configuration
    "TLSConfig",
    "HSTSConfig",
    "CertificateInfo",
    "TLSConfigError",
    "get_certificate_info",
    "generate_self_signed_cert",
    "create_development_tls",
    "create_production_tls",
    "CertificateExpiryLevel",
    "CertificateHealthStatus",
    "CertificateMonitor",
    "ACMEProvider",
    "ACMEConfig",

    # Rate Limit Backends
    "RateLimitState",
    "RateLimitBackend",
    "InMemoryRateLimitBackend",
    "RedisRateLimitBackend",
    "create_rate_limit_backend",

    # Security Framework
    "AlgorithmCategory",
    "AlgorithmStatus",
    "AlgorithmSpec",
    "AlgorithmRegistry",
    "InvariantSeverity",
    "InvariantResult",
    "SecurityInvariant",
    "TLSVersionInvariant",
    "CipherSuiteInvariant",
    "APIKeyHashInvariant",
    "RateLimitInvariant",
    "SecurityHeadersInvariant",
    "InvariantVerifier",
    "CTLogOperator",
    "CTLogInfo",
    "CTMonitor",
    "AnomalyType",
    "AnomalySeverity",
    "AnomalyEvent",
    "AnomalyDetector",
    "RateSpikeDetector",
    "AuthFailureDetector",
    "AnomalyDetectionEngine",

    # =========================================================================
    # FRONTIER SECURITY FEATURES (v2.0.0)
    # =========================================================================

    # Frontier version
    "__frontier_version__",

    # Post-Quantum Cryptography + HSM
    "NISTSecurityLevel",
    "HybridMode",
    "KeyExchangeResult",
    "KeyPair",
    "HybridKeyExchange",
    "HybridSignature",
    "HybridSigner",
    "HSMSlotInfo",
    "HSMKeyHandle",
    "HSMInterface",
    "PKCS11HSM",
    "SoftwareHSM",
    "create_hybrid_key_exchange",
    "create_hsm",
    "get_pq_capabilities",
    "HAS_CRYPTOGRAPHY",
    "HAS_LIBOQS",
    "HAS_PKCS11",

    # Security Posture
    "PostureStatus",
    "ComponentHealth",
    "RecommendationPriority",
    "ComponentAssessment",
    "SecurityRecommendation",
    "PostureReport",
    "ComponentAssessor",
    "CryptographyAssessor",
    "AuthenticationAssessor",
    "NetworkAssessor",
    "AnomalyDetectionAssessor",
    "AuditAssessor",
    "RecommendationGenerator",
    "SecurityPostureEngine",
    "SecurityPostureAPI",

    # Threshold Signatures
    "Share",
    "ThresholdKeyPair",
    "PartialSignature",
    "CombinedSignature",
    "ShamirSecretSharing",
    "ThresholdSignatureScheme",
    "ThresholdAPIKeyManager",
    "KeyCeremonyState",
    "KeyCeremony",
    "KeyCeremonyManager",

    # Self-Healing Security
    "ThreatCategory",
    "ThreatSeverity",
    "ResponseAction",
    "ThreatEvent",
    "ResponseResult",
    "ResponsePolicy",
    "IncidentState",
    "ThreatDetector",
    "BruteForceDetector",
    "CredentialStuffingDetector",
    "DataExfiltrationDetector",
    "KeyCompromiseDetector",
    "ResponseHandler",
    "LogOnlyHandler",
    "AlertHandler",
    "TemporaryBlockHandler",
    "RateLimitHandler",
    "RotateKeyHandler",
    "RevokeKeyHandler",
    "EscalateHandler",
    "SelfHealingEngine",
    "IPBlocklist",

    # Merkle Audit Trail
    "hash_leaf",
    "hash_node",
    "AuditEntry",
    "InclusionProof",
    "ConsistencyProof",
    "SignedTreeHead",
    "MerkleTree",
    "MerkleAuditLog",
    "AuditEventType",
    "AuditLogAPI",
    "create_audit_log",
]
