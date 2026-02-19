"""API routes for dashboard statistics."""

from typing import Any

from fastapi import APIRouter, Request

from cortex.db.queries.stats import get_dashboard_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats(request: Request) -> dict[str, Any]:
    """Get dashboard statistics."""
    conn = request.state.db
    return await get_dashboard_stats(conn)
