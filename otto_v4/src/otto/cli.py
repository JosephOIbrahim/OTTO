"""CLI interface for OTTO v4.0 — built with Click."""

from __future__ import annotations

from datetime import datetime, timezone

import click

from .models import Commitment, build_id_map, parse_duration
from .plasticity import PlasticityWindow
from .state import StateStore, _VALID_ENERGY, _VALID_BURNOUT, _VALID_MOMENTUM
from .store import CommitmentStore
from .trails import TrailStore


def _relative_time(dt: datetime) -> str:
    """Return a human-readable relative time string like '3 days ago'."""
    now = datetime.now(timezone.utc)
    # Ensure dt is timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


def _format_deadline(dt: datetime | None) -> str:
    """Format a deadline as 'Feb 12' or 'none'."""
    if dt is None:
        return "none"
    return dt.strftime("%b %d").replace(" 0", " ")




def _get_store() -> CommitmentStore:
    """Create the default store. Separated for testability."""
    return CommitmentStore()


def _get_state_store() -> StateStore:
    """Create the default state store (same DB). Separated for testability."""
    import os
    from pathlib import Path
    db_path = str(Path(os.path.expanduser("~/.otto/commitments.db")))
    return StateStore(db_path=db_path)


def _get_trail_store() -> TrailStore:
    """Create the default trail store (same DB). Separated for testability."""
    import os
    from pathlib import Path
    db_path = str(Path(os.path.expanduser("~/.otto/commitments.db")))
    return TrailStore(db_path=db_path)


@click.group()
def main():
    """OTTO -- a commitment tracker for people who forget."""
    pass


@main.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show all including done/parked")
@click.option("--due", is_flag=True, help="Show only overdue")
def list_commitments(show_all: bool, due: bool) -> None:
    """List commitments."""
    store = _get_store()

    if due:
        commitments = store.get_due()
        label = "Overdue Commitments"
    elif show_all:
        commitments = store.get_all()
        label = "All Commitments"
    else:
        commitments = store.get_active()
        label = "Active Commitments"

    if not commitments:
        if due:
            click.echo("No overdue commitments. Nice.")
        else:
            click.echo(
                "No active commitments. Either you're crushing it, "
                "or OTTO isn't watching yet."
            )
        return

    click.echo()
    click.echo(click.style(f"{label} ({len(commitments)})", bold=True))
    click.echo()

    id_map = build_id_map(commitments)
    for short_id, uuid in sorted(id_map.items()):
        c = next(cm for cm in commitments if cm.id == uuid)
        age = _relative_time(c.created_at)
        deadline_str = _format_deadline(c.deadline)
        source = c.source_chat
        follow_ups = c.follow_up_count

        line1 = f"  #{short_id}  [{age}]  {c.commitment_text}"
        if show_all and c.status != "active":
            line1 += click.style(f"  ({c.status})", fg="yellow")
        click.echo(line1)

        line2 = f"      From: {source} | Due: {deadline_str} | Followed up: {follow_ups}x"
        click.echo(click.style(line2, dim=True))

        line3 = f"      -> otto done {short_id} | otto park {short_id}"
        click.echo(click.style(line3, dim=True))
        click.echo()



@main.command()
@click.argument("commitment_id", type=int)
def done(commitment_id: int) -> None:
    """Mark a commitment as done."""
    store = _get_store()
    active = store.get_active()

    if not active:
        click.echo("No active commitments.")
        return

    id_map = build_id_map(active)
    uuid = id_map.get(commitment_id)

    if uuid is None:
        click.echo(f"No commitment #{commitment_id}. Use 'otto list' to see active ones.")
        return

    c = store.get(uuid)
    store.mark_done(uuid)

    # Track completion for nudge effectiveness + deposit trail
    state_store = _get_state_store()
    state_store.increment_nudges_completed()

    trail_store = _get_trail_store()
    if c.follow_up_count > 0:
        # Nudge led to completion -> strong positive trail (amplified during crisis)
        state = state_store.load()
        window = PlasticityWindow.load(state_store)
        window.update(state)
        window.save(state_store)
        trail_store.deposit("executor:nudge", "commitment_detected", window.adjust_strength(1.0))

    trail_store.record_outcome("executor", "commitment_detected", "success")
    click.echo(click.style(f"Done: {c.commitment_text}", fg="green"))


