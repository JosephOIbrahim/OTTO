"""
OTTO Discord Bot
================

Discord bot using discord.py library with slash commands.

[He2025] Compliance:
- Deterministic message processing order
- Fixed evaluation sequence in handlers
- Session state managed by DiscordAdapter

Requirements:
    pip install discord.py>=2.0

Environment:
    DISCORD_BOT_TOKEN: Your bot token from Discord Developer Portal

Usage:
    from otto.discord import create_bot

    bot = create_bot()
    bot.run()
"""

import logging
import os
import sys
from pathlib import Path
from typing import Final, Optional, TYPE_CHECKING

from .adapter import DiscordAdapter, DiscordMessage, DiscordResponse

logger = logging.getLogger(__name__)

# [He2025] Fixed constants
_DEFAULT_SESSION_PATH: Final[str] = "data/discord_sessions.json"
_CLEANUP_INTERVAL_SECONDS: Final[int] = 3600  # 1 hour
_MAX_EMBED_DESCRIPTION: Final[int] = 4096

# Check for discord library
try:
    import discord
    from discord import app_commands
    from discord.ext import commands, tasks
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    logger.warning(
        "discord.py not installed. "
        "Install with: pip install discord.py>=2.0"
    )


# Only define the full bot class when discord.py is available
if DISCORD_AVAILABLE:
    class OTTODiscordBot(commands.Bot):
        """
        Discord bot for OTTO cognitive support.

        [He2025] Compliance:
        - Fixed command registration order
        - Deterministic message processing
        - Session cleanup on fixed interval

        Usage:
            bot = OTTODiscordBot(token="YOUR_BOT_TOKEN")
            bot.run_bot()
        """

        def __init__(
            self,
            token: str,
            adapter: Optional[DiscordAdapter] = None,
            session_path: Optional[Path] = None,
        ):
            """
            Initialize the Discord bot.

            Args:
                token: Discord bot token
                adapter: DiscordAdapter instance (creates default if None)
                session_path: Path to session storage
            """
            # Set up intents
            intents = discord.Intents.default()
            intents.message_content = True  # Required for reading messages
            intents.dm_messages = True      # For DM support

            # Initialize bot with command prefix (for legacy commands)
            super().__init__(
                command_prefix="/",
                intents=intents,
                description="OTTO - Adaptive cognitive support assistant",
            )

            self.token = token
            self.session_path = session_path or Path(_DEFAULT_SESSION_PATH)

            # Ensure session directory exists
            self.session_path.parent.mkdir(parents=True, exist_ok=True)

            # Create adapter with session persistence
            self.adapter = adapter or DiscordAdapter(
                session_store_path=self.session_path
            )

            # Track sync status
            self._synced = False

        async def setup_hook(self) -> None:
            """
            Called when the bot is starting up.

            [He2025] Fixed setup order:
            1. Register slash commands
            2. Start background tasks
            """
            # Register slash commands
            await self._register_commands()

            # Start session cleanup task
            self.cleanup_sessions.start()

            logger.info("Bot setup complete")

        async def _register_commands(self) -> None:
            """
            Register slash commands.

            [He2025] Fixed registration order.
            """
            # 1. /start - Welcome
            @self.tree.command(name="start", description="Get started with OTTO")
            async def start_command(interaction: discord.Interaction):
                await self._handle_slash_command(interaction, "/start")

            # 2. /status - Current state
            @self.tree.command(name="status", description="See your current cognitive state")
            async def status_command(interaction: discord.Interaction):
                await self._handle_slash_command(interaction, "/status")

            # 3. /calibrate - Set state
            @self.tree.command(name="calibrate", description="Calibrate your current state")
            async def calibrate_command(interaction: discord.Interaction):
                await self._handle_slash_command(interaction, "/calibrate")

            # 4. /reset - Reset session
            @self.tree.command(name="reset", description="Reset your session")
            async def reset_command(interaction: discord.Interaction):
                await self._handle_slash_command(interaction, "/reset")

            # 5. /help - Help
            @self.tree.command(name="help", description="Get help with OTTO commands")
            async def help_command(interaction: discord.Interaction):
                await self._handle_slash_command(interaction, "/help")

            logger.info("Slash commands registered")

        async def _handle_slash_command(
            self,
            interaction: discord.Interaction,
            command_text: str,
        ) -> None:
            """
            Process slash command through adapter.

            [He2025] Fixed processing order:
            1. Defer response (for long operations)
            2. Convert to message
            3. Process through adapter
            4. Send response
            """
            await interaction.response.defer(ephemeral=False)

            message = self._interaction_to_message(interaction, command_text)
            response = self.adapter.process_message(message)

            await self._send_interaction_response(interaction, response)

        async def on_ready(self) -> None:
            """Called when the bot is ready."""
            logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
            logger.info(f"Connected to {len(self.guilds)} guilds")

            # Sync commands once
            if not self._synced:
                try:
                    synced = await self.tree.sync()
                    logger.info(f"Synced {len(synced)} slash commands")
                    self._synced = True
                except Exception as e:
                    logger.error(f"Failed to sync commands: {e}")

        async def on_message(self, message: discord.Message) -> None:
            """
            Handle incoming messages.

            [He2025] Processing order:
            1. Ignore bot messages
            2. Check if bot is mentioned or in DM
            3. Convert to normalized message
            4. Process through adapter
            5. Send response
            """
            # Ignore bot's own messages
            if message.author == self.user:
                return

            # Ignore other bots
            if message.author.bot:
                return

            # Only respond if:
            # 1. In a DM
            # 2. Bot is mentioned
            # 3. Message starts with bot prefix
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = self.user in message.mentions
            is_prefixed = message.content.startswith(("otto ", "OTTO ", "@otto ", "@OTTO "))

            if not (is_dm or is_mentioned or is_prefixed):
                return

            # Remove mention from message text if present
            text = message.content
            if is_mentioned:
                text = text.replace(f"<@{self.user.id}>", "").strip()
                text = text.replace(f"<@!{self.user.id}>", "").strip()
            if is_prefixed:
                for prefix in ("otto ", "OTTO ", "@otto ", "@OTTO "):
                    if text.startswith(prefix):
                        text = text[len(prefix):]
                        break

            # Skip if empty after cleaning
            if not text.strip():
                return

            # Convert and process
            normalized = self._discord_to_message(message, text)
            response = self.adapter.process_message(normalized)

            await self._send_message_response(message, response)

        def _discord_to_message(
            self,
            message: discord.Message,
            text: Optional[str] = None,
        ) -> DiscordMessage:
            """Convert Discord Message to normalized DiscordMessage."""
            reply_to_id = None
            if message.reference and message.reference.message_id:
                reply_to_id = message.reference.message_id

            guild_id = message.guild.id if message.guild else None
            is_dm = isinstance(message.channel, discord.DMChannel)

            return DiscordMessage(
                message_id=message.id,
                user_id=message.author.id,
                channel_id=message.channel.id,
                text=text or message.content,
                timestamp=message.created_at.timestamp(),
                guild_id=guild_id,
                reply_to_message_id=reply_to_id,
                is_dm=is_dm,
            )

        def _interaction_to_message(
            self,
            interaction: discord.Interaction,
            command_text: str,
        ) -> DiscordMessage:
            """Convert Discord Interaction to normalized DiscordMessage."""
            guild_id = interaction.guild_id
            is_dm = guild_id is None

            return DiscordMessage(
                message_id=interaction.id,  # Use interaction ID
                user_id=interaction.user.id,
                channel_id=interaction.channel_id,
                text=command_text,
                timestamp=interaction.created_at.timestamp(),
                guild_id=guild_id,
                reply_to_message_id=None,
                is_dm=is_dm,
            )

        async def _send_message_response(
            self,
            original: discord.Message,
            response: DiscordResponse,
        ) -> None:
            """Send response to a message."""
            response = response.truncate()

            try:
                # Build embed if embed_data provided
                embed = self._build_embed(response) if response.embed_data else None

                if embed and not response.text:
                    await original.reply(embed=embed)
                elif embed:
                    await original.reply(content=response.text, embed=embed)
                else:
                    await original.reply(content=response.text)

            except Exception as e:
                logger.error(f"Failed to send response: {e}")
                try:
                    await original.reply(content="Something went wrong. Please try again.")
                except Exception as e2:
                    logger.error(f"Failed to send error message: {e2}")

        async def _send_interaction_response(
            self,
            interaction: discord.Interaction,
            response: DiscordResponse,
        ) -> None:
            """Send response to a slash command interaction."""
            response = response.truncate()

            try:
                # Build embed if embed_data provided
                embed = self._build_embed(response) if response.embed_data else None

                if embed and not response.text:
                    await interaction.followup.send(
                        embed=embed,
                        ephemeral=response.ephemeral,
                    )
                elif embed:
                    await interaction.followup.send(
                        content=response.text,
                        embed=embed,
                        ephemeral=response.ephemeral,
                    )
                else:
                    await interaction.followup.send(
                        content=response.text,
                        ephemeral=response.ephemeral,
                    )

            except Exception as e:
                logger.error(f"Failed to send interaction response: {e}")
                try:
                    await interaction.followup.send(
                        content="Something went wrong. Please try again.",
                        ephemeral=True,
                    )
                except Exception as e2:
                    logger.error(f"Failed to send error message: {e2}")

        def _build_embed(self, response: DiscordResponse) -> Optional[discord.Embed]:
            """Build Discord embed from response embed_data."""
            if not response.embed_data:
                return None

            data = response.embed_data
            embed = discord.Embed(
                title=data.get("title"),
                description=data.get("description"),
                color=data.get("color", 0x5865F2),  # Discord blurple default
            )

            # Add fields
            for field in data.get("fields", []):
                embed.add_field(
                    name=field.get("name", ""),
                    value=field.get("value", ""),
                    inline=field.get("inline", False),
                )

            # Add footer
            if "footer" in data:
                embed.set_footer(text=data["footer"].get("text", ""))

            return embed

        @tasks.loop(seconds=_CLEANUP_INTERVAL_SECONDS)
        async def cleanup_sessions(self) -> None:
            """Periodically clean up expired sessions."""
            count = self.adapter.cleanup_expired_sessions()
            if count > 0:
                logger.info(f"Cleaned up {count} expired sessions")

        @cleanup_sessions.before_loop
        async def before_cleanup(self) -> None:
            """Wait for bot to be ready before starting cleanup task."""
            await self.wait_until_ready()

        async def on_error(self, event: str, *args, **kwargs) -> None:
            """Handle errors."""
            logger.exception(f"Error in event {event}")

        def run_bot(self, **kwargs) -> None:
            """
            Run the bot.

            Wrapper around discord.py's run() with proper error handling.
            """
            logger.info("Starting OTTO Discord bot...")
            try:
                self.run(self.token, **kwargs)
            except discord.LoginFailure:
                logger.error("Invalid Discord token")
                raise
            except Exception as e:
                logger.exception(f"Bot error: {e}")
                raise

        async def close(self) -> None:
            """Clean shutdown."""
            logger.info("Shutting down OTTO Discord bot...")

            # Stop background tasks
            self.cleanup_sessions.cancel()

            await super().close()
            logger.info("OTTO Discord bot stopped")

