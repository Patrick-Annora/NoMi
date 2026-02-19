"""Aggregation and statistics queries."""

import os
from typing import Any

import aiosqlite

from cortex.config import get_settings


async def get_dashboard_stats(conn: aiosqlite.Connection) -> dict[str, Any]:
    """Get all dashboard statistics.

    Args:
        conn: An active async SQLite connection.

    Returns:
        A dictionary with various statistics.
    """
    stats: dict[str, Any] = {}

    # Total notes and words
    rows = await conn.execute_fetchall(
        "SELECT COUNT(*) as count, COALESCE(SUM(word_count), 0) as words FROM notes"
    )
    stats["total_notes"] = rows[0]["count"]
    stats["total_words"] = rows[0]["words"]

    # Notes by category
    rows = await conn.execute_fetchall(
        """
        SELECT COALESCE(category, 'uncategorized') as category, COUNT(*) as count
        FROM notes GROUP BY category ORDER BY count DESC
        """
    )
    stats["by_category"] = [dict(r) for r in rows]

    # Notes by source
    rows = await conn.execute_fetchall(
        """
        SELECT source, COUNT(*) as count
        FROM notes GROUP BY source ORDER BY count DESC
        """
    )
    stats["by_source"] = [dict(r) for r in rows]

    # Top tags (last 30 days)
    rows = await conn.execute_fetchall(
        """
        SELECT t.name, t.tag_group, COUNT(nt.note_id) as recent_count
        FROM tags t
        JOIN note_tags nt ON t.id = nt.tag_id
        JOIN notes n ON n.id = nt.note_id
        WHERE n.created_at >= date('now', '-30 days')
        GROUP BY t.id
        ORDER BY recent_count DESC
        LIMIT 20
        """
    )
    stats["top_tags"] = [dict(r) for r in rows]

    # Notes per day (last 30 days)
    rows = await conn.execute_fetchall(
        """
        SELECT date(created_at) as day, COUNT(*) as count
        FROM notes
        WHERE created_at >= date('now', '-30 days')
        GROUP BY day
        ORDER BY day
        """
    )
    stats["notes_per_day"] = [dict(r) for r in rows]

    # Notes per week (last 12 weeks)
    rows = await conn.execute_fetchall(
        """
        SELECT strftime('%Y-W%W', created_at) as week, COUNT(*) as count
        FROM notes
        WHERE created_at >= date('now', '-84 days')
        GROUP BY week
        ORDER BY week
        """
    )
    stats["notes_per_week"] = [dict(r) for r in rows]

    # Database size
    db_path = get_settings().db_full_path
    if db_path.exists():
        stats["db_size_bytes"] = os.path.getsize(db_path)
        stats["db_size_mb"] = round(stats["db_size_bytes"] / (1024 * 1024), 2)
    else:
        stats["db_size_bytes"] = 0
        stats["db_size_mb"] = 0

    # Enrichment status
    rows = await conn.execute_fetchall(
        "SELECT COUNT(*) as count FROM notes WHERE summary IS NULL"
    )
    stats["unenriched_count"] = rows[0]["count"]

    # Tag count
    rows = await conn.execute_fetchall("SELECT COUNT(*) as count FROM tags")
    stats["total_tags"] = rows[0]["count"]

    return stats
