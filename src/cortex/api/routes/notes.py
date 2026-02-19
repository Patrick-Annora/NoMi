"""API routes for note CRUD operations."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from cortex.db.queries.notes import (
    async_delete_note,
    async_get_note,
    async_get_note_tags,
    async_insert_note,
    async_list_notes,
    async_update_note,
)
from cortex.db.queries.search import get_related_notes

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteCreate(BaseModel):
    """Request body for creating a note."""

    raw_text: str
    source: str = "web"
    is_journal: bool = False


class NoteUpdate(BaseModel):
    """Request body for updating a note."""

    raw_text: str | None = None
    summary: str | None = None
    category: str | None = None
    sentiment: str | None = None
    is_journal: bool | None = None


@router.post("")
async def create_note(body: NoteCreate, request: Request) -> dict[str, Any]:
    """Create a new note."""
    conn = request.state.db
    result = await async_insert_note(
        conn, body.raw_text, source=body.source, is_journal=body.is_journal
    )

    # Fire-and-forget enrichment
    note_id = result.get("id", "")
    if note_id:
        asyncio.create_task(_enrich_background(note_id, body.raw_text))

    return result


@router.get("")
async def list_notes(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    category: str | None = None,
    tag: str | None = None,
    date_after: str | None = None,
    date_before: str | None = None,
) -> list[dict[str, Any]]:
    """List notes with pagination and optional filters."""
    conn = request.state.db
    return await async_list_notes(
        conn, limit=limit, offset=offset,
        category=category, tag=tag,
        date_after=date_after, date_before=date_before,
    )


@router.get("/{note_id}")
async def get_note(note_id: str, request: Request) -> dict[str, Any]:
    """Get a single note with metadata."""
    conn = request.state.db
    note = await async_get_note(conn, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    note["tags"] = await async_get_note_tags(conn, note_id)
    return note


@router.patch("/{note_id}")
async def update_note(note_id: str, body: NoteUpdate, request: Request) -> dict[str, str]:
    """Update a note."""
    conn = request.state.db
    updated = await async_update_note(
        conn, note_id,
        raw_text=body.raw_text,
        summary=body.summary,
        category=body.category,
        sentiment=body.sentiment,
        is_journal=body.is_journal,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "updated"}


@router.delete("/{note_id}")
async def delete_note(note_id: str, request: Request) -> dict[str, str]:
    """Delete a note."""
    conn = request.state.db
    deleted = await async_delete_note(conn, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "deleted"}


@router.get("/{note_id}/enrichment")
async def get_note_enrichment(note_id: str, request: Request) -> dict[str, Any]:
    """Get the enrichment status and metadata of a note."""
    conn = request.state.db
    note = await async_get_note(conn, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    tags = await async_get_note_tags(conn, note_id)
    return {
        "id": note_id,
        "enriched": note.get("summary") is not None,
        "summary": note.get("summary"),
        "category": note.get("category"),
        "sentiment": note.get("sentiment"),
        "tags": [{"name": t["name"], "tag_group": t.get("tag_group")} for t in tags],
    }


@router.get("/{note_id}/related")
async def related_notes(
    note_id: str,
    request: Request,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Get semantically similar notes."""
    conn = request.state.db
    return await get_related_notes(conn, note_id, limit=limit)


async def _enrich_background(note_id: str, raw_text: str) -> None:
    """Background task to enrich a note."""
    try:
        from cortex.ai.enrichment import enrich_note

        await enrich_note(note_id, raw_text)
    except Exception:
        pass
