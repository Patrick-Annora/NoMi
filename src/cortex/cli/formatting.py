"""Rich console output helpers for CLI display."""

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


console = Console()


def print_note_saved(note_id: str, word_count: int) -> None:
    """Print a note save confirmation.

    Args:
        note_id: The saved note's hex ID.
        word_count: The note's word count.
    """
    console.print(
        f"[green]✓[/green] Saved  [dim]{note_id[:8]}[/dim]  ({word_count} words)"
    )


def print_note_saved_with_metadata(
    note_id: str,
    word_count: int,
    tags: list[str],
    category: str,
    summary: str,
) -> None:
    """Print a note save confirmation with extracted metadata.

    Args:
        note_id: The saved note's hex ID.
        word_count: The note's word count.
        tags: Extracted tag names.
        category: Extracted category.
        summary: Extracted summary.
    """
    console.print(
        f"[green]✓[/green] Saved  [dim]{note_id[:8]}[/dim]  ({word_count} words)"
    )
    if tags:
        console.print(f"  Tags:     [cyan]{', '.join(tags)}[/cyan]")
    if category:
        console.print(f"  Category: [yellow]{category}[/yellow]")
    if summary:
        console.print(f"  Summary:  [dim]{summary}[/dim]")


def print_note_list(notes: list[dict]) -> None:  # type: ignore[type-arg]
    """Print a list of notes in a clean format.

    Args:
        notes: A list of note dictionaries.
    """
    if not notes:
        console.print("[dim]No notes found.[/dim]")
        return

    for note in notes:
        _print_note_row(note)
        console.print()


def _print_note_row(note: dict) -> None:  # type: ignore[type-arg]
    """Print a single note row.

    Args:
        note: A note dictionary.
    """
    # Header: ID + timestamp
    note_id = note.get("id", "")[:8]
    created = note.get("created_at", "")
    category = note.get("category", "")
    source = note.get("source", "")

    header = Text()
    header.append(f"  {note_id}", style="dim")
    header.append(f"  {created}", style="dim italic")
    if category:
        header.append(f"  [{category}]", style="yellow")
    if source:
        header.append(f"  via {source}", style="dim")
    console.print(header)

    # Body: truncated text
    raw_text = note.get("raw_text", "")
    if len(raw_text) > 200:
        raw_text = raw_text[:200] + "..."
    console.print(f"  {raw_text}")

    # Tags
    tags = note.get("tags", [])
    if tags:
        tag_names = [t if isinstance(t, str) else t.get("name", "") for t in tags]
        console.print(f"  [cyan]{', '.join(tag_names)}[/cyan]")

    # Summary
    summary = note.get("summary")
    if summary:
        console.print(f"  [dim italic]{summary}[/dim italic]")


def print_search_results(results: list[dict], query: str) -> None:  # type: ignore[type-arg]
    """Print search results.

    Args:
        results: A list of note result dictionaries.
        query: The original search query.
    """
    console.print(f"\n[bold]Results for:[/bold] {query}")
    console.print(f"[dim]Found {len(results)} notes[/dim]\n")

    if not results:
        console.print("[dim]No matching notes found.[/dim]")
        return

    for note in results:
        similarity = note.get("similarity")
        relevance = note.get("relevance")

        score_text = ""
        if similarity is not None:
            score_text = f" ({similarity:.0%} match)"
        elif relevance is not None:
            score_text = f" (rank: {relevance:.2f})"

        note_id = note.get("id", "")[:8]
        console.print(f"  [dim]{note_id}[/dim]{score_text}")

        raw_text = note.get("raw_text", "")
        if len(raw_text) > 150:
            raw_text = raw_text[:150] + "..."
        console.print(f"  {raw_text}")

        tags = note.get("tags", [])
        if tags:
            tag_names = [t if isinstance(t, str) else t.get("name", "") for t in tags]
            console.print(f"  [cyan]{', '.join(tag_names)}[/cyan]")
        console.print()


def print_status(stats: dict) -> None:  # type: ignore[type-arg]
    """Print system status.

    Args:
        stats: A dictionary of system statistics.
    """
    table = Table(title="Cortex Status", show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Notes", str(stats.get("total_notes", 0)))
    table.add_row("Words", f"{stats.get('total_words', 0):,}")
    table.add_row("Tags", str(stats.get("total_tags", 0)))
    table.add_row("DB Size", f"{stats.get('db_size_mb', 0)} MB")
    table.add_row("Unenriched", str(stats.get("unenriched_count", 0)))
    table.add_row("Ollama", stats.get("ollama_status", "unknown"))

    console.print(table)
