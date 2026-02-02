"""
OTTO OS Scripts

Administrative and migration scripts for OTTO OS.

Available scripts:
- migrate_to_encrypted: Migrate plaintext data to encrypted storage
"""

from .migrate_to_encrypted import run_migration, MigrationResult

__all__ = [
    "run_migration",
    "MigrationResult",
]
