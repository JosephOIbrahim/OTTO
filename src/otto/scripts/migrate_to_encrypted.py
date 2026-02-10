#!/usr/bin/env python3
"""
Migration Script: Plaintext to Encrypted Storage

Migrates existing plaintext cognitive data to encrypted storage:
- Discord sessions (discord_sessions.json → encrypted)
- Telegram sessions (telegram_sessions.json → encrypted)
- Trail database (trails.db → encrypted)

Usage:
    python -m otto.scripts.migrate_to_encrypted

Or via CLI:
    otto encryption migrate

Prerequisites:
    - Run 'otto encryption setup' first to configure encryption
    - Run 'otto encryption unlock' to unlock if locked

Determinism:
    - Deterministic iteration (sorted keys)
    - Fixed encryption parameters (AES-256-GCM)
    - Graceful degradation with backup
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class MigrationResult:
    """Result of migration operation."""

    def __init__(self):
        self.success = True
        self.migrated: list[str] = []
        self.skipped: list[str] = []
        self.errors: list[tuple[str, str]] = []
        self.backup_path: Optional[Path] = None

    def add_success(self, item: str) -> None:
        self.migrated.append(item)

    def add_skip(self, item: str, reason: str = "") -> None:
        self.skipped.append(f"{item}: {reason}" if reason else item)

    def add_error(self, item: str, error: str) -> None:
        self.errors.append((item, error))
        self.success = False


def create_backup(otto_dir: Path) -> Optional[Path]:
    """Create backup of all data before migration."""
    if not otto_dir.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = otto_dir.parent / f".otto_backup_pre_encryption_{timestamp}"

    try:
        shutil.copytree(otto_dir, backup_dir, ignore=shutil.ignore_patterns("*.log"))
        logger.info(f"Created backup at {backup_dir}")
        return backup_dir
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return None


def migrate_discord_sessions(result: MigrationResult) -> None:
    """Migrate Discord sessions from plaintext to encrypted."""
    from ..substrate.protection import get_protection, SubstrateProtectionError

    otto_dir = Path.home() / ".otto"
    sessions_file = otto_dir / "discord_sessions.json"

    if not sessions_file.exists():
        result.add_skip("discord_sessions.json", "file not found")
        return

    protection = get_protection()
    if not protection.is_setup() or not protection.is_unlocked():
        result.add_error("discord_sessions.json", "protection not set up or locked")
        return

    try:
        # Read plaintext data
        with open(sessions_file) as f:
            data = json.load(f)

        if not data:
            result.add_skip("discord_sessions.json", "empty file")
            return

        # Write encrypted
        protection.write_protected_json("sessions/discord.json", data)

        # Rename old file (don't delete, for safety)
        backup_file = sessions_file.with_suffix(".json.plaintext.bak")
        sessions_file.rename(backup_file)

        result.add_success(f"discord_sessions.json ({len(data)} sessions)")
        logger.info(f"Migrated {len(data)} Discord sessions to encrypted storage")

    except SubstrateProtectionError as e:
        result.add_error("discord_sessions.json", str(e))
    except json.JSONDecodeError as e:
        result.add_error("discord_sessions.json", f"invalid JSON: {e}")
    except Exception as e:
        result.add_error("discord_sessions.json", str(e))


def migrate_telegram_sessions(result: MigrationResult) -> None:
    """Migrate Telegram sessions from plaintext to encrypted."""
    from ..substrate.protection import get_protection, SubstrateProtectionError

    otto_dir = Path.home() / ".otto"
    sessions_file = otto_dir / "telegram_sessions.json"

    if not sessions_file.exists():
        result.add_skip("telegram_sessions.json", "file not found")
        return

    protection = get_protection()
    if not protection.is_setup() or not protection.is_unlocked():
        result.add_error("telegram_sessions.json", "protection not set up or locked")
        return

    try:
        # Read plaintext data
        with open(sessions_file) as f:
            data = json.load(f)

        if not data:
            result.add_skip("telegram_sessions.json", "empty file")
            return

        # Write encrypted
        protection.write_protected_json("sessions/telegram.json", data)

        # Rename old file (don't delete, for safety)
        backup_file = sessions_file.with_suffix(".json.plaintext.bak")
        sessions_file.rename(backup_file)

        result.add_success(f"telegram_sessions.json ({len(data)} sessions)")
        logger.info(f"Migrated {len(data)} Telegram sessions to encrypted storage")

    except SubstrateProtectionError as e:
        result.add_error("telegram_sessions.json", str(e))
    except json.JSONDecodeError as e:
        result.add_error("telegram_sessions.json", f"invalid JSON: {e}")
    except Exception as e:
        result.add_error("telegram_sessions.json", str(e))


def migrate_trails_db(result: MigrationResult) -> None:
    """Migrate trails database to encrypted storage."""
    from ..trails.store import get_store, flush_encrypted, reset_store

    try:
        # Reset store to ensure fresh state
        reset_store()

        # Get store - this will initialize encryption mode if protection is unlocked
        store = get_store()

        # Check if encrypted file ACTUALLY exists on disk (not just in-memory flag)
        encrypted_path = store._encrypted_path
        plaintext_path = store._original_db_path

        if encrypted_path.exists() and not plaintext_path.exists():
            result.add_skip("trails.db", "already encrypted (encrypted file exists)")
            return

        if not store._is_encrypted:
            result.add_skip("trails.db", "encryption not active (protection may not be set up)")
            return

        # Force encryption: call _encrypt_and_save directly
        store._encrypt_and_save()

        # Verify encrypted file was created
        if encrypted_path.exists():
            # Remove plaintext file
            if plaintext_path.exists():
                plaintext_backup = plaintext_path.with_suffix(".db.plaintext.bak")
                plaintext_path.rename(plaintext_backup)
                logger.info(f"Backed up plaintext trails.db to {plaintext_backup}")

            result.add_success("trails.db")
            logger.info("Migrated trails database to encrypted storage")
        else:
            result.add_error("trails.db", "encryption failed - no encrypted file created")

    except Exception as e:
        result.add_error("trails.db", str(e))


def run_migration(create_backup_first: bool = True, passphrase: Optional[str] = None) -> MigrationResult:
    """
    Run full migration from plaintext to encrypted storage.

    Args:
        create_backup_first: Whether to create a backup before migration
        passphrase: Optional passphrase to unlock protection (prompts if needed and not provided)

    Returns:
        MigrationResult with details of what was migrated
    """
    import getpass
    from ..substrate.protection import get_protection, SubstrateProtectionError

    result = MigrationResult()

    # Check protection is ready
    protection = get_protection()
    if not protection.is_setup():
        result.add_error("migration", "encryption not set up - run 'otto encryption setup' first")
        return result

    # Unlock if needed (state doesn't persist across process invocations)
    if not protection.is_unlocked():
        if passphrase is None:
            # Prompt for passphrase
            print("Encryption passphrase required for migration.")
            passphrase = getpass.getpass("Enter encryption passphrase: ")

        try:
            protection.unlock(passphrase)
        except SubstrateProtectionError as e:
            result.add_error("migration", f"failed to unlock encryption: {e}")
            return result

    # Create backup
    if create_backup_first:
        otto_dir = Path.home() / ".otto"
        result.backup_path = create_backup(otto_dir)

    # Run migrations
    logger.info("Starting migration to encrypted storage...")

    migrate_discord_sessions(result)
    migrate_telegram_sessions(result)
    migrate_trails_db(result)

    logger.info(f"Migration complete: {len(result.migrated)} migrated, {len(result.skipped)} skipped, {len(result.errors)} errors")

    return result


def print_result(result: MigrationResult) -> None:
    """Print migration result to console."""
    print()
    print("=" * 60)
    print("OTTO Migration Results")
    print("=" * 60)
    print()

    if result.backup_path:
        print(f"Backup created: {result.backup_path}")
        print()

    if result.migrated:
        print("Migrated successfully:")
        for item in result.migrated:
            print(f"  + {item}")
        print()

    if result.skipped:
        print("Skipped:")
        for item in result.skipped:
            print(f"  - {item}")
        print()

    if result.errors:
        print("Errors:")
        for item, error in result.errors:
            print(f"  ! {item}: {error}")
        print()

    if result.success:
        print("Migration completed successfully.")
        print()
        print("New data will be encrypted automatically.")
        print("Plaintext backups saved with .plaintext.bak extension.")
    else:
        print("Migration completed with errors.")
        print("Review errors above and try again.")


def main() -> int:
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate OTTO data from plaintext to encrypted storage"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup before migration"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Set up logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run migration
    result = run_migration(create_backup_first=not args.no_backup)
    print_result(result)

    return 0 if result.success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
