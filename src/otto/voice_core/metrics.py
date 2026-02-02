"""
Voice processing metrics and instrumentation.

Tracks latency, costs, and quality metrics for voice pipeline.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from collections import deque
import statistics


@dataclass
class LatencyMetrics:
    """Latency breakdown for voice processing pipeline."""

    stt_ms: float = 0.0
    """Speech-to-text latency in milliseconds."""

    processing_ms: float = 0.0
    """Core processing latency (OTTO response) in milliseconds."""

    prepare_speech_ms: float = 0.0
    """Text preparation latency in milliseconds."""

    tts_ms: float = 0.0
    """Text-to-speech latency in milliseconds."""

    upload_ms: float = 0.0
    """Media upload latency in milliseconds."""

    total_ms: float = 0.0
    """Total end-to-end latency in milliseconds."""

    @property
    def within_target(self) -> bool:
        """Return True if within 10s target."""
        return self.total_ms < 10_000

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "stt_ms": self.stt_ms,
            "processing_ms": self.processing_ms,
            "prepare_speech_ms": self.prepare_speech_ms,
            "tts_ms": self.tts_ms,
            "upload_ms": self.upload_ms,
            "total_ms": self.total_ms,
            "within_target": self.within_target,
        }


@dataclass
class CostMetrics:
    """Cost breakdown for voice processing."""

    # Current pricing (as of Feb 2026)
    # Whisper: $0.006/minute
    # TTS: $15/1M characters (tts-1), $30/1M (tts-1-hd)
    # OTTO: ~$0.01 per interaction (estimated)

    stt_cost: float = 0.0
    """STT cost in USD."""

    tts_cost: float = 0.0
    """TTS cost in USD."""

    processing_cost: float = 0.0
    """Core processing cost in USD."""

    total_cost: float = 0.0
    """Total cost in USD."""

    audio_duration_seconds: float = 0.0
    """Input audio duration."""

    output_characters: int = 0
    """Output text character count."""

    @classmethod
    def calculate(
        cls,
        audio_duration_seconds: float,
        output_characters: int,
        processing_cost: float = 0.01,
        tts_model: str = "tts-1",
    ) -> "CostMetrics":
        """
        Calculate costs for a voice interaction.

        Args:
            audio_duration_seconds: Input audio duration
            output_characters: Output text character count
            processing_cost: OTTO processing cost estimate
            tts_model: TTS model used

        Returns:
            CostMetrics with calculated costs
        """
        # Whisper: $0.006/minute
        stt_cost = (audio_duration_seconds / 60) * 0.006

        # TTS pricing per million characters
        tts_rates = {
            "tts-1": 15.0 / 1_000_000,
            "tts-1-hd": 30.0 / 1_000_000,
        }
        tts_cost = output_characters * tts_rates.get(tts_model, 15.0 / 1_000_000)

        return cls(
            stt_cost=stt_cost,
            tts_cost=tts_cost,
            processing_cost=processing_cost,
            total_cost=stt_cost + tts_cost + processing_cost,
            audio_duration_seconds=audio_duration_seconds,
            output_characters=output_characters,
        )


@dataclass
class VoiceMetricsSnapshot:
    """Point-in-time metrics snapshot."""

    timestamp: datetime
    latency: LatencyMetrics
    cost: CostMetrics
    success: bool
    error: Optional[str] = None
    source_id: str = ""


class VoiceMetricsCollector:
    """
    Collects and aggregates voice processing metrics.

    Target: <10s latency, ~$0.22/user/day (20 interactions)
    """

    def __init__(self, window_size: int = 100):
        """
        Initialize metrics collector.

        Args:
            window_size: Number of snapshots to keep for aggregation
        """
        self._snapshots: deque[VoiceMetricsSnapshot] = deque(maxlen=window_size)
        self._total_interactions = 0
        self._total_success = 0
        self._total_cost = 0.0

    def record(
        self,
        latency: LatencyMetrics,
        cost: CostMetrics,
        success: bool,
        error: Optional[str] = None,
        source_id: str = "",
    ) -> VoiceMetricsSnapshot:
        """
        Record a voice interaction.

        Args:
            latency: Latency metrics
            cost: Cost metrics
            success: Whether interaction succeeded
            error: Error message if failed
            source_id: Source identifier

        Returns:
            Created snapshot
        """
        snapshot = VoiceMetricsSnapshot(
            timestamp=datetime.utcnow(),
            latency=latency,
            cost=cost,
            success=success,
            error=error,
            source_id=source_id,
        )

        self._snapshots.append(snapshot)
        self._total_interactions += 1
        self._total_cost += cost.total_cost

        if success:
            self._total_success += 1

        return snapshot

    def get_summary(self) -> dict:
        """Get metrics summary."""
        if not self._snapshots:
            return {
                "total_interactions": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "avg_cost_usd": 0.0,
                "total_cost_usd": 0.0,
                "within_target_rate": 0.0,
            }

        latencies = [s.latency.total_ms for s in self._snapshots]
        costs = [s.cost.total_cost for s in self._snapshots]
        within_target = sum(1 for s in self._snapshots if s.latency.within_target)

        return {
            "total_interactions": self._total_interactions,
            "success_rate": self._total_success / self._total_interactions,
            "avg_latency_ms": statistics.mean(latencies),
            "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0],
            "avg_cost_usd": statistics.mean(costs),
            "total_cost_usd": self._total_cost,
            "within_target_rate": within_target / len(self._snapshots),
        }

    def get_cost_projection(self, interactions_per_day: int = 20) -> dict:
        """
        Project costs based on current metrics.

        Args:
            interactions_per_day: Expected daily interactions per user

        Returns:
            Cost projections
        """
        summary = self.get_summary()
        avg_cost = summary["avg_cost_usd"]

        return {
            "cost_per_interaction": avg_cost,
            "cost_per_user_day": avg_cost * interactions_per_day,
            "cost_per_user_month": avg_cost * interactions_per_day * 30,
            "target_per_user_day": 0.22,  # Target from plan
            "within_budget": avg_cost * interactions_per_day <= 0.22,
        }

    def get_latency_breakdown(self) -> dict:
        """Get average latency breakdown by phase."""
        if not self._snapshots:
            return {}

        return {
            "stt_ms": statistics.mean(s.latency.stt_ms for s in self._snapshots),
            "processing_ms": statistics.mean(s.latency.processing_ms for s in self._snapshots),
            "prepare_speech_ms": statistics.mean(s.latency.prepare_speech_ms for s in self._snapshots),
            "tts_ms": statistics.mean(s.latency.tts_ms for s in self._snapshots),
            "upload_ms": statistics.mean(s.latency.upload_ms for s in self._snapshots),
        }


class LatencyTimer:
    """Context manager for timing operations."""

    def __init__(self):
        self._start: Optional[float] = None
        self._end: Optional[float] = None

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self._end = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        """Elapsed time in milliseconds."""
        if self._start is None or self._end is None:
            return 0.0
        return (self._end - self._start) * 1000


# Global metrics collector
_metrics_collector: Optional[VoiceMetricsCollector] = None


def get_metrics_collector() -> VoiceMetricsCollector:
    """Get global metrics collector (lazy init)."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = VoiceMetricsCollector()
    return _metrics_collector


def record_voice_interaction(
    latency: LatencyMetrics,
    cost: CostMetrics,
    success: bool,
    error: Optional[str] = None,
    source_id: str = "",
) -> VoiceMetricsSnapshot:
    """Convenience function to record voice interaction."""
    return get_metrics_collector().record(
        latency=latency,
        cost=cost,
        success=success,
        error=error,
        source_id=source_id,
    )
