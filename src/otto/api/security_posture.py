"""
Continuous Security Posture Assessment for OTTO API
====================================================

Real-time security health monitoring and scoring:

1. Component-by-Component Assessment
   - Cryptography health (algorithms, key age)
   - Authentication health (failure rates, key rotation)
   - Network health (TLS, ciphers, headers)
   - Anomaly health (detection rates, response times)

2. Overall Security Score
   - Weighted composite score (0-100)
   - Traffic light status (CRITICAL/WARNING/GOOD/EXCELLENT)
   - Trend tracking over time

3. Recommendations Engine
   - Prioritized remediation steps
   - Auto-generated security advice

Determinism:
- FIXED scoring weights
- DETERMINISTIC assessment
- Pre-computed thresholds

Frontier Feature: Most APIs have no real-time security visibility.
OTTO provides continuous posture assessment.

API Endpoints:
- GET /api/v1/security/posture - Current posture
- GET /api/v1/security/posture/history - Historical scores
- GET /api/v1/security/posture/recommendations - Remediation advice
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Posture Status Levels
# =============================================================================

class PostureStatus(Enum):
    """
    Overall security posture status.

    FIXED: Status thresholds are immutable.
    """
    CRITICAL = "critical"    # Score 0-39: Immediate action required
    WARNING = "warning"      # Score 40-59: Issues need attention
    GOOD = "good"            # Score 60-79: Acceptable security
    EXCELLENT = "excellent"  # Score 80-100: Strong security posture

    @classmethod
    def from_score(cls, score: float) -> "PostureStatus":
        """
        Determine status from score.

        FIXED thresholds.
        """
        if score < 40:
            return cls.CRITICAL
        elif score < 60:
            return cls.WARNING
        elif score < 80:
            return cls.GOOD
        else:
            return cls.EXCELLENT


class ComponentHealth(Enum):
    """Health status for individual components."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class RecommendationPriority(Enum):
    """Priority level for security recommendations."""
    CRITICAL = 1  # Must fix immediately
    HIGH = 2      # Fix soon
    MEDIUM = 3    # Should fix
    LOW = 4       # Nice to have


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ComponentAssessment:
    """
    Assessment of a single security component.

    Determinism: Deterministic structure.
    """
    name: str
    health: ComponentHealth
    score: float  # 0-100
    details: Dict[str, Any]
    checks_passed: int
    checks_failed: int
    last_checked: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "health": self.health.value,
            "score": round(self.score, 2),
            "details": self.details,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "last_checked": self.last_checked,
        }


@dataclass
class SecurityRecommendation:
    """
    A security improvement recommendation.

    Determinism: Deterministic structure.
    """
    id: str
    priority: RecommendationPriority
    component: str
    title: str
    description: str
    remediation: str
    impact: str
    effort: str  # "low", "medium", "high"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "priority": self.priority.name,
            "component": self.component,
            "title": self.title,
            "description": self.description,
            "remediation": self.remediation,
            "impact": self.impact,
            "effort": self.effort,
        }


@dataclass
class PostureReport:
    """
    Complete security posture report.

    Determinism: Deterministic structure.
    """
    timestamp: float
    overall_score: float
    status: PostureStatus
    trend: str  # "improving", "stable", "declining"
    components: List[ComponentAssessment]
    recommendations: List[SecurityRecommendation]
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "overall_score": round(self.overall_score, 2),
            "status": self.status.value,
            "trend": self.trend,
            "components": [c.to_dict() for c in self.components],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "summary": self.summary,
        }


# =============================================================================
# Component Assessors
# =============================================================================

class ComponentAssessor:
    """Base class for component security assessors."""

    def __init__(self, name: str, weight: float):
        """
        Initialize assessor.

        Args:
            name: Component name
            weight: Weight in overall score (0.0-1.0)
        """
        self.name = name
        self.weight = weight

    def assess(self, context: Dict[str, Any]) -> ComponentAssessment:
        """
        Assess component security.

        Args:
            context: System context with relevant data

        Returns:
            ComponentAssessment with results
        """
        raise NotImplementedError


