"""Conversation compaction manager.

Tracks token usage across a conversation and triggers compaction
when approaching context limits.  Uses the native Anthropic
Compaction API (beta) — no custom summarization.

Compaction strategy:

1. Track cumulative input+output tokens per exchange
2. When usage exceeds threshold (default: 80% of context window),
   signal that compaction should happen on next exchange
3. After compaction, reset token tracking

[He2025]: Token tracking uses Kahan summation for numerical
stability over many exchanges (potentially thousands in a long
session).
"""

from __future__ import annotations

from dataclasses import dataclass

from otto.core.determinism.kahan import KahanAccumulator


@dataclass(frozen=True)
class CompactionConfig:
    """Configuration for compaction behavior.

    Attributes:
        max_context_tokens: Maximum context window size.
        compaction_threshold: Fraction of context that triggers
            compaction (0.0–1.0).
        min_exchanges_before_compaction: Minimum exchanges before
            compaction is considered (avoids compacting short
            conversations).
    """

    max_context_tokens: int = 1_000_000
    compaction_threshold: float = 0.80
    min_exchanges_before_compaction: int = 5


@dataclass(frozen=True)
class CompactionStatus:
    """Current compaction state snapshot.

    Attributes:
        total_tokens: Estimated total tokens in conversation.
        threshold_tokens: Token count that triggers compaction.
        exchange_count: Number of exchanges tracked.
        should_compact: Whether compaction is recommended.
        utilization: Fraction of context used (0.0–1.0).
    """

    total_tokens: float
    threshold_tokens: int
    exchange_count: int
    should_compact: bool
    utilization: float


class CompactionManager:
    """Tracks conversation token usage and signals compaction need.

    This manager does NOT perform compaction itself — it signals
    when compaction should happen.  The actual compaction call
    goes through OTTOClient using the Anthropic Compaction API.

    Args:
        config: Compaction configuration.  Defaults to standard.
    """

    def __init__(self, config: CompactionConfig | None = None) -> None:
        self._config = config or CompactionConfig()
        self._token_acc = KahanAccumulator()
        self._exchange_count: int = 0
        self._threshold_tokens: int = int(
            self._config.max_context_tokens
            * self._config.compaction_threshold
        )

    @property
    def config(self) -> CompactionConfig:
        """The active compaction configuration."""
        return self._config

    def record_exchange(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> CompactionStatus:
        """Record token usage from an exchange.

        Tracks cumulative tokens and determines if compaction
        should be triggered.

        Args:
            input_tokens: Tokens used for input in this exchange.
            output_tokens: Tokens used for output in this exchange.

        Returns:
            CompactionStatus indicating current state.
        """
        self._token_acc.add(float(input_tokens + output_tokens))
        self._exchange_count += 1
        return self.status()

    def status(self) -> CompactionStatus:
        """Get current compaction status without recording.

        Returns:
            CompactionStatus with current state.
        """
        total = self._token_acc.total()
        max_ctx = self._config.max_context_tokens
        utilization = total / max_ctx if max_ctx > 0 else 0.0

        should_compact = (
            total >= self._threshold_tokens
            and self._exchange_count
            >= self._config.min_exchanges_before_compaction
        )

        return CompactionStatus(
            total_tokens=total,
            threshold_tokens=self._threshold_tokens,
            exchange_count=self._exchange_count,
            should_compact=should_compact,
            utilization=utilization,
        )

    def reset(self) -> None:
        """Reset token tracking after successful compaction.

        Clears the token accumulator and exchange count so the
        min_exchanges gate re-arms for the next compaction cycle.
        """
        self._token_acc.reset()
        self._exchange_count = 0
