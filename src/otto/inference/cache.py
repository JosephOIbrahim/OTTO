"""
Deterministic Response Cache
============================

Thread-safe response caching with integrity verification.

[He2025] Principles Applied:
- Deterministic cache key computation (sorted keys, stable serialization)
- Integrity verification via content hashing
- No dynamic eviction strategies that could vary with load
- Fixed evaluation order throughout

The cache provides the core Tier 1 determinism guarantee:
Same prompt + params → Same cached result (after first call)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from threading import RLock
from collections import OrderedDict
import hashlib
import json
import time


def compute_cache_key(
    prompt: str,
    system_prompt: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    model_id: Optional[str] = None,
) -> str:
    """
    Compute deterministic cache key from inference inputs.

    This function is critical for [He2025] compliance. It MUST produce
    identical keys for identical inputs, regardless of:
    - Dictionary insertion order
    - Parameter ordering in function calls
    - System state or load

    [He2025] Compliance:
    - Uses sorted keys for all dictionaries
    - Uses stable JSON serialization (separators, no whitespace variance)
    - Applies SHA-256 for collision resistance

    Args:
        prompt: The user prompt
        system_prompt: Optional system prompt
        params: Optional inference parameters
        model_id: Optional model identifier

    Returns:
        64-character hex string (SHA-256 hash)

    Example:
        >>> key1 = compute_cache_key("Hello", params={"a": 1, "b": 2})
        >>> key2 = compute_cache_key("Hello", params={"b": 2, "a": 1})
        >>> key1 == key2  # Order doesn't matter
        True
    """
    # Build canonical representation
    # CRITICAL: All dictionaries must use sorted keys
    canonical = {
        'prompt': prompt,
        'system_prompt': system_prompt,
        'model_id': model_id,
    }

    if params:
        # Deep sort any nested dictionaries
        canonical['params'] = _deep_sort_dict(params)

    # Serialize with fixed format (no whitespace variance)
    canonical_str = json.dumps(
        canonical,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,  # Consistent encoding
        default=str,  # Handle non-serializable types
    )

    # Hash for fixed-length key
    return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()


def _deep_sort_dict(obj: Any) -> Any:
    """
    Recursively sort dictionary keys for deterministic serialization.

    [He2025] Compliance: Ensures nested structures are consistently ordered.
    """
    if isinstance(obj, dict):
        return {k: _deep_sort_dict(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, (list, tuple)):
        return [_deep_sort_dict(item) for item in obj]
    elif isinstance(obj, set):
        return sorted(_deep_sort_dict(item) for item in obj)
    elif isinstance(obj, frozenset):
        return sorted(_deep_sort_dict(item) for item in obj)
    else:
        return obj


def compute_content_hash(content: str) -> str:
    """
    Compute hash of response content for integrity verification.

    Args:
        content: The response content

    Returns:
        32-character hex string (truncated SHA-256)
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:32]


@dataclass
class CacheEntry:
    """
    A single cache entry with metadata.

    Attributes:
        key: The cache key
        response: The cached response content
        content_hash: SHA-256 hash for integrity verification
        created_at: When the entry was created
        accessed_at: When the entry was last accessed
        access_count: Number of times this entry was accessed
        ttl_seconds: Optional TTL (None = no expiration)
        metadata: Optional additional metadata
    """
    key: str
    response: str
    content_hash: str
    created_at: datetime
    accessed_at: datetime
    access_count: int = 1
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Verify integrity on creation."""
        expected_hash = compute_content_hash(self.response)
        if self.content_hash != expected_hash:
            raise ValueError(
                f"Content hash mismatch: expected {expected_hash}, got {self.content_hash}"
            )

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.ttl_seconds is None:
            return False
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Get age of this entry in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    def verify_integrity(self) -> bool:
        """
        Verify the cached response hasn't been corrupted.

        Returns:
            True if content hash matches, False otherwise
        """
        return self.content_hash == compute_content_hash(self.response)

    def touch(self) -> None:
        """Update access timestamp and count."""
        self.accessed_at = datetime.now(timezone.utc)
        self.access_count += 1


@dataclass
class CacheStats:
    """
    Cache statistics for monitoring and debugging.

    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        size: Current number of entries
        evictions: Number of entries evicted
        integrity_failures: Number of integrity check failures
        oldest_entry_age: Age of oldest entry in seconds
        hit_rate: Ratio of hits to total requests
    """
    hits: int = 0
    misses: int = 0
    size: int = 0
    evictions: int = 0
    integrity_failures: int = 0
    oldest_entry_age: float = 0.0

    @property
    def total_requests(self) -> int:
        """Total number of cache requests."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'size': self.size,
            'evictions': self.evictions,
            'integrity_failures': self.integrity_failures,
            'oldest_entry_age': self.oldest_entry_age,
            'total_requests': self.total_requests,
            'hit_rate': self.hit_rate,
        }


