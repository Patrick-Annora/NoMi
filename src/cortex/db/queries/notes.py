"""Note CRUD database queries."""

import sqlite3
from datetime import datetime
from typing import Any

import aiosqlite


def insert_note(
    conn: sqlite3.Connection,
    raw_text: str,
    source: str = "cli",
    is_journal: bool = False,
) -> dict[str, Any]:
    """Insert a new note into the database.

    Args:
        conn: An active SQLite connection.
        raw_text: The raw text of the note.
        source: The note source ('cli', 'web', 'api').
        is_journal: Whether this is a journal entry.

    Returns:
        A dictionary with the created note's id, created_at, and word_count.
    """
    word_count = len(raw_text.split())
    cursor = conn.execute(
        """
        INSERT INTO notes (raw_text, source, is_journal, word_count)
        VALUES (?, ?, ?, ?)
        """,
        (raw_text, source, is_journal, word_count),
    )
    conn.commit()

    row = conn.execute(
        "SELECT id, created_at, word_count FROM notes WHERE rowid = ?",
        (cursor.lastrowid,),
    ).fetchone()

    return dict(row)


async def async_insert_note(
    conn: aiosqlite.Connection,
    raw_text: str,
    source: str = "web",
    is_journal: bool = False,
) -> dict[str, Any]:
    """Insert a new note asynchronously.

    Args:
        conn: An active async SQLite connection.
        raw_text: The raw text of the note.
        source: The note source.
        is_journal: Whether this is a journal entry.

    Returns:
        A dictionary with the created note's data.
    """
    word_count = len(raw_text.split())
    cursor = await conn.execute(
        """
        INSERT INTO notes (raw_text, source, is_journal, word_count)
        VALUES (?, ?, ?, ?)
        """,
        (raw_text, source, is_journal, word_count),
    )
    await conn.commit()

    row = await conn.execute_fetchall(
        "SELECT id, raw_text, summary, category, sentiment, source, is_journal, "
        "word_count, created_at, updated_at FROM notes WHERE rowid = ?",
        (cursor.lastrowid,),
    )
    return dict(row[0]) if row else {}


async def async_get_note(conn: aiosqlite.Connection, note_id: str) -> dict[str, Any] | None:
    """Get a single note by ID.

    Args:
        conn: An active async SQLite connection.
        note_id: The note's hex ID.

    Returns:
        A dictionary with the note's data, or None if not found.
    """
    rows = await conn.execute_fetchall(
        """
        SELECT n.id, n.raw_text, n.summary, n.category, n.sentiment,
               n.source, n.is_journal, n.word_count, n.created_at, n.updated_at
        FROM notes n
        WHERE n.id = ?
        """,
        (note_id,),
    )
    if not rows:
        return None
    return dict(rows[0])


async def async_get_note_tags(conn: aiosqlite.Connection, note_id: str) -> list[dict[str, Any]]:
    """Get all tags for a note.

    Args:
        conn: An active async SQLite connection.
        note_id: The note's hex ID.

    Returns:
        A list of tag dictionaries.
    """
    rows = await conn.execute_fetchall(
        """
        SELECT t.id, t.name, t.tag_group, nt.confidence
        FROM tags t
        JOIN note_tags nt ON t.id = nt.tag_id
        WHERE nt.note_id = ?
        ORDER BY nt.confidence DESC
        """,
        (note_id,),
    )
    return [dict(r) for r in rows]


