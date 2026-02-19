"""API routes for collections."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/collections", tags=["collections"])


class CollectionCreate(BaseModel):
    """Request body for creating a collection."""

    name: str
    description: str = ""


@router.post("")
async def create_collection(
    body: CollectionCreate,
    request: Request,
) -> dict[str, Any]:
    """Create a new collection."""
    conn = request.state.db
    cursor = await conn.execute(
        "INSERT INTO collections (name, description) VALUES (?, ?)",
        (body.name, body.description),
    )
    await conn.commit()
    rows = await conn.execute_fetchall(
        "SELECT * FROM collections WHERE rowid = ?", (cursor.lastrowid,)
    )
    return dict(rows[0]) if rows else {}


@router.get("")
async def list_collections(request: Request) -> list[dict[str, Any]]:
    """List all collections."""
    conn = request.state.db
    rows = await conn.execute_fetchall(
        """
        SELECT c.*, COUNT(nc.note_id) as note_count
        FROM collections c
        LEFT JOIN note_collections nc ON c.id = nc.collection_id
        GROUP BY c.id
        ORDER BY c.name
        """
    )
    return [dict(r) for r in rows]


@router.get("/{collection_id}")
async def get_collection(collection_id: int, request: Request) -> dict[str, Any]:
    """Get a collection with its notes."""
    conn = request.state.db
    rows = await conn.execute_fetchall(
        "SELECT * FROM collections WHERE id = ?", (collection_id,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Collection not found")

    collection = dict(rows[0])

    note_rows = await conn.execute_fetchall(
        """
        SELECT n.id, n.raw_text, n.summary, n.category, n.created_at
        FROM notes n
        JOIN note_collections nc ON n.id = nc.note_id
        WHERE nc.collection_id = ?
        ORDER BY n.created_at DESC
        """,
        (collection_id,),
    )
    collection["notes"] = [dict(r) for r in note_rows]
    return collection


@router.post("/{collection_id}/notes")
async def add_note_to_collection(
    collection_id: int,
    request: Request,
    note_id: str = "",
) -> dict[str, str]:
    """Add a note to a collection."""
    conn = request.state.db
    body = await request.json()
    nid = body.get("note_id", note_id)

    if not nid:
        raise HTTPException(status_code=400, detail="note_id required")

    await conn.execute(
        "INSERT OR IGNORE INTO note_collections (note_id, collection_id) VALUES (?, ?)",
        (nid, collection_id),
    )
    await conn.commit()
    return {"status": "added"}


@router.delete("/{collection_id}/notes/{note_id}")
async def remove_note_from_collection(
    collection_id: int,
    note_id: str,
    request: Request,
) -> dict[str, str]:
    """Remove a note from a collection."""
    conn = request.state.db
    await conn.execute(
        "DELETE FROM note_collections WHERE note_id = ? AND collection_id = ?",
        (note_id, collection_id),
    )
    await conn.commit()
    return {"status": "removed"}
