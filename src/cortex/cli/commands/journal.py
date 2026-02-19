"""cortex journal — longer-form journal entry."""

import os
import subprocess
import tempfile

from cortex.cli.formatting import console, print_note_saved
from cortex.db.connection import sync_db
from cortex.db.queries.notes import insert_note


def journal_entry() -> None:
    """Open your editor for a journal entry."""
    editor = os.environ.get("EDITOR", "nano")

    with tempfile.NamedTemporaryFile(suffix=".md", mode="w+", delete=False) as f:
        tmp_path = f.name
        f.write("# Journal Entry\n\n")

    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path) as f:
            text = f.read().strip()
    finally:
        os.unlink(tmp_path)

    if not text or text == "# Journal Entry":
        console.print("[dim]Empty journal entry — not saved.[/dim]")
        return

    with sync_db() as conn:
        result = insert_note(conn, text, source="cli", is_journal=True)

    print_note_saved(result["id"], result["word_count"])

    # Fire-and-forget enrichment
    try:
        import asyncio
        from cortex.ai.enrichment import enrich_note

        asyncio.run(enrich_note(result["id"], text))
    except Exception:
        pass
