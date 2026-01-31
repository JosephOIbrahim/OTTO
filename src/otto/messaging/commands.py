"""
OTTO Matrix Bot Commands
========================

Command handlers for OTTO operations via Matrix.

Provides commands for:
- System status and health
- Secure channel management
- Threshold operations (requires N-of-M approval)
- Cognitive state queries
"""

import json
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .matrix_bot import MatrixMessage, OTTOMatrixBot


# =============================================================================
# Command Decorators
# =============================================================================

def otto_command(
    name: str,
    description: str,
    usage: str = "",
    requires_auth: bool = True,
    requires_encryption: bool = False,
    min_args: int = 0,
    max_args: Optional[int] = None,
):
    """
    Decorator to register a command handler.

    Usage:
        @otto_command("status", "Show OTTO status")
        async def cmd_status(message, args):
            return "Status: OK"
    """
    def decorator(func):
        func._otto_command = {
            'name': name,
            'description': description,
            'usage': usage,
            'requires_auth': requires_auth,
            'requires_encryption': requires_encryption,
            'min_args': min_args,
            'max_args': max_args,
        }
        return func
    return decorator


# =============================================================================
# OTTO Command Handlers
# =============================================================================

class OTTOCommands:
    """
    OTTO-specific command handlers for the Matrix bot.

    Register these with the bot to enable OTTO functionality.
    """

    def __init__(self, bot: OTTOMatrixBot):
        """
        Initialize command handlers.

        Args:
            bot: The Matrix bot instance
        """
        self.bot = bot
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all commands with the bot."""
        # Find all methods with _otto_command attribute
        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, '_otto_command'):
                cmd = method._otto_command
                self.bot.register_command(
                    name=cmd['name'],
                    handler=method,
                    description=cmd['description'],
                    usage=cmd.get('usage', ''),
                    requires_auth=cmd.get('requires_auth', True),
                    requires_encryption=cmd.get('requires_encryption', False),
                    min_args=cmd.get('min_args', 0),
                    max_args=cmd.get('max_args'),
                )

    # =========================================================================
    # System Commands
    # =========================================================================

    @otto_command("health", "Check OTTO health status")
    async def cmd_health(self, message: MatrixMessage, args: List[str]) -> str:
        """Check system health."""
        # TODO: Integrate with actual OTTO health checks
        return (
            "OTTO Health Status\n"
            "==================\n"
            "Core: OK\n"
            "Crypto: OK\n"
            "Matrix Bot: OK\n"
            "Memory: OK"
        )

    @otto_command("info", "Show OTTO system information")
    async def cmd_info(self, message: MatrixMessage, args: List[str]) -> str:
        """Show system info."""
        from ..crypto.pqcrypto import get_pq_status

        pq_status = get_pq_status()

        return (
            "OTTO OS Information\n"
            "===================\n"
            f"Version: 0.1.0\n"
            f"PQ Crypto: {'Enabled' if pq_status.pq_available else 'Disabled'}\n"
            f"Algorithm: {pq_status.algorithm or 'X25519 only'}\n"
            f"Security Level: {pq_status.security_level}"
        )

    @otto_command("uptime", "Show bot uptime")
    async def cmd_uptime(self, message: MatrixMessage, args: List[str]) -> str:
        """Show uptime."""
        # TODO: Track actual start time
        return "Bot has been running since session start."

    # =========================================================================
    # Secure Channel Commands
    # =========================================================================

    @otto_command(
        "secure",
        "Manage secure channels",
        usage="<status|list|rotate>",
        requires_encryption=True,
    )
    async def cmd_secure(self, message: MatrixMessage, args: List[str]) -> str:
        """Manage secure channels."""
        if not args:
            return "Usage: !secure <status|list|rotate>"

        subcommand = args[0].lower()

        if subcommand == "status":
            return self._secure_status()
        elif subcommand == "list":
            return self._secure_list()
        elif subcommand == "rotate":
            return self._secure_rotate()
        else:
            return f"Unknown subcommand: {subcommand}"

    def _secure_status(self) -> str:
        """Get secure channel status."""
        from ..crypto.pqcrypto import get_pq_status
        status = get_pq_status()

        return (
            "Secure Channel Status\n"
            "=====================\n"
            f"PQ Available: {status.pq_available}\n"
            f"Algorithm: {status.algorithm}\n"
            f"Classical: {status.classical_algorithm}\n"
            f"Mode: {status.security_level}"
        )

    def _secure_list(self) -> str:
        """List active secure channels."""
        # TODO: Get from actual secure channel manager
        return "Active Secure Channels: 0"

    def _secure_rotate(self) -> str:
        """Rotate keys."""
        # TODO: Trigger actual key rotation
        return "Key rotation initiated."

    # =========================================================================
    # Threshold Commands
    # =========================================================================

    @otto_command(
        "threshold",
        "Threshold signature operations",
        usage="<status|sign|approve> [args]",
        requires_encryption=True,
    )
    async def cmd_threshold(self, message: MatrixMessage, args: List[str]) -> str:
        """Threshold signature operations."""
        if not args:
            return "Usage: !threshold <status|sign|approve>"

        subcommand = args[0].lower()

        if subcommand == "status":
            return self._threshold_status()
        elif subcommand == "sign":
            return await self._threshold_sign(args[1:])
        elif subcommand == "approve":
            return await self._threshold_approve(args[1:])
        else:
            return f"Unknown subcommand: {subcommand}"

    def _threshold_status(self) -> str:
        """Get threshold signing status."""
        return (
            "Threshold Signing Status\n"
            "========================\n"
            "Pending Requests: 0\n"
            "Configured: 2-of-3\n"
            "My Share: Loaded"
        )

    async def _threshold_sign(self, args: List[str]) -> str:
        """Initiate threshold signing."""
        if not args:
            return "Usage: !threshold sign <operation>"

        operation = args[0]
        return f"Threshold signature request created for: {operation}\nWaiting for approvals..."

    async def _threshold_approve(self, args: List[str]) -> str:
        """Approve a threshold signature request."""
        if not args:
            return "Usage: !threshold approve <request_id>"

        request_id = args[0]
        return f"Approved request: {request_id}\nPartial signature submitted."

    # =========================================================================
    # Cognitive State Commands (OTTO-specific)
    # =========================================================================

    @otto_command(
        "state",
        "Query cognitive state",
        requires_encryption=True,
    )
    async def cmd_state(self, message: MatrixMessage, args: List[str]) -> str:
        """Query cognitive state."""
        # TODO: Integrate with actual cognitive state
        return (
            "Cognitive State\n"
            "===============\n"
            "Mode: focused\n"
            "Energy: high\n"
            "Burnout: GREEN\n"
            "Momentum: rolling"
        )

    @otto_command(
        "projects",
        "List active projects",
    )
    async def cmd_projects(self, message: MatrixMessage, args: List[str]) -> str:
        """List active projects."""
        # TODO: Integrate with project management
        return (
            "Active Projects\n"
            "===============\n"
            "1. [FOCUS] OTTO OS\n"
            "2. [HOLDING] Orchestra\n"
            "3. [BACKGROUND] Portfolio"
        )

    # =========================================================================
    # Admin Commands
    # =========================================================================

    @otto_command(
        "admin",
        "Admin operations",
        usage="<users|rooms|config>",
        requires_auth=True,
        requires_encryption=True,
    )
    async def cmd_admin(self, message: MatrixMessage, args: List[str]) -> str:
        """Admin operations."""
        if not args:
            return "Usage: !admin <users|rooms|config>"

        subcommand = args[0].lower()

        if subcommand == "users":
            return self._admin_users()
        elif subcommand == "rooms":
            return self._admin_rooms()
        elif subcommand == "config":
            return self._admin_config()
        else:
            return f"Unknown admin command: {subcommand}"

    def _admin_users(self) -> str:
        """List allowed users."""
        users = self.bot.config.allowed_users
        if not users:
            return "Allowed Users: (all)"
        return "Allowed Users:\n" + "\n".join(f"  - {u}" for u in users)

    def _admin_rooms(self) -> str:
        """List rooms."""
        rooms = self.bot._state.rooms
        if not rooms:
            return "Joined Rooms: (none)"
        return "Joined Rooms:\n" + "\n".join(f"  - {r}" for r in rooms.keys())

    def _admin_config(self) -> str:
        """Show config."""
        cfg = self.bot.config
        return (
            "Bot Configuration\n"
            "=================\n"
            f"Homeserver: {cfg.homeserver}\n"
            f"User ID: {cfg.user_id}\n"
            f"Device ID: {cfg.device_id}\n"
            f"E2E: {cfg.enable_e2e}\n"
            f"PQ Layer: {cfg.enable_pq_layer}\n"
            f"Auto Join: {cfg.auto_join}"
        )


# =============================================================================
# Command Registration Helper
# =============================================================================

def register_otto_commands(bot: OTTOMatrixBot) -> OTTOCommands:
    """
    Register all OTTO commands with a bot instance.

    Args:
        bot: The Matrix bot instance

    Returns:
        OTTOCommands instance
    """
    return OTTOCommands(bot)
