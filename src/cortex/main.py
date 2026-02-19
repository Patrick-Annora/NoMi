"""FastAPI application factory with lifespan management."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from cortex.api.pages import router as pages_router
from cortex.api.routes.collections import router as collections_router
from cortex.api.routes.enrichment import router as enrichment_router
from cortex.api.routes.notes import router as notes_router
from cortex.api.routes.search import router as search_router
from cortex.api.routes.stats import router as stats_router
from cortex.api.routes.tags import router as tags_router
from cortex.db.connection import get_async_connection
from cortex.db.migrations import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — setup and teardown."""
    # Ensure database and schema exist
    run_migrations()

    # Pre-load embedding model in background (non-blocking)
    try:
        from cortex.ai.embeddings import get_embedding_model

        get_embedding_model()
    except Exception:
        pass  # Model loading is best-effort at startup

    yield


app = FastAPI(
    title="Cortex",
    description="Local-first AI-powered personal knowledge system",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# Database connection middleware
@app.middleware("http")
async def db_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    """Attach a database connection to each request."""
    conn = await get_async_connection()
    request.state.db = conn
    try:
        response = await call_next(request)
        return response
    finally:
        await conn.close()


# Include routers
app.include_router(notes_router)
app.include_router(search_router)
app.include_router(tags_router)
app.include_router(collections_router)
app.include_router(enrichment_router)
app.include_router(stats_router)
app.include_router(pages_router)
