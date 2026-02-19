"""cortex recent — show recent notes."""

import typer

from cortex.cli.formatting import print_note_list
from cortex.db.connection import sync_db
from cortex.db.queries.notes import get_recent_notes


def recent_notes(
    n: int = typer.Option(10, "--count", "-n", help="Number of notes to show"),
    today: bool = typer.Option(False, "--today", "-t", help="Show only today's notes"),
) -> None:
    """Show recent notes."""
    with sync_db() as conn:
        notes = get_recent_notes(conn, limit=n, today_only=today)

    print_note_list(notes)