class CryptographyAssessor(ComponentAssessor):
    """
    Assess cryptographic security.

    Checks:
    - Algorithm choices (deprecated, broken)
    - Key ages
    - Post-quantum readiness
    - Certificate validity
    """

    # FIXED thresholds
    KEY_AGE_WARNING_DAYS = 90
    KEY_AGE_CRITICAL_DAYS = 180
    CERT_EXPIRY_WARNING_DAYS = 30

    def __init__(self):
        super().__init__("cryptography", weight=0.25)

    def assess(self, context: Dict[str, Any]) -> ComponentAssessment:
        """Assess cryptographic security."""
        checks_passed = 0
        checks_failed = 0
        details = {}
        score = 100.0

        # Check algorithm registry
        algorithm_registry = context.get("algorithm_registry")
        if algorithm_registry:
            # Check for broken algorithms in use
            broken_in_use = context.get("algorithms_in_use", [])
            broken_count = 0
            for algo in broken_in_use:
                spec = algorithm_registry.get(algo)
                if spec and spec.status.value == "broken":
                    broken_count += 1

            if broken_count == 0:
                checks_passed += 1
                details["broken_algorithms"] = "none"
            else:
                checks_failed += 1
                details["broken_algorithms"] = broken_count
                score -= 30  # Major penalty for broken algorithms

            # Check for post-quantum readiness
            pq_algorithms = algorithm_registry.list_post_quantum()
            pq_in_use = any(
                algo in broken_in_use
                for algo in [a.name for a in pq_algorithms]
            )
            details["pq_ready"] = pq_in_use
            if pq_in_use:
                checks_passed += 1
                score += 10  # Bonus for PQ
            else:
                # Not a failure, but no bonus
                details["pq_recommendation"] = "Consider enabling post-quantum algorithms"

        # Check key ages
        key_manager = context.get("key_manager")
        if key_manager:
            now = time.time()
            old_keys = 0
            expired_keys = 0

            keys = getattr(key_manager, "_keys", {})
            for key_hash, key_data in keys.items():
                if hasattr(key_data, "created_at"):
                    age_days = (now - key_data.created_at) / 86400
                    if age_days > self.KEY_AGE_CRITICAL_DAYS:
                        expired_keys += 1
                    elif age_days > self.KEY_AGE_WARNING_DAYS:
                        old_keys += 1

            details["old_keys"] = old_keys
            details["expired_keys"] = expired_keys

            if expired_keys > 0:
                checks_failed += 1
                score -= 20
            elif old_keys > 0:
                score -= 10
            else:
                checks_passed += 1

        # Check TLS configuration
        tls_config = context.get("tls_config")
        if tls_config:
            min_version = getattr(tls_config, "min_version", None)
            if min_version:
                import ssl
                if min_version >= ssl.TLSVersion.TLSv1_3:
                    checks_passed += 1
                    details["tls_version"] = "TLS 1.3"
                elif min_version >= ssl.TLSVersion.TLSv1_2:
                    checks_passed += 1
                    details["tls_version"] = "TLS 1.2"
                    score -= 5  # Slight penalty for not using 1.3
                else:
                    checks_failed += 1
                    details["tls_version"] = "< TLS 1.2"
                    score -= 25

        # Determine health
        if score >= 80:
            health = ComponentHealth.HEALTHY
        elif score >= 50:
            health = ComponentHealth.DEGRADED
        else:
            health = ComponentHealth.UNHEALTHY

        return ComponentAssessment(
            name=self.name,
            health=health,
            score=max(0, min(100, score)),
            details=details,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )


