"""
SQLite-backed Trail Store for OTTO OS
======================================

Persistent storage for pheromone trails with atomic operations,
decay management, and deterministic query ordering.

ThinkingMachines [He2025] Compliance:
- All queries return results in deterministic order (path ASC, signal ASC)
- Strength aggregations use sorted order before computation
- No race conditions through SQLite transactions

Database Location: data/trails.db (configurable)

Encryption Support (v0.7.0):
- If SubstrateProtection is set up and unlocked, the database file
  is encrypted at rest using AES-256-GCM
- On initialization, encrypted DB is decrypted to working location
- On close(), the database is re-encrypted

Schema:
    CREATE TABLE trails (
        id INTEGER PRIMARY KEY,
        trail_type TEXT NOT NULL,
        path TEXT NOT NULL,
        signal TEXT NOT NULL,
        strength REAL DEFAULT 1.0,
        deposited_by TEXT NOT NULL,
        deposited_at TEXT NOT NULL,
        reinforced_count INTEGER DEFAULT 0,
        half_life_days REAL DEFAULT 7.0,
        metadata TEXT DEFAULT '{}',
        UNIQUE(trail_type, path, signal)
    );
"""

import atexit
import json
import logging
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

from .models import Trail, TrailQuery, TrailType

logger = logging.getLogger(__name__)


