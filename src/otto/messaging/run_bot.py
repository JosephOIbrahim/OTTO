"""
OTTO Matrix Bot Runner
======================

Production entry point for running the Matrix bot.

Usage:
    python -m otto.messaging.run_bot

Environment Variables:
    OTTO_HOMESERVER     Matrix homeserver URL (required)
    OTTO_USER_ID        Matrix user ID (required)
    OTTO_PASSWORD       Matrix password (or use OTTO_ACCESS_TOKEN)
    OTTO_ACCESS_TOKEN   Matrix access token (alternative to password)
    OTTO_DEVICE_ID      Device ID (default: OTTO_BOT)
    OTTO_DATA_DIR       Data directory (default: ~/.otto)
    OTTO_LOG_LEVEL      Log level (default: INFO)
    OTTO_ENABLE_PQ      Enable PQ crypto (default: true)
    OTTO_ALLOWED_USERS  Comma-separated allowed users (default: all)
    OTTO_AUTO_JOIN      Auto-join invites (default: false)
"""

import os
import sys
import asyncio
import logging
import signal
from pathlib import Path
from typing import Optional, List

# Configure logging before imports
log_level = os.environ.get('OTTO_LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger('otto.bot')


def get_env(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """Get environment variable with validation."""
    value = os.environ.get(key, default)
    if required and not value:
        logger.error(f"Required environment variable {key} is not set")
        sys.exit(1)
    return value


def parse_user_list(value: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated user list."""
    if not value:
        return None
    return [u.strip() for u in value.split(',') if u.strip()]


async def run_bot():
    """Main bot runner."""
    from otto.messaging import create_bot, register_otto_commands
    from otto.security.audit import log_event, EventType

    # Get configuration from environment
    homeserver = get_env('OTTO_HOMESERVER', required=True)
    user_id = get_env('OTTO_USER_ID', required=True)
    password = get_env('OTTO_PASSWORD')
    access_token = get_env('OTTO_ACCESS_TOKEN')
    device_id = get_env('OTTO_DEVICE_ID', 'OTTO_BOT')
    data_dir = Path(get_env('OTTO_DATA_DIR', str(Path.home() / '.otto')))
    enable_pq = get_env('OTTO_ENABLE_PQ', 'true').lower() == 'true'
    auto_join = get_env('OTTO_AUTO_JOIN', 'false').lower() == 'true'
    allowed_users = parse_user_list(get_env('OTTO_ALLOWED_USERS'))

    # Validate auth
    if not password and not access_token:
        logger.error("Either OTTO_PASSWORD or OTTO_ACCESS_TOKEN must be set")
        sys.exit(1)

    # Create data directories
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / 'store').mkdir(exist_ok=True)
    (data_dir / 'keys').mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("OTTO Matrix Bot Starting")
    logger.info("=" * 60)
    logger.info(f"Homeserver: {homeserver}")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Device ID: {device_id}")
    logger.info(f"Data Dir: {data_dir}")
    logger.info(f"PQ Crypto: {'Enabled' if enable_pq else 'Disabled'}")
    logger.info(f"Auto Join: {'Yes' if auto_join else 'No'}")
    if allowed_users:
        logger.info(f"Allowed Users: {len(allowed_users)} configured")
    logger.info("=" * 60)

    # Check PQ availability
    if enable_pq:
        try:
            from otto.crypto.pqcrypto import is_pq_available, get_pq_status
            if is_pq_available():
                status = get_pq_status()
                logger.info(f"PQ Crypto Active: {status.algorithm}")
            else:
                logger.warning("PQ crypto requested but liboqs not available")
        except ImportError:
            logger.warning("PQ crypto module not available")

    # Create bot
    bot = create_bot(
        homeserver=homeserver,
        user_id=user_id,
        device_id=device_id,
        store_path=str(data_dir / 'store'),
        enable_e2e=True,
        enable_pq_layer=enable_pq,
        auto_join=auto_join,
        allowed_users=allowed_users,
    )

    # Register OTTO commands
    register_otto_commands(bot)

    # Log startup event
    log_event(
        EventType.SYSTEM_START,
        actor="matrix_bot",
        description=f"OTTO Matrix Bot started on {homeserver}",
        metadata={
            'user_id': user_id,
            'device_id': device_id,
            'pq_enabled': enable_pq,
        }
    )

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig):
        logger.info(f"Received signal {sig}, shutting down...")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: signal_handler(s))

    # Login
    try:
        if access_token:
            logger.info("Logging in with access token...")
            await bot.login(token=access_token)
        else:
            logger.info("Logging in with password...")
            await bot.login(password=password)
        logger.info("Login successful!")
    except Exception as e:
        logger.error(f"Login failed: {e}")
        sys.exit(1)

    # Run bot until shutdown
    try:
        logger.info("Bot is running. Press Ctrl+C to stop.")

        # Create tasks
        bot_task = asyncio.create_task(bot.run())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for either bot to finish or shutdown signal
        done, pending = await asyncio.wait(
            [bot_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        # Graceful shutdown
        logger.info("Shutting down bot...")
        await bot.stop()

        # Log shutdown event
        log_event(
            EventType.SYSTEM_STOP,
            actor="matrix_bot",
            description="OTTO Matrix Bot stopped",
        )

        logger.info("Bot stopped.")


def main():
    """Entry point."""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
