"""
Tests for Self-Healing Security
===============================

Tests for automatic detection and remediation of security issues.
"""

import pytest
import time

from otto.security.healing import (
    SecurityHealer,
    SecurityIssue,
    IssueType,
    IssueSeverity,
    RemediationAction,
    RemediationStatus,
    RemediationRule,
    AuthenticationDetector,
    KeyManagementDetector,
    RateLimitDetector,
    scan_and_heal,
    get_security_status,
)


class TestSecurityIssue:
    """Tests for SecurityIssue dataclass."""

    def test_issue_creation(self):
        """Can create a security issue."""
        issue = SecurityIssue(
            issue_type=IssueType.BRUTE_FORCE_DETECTED,
            severity=IssueSeverity.HIGH,
            title="Brute force detected",
            description="Multiple failed auth attempts",
        )
        assert issue.issue_type == IssueType.BRUTE_FORCE_DETECTED
        assert issue.severity == IssueSeverity.HIGH
        assert len(issue.issue_id) == 16

    def test_issue_id_unique(self):
        """Different issues get different IDs."""
        issue1 = SecurityIssue(
            IssueType.BRUTE_FORCE_DETECTED,
            IssueSeverity.HIGH,
            "Issue 1",
            "Description 1",
        )
        issue2 = SecurityIssue(
            IssueType.BRUTE_FORCE_DETECTED,
            IssueSeverity.HIGH,
            "Issue 2",
            "Description 2",
        )
        assert issue1.issue_id != issue2.issue_id

    def test_issue_serialization(self):
        """Issue serializes to dict."""
        issue = SecurityIssue(
            IssueType.KEY_EXPIRED,
            IssueSeverity.CRITICAL,
            "Key expired",
            "Encryption key is old",
            metadata={"key_id": "abc123"},
        )
        data = issue.to_dict()
        assert data['issue_type'] == 'key_expired'
        assert data['severity'] == 'critical'
        assert data['metadata']['key_id'] == 'abc123'


class TestAuthenticationDetector:
    """Tests for authentication detector."""

    def test_no_issues_with_successful_auth(self):
        """No issues for successful auth."""
        detector = AuthenticationDetector()
        context = {
            'auth_events': [
                {'success': True, 'actor': 'user1'},
                {'success': True, 'actor': 'user2'},
            ]
        }
        issues = detector.detect(context)
        assert len(issues) == 0

    def test_detects_brute_force(self):
        """Detects brute force attack."""
        detector = AuthenticationDetector()
        current_time = time.time()

        # Simulate 5+ failed attempts
        context = {
            'auth_events': [
                {'success': False, 'actor': 'attacker', 'timestamp': current_time - i}
                for i in range(6)
            ]
        }
        issues = detector.detect(context)
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.BRUTE_FORCE_DETECTED

    def test_no_brute_force_under_threshold(self):
        """No brute force for few failures."""
        detector = AuthenticationDetector()
        current_time = time.time()

        # Only 3 failed attempts
        context = {
            'auth_events': [
                {'success': False, 'actor': 'user', 'timestamp': current_time - i}
                for i in range(3)
            ]
        }
        issues = detector.detect(context)
        assert len(issues) == 0

    def test_ignores_old_failures(self):
        """Ignores old failed attempts."""
        detector = AuthenticationDetector()
        current_time = time.time()

        # Old failures (>5 minutes ago)
        context = {
            'auth_events': [
                {'success': False, 'actor': 'user', 'timestamp': current_time - 600}
                for _ in range(10)
            ]
        }
        issues = detector.detect(context)
        assert len(issues) == 0


