"""API routes for tag management."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from cortex.db.queries.tags import (
    async_delete_tag,
    async_list_tags,
    async_merge_tags,
    async_rename_tag,
)

router = APIRouter(prefix="/api/tags", tags=["tags"])


class TagUpdate(BaseModel):
    """Request body for renaming or merging a tag."""

    new_name: str | None = None
    merge_into_id: int | None = None


@router.get("")
async def list_tags(
    request: Request,
    group: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List all tags with usage counts."""
    conn = request.state.db
    return await async_list_tags(conn, group=group, limit=limit)


@router.patch("/{tag_id}")
async def update_tag(
    tag_id: int,
    body: TagUpdate,
    request: Request,
) -> dict[str, str]:
    """Rename or merge a tag."""
    conn = request.state.db

    if body.merge_into_id is not None:
        await async_merge_tags(conn, source_id=tag_id, target_id=body.merge_into_id)
        return {"status": "merged"}

    if body.new_name is not None:
        updated = await async_rename_tag(conn, tag_id, body.new_name)
        if not updated:
            raise HTTPException(status_code=404, detail="Tag not found")
        return {"status": "renamed"}

    raise HTTPException(status_code=400, detail="Provide new_name or merge_into_id")


@router.delete("/{tag_id}")
async def delete_tag(tag_id: int, request: Request) -> dict[str, str]:
    """Delete a tag."""
    conn = request.state.db
    deleted = await async_delete_tag(conn, tag_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"status": "deleted"}