@main.command()
@click.argument("commitment_id", type=int)
def park(commitment_id: int) -> None:
    """Park a commitment (guilt-free)."""
    store = _get_store()
    active = store.get_active()

    if not active:
        click.echo("No active commitments.")
        return

    id_map = build_id_map(active)
    uuid = id_map.get(commitment_id)

    if uuid is None:
        click.echo(f"No commitment #{commitment_id}. Use 'otto list' to see active ones.")
        return

    c = store.get(uuid)
    store.mark_parked(uuid)

    trail_store = _get_trail_store()
    if c.follow_up_count > 0:
        # Nudge led to park -> weak positive trail (amplified during crisis)
        state_store = _get_state_store()
        state = state_store.load()
        window = PlasticityWindow.load(state_store)
        window.update(state)
        window.save(state_store)
        trail_store.deposit("executor:nudge", "commitment_detected", window.adjust_strength(0.3))

    trail_store.record_outcome("executor", "commitment_detected", "mixed")
    click.echo(click.style(f"Parked: {c.commitment_text}", fg="yellow"))


@main.command()
@click.argument("text")
@click.option("--to", "who_to", default="unknown", help="Who the commitment is to")
@click.option("--by", "deadline_str", default=None, help="Deadline (YYYY-MM-DD)")
def add(text: str, who_to: str, deadline_str: str | None) -> None:
    """Manually add a commitment."""
    deadline = None
    if deadline_str is not None:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            click.echo("Bad date format. Use YYYY-MM-DD.")
            return

    commitment = Commitment(
        raw_message=text,
        commitment_text=text,
        who_to=who_to,
        source_chat="manual",
        deadline=deadline,
        deadline_source="manual" if deadline else "none",
    )

    store = _get_store()
    store.add(commitment)
    click.echo(click.style(f"Added: {text}", fg="green"))


@main.command()
@click.option("--port", default=8000, help="Port for webhook server")
@click.option("--schedule", is_flag=True, help="Enable automatic nudge checks")
@click.option("--interval", default=60, help="Nudge check interval in seconds")
def watch(port: int, schedule: bool, interval: int) -> None:
    """Start WhatsApp watcher (webhook server)."""
    try:
        from .watcher import main as watcher_main
        import os
        os.environ.setdefault("OTTO_WATCHER_PORT", str(port))

        if schedule:
            from .scheduler import NudgeScheduler

            # Auto-detect WhatsApp transport from env vars
            transport = None
            wa_phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
            wa_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
            if wa_phone_id and wa_token:
                from .transport import WhatsAppTransport
                transport = WhatsAppTransport(
                    phone_number_id=wa_phone_id,
                    access_token=wa_token,
                )
                click.echo("WhatsApp outbound transport active")
            else:
                from .transport import CliTransport
                transport = CliTransport()

            scheduler = NudgeScheduler(
                store=_get_store(),
                state_store=_get_state_store(),
                interval_seconds=interval,
                transport=transport,
            )
            scheduler.start()
            click.echo(
                f"Nudge scheduler active (every {interval}s, "
                f"constitutional gating on)"
            )

        watcher_main()
    except ImportError as e:
        click.echo(f"Watcher not available: {e}")