class TestKeyManagementDetector:
    """Tests for key management detector."""

    def test_no_issues_for_fresh_keys(self):
        """No issues for fresh keys."""
        detector = KeyManagementDetector()
        context = {
            'keys': [
                {'key_id': 'key1', 'created_at': time.time() - 86400},  # 1 day old
            ]
        }
        issues = detector.detect(context)
        assert len(issues) == 0

    def test_detects_expiring_key(self):
        """Detects key nearing rotation."""
        detector = KeyManagementDetector()
        context = {
            'keys': [
                {'key_id': 'key1', 'created_at': time.time() - 35 * 86400},  # 35 days
            ]
        }
        issues = detector.detect(context)
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.KEY_EXPIRING_SOON
        assert issues[0].severity == IssueSeverity.MEDIUM

    def test_detects_expired_key(self):
        """Detects critically old key."""
        detector = KeyManagementDetector()
        context = {
            'keys': [
                {'key_id': 'key1', 'created_at': time.time() - 100 * 86400},  # 100 days
            ]
        }
        issues = detector.detect(context)
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.KEY_EXPIRED
        assert issues[0].severity == IssueSeverity.CRITICAL


class TestRateLimitDetector:
    """Tests for rate limit detector."""

    def test_no_issues_under_limit(self):
        """No issues for normal traffic."""
        detector = RateLimitDetector()
        current_time = time.time()
        context = {
            'requests': [
                {'client_id': 'client1', 'timestamp': current_time - i}
                for i in range(50)
            ]
        }
        issues = detector.detect(context)
        assert len(issues) == 0

    def test_detects_rate_limit_exceeded(self):
        """Detects rate limit exceeded."""
        detector = RateLimitDetector()
        current_time = time.time()
        context = {
            'requests': [
                {'client_id': 'spammer', 'timestamp': current_time - i * 0.5}
                for i in range(150)  # 150 requests in <1 minute
            ]
        }
        issues = detector.detect(context)
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.RATE_LIMIT_EXCEEDED


