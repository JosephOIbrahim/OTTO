"""
Determinism Utilities for OTTO OS
=================================

Implements ThinkingMachines [He2025] principles for application-level determinism.

Core insight from [He2025]: The same input should produce the same output,
regardless of batch size, system load, or other runtime factors.

This module provides deterministic alternatives to common Python operations
that can exhibit non-deterministic behavior:

1. max(dict.items()) - tie-breaking is undefined
2. dict iteration order - while Python 3.7+ maintains insertion order,
   dicts built from different sources may have different orderings
3. set iteration - explicitly unordered
4. floating-point summation - order-dependent due to FP precision

Constants:
    COGNITIVE_TILE_SIZE: Fixed batch size for memory operations (32)
    DETERMINISM_SEED: Fixed seed for any randomized operations (0xCAFEBABE)

References:
    [He2025] He, Horace and Thinking Machines Lab, "Defeating Nondeterminism
    in LLM Inference", Sep 2025.
    https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
"""

from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, TypeVar

# =============================================================================
# Constants (FIXED, never change)
# =============================================================================

COGNITIVE_TILE_SIZE = 32
"""Fixed tile size for batched operations. Never change this value."""

DETERMINISM_SEED = 0xCAFEBABE
"""Fixed seed for any operations requiring randomization."""

HASH_ALGORITHM = "sha256"
"""Hash algorithm for state checksums."""


# =============================================================================
# Type Variables
# =============================================================================

K = TypeVar('K')
V = TypeVar('V')


# =============================================================================
# Deterministic max() with Tie-Breaking
# =============================================================================

def sorted_max(
    d: Dict[K, V],
    key: Callable[[Tuple[K, V]], Any] = None,
    tiebreaker: Callable[[K], Any] = None
) -> Tuple[K, V]:
    """
    Return max item from dict with deterministic tie-breaking.

    When multiple items have the same max value, ties are broken by:
    1. Custom tiebreaker function if provided
    2. Lexicographic ordering of keys (default)

    This ensures the same input dict always produces the same result,
    unlike the built-in max() which has undefined tie-breaking behavior.

    Args:
        d: Dictionary to find max in
        key: Function to extract comparison value (default: item[1])
        tiebreaker: Function to break ties on keys (default: lexicographic)

    Returns:
        (key, value) tuple with maximum value

    Raises:
        ValueError: If dict is empty

    Example:
        >>> d = {"a": 0.5, "b": 0.5, "c": 0.3}
        >>> sorted_max(d)  # Always returns ("a", 0.5), never ("b", 0.5)
        ('a', 0.5)

    ThinkingMachines [He2025]: Fixed evaluation order ensures reproducibility.
    """
    if not d:
        raise ValueError("sorted_max() arg is an empty dict")

    if key is None:
        key = lambda x: x[1]

    if tiebreaker is None:
        tiebreaker = lambda k: k

    # Sort by: (value DESC, tiebreaker ASC) to get deterministic ordering
    sorted_items = sorted(
        d.items(),
        key=lambda x: (-key(x) if isinstance(key(x), (int, float)) else key(x), tiebreaker(x[0]))
    )

    # For numeric keys, we want highest value first, then lowest tiebreaker
    # Re-sort properly: max value first, then tiebreaker for ties
    items = list(d.items())
    max_value = max(key(item) for item in items)

    # Get all items with max value
    max_items = [item for item in items if key(item) == max_value]

    # Sort by tiebreaker
    max_items_sorted = sorted(max_items, key=lambda x: tiebreaker(x[0]))

    return max_items_sorted[0]


def sorted_max_value(d: Dict[K, V]) -> V:
    """
    Return max value from dict values with deterministic ordering.

    Simple wrapper around sorted_max for when you only need the value.
    """
    if not d:
        raise ValueError("sorted_max_value() arg is an empty dict")
    return sorted_max(d)[1]


def sorted_max_key(d: Dict[K, V]) -> K:
    """
    Return key with max value from dict with deterministic tie-breaking.

    Simple wrapper around sorted_max for when you only need the key.
    """
    if not d:
        raise ValueError("sorted_max_key() arg is an empty dict")
    return sorted_max(d)[0]


# =============================================================================
# Kahan Summation (Batch-Invariant)
# =============================================================================

def kahan_sum(values) -> float:
    """
    Compute sum with Kahan compensated summation for batch invariance.

    Sorts values before summing to ensure the same result regardless
    of input order. Uses Kahan's algorithm to minimize floating-point
    accumulation errors.

    Args:
        values: Iterable of numeric values

    Returns:
        Sum of all values

    Example:
        >>> values = [0.1, 0.2, 0.3]
        >>> kahan_sum(values)  # More accurate than sum()
        0.6

    ThinkingMachines [He2025]: Fixed reduction order + compensated accumulation.
    """
    # Convert to list and sort for deterministic order
    sorted_values = sorted(list(values))

    total = 0.0
    compensation = 0.0

    for value in sorted_values:
        y = value - compensation
        t = total + y
        compensation = (t - total) - y
        total = t

    return total


def kahan_weighted_sum(items: List[Tuple[float, float]]) -> float:
    """
    Compute weighted sum with Kahan compensation.

    Items are sorted by (value, weight) before computation for determinism.

    Args:
        items: List of (value, weight) tuples

    Returns:
        Sum of value * weight for all items

    Example:
        >>> items = [(0.5, 0.6), (0.3, 0.4)]
        >>> kahan_weighted_sum(items)
        0.42
    """
    # Sort for deterministic order
    sorted_items = sorted(items)

    products = [v * w for v, w in sorted_items]
    return kahan_sum(products)


