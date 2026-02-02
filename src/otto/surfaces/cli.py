"""
CLI Interaction Surface
=======================

Command-line interface surface for OTTO.

Features:
- Markdown rendering with terminal colors
- Progress bar display
- Status line formatting
- Input history

ThinkingMachines [He2025] Compliance:
- Deterministic color mapping
- Fixed progress bar format
- Sorted output for lists
"""

import os
import re
import sys
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Final, List, Optional

from .base import (
    Surface,
    SurfaceType,
    SurfaceMessage,
    SurfaceResponse,
    InputContext,
    RenderFormat,
    MessageRole,
    register_surface,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Constants - [He2025] Compliance
# ============================================================================

CLI_SEED: Final[int] = 0xC11FACE

# ANSI color codes (fixed mapping)
COLORS: Final[Dict[str, str]] = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "gray": "\033[90m",
}

# Burnout level colors (fixed mapping)
BURNOUT_COLORS: Final[Dict[str, str]] = {
    "GREEN": "green",
    "YELLOW": "yellow",
    "ORANGE": "yellow",  # Terminal doesn't have orange
    "RED": "red",
}


class TerminalCapability(Enum):
    """Terminal capabilities."""
    BASIC = "basic"      # No colors
    ANSI = "ansi"        # Standard ANSI colors
    TRUECOLOR = "true"   # 24-bit color


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class CLIConfig:
    """CLI surface configuration.

    Attributes:
        use_colors: Enable terminal colors
        progress_bar_width: Width of progress bars
        show_timestamps: Show timestamps in output
        show_thinking: Show thinking process
        prompt_char: Character for input prompt
        max_line_width: Maximum line width (0 = auto)
    """
    use_colors: bool = True
    progress_bar_width: int = 20
    show_timestamps: bool = False
    show_thinking: bool = False
    prompt_char: str = ">"
    max_line_width: int = 0  # 0 = use terminal width

    def __post_init__(self):
        # Auto-detect terminal width
        if self.max_line_width == 0:
            try:
                self.max_line_width = os.get_terminal_size().columns
            except OSError:
                self.max_line_width = 80


# ============================================================================
# CLI Surface
# ============================================================================