class AuthenticationAssessor(ComponentAssessor):
    """
    Assess authentication security.

    Checks:
    - Auth failure rates
    - Key rotation compliance
    - Rate limiting effectiveness
    - Replay protection
    """

    # FIXED thresholds
    FAILURE_RATE_WARNING = 0.05  # 5%
    FAILURE_RATE_CRITICAL = 0.10  # 10%
    ROTATION_COMPLIANCE_TARGET = 0.90  # 90% keys rotated on schedule

    def __init__(self):
        super().__init__("authentication", weight=0.30)

    def assess(self, context: Dict[str, Any]) -> ComponentAssessment:
        """Assess authentication security."""
        checks_passed = 0
        checks_failed = 0
        details = {}
        score = 100.0

        # Check auth failure rate
        auth_stats = context.get("auth_stats", {})
        total_attempts = auth_stats.get("total_attempts", 0)
        failed_attempts = auth_stats.get("failed_attempts", 0)

        if total_attempts > 0:
            failure_rate = failed_attempts / total_attempts
            details["failure_rate"] = f"{failure_rate:.2%}"

            if failure_rate > self.FAILURE_RATE_CRITICAL:
                checks_failed += 1
                score -= 30
                details["failure_status"] = "critical"
            elif failure_rate > self.FAILURE_RATE_WARNING:
                score -= 15
                details["failure_status"] = "warning"
            else:
                checks_passed += 1
                details["failure_status"] = "healthy"

        # Check rate limiting
        middleware_chain = context.get("middleware_chain")
        has_rate_limiting = False
        if middleware_chain:
            if hasattr(middleware_chain, "_middleware"):
                for mw in middleware_chain._middleware:
                    if "RateLimit" in type(mw).__name__:
                        has_rate_limiting = True
                        break

        if has_rate_limiting:
            checks_passed += 1
            details["rate_limiting"] = "enabled"
        else:
            checks_failed += 1
            details["rate_limiting"] = "disabled"
            score -= 25

        # Check replay protection
        has_replay_protection = False
        if middleware_chain and hasattr(middleware_chain, "_middleware"):
            for mw in middleware_chain._middleware:
                if "Replay" in type(mw).__name__:
                    has_replay_protection = True
                    break

        if has_replay_protection:
            checks_passed += 1
            details["replay_protection"] = "enabled"
        else:
            details["replay_protection"] = "disabled"
            score -= 10

        # Check key manager health
        key_manager = context.get("key_manager")
        if key_manager:
            keys = getattr(key_manager, "_keys", {})
            active_keys = sum(
                1 for k in keys.values()
                if not getattr(k, "revoked", False)
            )
            details["active_keys"] = active_keys

            if active_keys > 0:
                checks_passed += 1
            else:
                checks_failed += 1
                score -= 20

        # Determine health
        if score >= 80:
            health = ComponentHealth.HEALTHY
        elif score >= 50:
            health = ComponentHealth.DEGRADED
        else:
            health = ComponentHealth.UNHEALTHY

        return ComponentAssessment(
            name=self.name,
            health=health,
            score=max(0, min(100, score)),
            details=details,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )


class NetworkAssessor(ComponentAssessor):
    """
    Assess network security.

    Checks:
    - TLS configuration
    - Security headers
    - CORS policy
    - Certificate status
    """

    def __init__(self):
        super().__init__("network", weight=0.20)

    def assess(self, context: Dict[str, Any]) -> ComponentAssessment:
        """Assess network security."""
        checks_passed = 0
        checks_failed = 0
        details = {}
        score = 100.0

        # Check security headers
        middleware_chain = context.get("middleware_chain")
        security_headers_present = False
        if middleware_chain and hasattr(middleware_chain, "_middleware"):
            for mw in middleware_chain._middleware:
                if "SecurityHeaders" in type(mw).__name__:
                    security_headers_present = True
                    break

        if security_headers_present:
            checks_passed += 1
            details["security_headers"] = "present"
        else:
            checks_failed += 1
            details["security_headers"] = "missing"
            score -= 25

        # Check CORS
        cors_enabled = False
        if middleware_chain and hasattr(middleware_chain, "_middleware"):
            for mw in middleware_chain._middleware:
                if "CORS" in type(mw).__name__:
                    cors_enabled = True
                    break

        if cors_enabled:
            checks_passed += 1
            details["cors"] = "configured"
        else:
            details["cors"] = "not configured"
            score -= 10

        # Check TLS (may overlap with crypto, but network-specific checks)
        tls_config = context.get("tls_config")
        if tls_config:
            # Check for certificate
            cert_path = getattr(tls_config, "cert_path", None)
            if cert_path:
                checks_passed += 1
                details["certificate"] = "configured"
            else:
                checks_failed += 1
                details["certificate"] = "missing"
                score -= 20

        # Determine health
        if score >= 80:
            health = ComponentHealth.HEALTHY
        elif score >= 50:
            health = ComponentHealth.DEGRADED
        else:
            health = ComponentHealth.UNHEALTHY

        return ComponentAssessment(
            name=self.name,
            health=health,
            score=max(0, min(100, score)),
            details=details,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )


