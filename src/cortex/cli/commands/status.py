"""cortex status — show system status."""

import asyncio
import os

from cortex.cli.formatting import console, print_status
from cortex.config import get_settings


def show_status() -> None:
    """Show Cortex system status."""
    settings = get_settings()
    db_path = settings.db_full_path

    if not db_path.exists():
        console.print(
            "[bold]Cortex[/bold] — no database found. "
            "Run [cyan]cortex init[/cyan] to set up."
        )
        return

    asyncio.run(_gather_status())


async def _gather_status() -> None:
    """Gather and display system status."""
    from cortex.ai.ollama_client import OllamaClient
    from cortex.db.connection import get_async_connection
    from cortex.db.queries.stats import get_dashboard_stats

    conn = await get_async_connection()
    try:
        stats = await get_dashboard_stats(conn)

        # Check Ollama
        ollama = OllamaClient()
        if await ollama.is_available():
            if await ollama.has_model():
                stats["ollama_status"] = f"running ({ollama.model})"
            else:
                stats["ollama_status"] = f"running (model {ollama.model} not found)"
        else:
            stats["ollama_status"] = "not running"

        print_status(stats)
    finally:
        await conn.close()