class ResponseCache:
    """
    Thread-safe response cache with deterministic behavior.

    This cache provides the core Tier 1 determinism guarantee:
    after a response is cached, identical queries will always
    return identical results.

    [He2025] Compliance:
    - No dynamic eviction based on load (fixed max_size, LRU order)
    - Deterministic cache key computation
    - Integrity verification on retrieval
    - Thread-safe with explicit locking (no race conditions)

    Example:
        >>> cache = ResponseCache(max_size=1000)
        >>> cache.put("key1", "response1")
        >>> result = cache.get("key1")
        >>> result.response
        'response1'
    """

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: Optional[int] = None,
        verify_on_get: bool = True,
    ):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of entries (LRU eviction when exceeded)
            default_ttl: Default TTL for entries in seconds (None = no expiration)
            verify_on_get: Whether to verify integrity on every get
        """
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._verify_on_get = verify_on_get

        # OrderedDict for LRU ordering
        # CRITICAL: OrderedDict maintains insertion order, enabling
        # deterministic LRU eviction (oldest first)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = RLock()
        self._stats = CacheStats()

    @property
    def stats(self) -> CacheStats:
        """Get current cache statistics."""
        with self._lock:
            self._stats.size = len(self._cache)
            if self._cache:
                oldest = next(iter(self._cache.values()))
                self._stats.oldest_entry_age = oldest.age_seconds
            return self._stats

    def get(self, key: str) -> Optional[CacheEntry]:
        """
        Retrieve an entry from the cache.

        Args:
            key: The cache key (from compute_cache_key)

        Returns:
            CacheEntry if found and valid, None otherwise
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            # Check expiration
            if entry.is_expired:
                self._evict(key)
                self._stats.misses += 1
                return None

            # Verify integrity if enabled
            if self._verify_on_get and not entry.verify_integrity():
                self._stats.integrity_failures += 1
                self._evict(key)
                self._stats.misses += 1
                return None

            # Update access tracking
            entry.touch()

            # Move to end for LRU (most recently used)
            self._cache.move_to_end(key)

            self._stats.hits += 1
            return entry

    def put(
        self,
        key: str,
        response: str,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CacheEntry:
        """
        Store a response in the cache.

        Args:
            key: The cache key (from compute_cache_key)
            response: The response content to cache
            ttl_seconds: Optional TTL override (None uses default)
            metadata: Optional metadata to store with entry

        Returns:
            The created CacheEntry
        """
        now = datetime.now(timezone.utc)
        content_hash = compute_content_hash(response)

        entry = CacheEntry(
            key=key,
            response=response,
            content_hash=content_hash,
            created_at=now,
            accessed_at=now,
            access_count=1,
            ttl_seconds=ttl_seconds if ttl_seconds is not None else self._default_ttl,
            metadata=metadata or {},
        )

        with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                self._evict_oldest()

            self._cache[key] = entry
            self._cache.move_to_end(key)

        return entry

    def has(self, key: str) -> bool:
        """
        Check if a key exists in cache (without updating access time).

        Args:
            key: The cache key

        Returns:
            True if key exists and is not expired
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                self._evict(key)
                return False
            return True

    def invalidate(self, key: str) -> bool:
        """
        Remove a specific entry from the cache.

        Args:
            key: The cache key to invalidate

        Returns:
            True if entry was found and removed
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        """
        Clear all entries from the cache.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            for key in expired_keys:
                self._evict(key)
            return len(expired_keys)

    def get_all_keys(self) -> List[str]:
        """
        Get all cache keys (for debugging/inspection).

        Returns:
            List of all cache keys in LRU order (oldest first)
        """
        with self._lock:
            return list(self._cache.keys())

    def _evict(self, key: str) -> None:
        """Evict a specific key (internal, caller holds lock)."""
        if key in self._cache:
            del self._cache[key]
            self._stats.evictions += 1

    def _evict_oldest(self) -> None:
        """Evict the oldest entry (internal, caller holds lock)."""
        if self._cache:
            # OrderedDict: first item is oldest (LRU)
            oldest_key = next(iter(self._cache))
            self._evict(oldest_key)

    def export_state(self) -> Dict[str, Any]:
        """
        Export cache state for persistence.

        Returns:
            Serializable dict with all cache data
        """
        with self._lock:
            entries = []
            for key, entry in self._cache.items():
                entries.append({
                    'key': entry.key,
                    'response': entry.response,
                    'content_hash': entry.content_hash,
                    'created_at': entry.created_at.isoformat(),
                    'accessed_at': entry.accessed_at.isoformat(),
                    'access_count': entry.access_count,
                    'ttl_seconds': entry.ttl_seconds,
                    'metadata': entry.metadata,
                })

            return {
                'entries': entries,
                'stats': self._stats.to_dict(),
                'config': {
                    'max_size': self._max_size,
                    'default_ttl': self._default_ttl,
                    'verify_on_get': self._verify_on_get,
                },
            }

    def import_state(self, state: Dict[str, Any]) -> int:
        """
        Import cache state from persistence.

        Args:
            state: Previously exported state dict

        Returns:
            Number of entries imported
        """
        entries = state.get('entries', [])
        imported = 0

        with self._lock:
            for entry_data in entries:
                try:
                    entry = CacheEntry(
                        key=entry_data['key'],
                        response=entry_data['response'],
                        content_hash=entry_data['content_hash'],
                        created_at=datetime.fromisoformat(entry_data['created_at']),
                        accessed_at=datetime.fromisoformat(entry_data['accessed_at']),
                        access_count=entry_data['access_count'],
                        ttl_seconds=entry_data.get('ttl_seconds'),
                        metadata=entry_data.get('metadata', {}),
                    )

                    # Skip expired entries
                    if not entry.is_expired:
                        self._cache[entry.key] = entry
                        imported += 1

                except (KeyError, ValueError) as e:
                    # Skip malformed entries
                    continue

        return imported


class CacheKeyBuilder:
    """
    Fluent builder for cache keys.

    Provides a more readable API for complex cache key construction.

    Example:
        >>> key = (CacheKeyBuilder()
        ...     .with_prompt("Hello")
        ...     .with_system_prompt("Be helpful")
        ...     .with_model("claude-3-opus")
        ...     .with_param("temperature", 0.0)
        ...     .build())
    """

    def __init__(self):
        self._prompt: Optional[str] = None
        self._system_prompt: Optional[str] = None
        self._model_id: Optional[str] = None
        self._params: Dict[str, Any] = {}

    def with_prompt(self, prompt: str) -> 'CacheKeyBuilder':
        """Set the user prompt."""
        self._prompt = prompt
        return self

    def with_system_prompt(self, system_prompt: str) -> 'CacheKeyBuilder':
        """Set the system prompt."""
        self._system_prompt = system_prompt
        return self

    def with_model(self, model_id: str) -> 'CacheKeyBuilder':
        """Set the model ID."""
        self._model_id = model_id
        return self

    def with_param(self, key: str, value: Any) -> 'CacheKeyBuilder':
        """Add an inference parameter."""
        self._params[key] = value
        return self

    def with_params(self, params: Dict[str, Any]) -> 'CacheKeyBuilder':
        """Add multiple inference parameters."""
        self._params.update(params)
        return self

    def build(self) -> str:
        """
        Build the cache key.

        Raises:
            ValueError: If prompt is not set
        """
        if self._prompt is None:
            raise ValueError("prompt is required")

        return compute_cache_key(
            prompt=self._prompt,
            system_prompt=self._system_prompt,
            params=self._params if self._params else None,
            model_id=self._model_id,
        )
