"""cortex serve — start the web server."""

import typer

from cortex.config import get_settings


def serve_web(
    port: int = typer.Option(0, "--port", "-p", help="Port number (default: 8833)"),
    host: str = typer.Option("", "--host", "-h", help="Host address"),
) -> None:
    """Start the Cortex web server."""
    import uvicorn

    settings = get_settings()
    actual_port = port if port else settings.port
    actual_host = host if host else settings.host

    from cortex.cli.formatting import console

    console.print(f"[bold]Cortex[/bold] starting at http://{actual_host}:{actual_port}")

    uvicorn.run(
        "cortex.main:app",
        host=actual_host,
        port=actual_port,
        reload=True,
        log_level="info",
    )
