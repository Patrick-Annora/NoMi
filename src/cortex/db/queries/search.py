"""Search database queries — FTS5 keyword search and vector similarity search."""

from typing import Any

import aiosqlite


async def keyword_search(
    conn: aiosqlite.Connection,
    query: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Run a FTS5 keyword search across notes.

    Args:
        conn: An active async SQLite connection.
        query: The search query string.
        limit: Maximum number of results.

    Returns:
        A list of note dictionaries with match rank.
    """
    rows = await conn.execute_fetchall(
        """
        SELECT n.id, n.raw_text, n.summary, n.category, n.sentiment,
               n.source, n.word_count, n.created_at,
               rank AS relevance
        FROM notes_fts fts
        JOIN notes n ON n.rowid = fts.rowid
        WHERE notes_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    )

    results = []
    for row in rows:
        note = dict(row)
        tag_rows = await conn.execute_fetchall(
            """
            SELECT t.name, t.tag_group FROM tags t
            JOIN note_tags nt ON t.id = nt.tag_id
            WHERE nt.note_id = ?
            """,
            (note["id"],),
        )
        note["tags"] = [dict(t) for t in tag_rows]
        results.append(note)

    return results


async def semantic_search(
    conn: aiosqlite.Connection,
    query_embedding: list[float],
    limit: int = 20,
    category: str | None = None,
    tag: str | None = None,
    date_after: str | None = None,
    date_before: str | None = None,
) -> list[dict[str, Any]]:
    """Run a semantic similarity search using sqlite-vec.

    Args:
        conn: An active async SQLite connection.
        query_embedding: The query embedding vector.
        limit: Maximum number of results.
        category: Optional category filter.
        tag: Optional tag filter.
        date_after: Optional date lower bound.
        date_before: Optional date upper bound.

    Returns:
        A list of note dictionaries with similarity scores.
    """
    import struct

    # Pack the embedding as a binary blob for sqlite-vec
    embedding_blob = struct.pack(f"{len(query_embedding)}f", *query_embedding)

    # First get candidate note IDs from vector search (wider net)
    vec_rows = await conn.execute_fetchall(
        """
        SELECT note_id, distance
        FROM note_embeddings
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT ?
        """,
        (embedding_blob, limit * 3),
    )

    if not vec_rows:
        return []

    candidate_ids = [row["note_id"] for row in vec_rows]
    distances = {row["note_id"]: row["distance"] for row in vec_rows}

    # Build filtered query
    placeholders = ",".join("?" * len(candidate_ids))
    conditions = [f"n.id IN ({placeholders})"]
    params: list[Any] = list(candidate_ids)

    if category:
        conditions.append("n.category = ?")
        params.append(category)
    if tag:
        conditions.append(
            "n.id IN (SELECT nt.note_id FROM note_tags nt "
            "JOIN tags t ON t.id = nt.tag_id WHERE t.name = ?)"
        )
        params.append(tag)
    if date_after:
        conditions.append("n.created_at >= ?")
        params.append(date_after)
    if date_before:
        conditions.append("n.created_at <= ?")
        params.append(date_before)

    where = " AND ".join(conditions)
    params.append(limit)

    rows = await conn.execute_fetchall(
        f"""
        SELECT n.id, n.raw_text, n.summary, n.category, n.sentiment,
               n.source, n.word_count, n.created_at
        FROM notes n
        WHERE {where}
        LIMIT ?
        """,
        params,
    )

    results = []
    for row in rows:
        note = dict(row)
        note["distance"] = distances.get(note["id"], 999.0)
        note["similarity"] = max(0.0, 1.0 - note["distance"])
        tag_rows = await conn.execute_fetchall(
            """
            SELECT t.name, t.tag_group FROM tags t
            JOIN note_tags nt ON t.id = nt.tag_id
            WHERE nt.note_id = ?
            """,
            (note["id"],),
        )
        note["tags"] = [dict(t) for t in tag_rows]
        results.append(note)

    # Sort by similarity (highest first)
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


async def get_related_notes(
    conn: aiosqlite.Connection,
    note_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Get semantically similar notes to a given note.

    Args:
        conn: An active async SQLite connection.
        note_id: The reference note's ID.
        limit: Maximum number of related notes.

    Returns:
        A list of related note dictionaries with similarity scores.
    """
    import struct

    # Get the embedding for the reference note
    rows = await conn.execute_fetchall(
        "SELECT embedding FROM note_embeddings WHERE note_id = ?",
        (note_id,),
    )
    if not rows:
        return []

    embedding_blob = rows[0]["embedding"]

    # Find similar notes, excluding the reference note
    vec_rows = await conn.execute_fetchall(
        """
        SELECT note_id, distance
        FROM note_embeddings
        WHERE embedding MATCH ?
        AND note_id != ?
        ORDER BY distance
        LIMIT ?
        """,
        (embedding_blob, note_id, limit),
    )

    if not vec_rows:
        return []

    results = []
    for vr in vec_rows:
        note_rows = await conn.execute_fetchall(
            """
            SELECT id, raw_text, summary, category, created_at
            FROM notes WHERE id = ?
            """,
            (vr["note_id"],),
        )
        if note_rows:
            note = dict(note_rows[0])
            note["similarity"] = max(0.0, 1.0 - vr["distance"])
            results.append(note)

    return results
