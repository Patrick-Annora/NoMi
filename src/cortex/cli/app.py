"""Cortex CLI — main Typer application."""

import typer

from cortex.cli.commands.add import add_note
from cortex.cli.commands.enrich import enrich_notes
from cortex.cli.commands.journal import journal_entry
from cortex.cli.commands.recent import recent_notes
from cortex.cli.commands.search import search_notes
from cortex.cli.commands.serve import serve_web
from cortex.cli.commands.status import show_status
from cortex.cli.formatting import console

app = typer.Typer(
    name="cortex",
    help="Your external cortex — capture everything, ask for it back.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command("add")
def cmd_add(
    text: list[str] = typer.Argument(None, help="Note text to capture"),
    long: bool = typer.Option(False, "--long", "-l", help="Open $EDITOR for multi-line note"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for enrichment and show metadata"),
) -> None:
    """Capture a note quickly."""
    add_note(text, long, wait)


@app.command("recent")
def cmd_recent(
    n: int = typer.Option(10, "--count", "-n", help="Number of notes to show"),
    today: bool = typer.Option(False, "--today", "-t", help="Show only today's notes"),
) -> None:
    """Show recent notes."""
    recent_notes(n, today)


@app.command("journal")
def cmd_journal() -> None:
    """Open your editor for a journal entry."""
    journal_entry()


@app.command("search")
def cmd_search(
    query: list[str] = typer.Argument(..., help="Search query"),
    keyword: bool = typer.Option(False, "--keyword", "-k", help="Keyword (FTS5) search"),
    agent: bool = typer.Option(False, "--agent", "-a", help="AI agent synthesis"),
    model: str = typer.Option("auto", "--model", "-m", help="Model: auto, local, claude"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
) -> None:
    """Search your notes."""
    search_notes(query, keyword, agent, model, limit)


@app.command("serve")
def cmd_serve(
    port: int = typer.Option(0, "--port", "-p", help="Port number (default: 8833)"),
    host: str = typer.Option("", "--host", help="Host address"),
) -> None:
    """Start the web server."""
    serve_web(port, host)


@app.command("enrich")
def cmd_enrich(
    retry: bool = typer.Option(False, "--retry", "-r", help="Re-enrich failed notes"),
    all_notes: bool = typer.Option(False, "--all", "-a", help="Re-enrich all notes"),
    embeddings: bool = typer.Option(False, "--embeddings", "-e", help="Only regenerate embeddings"),
) -> None:
    """Re-run AI enrichment on notes."""
    enrich_notes(retry, all_notes, embeddings)


@app.command("status")
def cmd_status() -> None:
    """Show Cortex system status."""
    show_status()


@app.command("init")
def cmd_init() -> None:
    """Initialize the Cortex database."""
    from cortex.db.migrations import run_migrations

    console.print("[bold]Initializing Cortex...[/bold]")
    run_migrations()
    console.print("[green]✓[/green] Database created and schema applied.")


@app.command("backup")
def cmd_backup() -> None:
    """Create a timestamped backup of the database."""
    import shutil
    from datetime import datetime

    from cortex.config import get_settings

    settings = get_settings()
    db_path = settings.db_full_path

    if not db_path.exists():
        console.print("[red]No database found to backup.[/red]")
        raise typer.Exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"cortex_backup_{timestamp}.db"
    shutil.copy2(db_path, backup_path)
    console.print(f"[green]✓[/green] Backup saved to {backup_path}")


@app.command("export")
def cmd_export(
    format: str = typer.Option("json", "--format", "-f", help="Export format: json, csv"),
) -> None:
    """Export all notes with metadata."""
    import csv
    import json
    import sys

    from cortex.db.connection import sync_db

    with sync_db() as conn:
        rows = conn.execute(
            """
            SELECT n.id, n.raw_text, n.summary, n.category, n.sentiment,
                   n.source, n.is_journal, n.word_count, n.created_at
            FROM notes n ORDER BY n.created_at DESC
            """
        ).fetchall()

        notes = []
        for row in rows:
            note = dict(row)
            tag_rows = conn.execute(
                """
                SELECT t.name FROM tags t
                JOIN note_tags nt ON t.id = nt.tag_id
                WHERE nt.note_id = ?
                """,
                (note["id"],),
            ).fetchall()
            note["tags"] = [t["name"] for t in tag_rows]
            notes.append(note)

    if format == "json":
        json.dump(notes, sys.stdout, indent=2, default=str)
        console.print(f"\n[green]✓[/green] Exported {len(notes)} notes as JSON")
    elif format == "csv":
        if notes:
            writer = csv.DictWriter(sys.stdout, fieldnames=notes[0].keys())
            writer.writeheader()
            for note in notes:
                note["tags"] = ", ".join(note["tags"])
                writer.writerow(note)
            console.print(f"\n[green]✓[/green] Exported {len(notes)} notes as CSV")
    else:
        console.print(f"[red]Unknown format: {format}[/red]. Use json or csv.")


if __name__ == "__main__":
    app()
