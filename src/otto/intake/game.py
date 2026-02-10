"""
OTTO OS Personality Intake Game

A Hybrid CLI experience that helps OTTO understand how you work.

Design principles:
- ASCII art for visual interest
- Rich terminal formatting
- No clinical language
- Scenarios feel like conversations
- Results stored as USD

Determinism:
- Trait accumulation uses sorted key iteration
- Deterministic profile generation
"""

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from .scenarios import (
    Scenario,
    ScenarioResult,
    Choice,
    get_scenarios,
)
from .profile_writer import write_profile, ProfileData


console = Console()


# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

OTTO_LOGO = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║     ██████╗ ████████╗████████╗ ██████╗      ██████╗ ███████╗                  ║
║    ██╔═══██╗╚══██╔══╝╚══██╔══╝██╔═══██╗    ██╔═══██╗██╔════╝                  ║
║    ██║   ██║   ██║      ██║   ██║   ██║    ██║   ██║███████╗                  ║
║    ██║   ██║   ██║      ██║   ██║   ██║    ██║   ██║╚════██║                  ║
║    ╚██████╔╝   ██║      ██║   ╚██████╔╝    ╚██████╔╝███████║                  ║
║     ╚═════╝    ╚═╝      ╚═╝    ╚═════╝      ╚═════╝ ╚══════╝                  ║
║                                                                               ║
║              An Operating System for Variable Attention                       ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

OTTO_FACE = """
          ╭────────────╮
          │   ○    ○   │
          │     \\/     │
          │    ────    │
          ╰────────────╯
"""

OTTO_FACE_THINKING = """
          ╭────────────╮
          │   ○    ○   │
          │     \\/     │
          │    ~~~~    │
          ╰────────────╯
"""