class TestSecurityHealer:
    """Tests for SecurityHealer."""

    def test_healer_creation(self):
        """Can create healer."""
        healer = SecurityHealer()
        assert healer is not None
        assert len(healer._detectors) > 0
        assert len(healer._rules) > 0

    def test_scan_returns_issues(self):
        """Scan returns detected issues."""
        healer = SecurityHealer()
        current_time = time.time()

        context = {
            'auth_events': [
                {'success': False, 'actor': 'attacker', 'timestamp': current_time - i}
                for i in range(6)
            ]
        }

        issues = healer.scan(context)
        assert len(issues) > 0
        assert any(i.issue_type == IssueType.BRUTE_FORCE_DETECTED for i in issues)

    def test_remediate_block_ip(self):
        """Can remediate by blocking IP."""
        healer = SecurityHealer()
        issue = SecurityIssue(
            IssueType.BRUTE_FORCE_DETECTED,
            IssueSeverity.HIGH,
            "Brute force",
            "Attack from IP",
            metadata={'actor': '192.168.1.100'},
        )

        result = healer.remediate(issue, RemediationAction.BLOCK_IP)
        assert result.status == RemediationStatus.COMPLETED
        assert healer._remediator.is_ip_blocked('192.168.1.100')

    def test_remediate_revoke_token(self):
        """Can remediate by revoking token."""
        healer = SecurityHealer()
        issue = SecurityIssue(
            IssueType.INVALID_TOKEN_USED,
            IssueSeverity.HIGH,
            "Invalid token",
            "Suspicious token usage",
            metadata={'token_id': 'token123'},
        )

        result = healer.remediate(issue, RemediationAction.REVOKE_TOKEN)
        assert result.status == RemediationStatus.COMPLETED
        assert healer._remediator.is_token_revoked('token123')

    def test_auto_remediate_brute_force(self):
        """Auto-remediation blocks brute force."""
        healer = SecurityHealer()
        current_time = time.time()

        context = {
            'auth_events': [
                {'success': False, 'actor': '10.0.0.1', 'timestamp': current_time - i}
                for i in range(6)
            ]
        }

        issues = healer.scan(context)
        results = healer.auto_remediate(issues)

        assert len(results) > 0
        assert any(r.action == RemediationAction.BLOCK_IP for r in results)

    def test_scan_and_heal(self):
        """scan_and_heal runs full cycle."""
        healer = SecurityHealer()
        current_time = time.time()

        context = {
            'auth_events': [
                {'success': False, 'actor': 'bad_actor', 'timestamp': current_time - i}
                for i in range(6)
            ]
        }

        summary = healer.scan_and_heal(context)
        assert 'issues_detected' in summary
        assert 'remediations_attempted' in summary
        assert summary['issues_detected'] > 0

    def test_get_status(self):
        """Can get healer status."""
        healer = SecurityHealer()
        status = healer.get_status()

        assert 'monitoring' in status
        assert 'active_issues' in status
        assert 'detectors' in status
        assert 'rules' in status

    def test_get_active_issues(self):
        """Can get active issues."""
        healer = SecurityHealer()
        issue = SecurityIssue(
            IssueType.KEY_EXPIRED,
            IssueSeverity.CRITICAL,
            "Key expired",
            "Old key",
        )
        healer._active_issues[issue.issue_id] = issue

        active = healer.get_active_issues()
        assert len(active) == 1
        assert active[0].issue_id == issue.issue_id

    def test_remediation_history(self):
        """Tracks remediation history."""
        healer = SecurityHealer()
        issue = SecurityIssue(
            IssueType.RATE_LIMIT_EXCEEDED,
            IssueSeverity.MEDIUM,
            "Rate limit",
            "Exceeded",
        )

        healer.remediate(issue, RemediationAction.ALERT_ONLY)
        history = healer.get_remediation_history()

        assert len(history) == 1
        assert history[0].issue_id == issue.issue_id

    def test_register_custom_remediation(self):
        """Can register custom remediation rules."""
        healer = SecurityHealer()

        healer.register_remediation(
            IssueType.CONFIG_DRIFT,
            RemediationAction.RESTORE_CONFIG,
            auto_execute=True,
            cooldown_seconds=600,
        )

        assert IssueType.CONFIG_DRIFT in healer._rules
        rule = healer._rules[IssueType.CONFIG_DRIFT]
        assert rule.action == RemediationAction.RESTORE_CONFIG
        assert rule.auto_execute is True


class TestGlobalFunctions:
    """Tests for global helper functions."""

    def test_scan_and_heal(self):
        """Global scan_and_heal works."""
        import otto.security.healing as healing_module
        healing_module._healer = None

        result = scan_and_heal()
        assert 'issues_detected' in result
        assert 'remediations_attempted' in result

    def test_get_security_status(self):
        """Global get_security_status works."""
        import otto.security.healing as healing_module
        healing_module._healer = None

        status = get_security_status()
        assert 'monitoring' in status
        assert 'detectors' in status


class TestDeterminism:
    """Tests for [He2025] determinism compliance."""

    def test_same_context_same_issues(self):
        """Same context produces same issues."""
        healer = SecurityHealer()
        current_time = 1000.0

        context = {
            'auth_events': [
                {'success': False, 'actor': 'test', 'timestamp': current_time - i}
                for i in range(6)
            ]
        }

        issues1 = healer.scan(context)
        # Create new healer to reset state
        healer2 = SecurityHealer()
        issues2 = healer2.scan(context)

        # Same types should be detected
        types1 = {i.issue_type for i in issues1}
        types2 = {i.issue_type for i in issues2}
        assert types1 == types2

    def test_fixed_thresholds(self):
        """Thresholds are fixed values."""
        from otto.security.healing import (
            FAILED_AUTH_THRESHOLD,
            RATE_LIMIT_THRESHOLD,
            KEY_AGE_WARNING_DAYS,
        )

        # These should be fixed constants
        assert FAILED_AUTH_THRESHOLD == 5
        assert RATE_LIMIT_THRESHOLD == 100
        assert KEY_AGE_WARNING_DAYS == 30
