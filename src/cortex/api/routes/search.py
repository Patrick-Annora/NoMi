"""API routes for search — keyword, semantic, and agent."""

import json
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from cortex.ai.agent import agent_search
from cortex.ai.embeddings import encode_text
from cortex.db.queries.search import keyword_search, semantic_search

router = APIRouter(prefix="/api/search", tags=["search"])


class KeywordSearchRequest(BaseModel):
    """Request body for keyword search."""

    query: str
    limit: int = 20


class SemanticSearchRequest(BaseModel):
    """Request body for semantic search."""

    query: str
    limit: int = 20
    category: str | None = None
    tag: str | None = None
    date_after: str | None = None
    date_before: str | None = None


class AgentSearchRequest(BaseModel):
    """Request body for agent search."""

    query: str
    model: str = "auto"
    category_filter: str | None = None
    tag_filter: str | None = None
    date_filter: dict[str, str] | None = None
    note_id: str | None = None


@router.post("/keyword")
async def search_keyword(
    body: KeywordSearchRequest,
    request: Request,
) -> list[dict[str, Any]]:
    """Run FTS5 keyword search."""
    conn = request.state.db
    results = await keyword_search(conn, body.query, body.limit)

    # Log search
    await conn.execute(
        "INSERT INTO search_history (query_text, query_type, results_count, model_used) "
        "VALUES (?, 'keyword', ?, 'fts5')",
        (body.query, len(results)),
    )
    await conn.commit()

    return results


@router.post("/semantic")
async def search_semantic(
    body: SemanticSearchRequest,
    request: Request,
) -> list[dict[str, Any]]:
    """Run embedding similarity search."""
    conn = request.state.db
    query_embedding = encode_text(body.query)
    results = await semantic_search(
        conn, query_embedding, body.limit,
        category=body.category,
        tag=body.tag,
        date_after=body.date_after,
        date_before=body.date_before,
    )

    # Log search
    await conn.execute(
        "INSERT INTO search_history (query_text, query_type, results_count, model_used) "
        "VALUES (?, 'semantic', ?, 'embeddings')",
        (body.query, len(results)),
    )
    await conn.commit()

    return results


@router.post("/agent")
async def search_agent(body: AgentSearchRequest, request: Request) -> EventSourceResponse:
    """Run AI agent Q&A with SSE streaming."""
    conn = request.state.db
    date_after = None
    date_before = None
    if body.date_filter:
        date_after = body.date_filter.get("after")
        date_before = body.date_filter.get("before")

    async def event_generator():  # type: ignore[no-untyped-def]
        async for event in agent_search(
            conn, body.query,
            model_preference=body.model,
            category=body.category_filter,
            tag=body.tag_filter,
            date_after=date_after,
            date_before=date_before,
            note_id=body.note_id,
        ):
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"]),
            }

    return EventSourceResponse(event_generator())