class TrailStore:
    """
    SQLite-backed persistent storage for pheromone trails.

    Provides atomic CRUD operations with deterministic ordering.
    Trails are uniquely identified by (trail_type, path, signal).
    Depositing an existing trail reinforces it rather than duplicating.

    Encryption Support (v0.7.0):
    - If SubstrateProtection is set up, the DB file is encrypted at rest
    - Decrypted to temp file for operations
    - Re-encrypted on close()

    Attributes:
        db_path: Path to SQLite database file
        prune_threshold: Strength below which trails are pruned (default 0.1)
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        prune_threshold: float = 0.1,
        use_encryption: bool = True,
    ):
        """
        Initialize TrailStore with SQLite database.

        Args:
            db_path: Path to database file (default: data/trails.db relative to OTTO_OS)
            prune_threshold: Minimum strength to keep trails (default 0.1)
            use_encryption: Whether to use encryption if available (default: True)
        """
        if db_path is None:
            # Default to OTTO_OS/data/trails.db
            db_path = Path(__file__).parent.parent.parent.parent / "data" / "trails.db"

        self._original_db_path = Path(db_path)
        self._encrypted_path = self._original_db_path.with_suffix(".db.enc")
        self._temp_db_path: Optional[Path] = None
        self._protection = None
        self._is_encrypted = False
        self.prune_threshold = prune_threshold

        # Ensure parent directory exists
        self._original_db_path.parent.mkdir(parents=True, exist_ok=True)

        # Try to set up encryption
        if use_encryption:
            self._setup_encryption()

        # Set working db_path
        if self._is_encrypted and self._temp_db_path:
            self.db_path = self._temp_db_path
        else:
            self.db_path = self._original_db_path

        # Initialize database schema
        self._init_schema()

        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)

    def _setup_encryption(self) -> None:
        """
        Set up encryption if SubstrateProtection is available and configured.

        [He2025] Compliance: Deterministic decision based on protection state.
        """
        try:
            from ..substrate.protection import get_protection, SubstrateProtectionError

            self._protection = get_protection()

            if not self._protection.is_setup():
                logger.debug("Protection not set up, using plaintext trails.db")
                return

            if not self._protection.is_unlocked():
                logger.warning(
                    "Protection is set up but locked. "
                    "Trails stored in PLAINTEXT. Run 'otto protection unlock'."
                )
                return

            # Protection is ready - decrypt or create encrypted storage
            self._is_encrypted = True

            # Create temp file for decrypted DB
            temp_fd, temp_path = tempfile.mkstemp(suffix=".db", prefix="trails_")
            self._temp_db_path = Path(temp_path)

            # If encrypted file exists, decrypt it
            if self._encrypted_path.exists():
                encrypted_data = self._encrypted_path.read_bytes()
                decrypted_data = self._protection._encryption.decrypt(encrypted_data)
                self._temp_db_path.write_bytes(decrypted_data)
                logger.info("Decrypted trails.db for use")
            elif self._original_db_path.exists():
                # Migrate existing plaintext DB
                shutil.copy2(self._original_db_path, self._temp_db_path)
                logger.info("Migrating existing trails.db to encrypted storage")
            else:
                # New database - temp file already created empty
                logger.debug("Creating new encrypted trails.db")

        except ImportError:
            logger.debug("SubstrateProtection not available")
        except Exception as e:
            logger.warning(f"Failed to set up trail encryption: {e}")
            self._is_encrypted = False
            self._temp_db_path = None

    def _encrypt_and_save(self) -> None:
        """
        Encrypt the temp database and save to encrypted path.

        [He2025] Compliance: Atomic write via temp file.
        """
        if not self._is_encrypted or not self._temp_db_path or not self._protection:
            return

        try:
            if not self._temp_db_path.exists():
                return

            # Read current DB state
            db_data = self._temp_db_path.read_bytes()

            # Encrypt
            encrypted_data = self._protection._encryption.encrypt(db_data)

            # Atomic write
            temp_enc_path = self._encrypted_path.with_suffix(".enc.tmp")
            temp_enc_path.write_bytes(encrypted_data)
            temp_enc_path.replace(self._encrypted_path)

            logger.debug("Encrypted trails.db saved")

        except Exception as e:
            logger.warning(f"Failed to encrypt trails.db: {e}")

    def _cleanup_on_exit(self) -> None:
        """Cleanup handler for process exit."""
        self.close()

    def close(self) -> None:
        """
        Close the TrailStore and encrypt data.

        Must be called to ensure encrypted data is saved.
        """
        if self._is_encrypted:
            self._encrypt_and_save()

            # Clean up temp file
            if self._temp_db_path and self._temp_db_path.exists():
                try:
                    self._temp_db_path.unlink()
                except Exception:
                    pass

            # Remove plaintext if encrypted version exists
            if self._encrypted_path.exists() and self._original_db_path.exists():
                try:
                    self._original_db_path.unlink()
                    logger.info("Removed plaintext trails.db (now encrypted)")
                except Exception:
                    pass

    def _init_schema(self) -> None:
        """Create database tables if they don't exist."""
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trails (
                    id INTEGER PRIMARY KEY,
                    trail_type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    strength REAL DEFAULT 1.0,
                    deposited_by TEXT NOT NULL,
                    deposited_at TEXT NOT NULL,
                    reinforced_count INTEGER DEFAULT 0,
                    half_life_days REAL DEFAULT 7.0,
                    metadata TEXT DEFAULT '{}',
                    UNIQUE(trail_type, path, signal)
                )
            """)

            # Index for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trails_path
                ON trails(path)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trails_type_path
                ON trails(trail_type, path)
            """)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """
        Context manager for database connections.

        Ensures proper transaction handling and connection cleanup.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _row_to_trail(self, row: sqlite3.Row) -> Trail:
        """Convert database row to Trail object."""
        return Trail(
            id=row["id"],
            trail_type=TrailType(row["trail_type"]),
            path=row["path"],
            signal=row["signal"],
            strength=row["strength"],
            deposited_by=row["deposited_by"],
            deposited_at=datetime.fromisoformat(row["deposited_at"]),
            reinforced_count=row["reinforced_count"],
            half_life_days=row["half_life_days"],
            metadata=json.loads(row["metadata"]),
        )

    # =========================================================================
    # Core CRUD Operations
    # =========================================================================

    def deposit(self, trail: Trail) -> Trail:
        """
        Create or reinforce a trail.

        If a trail with the same (trail_type, path, signal) exists,
        it is reinforced instead of duplicated. Reinforcement:
        - Resets strength to max(current, new)
        - Updates deposited_at to now
        - Increments reinforced_count
        - Updates deposited_by

        Args:
            trail: Trail to deposit

        Returns:
            The deposited trail with updated ID
        """
        now = datetime.now()

        with self._connection() as conn:
            # Check for existing trail
            cursor = conn.execute(
                """
                SELECT * FROM trails
                WHERE trail_type = ? AND path = ? AND signal = ?
                """,
                (trail.trail_type.value, trail.path, trail.signal),
            )
            existing = cursor.fetchone()

            if existing:
                # Reinforce existing trail
                existing_trail = self._row_to_trail(existing)
                new_strength = max(
                    existing_trail.current_strength(now),
                    trail.strength,
                )
                # Cap strength at 1.0
                new_strength = min(new_strength, 1.0)

                conn.execute(
                    """
                    UPDATE trails SET
                        strength = ?,
                        deposited_by = ?,
                        deposited_at = ?,
                        reinforced_count = reinforced_count + 1,
                        metadata = ?
                    WHERE id = ?
                    """,
                    (
                        new_strength,
                        trail.deposited_by,
                        now.isoformat(),
                        json.dumps(trail.metadata),
                        existing_trail.id,
                    ),
                )

                return Trail(
                    id=existing_trail.id,
                    trail_type=trail.trail_type,
                    path=trail.path,
                    signal=trail.signal,
                    strength=new_strength,
                    deposited_by=trail.deposited_by,
                    deposited_at=now,
                    reinforced_count=existing_trail.reinforced_count + 1,
                    metadata=trail.metadata,
                    half_life_days=trail.half_life_days,
                )
            else:
                # Create new trail
                cursor = conn.execute(
                    """
                    INSERT INTO trails
                    (trail_type, path, signal, strength, deposited_by,
                     deposited_at, reinforced_count, half_life_days, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trail.trail_type.value,
                        trail.path,
                        trail.signal,
                        trail.strength,
                        trail.deposited_by,
                        now.isoformat(),
                        0,
                        trail.half_life_days,
                        json.dumps(trail.metadata),
                    ),
                )

                return Trail(
                    id=cursor.lastrowid,
                    trail_type=trail.trail_type,
                    path=trail.path,
                    signal=trail.signal,
                    strength=trail.strength,
                    deposited_by=trail.deposited_by,
                    deposited_at=now,
                    reinforced_count=0,
                    metadata=trail.metadata,
                    half_life_days=trail.half_life_days,
                )

    def reinforce(
        self,
        path: str,
        signal: str,
        trail_type: TrailType,
        boost: float = 0.2,
        by: str = "system",
    ) -> Optional[Trail]:
        """
        Strengthen an existing trail.

        Args:
            path: File path of the trail
            signal: Signal to reinforce
            trail_type: Type of trail
            boost: Amount to add to strength (default 0.2)
            by: Agent performing reinforcement

        Returns:
            Updated trail if found, None otherwise
        """
        now = datetime.now()

        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM trails
                WHERE trail_type = ? AND path = ? AND signal = ?
                """,
                (trail_type.value, path, signal),
            )
            row = cursor.fetchone()

            if not row:
                return None

            trail = self._row_to_trail(row)
            current = trail.current_strength(now)
            new_strength = min(current + boost, 1.0)

            conn.execute(
                """
                UPDATE trails SET
                    strength = ?,
                    deposited_by = ?,
                    deposited_at = ?,
                    reinforced_count = reinforced_count + 1
                WHERE id = ?
                """,
                (new_strength, by, now.isoformat(), trail.id),
            )

            return Trail(
                id=trail.id,
                trail_type=trail.trail_type,
                path=trail.path,
                signal=trail.signal,
                strength=new_strength,
                deposited_by=by,
                deposited_at=now,
                reinforced_count=trail.reinforced_count + 1,
                metadata=trail.metadata,
                half_life_days=trail.half_life_days,
            )

    def weaken(
        self,
        path: str,
        signal: str,
        trail_type: TrailType,
        reduction: float = 0.2,
    ) -> Optional[Trail]:
        """
        Weaken an existing trail (negative reinforcement).

        Args:
            path: File path of the trail
            signal: Signal to weaken
            trail_type: Type of trail
            reduction: Amount to subtract from strength (default 0.2)

        Returns:
            Updated trail if found, None otherwise
        """
        now = datetime.now()

        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM trails
                WHERE trail_type = ? AND path = ? AND signal = ?
                """,
                (trail_type.value, path, signal),
            )
            row = cursor.fetchone()

            if not row:
                return None

            trail = self._row_to_trail(row)
            current = trail.current_strength(now)
            new_strength = max(current - reduction, 0.0)

            conn.execute(
                """
                UPDATE trails SET
                    strength = ?,
                    deposited_at = ?
                WHERE id = ?
                """,
                (new_strength, now.isoformat(), trail.id),
            )

            return Trail(
                id=trail.id,
                trail_type=trail.trail_type,
                path=trail.path,
                signal=trail.signal,
                strength=new_strength,
                deposited_by=trail.deposited_by,
                deposited_at=now,
                reinforced_count=trail.reinforced_count,
                metadata=trail.metadata,
                half_life_days=trail.half_life_days,
            )

    def read_trails(self, path: str) -> List[Trail]:
        """
        Get all living trails for a file path.

        Returns trails in deterministic order: (trail_type, signal) ASC.

        Args:
            path: File path to query

        Returns:
            List of trails attached to this path
        """
        now = datetime.now()

        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM trails
                WHERE path = ?
                ORDER BY trail_type ASC, signal ASC
                """,
                (path,),
            )

            trails = []
            for row in cursor.fetchall():
                trail = self._row_to_trail(row)
                if trail.is_alive(self.prune_threshold, now):
                    trails.append(trail)

            return trails

    def follow_strongest(
        self,
        path: str,
        trail_type: TrailType,
    ) -> Optional[Trail]:
        """
        Get the strongest trail of a given type for a path.

        Uses deterministic tie-breaking: if multiple trails have the same
        strength (after rounding to 6 decimal places for [He2025] batch invariance),
        returns the one with the lexicographically smallest signal.

        Args:
            path: File path to query
            trail_type: Type of trail to look for

        Returns:
            Strongest living trail, or None if no trails exist
        """
        now = datetime.now()

        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM trails
                WHERE path = ? AND trail_type = ?
                """,
                (path, trail_type.value),
            )

            # Collect all living trails with their current strength
            # [He2025] batch invariance: round to 6 decimals to eliminate
            # microsecond timing noise in decay calculations
            candidates: list[tuple[float, str, Trail]] = []

            for row in cursor.fetchall():
                trail = self._row_to_trail(row)
                current = trail.current_strength(now)

                if current >= self.prune_threshold:
                    # Round for deterministic comparison
                    rounded_strength = round(current, 6)
                    candidates.append((rounded_strength, trail.signal, trail))

            if not candidates:
                return None

            # Sort by (-strength, signal) for deterministic tie-breaking
            # Highest strength first, then alphabetically by signal
            candidates.sort(key=lambda x: (-x[0], x[1]))

            return candidates[0][2]

    def query(self, q: TrailQuery) -> List[Trail]:
        """
        Flexible trail search with query parameters.

        Results are always returned in deterministic order:
        (path ASC, trail_type ASC, signal ASC).

        Args:
            q: Query parameters

        Returns:
            List of matching trails
        """
        now = datetime.now()
        conditions = []
        params = []

        if q.trail_type is not None:
            conditions.append("trail_type = ?")
            params.append(q.trail_type.value)

        if q.path is not None:
            conditions.append("path = ?")
            params.append(q.path)

        if q.path_prefix is not None:
            conditions.append("path LIKE ?")
            params.append(f"{q.path_prefix}%")

        if q.signal is not None:
            conditions.append("signal = ?")
            params.append(q.signal)

        if q.signal_contains is not None:
            conditions.append("signal LIKE ?")
            params.append(f"%{q.signal_contains}%")

        if q.deposited_by is not None:
            conditions.append("deposited_by = ?")
            params.append(q.deposited_by)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self._connection() as conn:
            cursor = conn.execute(
                f"""
                SELECT * FROM trails
                WHERE {where_clause}
                ORDER BY path ASC, trail_type ASC, signal ASC
                LIMIT ?
                """,
                params + [q.limit],
            )

            trails = []
            for row in cursor.fetchall():
                trail = self._row_to_trail(row)

                # Apply in-memory filters that can't be done in SQL
                if q.min_strength is not None:
                    if trail.current_strength(now) < q.min_strength:
                        continue

                if q.max_age_days is not None:
                    elapsed = now - trail.deposited_at
                    if elapsed.total_seconds() / 86400.0 > q.max_age_days:
                        continue

                if trail.is_alive(self.prune_threshold, now):
                    trails.append(trail)

            return trails

    def get_related_paths(self, path: str) -> List[str]:
        """
        Follow CONTEXT trails to find related files.

        Looks for trails with signals like "depends_on:X" or "used_by:X"
        to build a relationship graph.

        Args:
            path: Starting file path

        Returns:
            List of related file paths in deterministic order
        """
        related = set()

        trails = self.query(TrailQuery(
            path=path,
            trail_type=TrailType.CONTEXT,
        ))

        for trail in trails:
            signal = trail.signal
            if signal.startswith("depends_on:"):
                related.add(signal[len("depends_on:"):])
            elif signal.startswith("used_by:"):
                related.add(signal[len("used_by:"):])
            elif signal.startswith("related_to:"):
                related.add(signal[len("related_to:"):])

        # Also find paths that reference this path
        with self._connection() as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT path FROM trails
                WHERE trail_type = ? AND (
                    signal = ? OR signal = ? OR signal = ?
                )
                ORDER BY path ASC
                """,
                (
                    TrailType.CONTEXT.value,
                    f"depends_on:{path}",
                    f"used_by:{path}",
                    f"related_to:{path}",
                ),
            )
            for row in cursor.fetchall():
                related.add(row["path"])

        # Return in deterministic sorted order
        return sorted(related)

    # =========================================================================
    # Maintenance Operations
    # =========================================================================

    def decay_all(self) -> int:
        """
        Apply decay and prune dead trails.

        This should be run periodically (e.g., on session start or via cron).
        Trails with strength below prune_threshold after decay are deleted.

        Returns:
            Number of trails pruned
        """
        now = datetime.now()
        pruned = 0

        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM trails")
            rows = cursor.fetchall()

            for row in rows:
                trail = self._row_to_trail(row)
                current = trail.current_strength(now)

                if current < self.prune_threshold:
                    # Prune dead trail
                    conn.execute("DELETE FROM trails WHERE id = ?", (trail.id,))
                    pruned += 1
                else:
                    # Update stored strength to current decayed value
                    conn.execute(
                        """
                        UPDATE trails SET strength = ?, deposited_at = ?
                        WHERE id = ?
                        """,
                        (current, now.isoformat(), trail.id),
                    )

        return pruned

    def delete_trail(self, trail_id: int) -> bool:
        """
        Delete a specific trail by ID.

        Args:
            trail_id: ID of trail to delete

        Returns:
            True if trail was deleted, False if not found
        """
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM trails WHERE id = ?",
                (trail_id,),
            )
            return cursor.rowcount > 0

    def clear_path(self, path: str) -> int:
        """
        Delete all trails for a file path.

        Useful when a file is deleted or renamed.

        Args:
            path: File path to clear

        Returns:
            Number of trails deleted
        """
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM trails WHERE path = ?",
                (path,),
            )
            return cursor.rowcount

    def count_trails(self, trail_type: Optional[TrailType] = None) -> int:
        """
        Count trails, optionally filtered by type.

        Args:
            trail_type: Optional type filter

        Returns:
            Number of trails
        """
        with self._connection() as conn:
            if trail_type is not None:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM trails WHERE trail_type = ?",
                    (trail_type.value,),
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM trails")

            return cursor.fetchone()[0]


# =============================================================================
# Module-level convenience functions
# =============================================================================

_default_store: Optional[TrailStore] = None


def get_store() -> TrailStore:
    """Get or create the default TrailStore instance."""
    global _default_store
    if _default_store is None:
        _default_store = TrailStore()
    return _default_store


def reset_store() -> None:
    """
    Reset the store singleton and encrypt data.

    Used for testing and clean shutdown.
    """
    global _default_store
    if _default_store is not None:
        _default_store.close()
        _default_store = None


def deposit(trail: Trail) -> Trail:
    """Deposit a trail using the default store."""
    return get_store().deposit(trail)


def read_trails(path: str) -> List[Trail]:
    """Read trails for a path using the default store."""
    return get_store().read_trails(path)


def follow_strongest(path: str, trail_type: TrailType) -> Optional[Trail]:
    """Get strongest trail using the default store."""
    return get_store().follow_strongest(path, trail_type)


def flush_encrypted() -> None:
    """
    Flush encrypted state to disk.

    Call periodically or before risky operations to ensure
    encrypted data is persisted.
    """
    store = get_store()
    if store._is_encrypted:
        store._encrypt_and_save()


def is_encrypted() -> bool:
    """Check if the trail store is using encryption."""
    return get_store()._is_encrypted


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TrailStore",
    "get_store",
    "reset_store",
    "deposit",
    "read_trails",
    "follow_strongest",
    "flush_encrypted",
    "is_encrypted",
]
