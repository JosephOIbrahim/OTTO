"""Textual TUI dashboard for OTTO v5.1.

Provides a terminal UI for viewing and managing commitments,
cognitive state, and trail metrics.

Requires the optional ``tui`` dependency group:
    pip install otto[tui]
"""

from __future__ import annotations

import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static

from .log import get_logger
from .models import Commitment, build_id_map
from .state import StateStore
from .store import CommitmentStore
from .trails import TrailStore

_log = get_logger(__name__)

_DB_PATH = str(Path(os.path.expanduser("~/.otto/commitments.db")))


class StatePanel(Static):
    """Displays current cognitive state (energy, burnout, momentum)."""

    def update_state(self, energy: str, burnout: str, momentum: str) -> None:
        """Refresh the displayed state values."""
        text = (
            f"Energy: {energy}  |  "
            f"Burnout: {burnout}  |  "
            f"Momentum: {momentum}"
        )
        self.update(text)


class OttoApp(App):
    """OTTO TUI dashboard application."""

    TITLE = "OTTO"
    CSS_PATH = None

    CSS = """
    StatePanel {
        dock: top;
        height: 3;
        padding: 1;
        background: $surface;
        color: $text;
        text-style: bold;
    }

    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("d", "mark_done", "Done"),
        Binding("p", "mark_parked", "Park"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._commitment_store = CommitmentStore(_DB_PATH)
        self._state_store = StateStore(db_path=_DB_PATH)
        self._trail_store = TrailStore(db_path=_DB_PATH)
        # Maps displayed row index -> commitment UUID
        self._row_id_map: dict[int, str] = {}

    def compose(self) -> ComposeResult:
        """Build the widget tree."""
        yield Header()
        yield StatePanel(id="state-panel")
        yield DataTable(id="commitments-table")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize table columns and load data on startup."""
        table = self.query_one("#commitments-table", DataTable)
        table.add_columns("#", "Commitment", "To", "Status", "Follow-ups")
        table.cursor_type = "row"
        self._refresh_table()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        """Reload active commitments into the DataTable and update state."""
        # Update cognitive state panel
        state = self._state_store.load()
        panel = self.query_one("#state-panel", StatePanel)
        panel.update_state(state.energy, state.burnout, state.momentum)

        # Reload commitments
        table = self.query_one("#commitments-table", DataTable)
        table.clear()
        self._row_id_map.clear()

        commitments = self._commitment_store.get_active()
        if not commitments:
            return

        id_map = build_id_map(commitments)
        # Build a UUID -> Commitment lookup for fast access
        by_uuid: dict[str, Commitment] = {c.id: c for c in commitments}

        row_idx = 0
        for short_id, uuid in sorted(id_map.items()):
            c = by_uuid[uuid]
            table.add_row(
                str(short_id),
                c.commitment_text,
                c.who_to,
                c.status,
                str(c.follow_up_count),
            )
            self._row_id_map[row_idx] = uuid
            row_idx += 1

    def _get_selected_uuid(self) -> str | None:
        """Return the UUID for the currently selected table row, or None."""
        table = self.query_one("#commitments-table", DataTable)
        if table.cursor_row is None:
            return None
        return self._row_id_map.get(table.cursor_row)

    # ------------------------------------------------------------------
    # Actions (keybindings)
    # ------------------------------------------------------------------

    def action_mark_done(self) -> None:
        """Mark the selected commitment as done."""
        uuid = self._get_selected_uuid()
        if uuid is None:
            return
        self._commitment_store.mark_done(uuid)
        self._trail_store.record_outcome(
            "executor", "commitment_detected", "success"
        )
        _log.info("Marked done via TUI: %s", uuid)
        self._refresh_table()

    def action_mark_parked(self) -> None:
        """Park the selected commitment."""
        uuid = self._get_selected_uuid()
        if uuid is None:
            return
        self._commitment_store.mark_parked(uuid)
        self._trail_store.record_outcome(
            "executor", "commitment_detected", "mixed"
        )
        _log.info("Marked parked via TUI: %s", uuid)
        self._refresh_table()

    def action_refresh(self) -> None:
        """Refresh the table and state display."""
        self._refresh_table()