class CLISurface(Surface):
    """Command-line interface surface.

    Provides terminal-based interaction with:
    - Colored output
    - Progress bars
    - Status line display
    - Input prompt with history

    Example:
        >>> cli = CLISurface()
        >>> context = cli.receive_input("Hello")
        >>> cli.send_response(SurfaceResponse(content="Hi there!"))
    """

    surface_type = SurfaceType.CLI

    def __init__(
        self,
        config: CLIConfig = None,
    ):
        """Initialize CLI surface.

        Args:
            config: CLI configuration
        """
        super().__init__(render_format=RenderFormat.MARKDOWN)

        self.config = config or CLIConfig()
        self._capability = self._detect_capability()
        self._input_history: List[str] = []

        logger.info(f"CLI surface initialized with capability: {self._capability.value}")

    # =========================================================================
    # Terminal Detection
    # =========================================================================

    def _detect_capability(self) -> TerminalCapability:
        """Detect terminal capability level."""
        if not self.config.use_colors:
            return TerminalCapability.BASIC

        # Check for color support
        if os.environ.get("NO_COLOR"):
            return TerminalCapability.BASIC

        # Check TERM
        term = os.environ.get("TERM", "")
        if "256color" in term or "truecolor" in term:
            return TerminalCapability.TRUECOLOR
        elif term and term != "dumb":
            return TerminalCapability.ANSI

        # Windows check
        if sys.platform == "win32":
            # Windows 10+ supports ANSI
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(
                    kernel32.GetStdHandle(-11), 7
                )
                return TerminalCapability.ANSI
            except:
                return TerminalCapability.BASIC

        return TerminalCapability.BASIC

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text.

        Args:
            text: Text to colorize
            color: Color name

        Returns:
            Colorized text (or plain if colors disabled)
        """
        if self._capability == TerminalCapability.BASIC:
            return text

        color_code = COLORS.get(color, "")
        reset = COLORS["reset"]

        if color_code:
            return f"{color_code}{text}{reset}"
        return text

    # =========================================================================
    # Abstract Method Implementations
    # =========================================================================

    def render(self, response: SurfaceResponse) -> str:
        """Render response for CLI display.

        Converts markdown to terminal-friendly format.

        Args:
            response: Response to render

        Returns:
            Terminal-formatted string
        """
        content = response.content

        # Process markdown elements
        content = self._render_markdown(content)

        # Add thinking if enabled
        if self.config.show_thinking and response.thinking:
            thinking = self._colorize(
                f"Thinking: {response.thinking[:200]}...",
                "gray"
            )
            content = f"{thinking}\n\n{content}"

        # Add timestamp if enabled
        if self.config.show_timestamps:
            timestamp = datetime.now().strftime("%H:%M:%S")
            content = f"{self._colorize(timestamp, 'gray')} {content}"

        return content

    def _render_markdown(self, text: str) -> str:
        """Convert markdown to terminal format.

        Args:
            text: Markdown text

        Returns:
            Terminal-formatted text
        """
        if self._capability == TerminalCapability.BASIC:
            # Strip markdown for basic terminals
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            text = re.sub(r'`(.+?)`', r'\1', text)
            return text

        # Bold
        text = re.sub(
            r'\*\*(.+?)\*\*',
            lambda m: self._colorize(m.group(1), "bold"),
            text
        )

        # Italic (dim)
        text = re.sub(
            r'\*(.+?)\*',
            lambda m: self._colorize(m.group(1), "dim"),
            text
        )

        # Code (cyan)
        text = re.sub(
            r'`(.+?)`',
            lambda m: self._colorize(m.group(1), "cyan"),
            text
        )

        # Headers (bold blue)
        text = re.sub(
            r'^(#{1,3})\s+(.+)$',
            lambda m: self._colorize(m.group(2), "blue"),
            text,
            flags=re.MULTILINE
        )

        # Lists (green bullet)
        text = re.sub(
            r'^(\s*)-\s+',
            lambda m: f"{m.group(1)}{self._colorize('•', 'green')} ",
            text,
            flags=re.MULTILINE
        )

        return text

    def process_input(self, raw_input: str) -> InputContext:
        """Process CLI input.

        Args:
            raw_input: Raw input string

        Returns:
            Processed InputContext
        """
        context = InputContext(raw_input=raw_input)

        # Detect intent from commands
        if raw_input.startswith("/"):
            parts = raw_input[1:].split(None, 1)
            context.detected_intent = f"command:{parts[0]}"
            if len(parts) > 1:
                context.extracted_entities["args"] = parts[1]

        # Check for file references
        file_matches = re.findall(r'@(\S+)', raw_input)
        if file_matches:
            context.attachments.extend(file_matches)
            context.extracted_entities["files"] = file_matches

        # Add to history
        if raw_input.strip():
            self._input_history.append(raw_input)

        return context

    def display(self, content: str) -> None:
        """Display content to terminal.

        Args:
            content: Content to display
        """
        print(content)

    def prompt(self, message: str = "") -> str:
        """Prompt user for input.

        Args:
            message: Optional prompt message

        Returns:
            User input string
        """
        if message:
            print(message)

        prompt_str = f"{self._colorize(self.config.prompt_char, 'cyan')} "
        try:
            return input(prompt_str)
        except (EOFError, KeyboardInterrupt):
            return ""

    # =========================================================================
    # CLI-Specific Methods
    # =========================================================================

    def display_progress(
        self,
        current: int,
        total: int,
        description: str = "",
    ) -> None:
        """Display progress bar.

        Args:
            current: Current progress
            total: Total steps
            description: Progress description
        """
        if total <= 0:
            return

        percentage = current / total
        filled = int(self.config.progress_bar_width * percentage)
        empty = self.config.progress_bar_width - filled

        bar = f"[{'#' * filled}{'-' * empty}]"
        bar = self._colorize(bar, "cyan")

        line = f"\r{bar} {percentage * 100:.0f}%"
        if description:
            line += f" - {description}"

        # Pad to clear previous content
        line = line.ljust(self.config.max_line_width)

        sys.stdout.write(line)
        sys.stdout.flush()

        # Newline when complete
        if current >= total:
            print()

    def display_status(
        self,
        time_estimate: str,
        goal: str,
        expert: str,
        altitude: str,
        burnout: str,
        momentum: str,
    ) -> None:
        """Display cognitive status line.

        Args:
            time_estimate: Estimated session time
            goal: Current goal
            expert: Active expert
            altitude: Current altitude
            burnout: Burnout level
            momentum: Momentum phase
        """
        # Color burnout level
        burnout_color = BURNOUT_COLORS.get(burnout, "white")
        burnout_str = self._colorize(burnout, burnout_color)

        status = f"[{time_estimate} | Goal: {goal} | {expert} | {altitude} | {burnout_str} | {momentum}]"
        status = self._colorize(status, "dim")

        print(status)

    def display_error(self, message: str) -> None:
        """Display error message.

        Args:
            message: Error message
        """
        error = self._colorize(f"Error: {message}", "red")
        print(error)

    def display_warning(self, message: str) -> None:
        """Display warning message.

        Args:
            message: Warning message
        """
        warning = self._colorize(f"Warning: {message}", "yellow")
        print(warning)

    def display_success(self, message: str) -> None:
        """Display success message.

        Args:
            message: Success message
        """
        success = self._colorize(f"✓ {message}", "green")
        print(success)

    def display_separator(self, char: str = "─") -> None:
        """Display separator line.

        Args:
            char: Character to use for separator
        """
        line = char * min(self.config.max_line_width, 60)
        print(self._colorize(line, "dim"))

    def display_heading(self, text: str) -> None:
        """Display section heading.

        Args:
            text: Heading text
        """
        heading = self._colorize(text, "bold")
        print(f"\n{heading}")
        self.display_separator()

    def display_table(
        self,
        headers: List[str],
        rows: List[List[str]],
    ) -> None:
        """Display simple table.

        Args:
            headers: Column headers
            rows: Table rows
        """
        if not headers or not rows:
            return

        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(str(cell)))

        # Format header
        header_line = " | ".join(
            h.ljust(widths[i]) for i, h in enumerate(headers)
        )
        print(self._colorize(header_line, "bold"))

        # Separator
        sep_line = "-+-".join("-" * w for w in widths)
        print(sep_line)

        # Rows
        for row in rows:
            row_line = " | ".join(
                str(cell).ljust(widths[i]) if i < len(widths) else str(cell)
                for i, cell in enumerate(row)
            )
            print(row_line)

    def clear_screen(self) -> None:
        """Clear terminal screen using ANSI escape codes (safe, no shell)."""
        # Use ANSI escape sequence to clear screen - no shell invocation
        # \033[2J clears the screen, \033[H moves cursor to home position
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    # =========================================================================
    # Capabilities
    # =========================================================================

    def get_capabilities(self) -> Dict[str, bool]:
        """Get CLI surface capabilities."""
        base = super().get_capabilities()
        base.update({
            "colors": self._capability != TerminalCapability.BASIC,
            "progress_bar": True,
            "tables": True,
            "clear_screen": True,
            "streaming": True,
        })
        return base


# ============================================================================
# Module Initialization
# ============================================================================

# Create and register default CLI surface
_default_cli: Optional[CLISurface] = None


def get_cli_surface() -> CLISurface:
    """Get or create default CLI surface."""
    global _default_cli
    if _default_cli is None:
        _default_cli = CLISurface()
        register_surface(_default_cli)
    return _default_cli


__all__ = [
    "CLISurface",
    "CLIConfig",
    "TerminalCapability",
    "COLORS",
    "BURNOUT_COLORS",
    "get_cli_surface",
]
