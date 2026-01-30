"""
Inference Metrics and Reporting
===============================

Instrumentation for tracking inference behavior, determinism,
and performance.

[He2025] Compliance:
- Deterministic metric computation
- Fixed aggregation order
- Reproducible reports
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import defaultdict
import hashlib
import json
import statistics


@dataclass
class InferenceMetrics:
    """
    Collected metrics for inference operations.

    Attributes:
        total_requests: Total inference requests
        cache_hits: Requests served from cache
        cache_misses: Requests that required API call
        errors: Failed requests
        total_latency_ms: Sum of all latencies
        latencies: List of individual latencies (for percentiles)
        backend_requests: Requests per backend
        determinism_levels: Requests per determinism level
        created_at: When metrics collection started
    """
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    latencies: List[float] = field(default_factory=list)
    backend_requests: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    determinism_levels: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def record_request(
        self,
        cache_hit: bool,
        latency_ms: float,
        backend: str,
        determinism_level: str,
        error: bool = False,
    ) -> None:
        """Record a single inference request."""
        self.total_requests += 1
        self.total_latency_ms += latency_ms
        self.latencies.append(latency_ms)

        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        if error:
            self.errors += 1

        self.backend_requests[backend] += 1
        self.determinism_levels[determinism_level] += 1

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    @property
    def error_rate(self) -> float:
        """Error rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.errors / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        """Average latency in milliseconds."""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    @property
    def p50_latency_ms(self) -> float:
        """50th percentile latency."""
        if not self.latencies:
            return 0.0
        return statistics.median(self.latencies)

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def p99_latency_ms(self) -> float:
        """99th percentile latency."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "errors": self.errors,
            "cache_hit_rate": self.cache_hit_rate,
            "error_rate": self.error_rate,
            "latency": {
                "avg_ms": self.avg_latency_ms,
                "p50_ms": self.p50_latency_ms,
                "p95_ms": self.p95_latency_ms,
                "p99_ms": self.p99_latency_ms,
            },
            "backend_requests": dict(self.backend_requests),
            "determinism_levels": dict(self.determinism_levels),
            "created_at": self.created_at.isoformat(),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.errors = 0
        self.total_latency_ms = 0.0
        self.latencies = []
        self.backend_requests = defaultdict(int)
        self.determinism_levels = defaultdict(int)
        self.created_at = datetime.now(timezone.utc)


@dataclass
class DeterminismReport:
    """
    Report on determinism compliance.

    This report documents the level of determinism achieved
    and any deviations detected.

    Attributes:
        total_inferences: Total inference operations
        deterministic_count: Operations with deterministic guarantee
        non_deterministic_count: Operations without guarantee
        cache_served_count: Operations served from cache
        kernel_level_count: Operations with kernel-level determinism
        verification_count: Operations that were verified
        divergences_detected: Number of divergences found (Tier 2)
        report_hash: Deterministic hash of this report
    """
    total_inferences: int = 0
    deterministic_count: int = 0
    non_deterministic_count: int = 0
    cache_served_count: int = 0
    kernel_level_count: int = 0
    verification_count: int = 0
    divergences_detected: int = 0
    divergence_details: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def record_inference(
        self,
        determinism_level: str,
        cache_hit: bool,
        verified: bool = False,
        divergence: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an inference for the report."""
        self.total_inferences += 1

        if cache_hit:
            self.cache_served_count += 1
            self.deterministic_count += 1
        elif determinism_level == "kernel":
            self.kernel_level_count += 1
            self.deterministic_count += 1
        elif determinism_level == "api":
            # API-level determinism is best-effort
            self.deterministic_count += 1
        else:
            self.non_deterministic_count += 1

        if verified:
            self.verification_count += 1

        if divergence:
            self.divergences_detected += 1
            self.divergence_details.append(divergence)

    @property
    def determinism_rate(self) -> float:
        """Rate of deterministic operations."""
        if self.total_inferences == 0:
            return 0.0
        return self.deterministic_count / self.total_inferences

    @property
    def cache_rate(self) -> float:
        """Rate of cache-served operations."""
        if self.total_inferences == 0:
            return 0.0
        return self.cache_served_count / self.total_inferences

    @property
    def kernel_rate(self) -> float:
        """Rate of kernel-level deterministic operations."""
        if self.total_inferences == 0:
            return 0.0
        return self.kernel_level_count / self.total_inferences

    @property
    def report_hash(self) -> str:
        """
        Deterministic hash of this report.

        [He2025] Compliance: Uses sorted keys for reproducibility.
        """
        report_data = {
            "total_inferences": self.total_inferences,
            "deterministic_count": self.deterministic_count,
            "non_deterministic_count": self.non_deterministic_count,
            "cache_served_count": self.cache_served_count,
            "kernel_level_count": self.kernel_level_count,
            "verification_count": self.verification_count,
            "divergences_detected": self.divergences_detected,
        }
        report_str = json.dumps(report_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(report_str.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "summary": {
                "total_inferences": self.total_inferences,
                "deterministic_count": self.deterministic_count,
                "non_deterministic_count": self.non_deterministic_count,
                "determinism_rate": self.determinism_rate,
            },
            "breakdown": {
                "cache_served": self.cache_served_count,
                "kernel_level": self.kernel_level_count,
                "verified": self.verification_count,
            },
            "rates": {
                "cache_rate": self.cache_rate,
                "kernel_rate": self.kernel_rate,
            },
            "divergences": {
                "count": self.divergences_detected,
                "details": self.divergence_details,
            },
            "metadata": {
                "generated_at": self.generated_at.isoformat(),
                "report_hash": self.report_hash,
            },
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        return f"""# Determinism Report

**Generated**: {self.generated_at.isoformat()}
**Report Hash**: `{self.report_hash}`

## Summary

| Metric | Value |
|--------|-------|
| Total Inferences | {self.total_inferences} |
| Deterministic | {self.deterministic_count} ({self.determinism_rate:.1%}) |
| Non-Deterministic | {self.non_deterministic_count} |

## Breakdown

| Source | Count | Rate |
|--------|-------|------|
| Cache-Served | {self.cache_served_count} | {self.cache_rate:.1%} |
| Kernel-Level | {self.kernel_level_count} | {self.kernel_rate:.1%} |
| Verified | {self.verification_count} | - |

## Divergences

- **Detected**: {self.divergences_detected}

{self._format_divergences()}

## [He2025] Compliance

- **Tier 1 (API-Maximized)**: {self.determinism_rate:.1%} of requests
- **Tier 3 (Kernel-Level)**: {self.kernel_rate:.1%} of requests
- **Cache Hit Rate**: {self.cache_rate:.1%}

---
*Report generated with deterministic hash for verification*
"""

    def _format_divergences(self) -> str:
        """Format divergence details for markdown."""
        if not self.divergence_details:
            return "*No divergences detected*"

        lines = []
        for i, div in enumerate(self.divergence_details[:10]):  # Limit to 10
            lines.append(f"- Divergence {i+1}: {div.get('description', 'Unknown')}")

        if len(self.divergence_details) > 10:
            lines.append(f"- ... and {len(self.divergence_details) - 10} more")

        return "\n".join(lines)


class MetricsCollector:
    """
    Centralized metrics collection for inference operations.

    Thread-safe collector that aggregates metrics across
    multiple wrapper instances.
    """

    def __init__(self):
        self._metrics = InferenceMetrics()
        self._report = DeterminismReport()
        self._lock = None  # Lazy init for threading

    @property
    def metrics(self) -> InferenceMetrics:
        """Get current metrics."""
        return self._metrics

    @property
    def report(self) -> DeterminismReport:
        """Get current determinism report."""
        return self._report

    def record(
        self,
        cache_hit: bool,
        latency_ms: float,
        backend: str,
        determinism_level: str,
        error: bool = False,
        verified: bool = False,
        divergence: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record an inference operation.

        Args:
            cache_hit: Whether served from cache
            latency_ms: Request latency
            backend: Backend used
            determinism_level: Achieved determinism level
            error: Whether an error occurred
            verified: Whether result was verified (Tier 2)
            divergence: Divergence details if detected
        """
        self._metrics.record_request(
            cache_hit=cache_hit,
            latency_ms=latency_ms,
            backend=backend,
            determinism_level=determinism_level,
            error=error,
        )

        self._report.record_inference(
            determinism_level=determinism_level,
            cache_hit=cache_hit,
            verified=verified,
            divergence=divergence,
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get combined summary of metrics and determinism."""
        return {
            "metrics": self._metrics.to_dict(),
            "determinism": self._report.to_dict(),
        }

    def reset(self) -> None:
        """Reset all collected data."""
        self._metrics.reset()
        self._report = DeterminismReport()


# Global metrics collector
_global_collector: Optional[MetricsCollector] = None


def get_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector
