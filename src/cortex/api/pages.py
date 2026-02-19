"""Jinja2 page routes — server-rendered HTML pages."""

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from cortex.db.queries.notes import (
    async_get_note,
    async_get_note_tags,
    async_list_notes,
)
from cortex.db.queries.search import get_related_notes
from cortex.db.queries.stats import get_dashboard_stats
from cortex.db.queries.tags import async_list_tags

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="src/cortex/templates")


def _relative_time(dt_str: str) -> str:
    """Convert an ISO datetime string to a relative time string.

    Args:
        dt_str: An ISO-formatted datetime string.

    Returns:
        A human-readable relative time (e.g., '2 hours ago').
    """
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(dt_str)
        now = datetime.now()
        diff = now - dt

        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days == 1:
            return "yesterday"
        if days < 30:
            return f"{days}d ago"
        return dt.strftime("%b %d")
    except (ValueError, TypeError):
        return dt_str


@router.get("/", response_class=HTMLResponse)
async def feed_page(
    request: Request,
    category: str | None = None,
    tag: str | None = None,
) -> HTMLResponse:
    """Render the home feed page."""
    conn = request.state.db
    notes = await async_list_notes(conn, limit=30, category=category, tag=tag)

    # Group by date
    grouped: dict[str, list[dict[str, Any]]] = {}
    for note in notes:
        note["relative_time"] = _relative_time(note.get("created_at", ""))
        created = note.get("created_at", "")[:10]
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.now().replace(hour=0) - __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")

        if created == today:
            label = "Today"
        elif created == yesterday_str:
            label = "Yesterday"
        else:
            try:
                label = datetime.fromisoformat(created).strftime("%b %d")
            except (ValueError, TypeError):
                label = created
        grouped.setdefault(label, []).append(note)

    categories = await conn.execute_fetchall(
        "SELECT DISTINCT category FROM notes WHERE category IS NOT NULL ORDER BY category"
    )
    all_categories = [r["category"] for r in categories]

    return templates.TemplateResponse("feed.html", {
        "request": request,
        "grouped_notes": grouped,
        "categories": all_categories,
        "active_category": category,
        "active_tag": tag,
    })


@router.get("/notes/{note_id}", response_class=HTMLResponse)
async def note_detail_page(note_id: str, request: Request) -> HTMLResponse:
    """Render the note detail page."""
    conn = request.state.db
    note = await async_get_note(conn, note_id)
    if not note:
        return templates.TemplateResponse("404.html", {
            "request": request,
            "message": "Note not found",
        }, status_code=404)

    note["tags"] = await async_get_note_tags(conn, note_id)
    note["relative_time"] = _relative_time(note.get("created_at", ""))

    related = await get_related_notes(conn, note_id, limit=5)

    return templates.TemplateResponse("note_detail.html", {
        "request": request,
        "note": note,
        "related": related,
    })


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request) -> HTMLResponse:
    """Render the search page."""
    return templates.TemplateResponse("search.html", {
        "request": request,
    })


@router.get("/tags", response_class=HTMLResponse)
async def tags_page(request: Request) -> HTMLResponse:
    """Render the tag explorer page."""
    conn = request.state.db
    tags = await async_list_tags(conn, limit=200)

    # Group by tag_group
    groups: dict[str, list[dict[str, Any]]] = {}
    for tag in tags:
        group = tag.get("tag_group", "other") or "other"
        groups.setdefault(group, []).append(tag)

    return templates.TemplateResponse("tags.html", {
        "request": request,
        "tag_groups": groups,
        "all_tags": tags,
    })


@router.get("/compose", response_class=HTMLResponse)
async def compose_page(request: Request) -> HTMLResponse:
    """Render the compose page."""
    return templates.TemplateResponse("compose.html", {
        "request": request,
    })


@router.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request) -> HTMLResponse:
    """Render the stats dashboard page."""
    conn = request.state.db
    stats = await get_dashboard_stats(conn)

    return templates.TemplateResponse("stats.html", {
        "request": request,
        "stats": stats,
        "stats_json": json.dumps(stats, default=str),
    })


# --- HTMX Partials ---

@router.get("/partials/notes", response_class=HTMLResponse)
async def partial_notes(
    request: Request,
    page: int = 1,
    limit: int = 20,
    category: str | None = None,
    tag: str | None = None,
) -> HTMLResponse:
    """Render a note list fragment for infinite scroll."""
    conn = request.state.db
    offset = (page - 1) * limit
    notes = await async_list_notes(
        conn, limit=limit, offset=offset, category=category, tag=tag
    )

    for note in notes:
        note["relative_time"] = _relative_time(note.get("created_at", ""))

    return templates.TemplateResponse("partials/note_list.html", {
        "request": request,
        "notes": notes,
        "next_page": page + 1 if len(notes) == limit else None,
        "category": category,
        "tag": tag,
    })


@router.get("/partials/note/{note_id}/full", response_class=HTMLResponse)
async def partial_note_full(note_id: str, request: Request) -> HTMLResponse:
    """Render full note text for expand."""
    conn = request.state.db
    note = await async_get_note(conn, note_id)
    if not note:
        return HTMLResponse("<p>Note not found</p>", status_code=404)

    note["tags"] = await async_get_note_tags(conn, note_id)

    return templates.TemplateResponse("partials/note_card.html", {
        "request": request,
        "note": note,
        "expanded": True,
    })


@router.get("/partials/search-results", response_class=HTMLResponse)
async def partial_search_results(
    request: Request,
    q: str = "",
    mode: str = "semantic",
) -> HTMLResponse:
    """Render search results fragment."""
    if not q:
        return HTMLResponse("")

    conn = request.state.db
    results: list[dict[str, Any]] = []

    if mode == "keyword":
        from cortex.db.queries.search import keyword_search

        results = await keyword_search(conn, q, limit=20)
    else:
        from cortex.ai.embeddings import encode_text
        from cortex.db.queries.search import semantic_search

        query_embedding = encode_text(q)
        results = await semantic_search(conn, query_embedding, limit=20)

    for note in results:
        note["relative_time"] = _relative_time(note.get("created_at", ""))

    return templates.TemplateResponse("partials/search_results.html", {
        "request": request,
        "results": results,
        "query": q,
        "mode": mode,
    })