# =============================================================================
# Deterministic Collection Iteration
# =============================================================================

def sorted_set_to_list(s: set) -> list:
    """
    Convert set to sorted list for deterministic iteration.

    Sets are explicitly unordered in Python. This function ensures
    deterministic ordering by sorting the elements.

    Args:
        s: Set to convert

    Returns:
        Sorted list of set elements

    Example:
        >>> s = {"c", "a", "b"}
        >>> sorted_set_to_list(s)
        ['a', 'b', 'c']

    ThinkingMachines [He2025]: Sets are non-deterministic by design.
    """
    return sorted(list(s))


def deterministic_dict_iter(d: Dict[K, V]) -> Iterator[Tuple[K, V]]:
    """
    Iterate dict items in sorted key order.

    While Python 3.7+ dicts maintain insertion order, dicts built from
    different sources may have different orderings. This ensures
    deterministic iteration regardless of how the dict was constructed.

    Args:
        d: Dictionary to iterate

    Yields:
        (key, value) tuples in sorted key order

    Example:
        >>> d = {"b": 1, "a": 2}
        >>> list(deterministic_dict_iter(d))
        [('a', 2), ('b', 1)]
    """
    for key in sorted(d.keys()):
        yield (key, d[key])


def deterministic_dict_values(d: Dict[K, V]) -> List[V]:
    """
    Get dict values in sorted key order.

    Args:
        d: Dictionary

    Returns:
        List of values in sorted key order
    """
    return [d[k] for k in sorted(d.keys())]


# =============================================================================
# Aggregation Strategies (5 strategies per v7.1.0 spec)
# =============================================================================

def aggregate_max(values) -> float:
    """
    MAX aggregation strategy.

    Returns the maximum value. Deterministic (single pass, order-independent).

    Args:
        values: Iterable of numeric values

    Returns:
        Maximum value, or 0.0 if empty
    """
    value_list = list(values)
    if not value_list:
        return 0.0
    return max(value_list)


def aggregate_mean(values) -> float:
    """
    MEAN aggregation strategy.

    Uses Kahan summation for batch-invariant accumulation.

    Args:
        values: Iterable of numeric values

    Returns:
        Arithmetic mean, or 0.0 if empty
    """
    value_list = list(values)
    if not value_list:
        return 0.0
    return kahan_sum(value_list) / len(value_list)


def aggregate_weighted_mean(values: List[float], weights: List[float]) -> float:
    """
    WEIGHTED_MEAN aggregation strategy.

    Sorts by (value, weight) before aggregation for determinism.

    Args:
        values: List of values
        weights: List of corresponding weights

    Returns:
        Weighted mean, or 0.0 if empty
    """
    if not values or not weights:
        return 0.0

    if len(values) != len(weights):
        raise ValueError("values and weights must have same length")

    # Pair and sort for determinism
    pairs = sorted(zip(values, weights))

    numerator = kahan_sum([v * w for v, w in pairs])
    denominator = kahan_sum([w for _, w in pairs])

    if denominator == 0:
        return 0.0

    return numerator / denominator


def aggregate_decay_mean(values, decay: float = 0.99) -> float:
    """
    DECAY_MEAN aggregation strategy.

    Applies exponential decay based on position (sorted order).
    Earlier values (in sorted order) get higher weight.

    Args:
        values: Iterable of numeric values
        decay: Decay factor per position (default 0.99)

    Returns:
        Decay-weighted mean, or 0.0 if empty
    """
    sorted_values = sorted(list(values))
    if not sorted_values:
        return 0.0

    weights = [decay ** i for i in range(len(sorted_values))]
    return aggregate_weighted_mean(sorted_values, weights)


def aggregate_threshold_filter(values, threshold: float) -> float:
    """
    THRESHOLD_FILTER aggregation strategy.

    Returns max of values that meet threshold, or 0.0 if none do.

    Args:
        values: Iterable of numeric values
        threshold: Minimum value to include

    Returns:
        Max of filtered values, or 0.0 if none meet threshold
    """
    filtered = [v for v in values if v >= threshold]
    if not filtered:
        return 0.0
    return max(filtered)


# =============================================================================
# Verification Utilities
# =============================================================================

def verify_determinism(func: Callable, *args, n_trials: int = 100, **kwargs) -> bool:
    """
    Verify a function produces deterministic output.

    Runs the function n_trials times and checks that all results are identical.

    Args:
        func: Function to test
        *args: Positional arguments to pass to func
        n_trials: Number of trials (default 100)
        **kwargs: Keyword arguments to pass to func

    Returns:
        True if all trials produced identical results

    Example:
        >>> verify_determinism(sorted_max, {"a": 1, "b": 1})
        True
    """
    results = []
    for _ in range(n_trials):
        result = func(*args, **kwargs)
        results.append(str(result))  # Convert to string for comparison

    return len(set(results)) == 1


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Constants
    'COGNITIVE_TILE_SIZE',
    'DETERMINISM_SEED',
    'HASH_ALGORITHM',

    # Deterministic max
    'sorted_max',
    'sorted_max_value',
    'sorted_max_key',

    # Kahan summation
    'kahan_sum',
    'kahan_weighted_sum',

    # Collection utilities
    'sorted_set_to_list',
    'deterministic_dict_iter',
    'deterministic_dict_values',

    # Aggregation strategies
    'aggregate_max',
    'aggregate_mean',
    'aggregate_weighted_mean',
    'aggregate_decay_mean',
    'aggregate_threshold_filter',

    # Verification
    'verify_determinism',
]
