"""cortex search — search your notes."""

import asyncio
from typing import Optional

import typer

from cortex.cli.formatting import console, print_search_results


def search_notes(
    query: list[str] = typer.Argument(..., help="Search query"),
    keyword: bool = typer.Option(False, "--keyword", "-k", help="Use keyword (FTS5) search"),
    agent: bool = typer.Option(False, "--agent", "-a", help="Use AI agent for synthesis"),
    model: str = typer.Option("auto", "--model", "-m", help="Model: auto, local, claude"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
) -> None:
    """Search your notes with natural language or keywords."""
    query_text = " ".join(query)
    asyncio.run(_run_search(query_text, keyword, agent, model, limit))


async def _run_search(
    query_text: str,
    keyword: bool,
    agent: bool,
    model: str,
    limit: int,
) -> None:
    """Run the search asynchronously.

    Args:
        query_text: The search query.
        keyword: Whether to use keyword search.
        agent: Whether to use agent search.
        model: Model preference.
        limit: Max results.
    """
    from cortex.db.connection import get_async_connection

    conn = await get_async_connection()
    try:
        if agent:
            await _agent_search(conn, query_text, model)
        elif keyword:
            await _keyword_search(conn, query_text, limit)
        else:
            await _semantic_search(conn, query_text, limit)
    finally:
        await conn.close()


async def _keyword_search(conn: object, query_text: str, limit: int) -> None:
    """Run keyword search and display results."""
    from cortex.db.queries.search import keyword_search

    results = await keyword_search(conn, query_text, limit)  # type: ignore[arg-type]
    print_search_results(results, query_text)


async def _semantic_search(conn: object, query_text: str, limit: int) -> None:
    """Run semantic search and display results."""
    from cortex.ai.embeddings import encode_text
    from cortex.db.queries.search import semantic_search

    query_embedding = encode_text(query_text)
    results = await semantic_search(conn, query_embedding, limit)  # type: ignore[arg-type]
    print_search_results(results, query_text)


async def _agent_search(conn: object, query_text: str, model: str) -> None:
    """Run agent search and stream results."""
    from cortex.ai.agent import agent_search

    console.print(f"\n[bold]Agent search:[/bold] {query_text}\n")

    async for event in agent_search(conn, query_text, model_preference=model):  # type: ignore[arg-type]
        if event["event"] == "token":
            console.print(event["data"]["text"], end="")
        elif event["event"] == "citations":
            note_ids = event["data"]["note_ids"]
            if note_ids:
                console.print(f"\n\n[dim]Referenced notes: {', '.join(i[:8] for i in note_ids)}[/dim]")
        elif event["event"] == "done":
            data = event["data"]
            console.print(
                f"\n[dim]Model: {data['model_used']} | "
                f"Notes searched: {data['notes_searched']} | "
                f"Notes cited: {data['notes_cited']}[/dim]"
            )
