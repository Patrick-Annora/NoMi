"""API routes for enrichment management."""

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])


@router.post("/retry")
async def retry_enrichment(request: Request) -> dict[str, Any]:
    """Re-enrich notes that failed enrichment."""
    conn = request.state.db
    rows = await conn.execute_fetchall(
        "SELECT id, raw_text FROM notes WHERE summary IS NULL LIMIT 50"
    )

    count = 0
    for row in rows:
        try:
            from cortex.ai.enrichment import enrich_note

            result = await enrich_note(row["id"], row["raw_text"])
            if result:
                count += 1
        except Exception:
            continue

    return {"enriched": count, "total_pending": len(rows)}


@router.post("/all")
async def enrich_all(request: Request) -> dict[str, Any]:
    """Re-enrich all notes (warning: may be slow with many notes)."""
    conn = request.state.db
    rows = await conn.execute_fetchall("SELECT id, raw_text FROM notes")

    count = 0
    for row in rows:
        try:
            from cortex.ai.enrichment import enrich_note

            result = await enrich_note(row["id"], row["raw_text"])
            if result:
                count += 1
        except Exception:
            continue

    return {"enriched": count, "total": len(rows)}