else:
    # Stub class when discord.py is not available
    class OTTODiscordBot:
        """Stub class when discord.py is not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "discord.py is required. "
                "Install with: pip install discord.py>=2.0"
            )


def create_bot(
    token: Optional[str] = None,
    session_path: Optional[Path] = None,
) -> "OTTODiscordBot":
    """
    Create and configure a Discord bot instance.

    Args:
        token: Bot token (defaults to DISCORD_BOT_TOKEN env var)
        session_path: Path to session storage

    Returns:
        Configured OTTODiscordBot instance

    Raises:
        ValueError: If no token provided and DISCORD_BOT_TOKEN not set
        ImportError: If discord.py is not installed
    """
    if not DISCORD_AVAILABLE:
        raise ImportError(
            "discord.py is required. "
            "Install with: pip install discord.py>=2.0"
        )

    bot_token = token or os.environ.get("DISCORD_BOT_TOKEN")

    if not bot_token:
        raise ValueError(
            "No Discord bot token provided. "
            "Set DISCORD_BOT_TOKEN environment variable or pass token directly."
        )

    return OTTODiscordBot(token=bot_token, session_path=session_path)


def main() -> None:
    """Entry point for running the bot directly."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    try:
        bot = create_bot()
        bot.run_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


__all__ = [
    "OTTODiscordBot",
    "create_bot",
    "DISCORD_AVAILABLE",
]
