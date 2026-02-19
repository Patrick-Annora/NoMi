"""cortex enrich — manage AI enrichment of notes."""

import asyncio

import typer

from cortex.cli.formatting import console


def enrich_notes(
    retry: bool = typer.Option(False, "--retry", "-r", help="Re-enrich failed notes"),
    all_notes: bool = typer.Option(False, "--all", "-a", help="Re-enrich all notes"),
    embeddings: bool = typer.Option(False, "--embeddings", "-e", help="Only regenerate embeddings"),
) -> None:
    """Re-run AI enrichment on notes."""
    if all_notes:
        console.print("[bold]Re-enriching all notes...[/bold]")
        asyncio.run(_enrich_all(embeddings_only=embeddings))
    elif retry:
        console.print("[bold]Re-enriching failed notes...[/bold]")
        from cortex.ai.enrichment import enrich_pending_notes_sync

        count = enrich_pending_notes_sync()
        console.print(f"[green]✓[/green] Enriched {count} notes")
    elif embeddings:
        console.print("[bold]Regenerating all embeddings...[/bold]")
        asyncio.run(_enrich_all(embeddings_only=True))
    else:
        console.print("Use --retry, --all, or --embeddings. See --help for details.")


async def _enrich_all(embeddings_only: bool = False) -> None:
    """Re-enrich all notes.

    Args:
        embeddings_only: If True, only regenerate embeddings (skip Ollama).
    """
    from cortex.db.connection import get_sync_connection

    conn = get_sync_connection()
    try:
        rows = conn.execute("SELECT id, raw_text FROM notes ORDER BY created_at").fetchall()
        total = len(rows)
        console.print(f"Processing {total} notes...")

        for i, row in enumerate(rows):
            note_id = row["id"]
            raw_text = row["raw_text"]
            try:
                if embeddings_only:
                    from cortex.ai.enrichment import enrich_note_embedding_only

                    await enrich_note_embedding_only(note_id, raw_text)
                else:
                    from cortex.ai.enrichment import enrich_note

                    await enrich_note(note_id, raw_text)
                console.print(f"  [{i + 1}/{total}] {note_id[:8]} [green]✓[/green]")
            except Exception as e:
                console.print(f"  [{i + 1}/{total}] {note_id[:8]} [red]✗[/red] {e}")

        console.print(f"\n[green]✓[/green] Done processing {total} notes")
    finally:
        conn.close()