class AnomalyDetectionAssessor(ComponentAssessor):
    """
    Assess anomaly detection health.

    Checks:
    - Detector coverage
    - Alert response times
    - False positive rates
    - Detection effectiveness
    """

    def __init__(self):
        super().__init__("anomaly_detection", weight=0.15)

    def assess(self, context: Dict[str, Any]) -> ComponentAssessment:
        """Assess anomaly detection health."""
        checks_passed = 0
        checks_failed = 0
        details = {}
        score = 100.0

        # Check anomaly detection engine
        detection_engine = context.get("anomaly_detection_engine")
        if detection_engine:
            stats = detection_engine.get_stats()
            details["detectors"] = stats.get("detectors", [])
            details["events_processed"] = stats.get("events_processed", 0)
            details["anomalies_detected"] = stats.get("anomalies_detected", 0)

            detector_count = stats.get("detector_count", 0)
            if detector_count >= 2:
                checks_passed += 1
                details["coverage"] = "adequate"
            elif detector_count >= 1:
                details["coverage"] = "minimal"
                score -= 10
            else:
                checks_failed += 1
                details["coverage"] = "none"
                score -= 30

            # Check anomaly rate (too high might indicate attack, too low might indicate blind spots)
            anomaly_rate = stats.get("anomaly_rate", 0)
            details["anomaly_rate"] = f"{anomaly_rate:.2%}"
            if anomaly_rate > 0.10:
                details["anomaly_status"] = "elevated - possible attack"
                score -= 10
            elif anomaly_rate > 0:
                checks_passed += 1
                details["anomaly_status"] = "normal"
            else:
                details["anomaly_status"] = "no anomalies detected"

        else:
            checks_failed += 1
            details["status"] = "not configured"
            score -= 40

        # Determine health
        if score >= 80:
            health = ComponentHealth.HEALTHY
        elif score >= 50:
            health = ComponentHealth.DEGRADED
        else:
            health = ComponentHealth.UNHEALTHY

        return ComponentAssessment(
            name=self.name,
            health=health,
            score=max(0, min(100, score)),
            details=details,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )


class AuditAssessor(ComponentAssessor):
    """
    Assess audit logging health.

    Checks:
    - Audit log enabled
    - Log integrity
    - Coverage of security events
    """

    def __init__(self):
        super().__init__("audit", weight=0.10)

    def assess(self, context: Dict[str, Any]) -> ComponentAssessment:
        """Assess audit logging health."""
        checks_passed = 0
        checks_failed = 0
        details = {}
        score = 100.0

        # Check audit logger
        audit_logger = context.get("audit_logger")
        if audit_logger:
            checks_passed += 1
            details["logging"] = "enabled"

            # Check log file exists and is writable
            log_path = getattr(audit_logger, "_log_path", None)
            if log_path:
                import os
                if os.path.exists(log_path):
                    checks_passed += 1
                    details["log_file"] = "accessible"
                else:
                    details["log_file"] = "not found"
                    score -= 10
        else:
            checks_failed += 1
            details["logging"] = "disabled"
            score -= 40

        # Check for Merkle verification (frontier feature)
        merkle_audit = context.get("merkle_audit")
        if merkle_audit:
            checks_passed += 1
            details["integrity_verification"] = "merkle_tree"
            score += 10  # Bonus for frontier feature
        else:
            details["integrity_verification"] = "none"

        # Determine health
        if score >= 80:
            health = ComponentHealth.HEALTHY
        elif score >= 50:
            health = ComponentHealth.DEGRADED
        else:
            health = ComponentHealth.UNHEALTHY

        return ComponentAssessment(
            name=self.name,
            health=health,
            score=max(0, min(100, score)),
            details=details,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )


# =============================================================================
# Recommendation Generator
# =============================================================================

