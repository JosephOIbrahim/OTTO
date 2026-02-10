"""
Validation Agent for OTTO OS
============================

A specialized agent that validates files for [He2025]-inspired determinism
and deposits QUALITY trails based on findings.

Determinism (inspired by [He2025]):
- Uses deterministic pattern matching
- Deposits trails in sorted order
- Fixed signal patterns

Usage:
    agent = ValidationAgent()
    result = await agent.validate_file("src/otto/example.py")
    result = await agent.validate_directory("src/otto/")
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from ..hooks.auto_validate import check_he2025_compliance, validate_file as validate_he2025
from ..trails import Trail, TrailStore, TrailType, get_store


class ValidationSeverity(Enum):
    """Severity levels for validation findings."""
    INFO = "info"           # Informational, no action needed
    WARNING = "warning"     # Potential issue, should review
    ERROR = "error"         # Definite violation, must fix
    CRITICAL = "critical"   # Severe violation, blocks ship


@dataclass
class ValidationFinding:
    """A single validation finding."""
    file_path: str
    line: int
    column: int
    code: str              # e.g., "HE2025-001"
    message: str
    severity: ValidationSeverity
    suggestion: Optional[str] = None

    def to_signal(self) -> str:
        """Convert to trail signal format."""
        return f"he2025_violation:{self.code}:L{self.line}"


@dataclass
class ValidationResult:
    """Result of validating a file or directory."""
    path: str
    is_compliant: bool
    findings: list[ValidationFinding] = field(default_factory=list)
    trails_deposited: int = 0
    validation_time: datetime = field(default_factory=datetime.now)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL))

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == ValidationSeverity.WARNING)


# Violation code mapping for [He2025]
VIOLATION_CODES = {
    "max_on_dict_items": ("HE2025-001", "max() on dict.items() is non-deterministic", "Use sorted_max() from otto.determinism"),
    "iterate_set": ("HE2025-002", "Iterating over set is non-deterministic", "Use sorted(set(...)) or convert to list"),
    "iterate_dict_keys": ("HE2025-003", "Iterating over dict.keys() is non-deterministic", "Use sorted(dict.keys())"),
    "unseeded_random": ("HE2025-004", "Using random without fixed seed", "Use random.seed(DETERMINISM_SEED) first"),
    "sum_without_sort": ("HE2025-005", "Summing unsorted values may have batch variance", "Use kahan_sum(sorted(values))"),
}


class ValidationAgent:
    """
    Agent for validating files against [He2025] determinism requirements.

    Provides:
    - Single file validation
    - Directory validation
    - Trail deposition for findings
    - Compliance reporting
    """

    def __init__(
        self,
        store: Optional[TrailStore] = None,
        agent_id: str = "validation_agent",
        auto_deposit: bool = True,
    ):
        """
        Initialize the ValidationAgent.

        Args:
            store: TrailStore to use (defaults to global store)
            agent_id: Identifier for trail deposits
            auto_deposit: Whether to automatically deposit trails
        """
        self.store = store or get_store()
        self.agent_id = agent_id
        self.auto_deposit = auto_deposit

    async def validate_file(self, file_path: str | Path) -> ValidationResult:
        """
        Validate a single file for determinism (inspired by [He2025]).

        Args:
            file_path: Path to the Python file

        Returns:
            ValidationResult with findings and compliance status
        """
        path = Path(file_path)
        if not path.exists():
            return ValidationResult(
                path=str(path),
                is_compliant=True,  # Non-existent files are "compliant"
                findings=[],
            )

        if path.suffix != ".py":
            return ValidationResult(
                path=str(path),
                is_compliant=True,
                findings=[],
            )

        # Read file content
        content = path.read_text(encoding="utf-8", errors="ignore")

        # Run [He2025]-inspired determinism check
        violations, compliances = check_he2025_compliance(content)

        # Convert to findings
        findings: list[ValidationFinding] = []

        for v in violations:
            v_type = v.get("type", "unknown")
            v_line = v.get("line", 0)
            v_col = v.get("column", 0)

            code_info = VIOLATION_CODES.get(v_type, ("HE2025-XXX", f"Unknown violation: {v_type}", None))
            code, message, suggestion = code_info

            findings.append(ValidationFinding(
                file_path=str(path),
                line=v_line,
                column=v_col,
                code=code,
                message=message,
                severity=ValidationSeverity.ERROR,
                suggestion=suggestion,
            ))

        # Build result
        is_compliant = len(findings) == 0
        result = ValidationResult(
            path=str(path),
            is_compliant=is_compliant,
            findings=findings,
        )

        # Deposit trails if enabled
        if self.auto_deposit:
            result.trails_deposited = self._deposit_trails(str(path), findings, compliances)

        return result

    async def validate_directory(
        self,
        dir_path: str | Path,
        recursive: bool = True,
    ) -> list[ValidationResult]:
        """
        Validate all Python files in a directory.

        Args:
            dir_path: Path to the directory
            recursive: Whether to search recursively

        Returns:
            List of ValidationResults (sorted by path for determinism)
        """
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            return []

        # Find all Python files
        if recursive:
            files = sorted(path.rglob("*.py"))
        else:
            files = sorted(path.glob("*.py"))

        # Filter out __pycache__
        files = [f for f in files if "__pycache__" not in str(f)]

        # Validate each file
        results = []
        for py_file in files:
            result = await self.validate_file(py_file)
            results.append(result)

        return results

    def _deposit_trails(
        self,
        file_path: str,
        findings: list[ValidationFinding],
        compliances: list[dict],
    ) -> int:
        """
        Deposit QUALITY trails for validation findings.

        Returns:
            Number of trails deposited
        """
        count = 0

        # Deposit violation trails
        for finding in sorted(findings, key=lambda f: (f.line, f.code)):
            trail = Trail(
                path=file_path,
                signal=finding.to_signal(),
                trail_type=TrailType.QUALITY,
                deposited_by=self.agent_id,
                strength=1.0,
                metadata={
                    "severity": finding.severity.value,
                    "message": finding.message,
                    "suggestion": finding.suggestion,
                },
            )
            self.store.deposit(trail)
            count += 1

        # Deposit compliance trails
        for c in sorted(compliances, key=lambda x: x.get("type", "")):
            c_type = c.get("type", "unknown")
            trail = Trail(
                path=file_path,
                signal=f"he2025_compliant:{c_type}",
                trail_type=TrailType.QUALITY,
                deposited_by=self.agent_id,
                strength=1.0,
            )
            self.store.deposit(trail)
            count += 1

        return count

    def get_summary(self, results: list[ValidationResult]) -> dict:
        """
        Generate summary statistics from validation results.

        Returns:
            Summary dict with counts and compliance percentage
        """
        total_files = len(results)
        compliant_files = sum(1 for r in results if r.is_compliant)
        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)
        total_trails = sum(r.trails_deposited for r in results)

        compliance_rate = (compliant_files / total_files * 100) if total_files > 0 else 100.0

        return {
            "total_files": total_files,
            "compliant_files": compliant_files,
            "non_compliant_files": total_files - compliant_files,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "total_trails_deposited": total_trails,
            "compliance_rate": round(compliance_rate, 2),
        }

    def format_report(self, results: list[ValidationResult]) -> str:
        """
        Format validation results as a readable report.

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("[He2025] Determinism Report")
        lines.append("=" * 60)
        lines.append("")

        summary = self.get_summary(results)

        lines.append(f"Files analyzed: {summary['total_files']}")
        lines.append(f"Compliant:      {summary['compliant_files']}")
        lines.append(f"Non-compliant:  {summary['non_compliant_files']}")
        lines.append(f"Compliance:     {summary['compliance_rate']}%")
        lines.append("")

        if summary["total_errors"] > 0:
            lines.append("-" * 60)
            lines.append("VIOLATIONS:")
            lines.append("-" * 60)

            for result in results:
                if not result.is_compliant:
                    lines.append(f"\n{result.path}:")
                    for finding in result.findings:
                        lines.append(f"  L{finding.line}: [{finding.code}] {finding.message}")
                        if finding.suggestion:
                            lines.append(f"         → {finding.suggestion}")

        lines.append("")
        lines.append(f"Trails deposited: {summary['total_trails_deposited']}")
        lines.append("=" * 60)

        return "\n".join(lines)


# Module-level convenience functions
async def validate_file(file_path: str | Path) -> ValidationResult:
    """Validate a single file using default agent."""
    agent = ValidationAgent()
    return await agent.validate_file(file_path)


async def validate_directory(dir_path: str | Path, recursive: bool = True) -> list[ValidationResult]:
    """Validate a directory using default agent."""
    agent = ValidationAgent()
    return await agent.validate_directory(dir_path, recursive)


__all__ = [
    "ValidationAgent",
    "ValidationResult",
    "ValidationFinding",
    "ValidationSeverity",
    "validate_file",
    "validate_directory",
]
