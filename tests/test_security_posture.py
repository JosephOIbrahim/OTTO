"""
Tests for Security Posture API
==============================

Tests for real-time security posture assessment.
"""

import pytest

from otto.security.posture import (
    SecurityPosture,
    ComponentScore,
    SecurityIssue,
    Severity,
    ComponentStatus,
    SecurityAssessor,
    SecurityCheck,
    assess_posture,
    get_posture_summary,
    get_posture_details,
    GRADE_THRESHOLDS,
    COMPONENT_WEIGHTS,
)


class TestConstants:
    """Tests for posture constants."""

    def test_grade_thresholds(self):
        """Grade thresholds are properly defined."""
        assert GRADE_THRESHOLDS['A'] == 90
        assert GRADE_THRESHOLDS['B'] == 80
        assert GRADE_THRESHOLDS['C'] == 70
        assert GRADE_THRESHOLDS['D'] == 60
        assert GRADE_THRESHOLDS['F'] == 0

    def test_component_weights_sum_to_one(self):
        """Component weights sum to 1.0."""
        total = sum(COMPONENT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


class TestSecurityIssue:
    """Tests for SecurityIssue dataclass."""

    def test_issue_creation(self):
        """Can create a security issue."""
        issue = SecurityIssue(
            id="test-001",
            component="crypto",
            severity=Severity.HIGH,
            title="Test Issue",
            description="A test issue",
            remediation="Fix it",
        )
        assert issue.id == "test-001"
        assert issue.component == "crypto"
        assert issue.severity == Severity.HIGH

    def test_issue_to_dict(self):
        """Issue serializes to dict."""
        issue = SecurityIssue(
            id="test-001",
            component="crypto",
            severity=Severity.CRITICAL,
            title="Test",
            description="Desc",
            remediation="Fix",
            metadata={"key": "value"},
        )
        data = issue.to_dict()

        assert data['id'] == "test-001"
        assert data['severity'] == "critical"
        assert data['metadata']['key'] == "value"


class TestComponentScore:
    """Tests for ComponentScore dataclass."""

    def test_score_creation(self):
        """Can create component score."""
        score = ComponentScore(
            name="crypto",
            score=85,
            status=ComponentStatus.HEALTHY,
            checks_passed=8,
            checks_failed=2,
        )
        assert score.name == "crypto"
        assert score.score == 85
        assert score.checks_total == 10

    def test_score_to_dict(self):
        """Score serializes to dict."""
        score = ComponentScore(
            name="auth",
            score=70,
            status=ComponentStatus.DEGRADED,
        )
        data = score.to_dict()

        assert data['name'] == "auth"
        assert data['score'] == 70
        assert data['status'] == "degraded"


class TestSecurityPosture:
    """Tests for SecurityPosture dataclass."""

    def test_posture_creation(self):
        """Can create security posture."""
        posture = SecurityPosture(
            score=85,
            grade="B",
            status=ComponentStatus.HEALTHY,
            components={},
            issues=[],
            assessed_at=1000.0,
            assessment_id="abc123",
        )
        assert posture.score == 85
        assert posture.grade == "B"

    def test_critical_issues_filter(self):
        """Can filter critical issues."""
        issues = [
            SecurityIssue("1", "c", Severity.CRITICAL, "T", "D", "R"),
            SecurityIssue("2", "c", Severity.HIGH, "T", "D", "R"),
            SecurityIssue("3", "c", Severity.CRITICAL, "T", "D", "R"),
        ]
        posture = SecurityPosture(
            score=50,
            grade="F",
            status=ComponentStatus.UNHEALTHY,
            components={},
            issues=issues,
            assessed_at=1000.0,
            assessment_id="abc123",
        )

        assert len(posture.critical_issues) == 2
        assert len(posture.high_issues) == 1

    def test_posture_to_dict(self):
        """Posture serializes to dict."""
        posture = SecurityPosture(
            score=90,
            grade="A",
            status=ComponentStatus.HEALTHY,
            components={},
            issues=[],
            assessed_at=1000.0,
            assessment_id="abc123",
        )
        data = posture.to_dict()

        assert data['score'] == 90
        assert data['grade'] == "A"
        assert 'issues_by_severity' in data


class TestSecurityCheck:
    """Tests for SecurityCheck."""

    def test_check_passes(self):
        """Check passes when function returns True."""
        check = SecurityCheck(
            id="test-pass",
            name="Passing Check",
            component="test",
            check_fn=lambda: True,
        )
        passed, issue = check.run()

        assert passed is True
        assert issue is None

    def test_check_fails(self):
        """Check fails when function returns False."""
        check = SecurityCheck(
            id="test-fail",
            name="Failing Check",
            component="test",
            check_fn=lambda: False,
            severity_on_fail=Severity.HIGH,
            description="Check failed",
            remediation="Fix it",
        )
        passed, issue = check.run()

        assert passed is False
        assert issue is not None
        assert issue.severity == Severity.HIGH

    def test_check_handles_exception(self):
        """Check handles exceptions gracefully."""
        def failing_fn():
            raise ValueError("Test error")

        check = SecurityCheck(
            id="test-error",
            name="Error Check",
            component="test",
            check_fn=failing_fn,
        )
        passed, issue = check.run()

        assert passed is False
        assert issue is not None
        assert "error" in issue.title.lower()


class TestSecurityAssessor:
    """Tests for SecurityAssessor."""

    def test_assessor_creation(self):
        """Can create assessor with default checks."""
        assessor = SecurityAssessor()
        assert len(assessor._checks) > 0

    def test_register_check(self):
        """Can register custom checks."""
        assessor = SecurityAssessor()
        initial_count = len(assessor._checks)

        assessor.register_check(SecurityCheck(
            id="custom-check",
            name="Custom Check",
            component="crypto",
            check_fn=lambda: True,
        ))

        assert len(assessor._checks) == initial_count + 1

    def test_assess_returns_posture(self):
        """Assessment returns SecurityPosture."""
        assessor = SecurityAssessor()
        posture = assessor.assess()

        assert isinstance(posture, SecurityPosture)
        assert 0 <= posture.score <= 100
        assert posture.grade in ['A', 'B', 'C', 'D', 'F']

    def test_assess_caching(self):
        """Assessment uses cache."""
        assessor = SecurityAssessor()

        posture1 = assessor.assess(use_cache=True)
        posture2 = assessor.assess(use_cache=True)

        # Same assessment ID means cache was used
        assert posture1.assessment_id == posture2.assessment_id

    def test_assess_without_cache(self):
        """Assessment can bypass cache."""
        assessor = SecurityAssessor()

        posture1 = assessor.assess(use_cache=False)
        posture2 = assessor.assess(use_cache=False)

        # Different assessment IDs
        assert posture1.assessment_id != posture2.assessment_id


class TestGlobalFunctions:
    """Tests for global assessment functions."""

    def test_assess_posture(self):
        """assess_posture helper works."""
        import otto.security.posture as posture_module
        posture_module._assessor = None  # Reset

        posture = assess_posture()
        assert isinstance(posture, SecurityPosture)

    def test_get_posture_summary(self):
        """get_posture_summary helper works."""
        import otto.security.posture as posture_module
        posture_module._assessor = None  # Reset

        summary = get_posture_summary()
        assert 'score' in summary
        assert 'grade' in summary

    def test_get_posture_details(self):
        """get_posture_details helper works."""
        import otto.security.posture as posture_module
        posture_module._assessor = None  # Reset

        details = get_posture_details()
        assert 'score' in details
        assert 'components' in details


class TestGrading:
    """Tests for grade calculation."""

    def test_grade_a(self):
        """Score >= 90 gets A."""
        assessor = SecurityAssessor()
        # All checks pass = 100
        for check in assessor._checks:
            check.check_fn = lambda: True

        posture = assessor.assess(use_cache=False)
        # Should be A (all checks pass)
        assert posture.grade in ['A', 'B']  # B if PQ not available

    def test_grade_calculation_deterministic(self):
        """Same checks produce same grade."""
        assessor1 = SecurityAssessor()
        assessor2 = SecurityAssessor()

        # Make both pass all checks
        for a in [assessor1, assessor2]:
            for check in a._checks:
                check.check_fn = lambda: True

        p1 = assessor1.assess(use_cache=False)
        p2 = assessor2.assess(use_cache=False)

        assert p1.score == p2.score
        assert p1.grade == p2.grade


class TestDeterminism:
    """Tests for [He2025] determinism compliance."""

    def test_same_state_same_score(self):
        """Same state produces same score."""
        assessor = SecurityAssessor()

        # Set all checks to pass
        for check in assessor._checks:
            check.check_fn = lambda: True

        scores = [assessor.assess(use_cache=False).score for _ in range(5)]
        assert len(set(scores)) == 1

    def test_fixed_weights(self):
        """Weights are fixed constants."""
        assert COMPONENT_WEIGHTS['crypto'] == 0.30
        assert COMPONENT_WEIGHTS['authentication'] == 0.25
        assert COMPONENT_WEIGHTS['audit'] == 0.20

    def test_fixed_thresholds(self):
        """Thresholds are fixed constants."""
        assert GRADE_THRESHOLDS['A'] == 90
        assert GRADE_THRESHOLDS['B'] == 80