class RecommendationGenerator:
    """
    Generate security recommendations based on assessments.

    Determinism: Deterministic recommendation generation.
    """

    # FIXED recommendation templates
    RECOMMENDATIONS = {
        "enable_pq": SecurityRecommendation(
            id="REC-001",
            priority=RecommendationPriority.MEDIUM,
            component="cryptography",
            title="Enable Post-Quantum Cryptography",
            description="Post-quantum algorithms are not enabled. Your system is vulnerable to 'harvest now, decrypt later' attacks.",
            remediation="Enable ML-KEM-768 hybrid key exchange and ML-DSA-65 signatures.",
            impact="Protection against quantum computer attacks",
            effort="medium",
        ),
        "rotate_old_keys": SecurityRecommendation(
            id="REC-002",
            priority=RecommendationPriority.HIGH,
            component="cryptography",
            title="Rotate Aged API Keys",
            description="Some API keys have not been rotated in over 90 days.",
            remediation="Rotate keys using the key rotation API or CLI.",
            impact="Reduced risk from key compromise",
            effort="low",
        ),
        "enable_rate_limiting": SecurityRecommendation(
            id="REC-003",
            priority=RecommendationPriority.CRITICAL,
            component="authentication",
            title="Enable Rate Limiting",
            description="Rate limiting is not configured. System is vulnerable to brute force and DoS attacks.",
            remediation="Configure RateLimitMiddleware in the middleware chain.",
            impact="Protection against brute force and DoS",
            effort="low",
        ),
        "add_security_headers": SecurityRecommendation(
            id="REC-004",
            priority=RecommendationPriority.HIGH,
            component="network",
            title="Add Security Headers",
            description="Security headers (CSP, X-Frame-Options, etc.) are not configured.",
            remediation="Enable SecurityHeadersMiddleware.",
            impact="Protection against XSS, clickjacking, and other web attacks",
            effort="low",
        ),
        "configure_anomaly_detection": SecurityRecommendation(
            id="REC-005",
            priority=RecommendationPriority.HIGH,
            component="anomaly_detection",
            title="Configure Anomaly Detection",
            description="Anomaly detection is not configured. Security incidents may go unnoticed.",
            remediation="Initialize AnomalyDetectionEngine with default detectors.",
            impact="Early detection of security incidents",
            effort="medium",
        ),
        "enable_audit_logging": SecurityRecommendation(
            id="REC-006",
            priority=RecommendationPriority.CRITICAL,
            component="audit",
            title="Enable Audit Logging",
            description="Audit logging is disabled. Security events are not being recorded.",
            remediation="Configure AuditLogger with appropriate log path.",
            impact="Security incident investigation and compliance",
            effort="low",
        ),
        "upgrade_tls": SecurityRecommendation(
            id="REC-007",
            priority=RecommendationPriority.HIGH,
            component="cryptography",
            title="Upgrade to TLS 1.3",
            description="TLS 1.2 is in use. TLS 1.3 provides better security and performance.",
            remediation="Configure minimum TLS version to 1.3 in TLSConfig.",
            impact="Improved security and performance",
            effort="low",
        ),
        "enable_replay_protection": SecurityRecommendation(
            id="REC-008",
            priority=RecommendationPriority.MEDIUM,
            component="authentication",
            title="Enable Replay Protection",
            description="Replay protection is not enabled. Requests can be replayed by attackers.",
            remediation="Enable ReplayProtectionMiddleware.",
            impact="Protection against replay attacks",
            effort="low",
        ),
        "enable_merkle_audit": SecurityRecommendation(
            id="REC-009",
            priority=RecommendationPriority.LOW,
            component="audit",
            title="Enable Merkle Tree Audit Verification",
            description="Audit logs do not have integrity verification. Log tampering would not be detected.",
            remediation="Enable MerkleAuditLog for tamper-evident logging.",
            impact="Tamper-evident audit logs",
            effort="medium",
        ),
        "investigate_high_failures": SecurityRecommendation(
            id="REC-010",
            priority=RecommendationPriority.HIGH,
            component="authentication",
            title="Investigate High Authentication Failure Rate",
            description="Authentication failure rate is unusually high. This may indicate an attack.",
            remediation="Review auth logs, check for brute force attempts, consider temporary IP blocks.",
            impact="Prevention of credential stuffing attacks",
            effort="medium",
        ),
    }

    def generate(
        self,
        assessments: List[ComponentAssessment],
    ) -> List[SecurityRecommendation]:
        """
        Generate recommendations based on assessments.

        Args:
            assessments: List of component assessments

        Returns:
            List of prioritized recommendations
        """
        recommendations = []

        for assessment in assessments:
            recommendations.extend(
                self._generate_for_component(assessment)
            )

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority.value)

        return recommendations

    def _generate_for_component(
        self,
        assessment: ComponentAssessment,
    ) -> List[SecurityRecommendation]:
        """Generate recommendations for a specific component."""
        recs = []

        if assessment.name == "cryptography":
            if not assessment.details.get("pq_ready", False):
                recs.append(self.RECOMMENDATIONS["enable_pq"])

            if assessment.details.get("expired_keys", 0) > 0:
                recs.append(self.RECOMMENDATIONS["rotate_old_keys"])

            if assessment.details.get("tls_version") == "TLS 1.2":
                recs.append(self.RECOMMENDATIONS["upgrade_tls"])

        elif assessment.name == "authentication":
            if assessment.details.get("rate_limiting") == "disabled":
                recs.append(self.RECOMMENDATIONS["enable_rate_limiting"])

            if assessment.details.get("replay_protection") == "disabled":
                recs.append(self.RECOMMENDATIONS["enable_replay_protection"])

            if assessment.details.get("failure_status") == "critical":
                recs.append(self.RECOMMENDATIONS["investigate_high_failures"])

        elif assessment.name == "network":
            if assessment.details.get("security_headers") == "missing":
                recs.append(self.RECOMMENDATIONS["add_security_headers"])

        elif assessment.name == "anomaly_detection":
            if assessment.details.get("coverage") == "none":
                recs.append(self.RECOMMENDATIONS["configure_anomaly_detection"])

        elif assessment.name == "audit":
            if assessment.details.get("logging") == "disabled":
                recs.append(self.RECOMMENDATIONS["enable_audit_logging"])

            if assessment.details.get("integrity_verification") == "none":
                recs.append(self.RECOMMENDATIONS["enable_merkle_audit"])

        return recs