@main.command()
def nudge() -> None:
    """Run follow-up check now."""
    try:
        from .constitutional import should_suppress
        from .modes import (
            AcknowledgerMode,
            DecomposerMode,
            ExecutorMode,
            GuideMode,
            ProtectorMode,
            RedirectorMode,
            RestorerMode,
        )
        from .learner import compute_ucb_adjustments
        from .router import route_and_execute
        from .signals import Signal, SignalType, detect_signals
    except ImportError:
        click.echo("Nudge module not ready yet.")
        return

    # Constitutional gate: fast-fail before entering the pipeline
    state_store = _get_state_store()
    state = state_store.load()
    suppression = should_suppress(state, "nudge")
    if suppression is not None:
        click.echo(click.style(suppression.reason, fg="yellow"))
        state_store.increment_suppressed()
        return

    store = _get_store()
    trail_store = _get_trail_store()

    # PRISM -> NEXUS -> Modes pipeline
    # For scheduled nudge checks, inject a commitment signal
    signals = [Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8)]

    # UCB1-based learning adjustments from outcome history
    adjustments = compute_ucb_adjustments(signals, trail_store)

    modes = [
        ExecutorMode(store=store),
        ProtectorMode(),
        RestorerMode(),
        DecomposerMode(),
        AcknowledgerMode(),
        RedirectorMode(),
        GuideMode(),
    ]

    response = route_and_execute(signals, state, modes, trail_adjustments=adjustments)

    if response is None or not response.text:
        click.echo("Nothing to nudge about right now.")
    else:
        # Record which mode was selected
        primary = response.metadata.get("primary", "unknown")
        context = signals[0].type.value if signals else "unknown"
        trail_store.record_outcome(primary, context, "activated")

        if response.suppress_others:
            # Safety mode activated (protector/restorer)
            click.echo(click.style(response.text, fg="yellow"))
        else:
            click.echo(response.text)


@main.command()
def stats() -> None:
    """Show commitment statistics."""
    store = _get_store()
    counts = store.count()

    active = counts.get("active", 0)
    done_count = counts.get("done", 0)
    parked = counts.get("parked", 0)

    avg_raw = store.avg_follow_ups_done()
    avg_follow = f"{avg_raw:.1f}" if avg_raw is not None else "n/a"

    click.echo()
    click.echo(click.style("OTTO Stats", bold=True))
    click.echo(f"  Active: {active}")
    click.echo(f"  Done: {done_count}")
    click.echo(f"  Parked: {parked}")
    click.echo(f"  Avg follow-ups before done: {avg_follow}")
    click.echo()



@main.command()
@click.argument("level", required=False, default=None)
def energy(level: str | None) -> None:
    """Show or set your energy level.

    Without arguments, shows the current cognitive state.
    With an argument (high, medium, low, depleted), sets energy.
    """
    state_store = _get_state_store()

    if level is None:
        # Show current state
        state = state_store.load()
        click.echo()
        click.echo(click.style("OTTO Cognitive State", bold=True))
        click.echo(f"  Energy:   {state.energy}")
        click.echo(f"  Burnout:  {state.burnout}")
        click.echo(f"  Momentum: {state.momentum}")
        if state.nudges_sent_today > 0:
            click.echo(
                f"  Nudges today: {state.nudges_sent_today} sent, "
                f"{state.nudges_completed_today} completed"
            )
        if state.suppressed_count > 0:
            click.echo(f"  Suppressed: {state.suppressed_count}")
        click.echo()
        return

    try:
        state = state_store.set_energy(level)
    except ValueError:
        valid = ", ".join(sorted(_VALID_ENERGY))
        click.echo(f"Invalid level. Choose from: {valid}")
        return

    click.echo(click.style(f"Energy set to {level}.", fg="green"))
    if level == "depleted":
        click.echo("OTTO will give you space. Your commitments are safe.")
    elif level == "low":
        click.echo("OTTO will go easy. Only urgent things.")




@main.command()
@click.argument("commitment_id", type=int)
@click.argument("duration", type=str)
def snooze(commitment_id: int, duration: str) -> None:
    """Snooze a commitment for a duration (e.g. 4h, 2d, 30m)."""
    delta = parse_duration(duration)
    if delta is None:
        click.echo("Invalid duration. Use e.g. 30m, 4h, 2d.")
        return

    store = _get_store()
    active = store.get_active()

    if not active:
        click.echo("No commitment to snooze.")
        return

    id_map = build_id_map(active)
    uuid = id_map.get(commitment_id)

    if uuid is None:
        click.echo(f"No commitment #{commitment_id}. Use 'otto list' to see active ones.")
        return

    until = datetime.now(timezone.utc) + delta
    store.snooze(uuid, until)
    c = store.get(uuid)
    click.echo(click.style(f"Snoozed: {c.commitment_text} (until {until.strftime('%b %d %H:%M')} UTC)", fg="cyan"))


