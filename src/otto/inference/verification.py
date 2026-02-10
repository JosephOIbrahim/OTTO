"""
Tier 2: Determinism Verification
================================

Multi-trial inference verification for detecting non-determinism.

This module provides probabilistic detection of non-determinism by:
1. Running identical queries multiple times
2. Comparing results to detect divergence
3. Using consensus mechanisms when divergence occurs
4. Tracking divergence patterns for analysis

Context:
Tier 2 cannot GUARANTEE determinism (that requires kernel-level control),
but it can DETECT when non-determinism occurs, enabling:
- Flagging unreliable results
- Falling back to cached or local inference
- Building confidence metrics over time

Use Cases:
- Critical decisions that need verification
- Building trust metrics for API backends
- Identifying when to upgrade to Tier 3
"""

import asyncio
import hashlib
import difflib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Tuple
from collections import Counter

from .backends.base import InferenceBackend, InferenceResponse


class ConsensusStrategy(Enum):
    """Strategy for resolving divergent results."""
    MAJORITY = "majority"       # Most common response wins
    FIRST = "first"             # First response wins (fastest)
    STRICTEST = "strictest"     # Require unanimous agreement or fail
    SHORTEST = "shortest"       # Shortest response (likely most focused)
    LONGEST = "longest"         # Longest response (likely most complete)


class DivergenceType(Enum):
    """Classification of divergence severity."""
    NONE = "none"               # Bit-identical
    TRIVIAL = "trivial"         # Whitespace/punctuation only
    MINOR = "minor"             # Small wording differences
    MODERATE = "moderate"       # Different phrasing, same meaning
    MAJOR = "major"             # Substantially different content
    COMPLETE = "complete"       # Completely different responses


@dataclass
class VerificationResult:
    """
    Result from verified inference.

    Attributes:
        response: The final response (from consensus if diverged)
        verified: True if all trials produced identical results
        trials: Number of trials run
        divergence_type: Classification of divergence
        divergence_score: Quantified divergence (0.0 = identical, 1.0 = complete)
        consensus_strategy: Strategy used to select response
        all_responses: All responses from trials (for analysis)
        latency_ms: Total verification latency
        confidence: Confidence in the result (based on agreement)
        metadata: Additional verification metadata
    """
    response: str
    verified: bool
    trials: int
    divergence_type: DivergenceType = DivergenceType.NONE
    divergence_score: float = 0.0
    consensus_strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY
    all_responses: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """Hash of the final response."""
        return hashlib.sha256(self.response.encode()).hexdigest()[:32]

    @property
    def is_unanimous(self) -> bool:
        """Check if all trials produced identical results."""
        return self.divergence_type == DivergenceType.NONE

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "response": self.response,
            "verified": self.verified,
            "trials": self.trials,
            "divergence_type": self.divergence_type.value,
            "divergence_score": self.divergence_score,
            "consensus_strategy": self.consensus_strategy.value,
            "latency_ms": self.latency_ms,
            "confidence": self.confidence,
            "content_hash": self.content_hash,
            "is_unanimous": self.is_unanimous,
            "metadata": self.metadata,
        }


