"""CLI interface for OTTO v4.0 — built with Click."""

from __future__ import annotations

from datetime import datetime, timezone

import click

from .models import Commitment
from .state import StateStore, _VALID_ENERGY, _VALID_BURNOUT, _VALID_MOMENTUM
from .store import CommitmentStore


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


def _build_id_map(commitments: list[Commitment]) -> dict[int, str]:
    """Build a mapping from short sequential IDs (1-based) to UUIDs."""
    return {i + 1: c.id for i, c in enumerate(commitments)}


def _get_store() -> CommitmentStore:
    """Create the default store. Separated for testability."""
    return CommitmentStore()


def _get_state_store() -> StateStore:
    """Create the default state store (same DB). Separated for testability."""
    import os
    from pathlib import Path
    db_path = str(Path(os.path.expanduser("~/.otto/commitments.db")))
    return StateStore(db_path=db_path)


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

    id_map = _build_id_map(commitments)
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

    id_map = _build_id_map(active)
    uuid = id_map.get(commitment_id)

    if uuid is None:
        click.echo(f"No commitment #{commitment_id}. Use 'otto list' to see active ones.")
        return

    c = store.get(uuid)
    store.mark_done(uuid)
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

    id_map = _build_id_map(active)
    uuid = id_map.get(commitment_id)

    if uuid is None:
        click.echo(f"No commitment #{commitment_id}. Use 'otto list' to see active ones.")
        return

    c = store.get(uuid)
    store.mark_parked(uuid)
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
            scheduler = NudgeScheduler(
                store=_get_store(),
                state_store=_get_state_store(),
                interval_seconds=interval,
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
        from .nudge import check_and_nudge  # type: ignore[import-not-found]
        from .constitutional import should_suppress
    except ImportError:
        click.echo("Nudge module not ready yet.")
        return

    # Constitutional gate: check cognitive state before nudging
    state_store = _get_state_store()
    state = state_store.load()
    suppression = should_suppress(state, "nudge")
    if suppression is not None:
        click.echo(click.style(suppression.reason, fg="yellow"))
        state_store.increment_suppressed()
        return

    store = _get_store()
    messages = check_and_nudge(store)
    if not messages:
        click.echo("Nothing to nudge about right now.")
    else:
        for msg in messages:
            click.echo(msg)
            click.echo()


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
@click.confirmation_option(prompt="This will delete ALL your commitment data. Are you sure?")
def nuke() -> None:
    """Delete ALL data. Fresh start."""
    store = _get_store()
    store.nuke()
    click.echo(click.style("All data deleted. Fresh start.", fg="red"))
