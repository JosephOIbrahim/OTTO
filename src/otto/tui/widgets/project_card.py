"""
Project Card Widget
===================

[He2025] Compliant widget displaying active project.

Principles:
1. Render is a pure function of Project
2. All visual mappings from constants (FIXED)
3. No internal mutable state
4. Deterministic progress bar calculation
"""

from rich.console import Console, ConsoleOptions, RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress_bar import ProgressBar
from typing import Optional, Tuple

from ..state import Project, TUIState
from ..constants import (
    PROJECT_STATUS_COLORS,
    PROJECT_STATUS_ICONS,
)


class ProjectCardWidget:
    """
    Widget displaying the active FOCUS project.

    [He2025] Compliance:
    - No internal mutable state
    - Render is pure function of input
    - All mappings from FIXED constants
    - Progress bar calculation is deterministic
    """

    def __init__(
        self,
        project: Optional[Project] = None,
        all_projects: Tuple[Project, ...] = (),
    ):
        """Initialize with optional project."""
        self._project = project
        self._all_projects = all_projects

    def update(
        self,
        project: Optional[Project] = None,
        all_projects: Tuple[Project, ...] = (),
    ) -> "ProjectCardWidget":
        """
        Create new widget with updated project.

        [He2025] Compliance: Returns new instance, doesn't mutate.
        """
        return ProjectCardWidget(project, all_projects)

    def _render_progress_bar(self, progress: float, width: int = 20) -> Text:
        """
        Render deterministic progress bar.

        [He2025] Compliance:
        - Integer math to avoid floating point non-determinism
        - Fixed width calculation
        """
        # Convert to integer percentage to avoid FP issues
        percentage = int(progress * 100)
        filled_count = int(percentage * width / 100)
        empty_count = width - filled_count

        # Determine color based on progress thresholds
        # [He2025]: Fixed thresholds, no runtime variation
        if percentage >= 75:
            color = "green"
        elif percentage >= 50:
            color = "yellow"
        elif percentage >= 25:
            color = "dark_orange"
        else:
            color = "red"

        text = Text()
        text.append("█" * filled_count, style=color)
        text.append("░" * empty_count, style="dim")
        text.append(f" {percentage}%", style="bold")
        return text

    def _render_status_badge(self, status: str) -> Text:
        """
        Render status badge.

        [He2025] Compliance: Pure function, FIXED mappings.
        """
        icon = PROJECT_STATUS_ICONS.get(status, "○")
        color_name, _ = PROJECT_STATUS_COLORS.get(status, ("white", "#ffffff"))

        text = Text()
        text.append(f"[{icon} {status}]", style=f"bold {color_name}")
        return text

    def _render_project_list(self) -> Text:
        """
        Render list of all projects with status.

        [He2025] Compliance:
        - Fixed ordering (FOCUS first, then by status priority)
        - Pure function
        """
        if not self._all_projects:
            return Text("No projects", style="dim")

        # Sort projects by status priority
        # [He2025]: Fixed sort order
        status_priority = {
            "FOCUS": 0,
            "HOLDING": 1,
            "BACKGROUND": 2,
            "PARKED": 3,
            "ARCHIVED": 4,
        }

        sorted_projects = sorted(
            self._all_projects,
            key=lambda p: (status_priority.get(p.status, 99), p.name)
        )

        text = Text()
        for i, project in enumerate(sorted_projects[:5]):  # Max 5 projects
            if i > 0:
                text.append("\n")

            icon = PROJECT_STATUS_ICONS.get(project.status, "○")
            color_name, _ = PROJECT_STATUS_COLORS.get(
                project.status, ("white", "#ffffff")
            )

            text.append(f"  {icon} ", style=color_name)
            text.append(project.name, style=f"bold {color_name}" if project.status == "FOCUS" else "")

            if project.status != "FOCUS":
                text.append(f" ({project.status})", style="dim")

        if len(sorted_projects) > 5:
            text.append(f"\n  ... and {len(sorted_projects) - 5} more", style="dim")

        return text

    def render(self) -> Panel:
        """
        Render the complete project card widget.

        [He2025] Compliance:
        - Pure function of self._project
        - Fixed layout structure
        - All mappings from constants
        """
        if self._project is None:
            # No focus project
            content = Text()
            content.append("No active FOCUS project\n\n", style="dim italic")
            content.append("Projects:\n", style="bold")
            content.append_text(self._render_project_list())

            return Panel(
                content,
                title="[bold yellow]Active Project[/bold yellow]",
                border_style="yellow",
            )

        project = self._project

        # Create table with FIXED structure
        table = Table.grid(padding=(0, 1))
        table.add_column("Content", no_wrap=False)

        # Row 1: Project name with status badge
        name_row = Text()
        name_row.append_text(self._render_status_badge(project.status))
        name_row.append(" ")
        name_row.append(project.name, style="bold bright_white")
        table.add_row(name_row)

        # Row 2: Progress bar
        progress_row = Text()
        progress_row.append("Progress: ", style="dim")
        progress_row.append_text(self._render_progress_bar(project.progress))
        table.add_row(progress_row)

        # Row 3: Next action
        if project.next_action:
            next_row = Text()
            next_row.append("Next: ", style="bold cyan")
            next_row.append(project.next_action)
            table.add_row(next_row)

        # Row 4: Other projects (if any besides focus)
        other_projects = tuple(
            p for p in self._all_projects if p.status != "FOCUS"
        )
        if other_projects:
            table.add_row(Text())  # Spacer
            other_row = Text()
            other_row.append("Other Projects:\n", style="bold dim")

            for i, p in enumerate(other_projects[:3]):
                if i > 0:
                    other_row.append("\n")
                icon = PROJECT_STATUS_ICONS.get(p.status, "○")
                color_name, _ = PROJECT_STATUS_COLORS.get(p.status, ("dim", "#888"))
                other_row.append(f"  {icon} ", style=color_name)
                other_row.append(p.name, style="dim")
                other_row.append(f" ({p.status})", style="dim")

            table.add_row(other_row)

        return Panel(
            table,
            title="[bold green]Active Project[/bold green]",
            border_style="green",
        )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()


def render_project_card(state: TUIState) -> Panel:
    """
    Functional interface for rendering project card.

    [He2025] Compliance: Pure function, no side effects.
    """
    focus_project = state.get_focus_project()
    widget = ProjectCardWidget(focus_project, state.projects)
    return widget.render()