@dataclass
class DivergenceAnalysis:
    """
    Detailed analysis of divergence between responses.

    Attributes:
        responses: The responses being compared
        unique_count: Number of unique responses
        similarity_matrix: Pairwise similarity scores
        edit_distances: Pairwise edit distances
        common_prefix_len: Length of common prefix
        common_suffix_len: Length of common suffix
        divergence_point: Character index where divergence begins
        diff_summary: Human-readable diff summary
    """
    responses: List[str]
    unique_count: int
    similarity_matrix: List[List[float]] = field(default_factory=list)
    edit_distances: List[List[int]] = field(default_factory=list)
    common_prefix_len: int = 0
    common_suffix_len: int = 0
    divergence_point: int = 0
    diff_summary: str = ""

    @classmethod
    def analyze(cls, responses: List[str]) -> 'DivergenceAnalysis':
        """
        Perform full divergence analysis on a set of responses.

        Args:
            responses: List of response strings to analyze

        Returns:
            DivergenceAnalysis with computed metrics
        """
        if not responses:
            return cls(responses=[], unique_count=0)

        unique_responses = list(set(responses))
        unique_count = len(unique_responses)

        # Compute similarity matrix
        n = len(responses)
        similarity_matrix = [[0.0] * n for _ in range(n)]
        edit_distances = [[0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i == j:
                    similarity_matrix[i][j] = 1.0
                    edit_distances[i][j] = 0
                else:
                    # Use SequenceMatcher for similarity
                    similarity_matrix[i][j] = difflib.SequenceMatcher(
                        None, responses[i], responses[j]
                    ).ratio()
                    # Levenshtein-like distance via SequenceMatcher
                    edit_distances[i][j] = _edit_distance(responses[i], responses[j])

        # Find common prefix/suffix
        common_prefix_len = _common_prefix_length(responses)
        common_suffix_len = _common_suffix_length(responses)

        # Find divergence point
        divergence_point = common_prefix_len

        # Generate diff summary
        diff_summary = _generate_diff_summary(responses)

        return cls(
            responses=responses,
            unique_count=unique_count,
            similarity_matrix=similarity_matrix,
            edit_distances=edit_distances,
            common_prefix_len=common_prefix_len,
            common_suffix_len=common_suffix_len,
            divergence_point=divergence_point,
            diff_summary=diff_summary,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "unique_count": self.unique_count,
            "common_prefix_len": self.common_prefix_len,
            "common_suffix_len": self.common_suffix_len,
            "divergence_point": self.divergence_point,
            "diff_summary": self.diff_summary,
        }


class DeterminismVerifier:
    """
    Multi-trial verification for detecting non-determinism.

    This verifier runs multiple inference trials and compares results
    to detect when the backend produces non-deterministic output.

    Example:
        >>> verifier = DeterminismVerifier(backend, n_trials=3)
        >>> result = await verifier.verify("What is 2+2?")
        >>> if result.verified:
        ...     print("Deterministic!")
        ... else:
        ...     print(f"Divergence detected: {result.divergence_type}")

    Configuration:
        n_trials: Number of times to run each query (default: 3)
        tolerance: Maximum divergence score to consider "verified" (default: 0.0)
        consensus_strategy: How to pick final response when diverged
        parallel: Whether to run trials in parallel (faster but more load)
    """

    def __init__(
        self,
        backend: InferenceBackend,
        n_trials: int = 3,
        tolerance: float = 0.0,
        consensus_strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY,
        parallel: bool = True,
        timeout_per_trial: float = 120.0,
    ):
        """
        Initialize the verifier.

        Args:
            backend: The inference backend to verify
            n_trials: Number of trials per verification (2-10)
            tolerance: Divergence tolerance (0.0 = exact match required)
            consensus_strategy: How to resolve divergent results
            parallel: Run trials in parallel (faster, more API load)
            timeout_per_trial: Timeout for each trial in seconds
        """
        if not 2 <= n_trials <= 10:
            raise ValueError(f"n_trials must be 2-10, got {n_trials}")
        if not 0.0 <= tolerance <= 1.0:
            raise ValueError(f"tolerance must be 0.0-1.0, got {tolerance}")

        self._backend = backend
        self._n_trials = n_trials
        self._tolerance = tolerance
        self._consensus_strategy = consensus_strategy
        self._parallel = parallel
        self._timeout = timeout_per_trial

        # Statistics
        self._total_verifications = 0
        self._unanimous_count = 0
        self._divergence_count = 0
        self._divergence_history: List[DivergenceAnalysis] = []

    @property
    def backend(self) -> InferenceBackend:
        """Get the backend being verified."""
        return self._backend

    @property
    def n_trials(self) -> int:
        """Get number of trials."""
        return self._n_trials

    @property
    def stats(self) -> Dict[str, Any]:
        """Get verification statistics."""
        return {
            "total_verifications": self._total_verifications,
            "unanimous_count": self._unanimous_count,
            "divergence_count": self._divergence_count,
            "unanimity_rate": (
                self._unanimous_count / max(1, self._total_verifications)
            ),
            "n_trials": self._n_trials,
            "tolerance": self._tolerance,
        }

    async def verify(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> VerificationResult:
        """
        Run verified inference with multiple trials.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 recommended)
            max_tokens: Maximum tokens to generate
            seed: Random seed (same seed used for all trials)
            **kwargs: Additional backend parameters

        Returns:
            VerificationResult with consensus response and divergence info
        """
        import time
        start_time = time.perf_counter()

        # Run trials
        if self._parallel:
            responses = await self._run_parallel_trials(
                prompt, system_prompt, temperature, max_tokens, seed, **kwargs
            )
        else:
            responses = await self._run_sequential_trials(
                prompt, system_prompt, temperature, max_tokens, seed, **kwargs
            )

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract response strings
        response_strings = [r.content for r in responses]

        # Analyze divergence
        analysis = DivergenceAnalysis.analyze(response_strings)

        # Classify divergence
        divergence_type, divergence_score = self._classify_divergence(analysis)

        # Determine if verified (within tolerance)
        verified = divergence_score <= self._tolerance

        # Select final response via consensus
        final_response = self._apply_consensus(response_strings, analysis)

        # Calculate confidence
        confidence = self._calculate_confidence(analysis, divergence_score)

        # Update statistics
        self._total_verifications += 1
        if divergence_type == DivergenceType.NONE:
            self._unanimous_count += 1
        else:
            self._divergence_count += 1
            self._divergence_history.append(analysis)

        return VerificationResult(
            response=final_response,
            verified=verified,
            trials=self._n_trials,
            divergence_type=divergence_type,
            divergence_score=divergence_score,
            consensus_strategy=self._consensus_strategy,
            all_responses=response_strings,
            latency_ms=latency_ms,
            confidence=confidence,
            metadata={
                "analysis": analysis.to_dict(),
                "backend": self._backend.name,
                "parallel": self._parallel,
            },
        )

    async def _run_parallel_trials(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        seed: Optional[int],
        **kwargs: Any,
    ) -> List[InferenceResponse]:
        """Run all trials in parallel."""
        tasks = [
            self._run_single_trial(
                prompt, system_prompt, temperature, max_tokens, seed, **kwargs
            )
            for _ in range(self._n_trials)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        responses = []
        for r in results:
            if isinstance(r, Exception):
                # Create error response
                responses.append(InferenceResponse(
                    content=f"[ERROR: {r}]",
                    model=self._backend.model_id,
                    finish_reason="error",
                ))
            else:
                responses.append(r)

        return responses

    async def _run_sequential_trials(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        seed: Optional[int],
        **kwargs: Any,
    ) -> List[InferenceResponse]:
        """Run trials one at a time."""
        responses = []
        for _ in range(self._n_trials):
            try:
                response = await self._run_single_trial(
                    prompt, system_prompt, temperature, max_tokens, seed, **kwargs
                )
                responses.append(response)
            except Exception as e:
                responses.append(InferenceResponse(
                    content=f"[ERROR: {e}]",
                    model=self._backend.model_id,
                    finish_reason="error",
                ))
        return responses

    async def _run_single_trial(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        seed: Optional[int],
        **kwargs: Any,
    ) -> InferenceResponse:
        """Run a single inference trial."""
        return await asyncio.wait_for(
            self._backend.infer(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                seed=seed,
                **kwargs,
            ),
            timeout=self._timeout,
        )

    def _classify_divergence(
        self,
        analysis: DivergenceAnalysis,
    ) -> Tuple[DivergenceType, float]:
        """
        Classify the type and severity of divergence.

        Returns:
            Tuple of (DivergenceType, score from 0.0 to 1.0)
        """
        if analysis.unique_count == 1:
            return DivergenceType.NONE, 0.0

        # Calculate average similarity
        n = len(analysis.responses)
        if n < 2:
            return DivergenceType.NONE, 0.0

        total_sim = 0.0
        count = 0
        for i in range(n):
            for j in range(i + 1, n):
                total_sim += analysis.similarity_matrix[i][j]
                count += 1

        avg_similarity = total_sim / max(1, count)
        divergence_score = 1.0 - avg_similarity

        # Classify by similarity threshold
        if avg_similarity >= 0.99:
            # Check if just whitespace/punctuation
            normalized = [_normalize_whitespace(r) for r in analysis.responses]
            if len(set(normalized)) == 1:
                return DivergenceType.TRIVIAL, divergence_score

        if avg_similarity >= 0.95:
            return DivergenceType.MINOR, divergence_score
        elif avg_similarity >= 0.80:
            return DivergenceType.MODERATE, divergence_score
        elif avg_similarity >= 0.50:
            return DivergenceType.MAJOR, divergence_score
        else:
            return DivergenceType.COMPLETE, divergence_score

    def _apply_consensus(
        self,
        responses: List[str],
        analysis: DivergenceAnalysis,
    ) -> str:
        """
        Select final response based on consensus strategy.

        Args:
            responses: All response strings
            analysis: Divergence analysis

        Returns:
            Selected response string
        """
        if not responses:
            return ""

        if analysis.unique_count == 1:
            return responses[0]

        strategy = self._consensus_strategy

        if strategy == ConsensusStrategy.FIRST:
            return responses[0]

        elif strategy == ConsensusStrategy.SHORTEST:
            return min(responses, key=len)

        elif strategy == ConsensusStrategy.LONGEST:
            return max(responses, key=len)

        elif strategy == ConsensusStrategy.STRICTEST:
            # All must match or return empty/error indicator
            if analysis.unique_count == 1:
                return responses[0]
            else:
                return f"[VERIFICATION FAILED: {analysis.unique_count} unique responses]"

        else:  # MAJORITY (default)
            # Find most common response
            counter = Counter(responses)
            most_common = counter.most_common(1)
            if most_common:
                return most_common[0][0]
            return responses[0]

    def _calculate_confidence(
        self,
        analysis: DivergenceAnalysis,
        divergence_score: float,
    ) -> float:
        """
        Calculate confidence score based on agreement.

        Returns:
            Confidence from 0.0 (no confidence) to 1.0 (full confidence)
        """
        if analysis.unique_count == 1:
            return 1.0

        # Base confidence on:
        # 1. How many responses agree
        # 2. How similar the responses are

        # Agreement ratio
        counter = Counter(analysis.responses)
        most_common_count = counter.most_common(1)[0][1]
        agreement_ratio = most_common_count / len(analysis.responses)

        # Similarity factor
        similarity_factor = 1.0 - divergence_score

        # Combined confidence
        confidence = (agreement_ratio * 0.6) + (similarity_factor * 0.4)

        return max(0.0, min(1.0, confidence))

    def get_divergence_report(self) -> Dict[str, Any]:
        """
        Generate a report on observed divergences.

        Returns:
            Dict with divergence patterns and statistics
        """
        if not self._divergence_history:
            return {
                "total_divergences": 0,
                "patterns": [],
                "summary": "No divergences observed",
            }

        # Analyze patterns
        avg_unique = sum(a.unique_count for a in self._divergence_history) / len(self._divergence_history)

        return {
            "total_divergences": len(self._divergence_history),
            "total_verifications": self._total_verifications,
            "divergence_rate": self._divergence_count / max(1, self._total_verifications),
            "avg_unique_responses": avg_unique,
            "patterns": [a.to_dict() for a in self._divergence_history[-10:]],  # Last 10
            "summary": (
                f"{self._divergence_count}/{self._total_verifications} verifications "
                f"showed divergence ({self._divergence_count/max(1,self._total_verifications)*100:.1f}%)"
            ),
        }


class VerifiedInferenceWrapper:
    """
    Wrapper that adds verification to any backend.

    This wrapper intercepts inference calls and optionally verifies
    them based on criticality level.

    Example:
        >>> backend = ClaudeBackend()
        >>> verified = VerifiedInferenceWrapper(backend)
        >>>
        >>> # Normal inference (no verification)
        >>> result = await verified.infer("Hello")
        >>>
        >>> # Verified inference
        >>> result = await verified.infer_verified("Critical question")
        >>> print(result.verified)
    """

    def __init__(
        self,
        backend: InferenceBackend,
        n_trials: int = 3,
        auto_verify_threshold: str = "high",
    ):
        """
        Initialize the verified wrapper.

        Args:
            backend: The backend to wrap
            n_trials: Number of verification trials
            auto_verify_threshold: Criticality level that triggers auto-verification
                                   ("low", "normal", "high", "critical", "none")
        """
        self._backend = backend
        self._verifier = DeterminismVerifier(backend, n_trials=n_trials)
        self._auto_verify_threshold = auto_verify_threshold

        # Criticality levels
        self._criticality_levels = {
            "low": 0,
            "normal": 1,
            "high": 2,
            "critical": 3,
        }
        self._threshold_level = self._criticality_levels.get(auto_verify_threshold, 99)

    @property
    def backend(self) -> InferenceBackend:
        """Get the underlying backend."""
        return self._backend

    @property
    def verifier(self) -> DeterminismVerifier:
        """Get the verifier."""
        return self._verifier

    async def infer(
        self,
        prompt: str,
        criticality: str = "normal",
        **kwargs: Any,
    ) -> InferenceResponse:
        """
        Perform inference, auto-verifying if criticality exceeds threshold.

        Args:
            prompt: The prompt
            criticality: Criticality level ("low", "normal", "high", "critical")
            **kwargs: Additional inference parameters

        Returns:
            InferenceResponse (or VerificationResult if verified)
        """
        crit_level = self._criticality_levels.get(criticality, 1)

        if crit_level >= self._threshold_level and self._auto_verify_threshold != "none":
            # Auto-verify
            result = await self._verifier.verify(prompt, **kwargs)
            # Convert to InferenceResponse
            return InferenceResponse(
                content=result.response,
                model=self._backend.model_id,
                finish_reason="stop" if result.verified else "unverified",
                latency_ms=result.latency_ms,
                metadata={
                    "verified": result.verified,
                    "confidence": result.confidence,
                    "divergence_type": result.divergence_type.value,
                },
            )
        else:
            # Normal inference
            return await self._backend.infer(prompt, **kwargs)

    async def infer_verified(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> VerificationResult:
        """
        Always perform verified inference.

        Args:
            prompt: The prompt
            **kwargs: Additional inference parameters

        Returns:
            VerificationResult with full verification data
        """
        return await self._verifier.verify(prompt, **kwargs)


# =============================================================================
# Helper Functions
# =============================================================================

def _edit_distance(s1: str, s2: str) -> int:
    """
    Compute Levenshtein edit distance between two strings.

    Uses dynamic programming for O(mn) time and O(min(m,n)) space.
    """
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))

    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (0 if c1 == c2 else 1)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def _common_prefix_length(strings: List[str]) -> int:
    """Find length of common prefix across all strings."""
    if not strings:
        return 0
    if len(strings) == 1:
        return len(strings[0])

    min_len = min(len(s) for s in strings)
    prefix_len = 0

    for i in range(min_len):
        chars = set(s[i] for s in strings)
        if len(chars) == 1:
            prefix_len += 1
        else:
            break

    return prefix_len


def _common_suffix_length(strings: List[str]) -> int:
    """Find length of common suffix across all strings."""
    if not strings:
        return 0
    if len(strings) == 1:
        return len(strings[0])

    reversed_strings = [s[::-1] for s in strings]
    return _common_prefix_length(reversed_strings)


def _normalize_whitespace(s: str) -> str:
    """Normalize whitespace for comparison."""
    return " ".join(s.split())


def _generate_diff_summary(responses: List[str]) -> str:
    """Generate a human-readable diff summary."""
    if len(responses) < 2:
        return "Single response, no diff"

    if len(set(responses)) == 1:
        return "All responses identical"

    # Compare first two different responses
    unique = list(dict.fromkeys(responses))  # Preserve order, remove dupes
    if len(unique) < 2:
        return "All responses identical"

    r1, r2 = unique[0], unique[1]

    # Generate unified diff
    diff = list(difflib.unified_diff(
        r1.splitlines(keepends=True),
        r2.splitlines(keepends=True),
        lineterm="",
        n=1,  # Context lines
    ))

    if not diff:
        return "Responses differ but no line-level diff"

    # Summarize
    additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    return f"{additions} additions, {deletions} deletions across responses"