async def async_list_notes(
    conn: aiosqlite.Connection,
    limit: int = 20,
    offset: int = 0,
    category: str | None = None,
    tag: str | None = None,
    date_after: str | None = None,
    date_before: str | None = None,
) -> list[dict[str, Any]]:
    """List notes with pagination and optional filters.

    Args:
        conn: An active async SQLite connection.
        limit: Maximum number of notes to return.
        offset: Number of notes to skip.
        category: Filter by category.
        tag: Filter by tag name.
        date_after: Filter notes created after this date.
        date_before: Filter notes created before this date.

    Returns:
        A list of note dictionaries with their tags.
    """
    conditions = []
    params: list[Any] = []

    if category:
        conditions.append("n.category = ?")
        params.append(category)
    if date_after:
        conditions.append("n.created_at >= ?")
        params.append(date_after)
    if date_before:
        conditions.append("n.created_at <= ?")
        params.append(date_before)
    if tag:
        conditions.append(
            "n.id IN (SELECT nt.note_id FROM note_tags nt "
            "JOIN tags t ON t.id = nt.tag_id WHERE t.name = ?)"
        )
        params.append(tag)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await conn.execute_fetchall(
        f"""
        SELECT n.id, n.raw_text, n.summary, n.category, n.sentiment,
               n.source, n.is_journal, n.word_count, n.created_at, n.updated_at
        FROM notes n
        {where}
        ORDER BY n.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )

    notes = []
    for row in rows:
        note = dict(row)
        tag_rows = await conn.execute_fetchall(
            """
            SELECT t.name, t.tag_group
            FROM tags t JOIN note_tags nt ON t.id = nt.tag_id
            WHERE nt.note_id = ?
            """,
            (note["id"],),
        )
        note["tags"] = [dict(t) for t in tag_rows]
        notes.append(note)

    return notes


async def async_update_note(
    conn: aiosqlite.Connection,
    note_id: str,
    raw_text: str | None = None,
    summary: str | None = None,
    category: str | None = None,
    sentiment: str | None = None,
    is_journal: bool | None = None,
) -> bool:
    """Update a note's fields.

    Args:
        conn: An active async SQLite connection.
        note_id: The note's hex ID.
        raw_text: New text content.
        summary: New summary.
        category: New category.
        sentiment: New sentiment.
        is_journal: New journal flag.

    Returns:
        True if the note was updated, False if not found.
    """
    updates = []
    params: list[Any] = []

    if raw_text is not None:
        updates.append("raw_text = ?")
        params.append(raw_text)
        updates.append("word_count = ?")
        params.append(len(raw_text.split()))
    if summary is not None:
        updates.append("summary = ?")
        params.append(summary)
    if category is not None:
        updates.append("category = ?")
        params.append(category)
    if sentiment is not None:
        updates.append("sentiment = ?")
        params.append(sentiment)
    if is_journal is not None:
        updates.append("is_journal = ?")
        params.append(is_journal)

    if not updates:
        return False

    updates.append("updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')")
    params.append(note_id)

    result = await conn.execute(
        f"UPDATE notes SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    await conn.commit()
    return (result.rowcount or 0) > 0


async def async_delete_note(conn: aiosqlite.Connection, note_id: str) -> bool:
    """Delete a note by ID.

    Args:
        conn: An active async SQLite connection.
        note_id: The note's hex ID.

    Returns:
        True if the note was deleted, False if not found.
    """
    result = await conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    await conn.commit()
    return (result.rowcount or 0) > 0


async def async_get_note_count(conn: aiosqlite.Connection) -> int:
    """Get the total number of notes.

    Args:
        conn: An active async SQLite connection.

    Returns:
        The total note count.
    """
    rows = await conn.execute_fetchall("SELECT COUNT(*) as count FROM notes")
    return rows[0]["count"] if rows else 0


def get_recent_notes(
    conn: sqlite3.Connection,
    limit: int = 10,
    today_only: bool = False,
) -> list[dict[str, Any]]:
    """Get recent notes (synchronous, for CLI use).

    Args:
        conn: An active SQLite connection.
        limit: Maximum number of notes to return.
        today_only: If True, only return today's notes.

    Returns:
        A list of note dictionaries.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    if today_only:
        rows = conn.execute(
            """
            SELECT id, raw_text, summary, category, source, word_count, created_at
            FROM notes
            WHERE created_at >= ?
            ORDER BY created_at DESC
            """,
            (today,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, raw_text, summary, category, source, word_count, created_at
            FROM notes
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    results = []
    for row in rows:
        note = dict(row)
        tag_rows = conn.execute(
            """
            SELECT t.name FROM tags t
            JOIN note_tags nt ON t.id = nt.tag_id
            WHERE nt.note_id = ?
            """,
            (note["id"],),
        ).fetchall()
        note["tags"] = [t["name"] for t in tag_rows]
        results.append(note)

    return results


def update_note_enrichment(
    conn: sqlite3.Connection,
    note_id: str,
    summary: str,
    category: str,
    sentiment: str,
    is_journal: bool,
    tags: list[dict[str, str]],
) -> None:
    """Update a note with AI-extracted metadata and tags.

    Args:
        conn: An active SQLite connection.
        note_id: The note's hex ID.
        summary: AI-generated summary.
        category: AI-assigned category.
        sentiment: AI-assessed sentiment.
        is_journal: Whether this is a journal entry.
        tags: List of tag dicts with 'name' and 'group' keys.
    """
    conn.execute(
        """
        UPDATE notes SET summary = ?, category = ?, sentiment = ?, is_journal = ?,
        updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
        WHERE id = ?
        """,
        (summary, category, sentiment, is_journal, note_id),
    )

    for tag_info in tags:
        name = tag_info["name"].lower().strip()
        group = tag_info.get("group", "topic")

        # Upsert tag
        conn.execute(
            """
            INSERT INTO tags (name, tag_group) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET usage_count = usage_count + 1
            """,
            (name, group),
        )
        tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        if tag_row:
            conn.execute(
                """
                INSERT OR IGNORE INTO note_tags (note_id, tag_id)
                VALUES (?, ?)
                """,
                (note_id, tag_row["id"]),
            )

    conn.commit()


def get_unenriched_notes(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    """Get notes that haven't been enriched yet.

    Args:
        conn: An active SQLite connection.
        limit: Maximum number of notes to return.

    Returns:
        A list of note dictionaries missing enrichment data.
    """
    rows = conn.execute(
        """
        SELECT id, raw_text FROM notes
        WHERE summary IS NULL
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
