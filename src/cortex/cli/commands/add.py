"""cortex add — capture a note."""

import asyncio
import os
import subprocess
import sys
import tempfile
from typing import Optional

import typer

from cortex.cli.formatting import console, print_note_saved, print_note_saved_with_metadata
from cortex.db.connection import sync_db
from cortex.db.queries.notes import insert_note


def add_note(
    text: Optional[list[str]] = typer.Argument(None, help="Note text to capture"),
    long: bool = typer.Option(False, "--long", "-l", help="Open $EDITOR for multi-line note"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for enrichment and show metadata"),
) -> None:
    """Capture a note quickly."""
    # Determine note text
    note_text: str = ""

    if long:
        note_text = _open_editor()
    elif text:
        note_text = " ".join(text)
    elif not sys.stdin.isatty():
        note_text = sys.stdin.read().strip()
    else:
        console.print("[red]No text provided.[/red] Usage: cortex add \"your note text\"")
        raise typer.Exit(1)

    if not note_text.strip():
        console.print("[red]Empty note — not saved.[/red]")
        raise typer.Exit(1)

    # Save to database
    with sync_db() as conn:
        result = insert_note(conn, note_text, source="cli")

    note_id = result["id"]
    word_count = result["word_count"]

    if wait:
        # Run enrichment synchronously and show metadata
        try:
            from cortex.ai.enrichment import enrich_note

            metadata = asyncio.run(enrich_note(note_id, note_text))
            if metadata:
                tag_names = [t["name"] for t in metadata.get("tags", [])]
                print_note_saved_with_metadata(
                    note_id, word_count,
                    tags=tag_names,
                    category=metadata.get("category", ""),
                    summary=metadata.get("summary", ""),
                )
                return
        except Exception:
            pass

        print_note_saved(note_id, word_count)
    else:
        print_note_saved(note_id, word_count)

        # Fire-and-forget enrichment
        try:
            from cortex.ai.enrichment import enrich_note

            asyncio.run(enrich_note(note_id, note_text))
        except Exception:
            pass  # Enrichment is best-effort


def _open_editor() -> str:
    """Open the user's editor for multi-line note input.

    Returns:
        The text entered by the user.
    """
    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w+", delete=False) as f:
        tmp_path = f.name
        f.write("")

    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path) as f:
            return f.read().strip()
    finally:
        os.unlink(tmp_path)