@main.command()
@click.argument("commitment_id", type=int)
@click.argument("note", type=str)
def wip(commitment_id: int, note: str) -> None:
    """Add a work-in-progress note to a commitment."""
    store = _get_store()
    active = store.get_active()

    if not active:
        click.echo("No commitment to add note to.")
        return

    id_map = build_id_map(active)
    uuid = id_map.get(commitment_id)

    if uuid is None:
        click.echo(f"No commitment #{commitment_id}. Use 'otto list' to see active ones.")
        return

    store.add_note(uuid, note)
    c = store.get(uuid)
    click.echo(click.style(f"Noted on: {c.commitment_text}", fg="green"))


@main.command()
def metrics() -> None:
    """Show learning metrics and routing statistics."""
    trail_store = _get_trail_store()

    # Mode outcomes
    total_outcomes = trail_store.get_total_outcomes()
    click.echo()
    click.echo(click.style("OTTO Learning Metrics", bold=True))
    click.echo()

    if total_outcomes == 0:
        click.echo("  No outcome data yet. Use OTTO and data will accumulate.")
        click.echo()
        return

    click.echo(click.style("Mode outcomes:", bold=True))
    all_modes = trail_store.get_all_modes()

    for mode_name in all_modes:
        stats = trail_store.get_mode_stats(mode_name)
        rate = trail_store.get_success_rate(mode_name)
        rate_str = f"{rate:.0%}" if rate is not None else "n/a"
        outcomes = ", ".join(
            f"{k}={v}" for k, v in sorted(stats.items()) if k != "total"
        )
        click.echo(f"  {mode_name}: {outcomes} (total={stats['total']}, success_rate={rate_str})")

    # UCB adjustments
    click.echo()
    click.echo(click.style("UCB1 adjustments (current):", bold=True))
    try:
        from .learner import compute_ucb_adjustments
        from .signals import Signal, SignalType

        # Compute for all signal types that have mode mappings
        all_signals = [
            Signal(type=st, confidence=0.8)
            for st in SignalType
        ]
        adjustments = compute_ucb_adjustments(all_signals, trail_store)
        if adjustments:
            for mode_name, adj in sorted(adjustments.items()):
                direction = "+" if adj >= 0 else ""
                click.echo(f"  {mode_name}: {direction}{adj:.4f}")
        else:
            click.echo("  No adjustments yet (need >= 3 samples per mode)")
    except ImportError:
        click.echo("  UCB module not available")

    # Trail counts
    click.echo()
    trail_count = trail_store.count()
    click.echo(f"  Trail deposits: {trail_count}")
    click.echo(f"  Total outcomes: {total_outcomes}")
    click.echo()


@main.command()
@click.option("--cycles", default=100, help="Number of simulation cycles")
@click.option("--seed", default=42, help="Deterministic seed")
def simulate(cycles: int, seed: int) -> None:
    """Run learning simulation to exercise UCB1 pipeline."""
    import tempfile
    from pathlib import Path

    from .simulate import SimulationEngine

    db_path = str(Path(tempfile.mkdtemp()) / "simulation.db")
    engine = SimulationEngine(db_path=db_path)

    click.echo(f"Running {cycles} cycles (seed={seed})...")
    result = engine.run(n_cycles=cycles, seed=seed)
    click.echo()
    click.echo(result.summary())


@main.command()
def tui() -> None:
    """Launch the TUI dashboard."""
    try:
        from .tui import OttoApp
        app = OttoApp()
        app.run()
    except ImportError:
        click.echo("TUI requires textual. Install with: pip install otto[tui]")


@main.command()
@click.confirmation_option(prompt="This will delete ALL your data (commitments + learning). Are you sure?")
def nuke() -> None:
    """Delete ALL data. Fresh start."""
    store = _get_store()
    store.nuke()
    trail_store = _get_trail_store()
    trail_store.nuke()
    click.echo(click.style("All data deleted. Fresh start.", fg="red"))