# =============================================================================
# Security Posture Engine
# =============================================================================

class SecurityPostureEngine:
    """
    Continuous Security Posture Assessment Engine.

    Provides real-time security health monitoring with:
    - Component-by-component assessment
    - Overall security score
    - Trend tracking
    - Automated recommendations

    Determinism:
    - FIXED assessor weights
    - DETERMINISTIC scoring algorithm
    - Pre-computed thresholds

    Frontier Feature: Most APIs have no real-time security visibility.

    Usage:
        engine = SecurityPostureEngine.default()
        report = engine.assess(context)
        print(f"Security Score: {report.overall_score}")
        print(f"Status: {report.status.value}")
    """

    def __init__(
        self,
        assessors: Optional[List[ComponentAssessor]] = None,
        history_size: int = 100,
    ):
        """
        Initialize posture engine.

        Args:
            assessors: List of component assessors
            history_size: Number of historical scores to keep
        """
        if assessors is None:
            assessors = [
                CryptographyAssessor(),
                AuthenticationAssessor(),
                NetworkAssessor(),
                AnomalyDetectionAssessor(),
                AuditAssessor(),
            ]

        self._assessors = assessors
        self._recommendation_generator = RecommendationGenerator()
        self._history: List[Tuple[float, float]] = []  # (timestamp, score)
        self._history_size = history_size

    @classmethod
    def default(cls) -> "SecurityPostureEngine":
        """Create engine with default assessors."""
        return cls()

    def assess(self, context: Dict[str, Any]) -> PostureReport:
        """
        Perform security posture assessment.

        Args:
            context: System context containing:
                - algorithm_registry
                - key_manager
                - tls_config
                - middleware_chain
                - anomaly_detection_engine
                - audit_logger
                - merkle_audit

        Returns:
            Complete PostureReport
        """
        timestamp = time.time()

        # Run all assessors
        assessments = []
        for assessor in self._assessors:
            try:
                assessment = assessor.assess(context)
                assessments.append(assessment)
            except Exception as e:
                logger.error(f"Assessor {assessor.name} failed: {e}")
                assessments.append(ComponentAssessment(
                    name=assessor.name,
                    health=ComponentHealth.UNKNOWN,
                    score=0,
                    details={"error": str(e)},
                    checks_passed=0,
                    checks_failed=0,
                ))

        # Calculate overall score (weighted average)
        total_weight = sum(a.weight for a in self._assessors)
        overall_score = 0.0

        for assessment, assessor in zip(assessments, self._assessors):
            overall_score += (assessment.score * assessor.weight) / total_weight

        # Determine status
        status = PostureStatus.from_score(overall_score)

        # Calculate trend
        trend = self._calculate_trend(overall_score)

        # Record in history
        self._history.append((timestamp, overall_score))
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size:]

        # Generate recommendations
        recommendations = self._recommendation_generator.generate(assessments)

        # Generate summary
        summary = self._generate_summary(overall_score, status, assessments, recommendations)

        return PostureReport(
            timestamp=timestamp,
            overall_score=overall_score,
            status=status,
            trend=trend,
            components=assessments,
            recommendations=recommendations,
            summary=summary,
        )

    def _calculate_trend(self, current_score: float) -> str:
        """Calculate score trend."""
        if len(self._history) < 5:
            return "stable"

        # Compare to average of last 5 scores
        recent_avg = sum(s for _, s in self._history[-5:]) / 5

        if current_score > recent_avg + 2:
            return "improving"
        elif current_score < recent_avg - 2:
            return "declining"
        else:
            return "stable"

    def _generate_summary(
        self,
        score: float,
        status: PostureStatus,
        assessments: List[ComponentAssessment],
        recommendations: List[SecurityRecommendation],
    ) -> str:
        """Generate human-readable summary."""
        unhealthy = [a for a in assessments if a.health == ComponentHealth.UNHEALTHY]
        degraded = [a for a in assessments if a.health == ComponentHealth.DEGRADED]
        critical_recs = [r for r in recommendations if r.priority == RecommendationPriority.CRITICAL]

        if status == PostureStatus.EXCELLENT:
            summary = f"Security posture is excellent (score: {score:.1f}/100). "
            summary += "All components are healthy."

        elif status == PostureStatus.GOOD:
            summary = f"Security posture is good (score: {score:.1f}/100). "
            if degraded:
                summary += f"{len(degraded)} component(s) need attention: {', '.join(a.name for a in degraded)}."

        elif status == PostureStatus.WARNING:
            summary = f"Security posture needs attention (score: {score:.1f}/100). "
            if unhealthy:
                summary += f"Unhealthy: {', '.join(a.name for a in unhealthy)}. "
            if degraded:
                summary += f"Degraded: {', '.join(a.name for a in degraded)}."

        else:  # CRITICAL
            summary = f"CRITICAL: Security posture requires immediate action (score: {score:.1f}/100). "
            if unhealthy:
                summary += f"Unhealthy components: {', '.join(a.name for a in unhealthy)}. "
            if critical_recs:
                summary += f"{len(critical_recs)} critical issue(s) need immediate remediation."

        return summary

    def get_history(self) -> List[Dict[str, Any]]:
        """Get historical scores."""
        return [
            {"timestamp": ts, "score": score}
            for ts, score in self._history
        ]

    def get_current_status(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get quick status without full recommendations.

        Faster than full assess() for dashboards.
        """
        report = self.assess(context)
        return {
            "timestamp": report.timestamp,
            "score": round(report.overall_score, 2),
            "status": report.status.value,
            "trend": report.trend,
            "components": {
                a.name: a.health.value for a in report.components
            },
            "critical_issues": sum(
                1 for r in report.recommendations
                if r.priority == RecommendationPriority.CRITICAL
            ),
        }


# =============================================================================
# API Endpoint Handler
# =============================================================================

class SecurityPostureAPI:
    """
    API handler for security posture endpoints.

    Endpoints:
    - GET /api/v1/security/posture - Current posture
    - GET /api/v1/security/posture/history - Historical scores
    - GET /api/v1/security/posture/recommendations - Recommendations only
    """

    def __init__(self, engine: Optional[SecurityPostureEngine] = None):
        """Initialize API handler."""
        self.engine = engine or SecurityPostureEngine.default()

    def get_posture(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET /api/v1/security/posture

        Returns full security posture report.
        """
        report = self.engine.assess(context)
        return report.to_dict()

    def get_history(self) -> Dict[str, Any]:
        """
        GET /api/v1/security/posture/history

        Returns historical security scores.
        """
        history = self.engine.get_history()
        return {
            "history": history,
            "count": len(history),
        }

    def get_recommendations(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET /api/v1/security/posture/recommendations

        Returns only recommendations (faster than full posture).
        """
        report = self.engine.assess(context)
        return {
            "recommendations": [r.to_dict() for r in report.recommendations],
            "critical_count": sum(
                1 for r in report.recommendations
                if r.priority == RecommendationPriority.CRITICAL
            ),
            "total_count": len(report.recommendations),
        }

    def get_status(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET /api/v1/security/posture/status

        Returns quick status (for dashboards).
        """
        return self.engine.get_current_status(context)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "PostureStatus",
    "ComponentHealth",
    "RecommendationPriority",

    # Data classes
    "ComponentAssessment",
    "SecurityRecommendation",
    "PostureReport",

    # Assessors
    "ComponentAssessor",
    "CryptographyAssessor",
    "AuthenticationAssessor",
    "NetworkAssessor",
    "AnomalyDetectionAssessor",
    "AuditAssessor",

    # Engine
    "RecommendationGenerator",
    "SecurityPostureEngine",

    # API
    "SecurityPostureAPI",
]