# ═══════════════════════════════════════════════════════════════════════════════
# INTAKE GAME
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class IntakeGame:
    """Main game controller for personality intake"""

    results: list[ScenarioResult] = field(default_factory=list)
    trait_accumulator: dict[str, float | str | list] = field(default_factory=dict)

    def run(self) -> ProfileData:
        """Run the complete intake experience"""
        self._show_intro()

        scenarios = get_scenarios()
        total = len(scenarios)

        for i, scenario in enumerate(scenarios, 1):
            self._show_progress(i, total)
            result = self._run_scenario(scenario)
            self.results.append(result)
            self._accumulate_traits(result)

        self._show_outro()

        return ProfileData(traits=self.trait_accumulator)

    def _show_intro(self) -> None:
        """Show the introduction sequence"""
        console.clear()
        console.print(OTTO_LOGO, style="bold cyan")
        time.sleep(1)

        console.print()
        console.print(
            Panel(
                "[bold]Welcome.[/bold]\n\n"
                "I'm OTTO. Before we begin working together, "
                "I'd like to understand how you work.\n\n"
                "This isn't a test. There are no wrong answers.\n"
                "Just scenarios and choices.\n\n"
                "[dim]This takes about 10 minutes.[/dim]",
                title="",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )

        console.print()
        Prompt.ask("[dim]Press Enter to begin[/dim]")
        console.clear()

    def _show_progress(self, current: int, total: int) -> None:
        """Show progress indicator"""
        progress_bar = "█" * current + "░" * (total - current)
        console.print(
            f"\n[dim]Scenario {current}/{total}  [{progress_bar}][/dim]\n",
            justify="center"
        )

    def _run_scenario(self, scenario: Scenario) -> ScenarioResult:
        """Run a single scenario and get user choice"""

        # Show ASCII art if present
        if scenario.ascii_art:
            console.print(
                Panel(
                    scenario.ascii_art,
                    border_style="dim",
                    box=box.ROUNDED,
                ),
                justify="center"
            )

        # Show setup
        console.print(f"\n[italic]{scenario.setup}[/italic]\n")

        # Show OTTO's question
        console.print(OTTO_FACE, style="cyan")
        console.print(
            Panel(
                f"[bold]{scenario.otto_says}[/bold]",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )

        # Show choices
        console.print()
        for i, choice in enumerate(scenario.choices, 1):
            console.print(f"  [bold cyan][{i}][/bold cyan] {choice.text}")
        console.print()

        # Get user input
        while True:
            try:
                response = Prompt.ask(
                    "[dim]Your choice[/dim]",
                    choices=[str(i) for i in range(1, len(scenario.choices) + 1)],
                    show_choices=False,
                )
                choice_index = int(response) - 1
                break
            except (ValueError, KeyError):
                console.print("[red]Please enter a valid number.[/red]")

        # Show follow-up
        selected_choice = scenario.choices[choice_index]
        if selected_choice.follow_up:
            console.print()
            console.print(OTTO_FACE_THINKING, style="cyan")

            # Thinking animation
            with Progress(
                SpinnerColumn(),
                TextColumn("[dim]Processing...[/dim]"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("", total=None)
                time.sleep(1)

            console.print(
                Panel(
                    f"[italic]{selected_choice.follow_up}[/italic]",
                    border_style="green",
                    box=box.ROUNDED,
                )
            )
            time.sleep(1.5)

        console.clear()

        return ScenarioResult(
            scenario_id=scenario.id,
            choice_index=choice_index,
            trait_mappings=selected_choice.trait_mappings,
        )

    def _accumulate_traits(self, result: ScenarioResult) -> None:
        """
        Accumulate traits from scenario result.

        Determinism: Uses sorted key iteration for determinism.
        """
        # Sort keys for deterministic iteration order
        for key in sorted(result.trait_mappings.keys()):
            self.trait_accumulator[key] = result.trait_mappings[key]

    def _show_outro(self) -> None:
        """Show the closing sequence"""
        console.clear()

        console.print(OTTO_FACE, style="cyan")
        console.print(
            Panel(
                "[bold]Got it.[/bold]\n\n"
                "I've built your profile based on what you've shared.\n\n"
                "Remember: this isn't fixed. I'll learn and adapt as we work together.\n"
                "If something doesn't feel right, just tell me.\n\n"
                "[dim]Your profile is stored locally at ~/.otto/profile.usda[/dim]",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )

        console.print()

        # Show summary of detected traits
        console.print("[bold]What I learned:[/bold]\n")

        trait_descriptions = self._generate_trait_summary()
        for desc in trait_descriptions:
            console.print(f"  • {desc}")

        console.print()
        console.print("[dim]Run 'otto' to start working together.[/dim]")
        console.print()

    def _generate_trait_summary(self) -> list[str]:
        """Generate human-readable trait summary"""
        descriptions = []

        # Chronotype
        if chronotype := self.trait_accumulator.get("chronotype"):
            if chronotype == "night_owl":
                descriptions.append("You come alive at night")
            elif chronotype == "early_bird":
                descriptions.append("Mornings are your power hours")
            else:
                descriptions.append("Your energy varies day to day")

        # Work style
        if work_style := self.trait_accumulator.get("work_style"):
            if work_style == "deep_work":
                descriptions.append("You prefer deep, uninterrupted focus")
            elif work_style == "task_switcher":
                descriptions.append("You work well bouncing between tasks")
            else:
                descriptions.append("You work in intense bursts")

        # Stress response
        if stress := self.trait_accumulator.get("stress_response"):
            if stress == "avoid":
                descriptions.append("Overwhelm makes you want to retreat")
            elif stress == "confront":
                descriptions.append("You tackle stress head-on")
            elif stress == "process":
                descriptions.append("You need time to process before acting")
            else:
                descriptions.append("You're good at deprioritizing stress")

        # Protection preference
        if firmness := self.trait_accumulator.get("protection_firmness"):
            if firmness >= 0.7:
                descriptions.append("You want firm boundaries when needed")
            elif firmness <= 0.3:
                descriptions.append("You prefer gentle suggestions")
            else:
                descriptions.append("You want adaptive protection")

        # Recovery
        if recovery := self.trait_accumulator.get("preferred_recovery"):
            descriptions.append(f"When depleted, you recharge through {recovery}")

        return descriptions


def run_intake(use_profile_manager: bool = True) -> None:
    """
    Entry point for intake game.

    Args:
        use_profile_manager: If True, also loads traits into ProfileManager.
                            Default True for integration with cognitive substrate.

    Determinism: Sorted trait accumulation, deterministic profile generation.
    """
    game = IntakeGame()
    profile_data = game.run()

    # Write USD profile (always, for human readability)
    profile_path = Path.home() / ".otto" / "profile.usda"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    write_profile(profile_data, profile_path)
    console.print(f"\n[green]✓[/green] Profile saved to {profile_path}")

    # Also load into ProfileManager if requested
    if use_profile_manager:
        try:
            from .profile_integration import load_intake_to_profile_manager
            profile = load_intake_to_profile_manager(profile_data.traits)
            console.print(f"[green]✓[/green] Profile loaded into cognitive substrate")
        except ImportError:
            # otto.core not available (e.g., running standalone)
            pass
        except Exception as e:
            console.print(f"[yellow]![/yellow] Could not load into cognitive substrate: {e}")


def main() -> None:
    """CLI entry point"""
    try:
        run_intake()
    except KeyboardInterrupt:
        console.print("\n\n[dim]Intake cancelled. Run 'otto-intake' to try again.[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()
