"""Tag database queries."""

from typing import Any

import aiosqlite


async def async_list_tags(
    conn: aiosqlite.Connection,
    group: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List all tags with usage counts.

    Args:
        conn: An active async SQLite connection.
        group: Optional filter by tag group.
        limit: Maximum number of tags to return.

    Returns:
        A list of tag dictionaries sorted by usage count.
    """
    if group:
        rows = await conn.execute_fetchall(
            """
            SELECT id, name, tag_group, usage_count, first_seen
            FROM tags
            WHERE tag_group = ?
            ORDER BY usage_count DESC
            LIMIT ?
            """,
            (group, limit),
        )
    else:
        rows = await conn.execute_fetchall(
            """
            SELECT id, name, tag_group, usage_count, first_seen
            FROM tags
            ORDER BY usage_count DESC
            LIMIT ?
            """,
            (limit,),
        )
    return [dict(r) for r in rows]


async def async_rename_tag(
    conn: aiosqlite.Connection,
    tag_id: int,
    new_name: str,
) -> bool:
    """Rename a tag.

    Args:
        conn: An active async SQLite connection.
        tag_id: The tag's ID.
        new_name: The new tag name.

    Returns:
        True if the tag was renamed, False if not found.
    """
    result = await conn.execute(
        "UPDATE tags SET name = ? WHERE id = ?",
        (new_name.lower().strip(), tag_id),
    )
    await conn.commit()
    return (result.rowcount or 0) > 0


async def async_merge_tags(
    conn: aiosqlite.Connection,
    source_id: int,
    target_id: int,
) -> bool:
    """Merge source tag into target tag.

    Args:
        conn: An active async SQLite connection.
        source_id: The tag to merge from (will be deleted).
        target_id: The tag to merge into.

    Returns:
        True if the merge succeeded.
    """
    # Move note associations from source to target
    await conn.execute(
        """
        UPDATE OR IGNORE note_tags
        SET tag_id = ?
        WHERE tag_id = ?
        """,
        (target_id, source_id),
    )
    # Delete orphaned associations (already existed on target)
    await conn.execute("DELETE FROM note_tags WHERE tag_id = ?", (source_id,))
    # Update usage count on target
    await conn.execute(
        """
        UPDATE tags SET usage_count = (
            SELECT COUNT(*) FROM note_tags WHERE tag_id = ?
        ) WHERE id = ?
        """,
        (target_id, target_id),
    )
    # Delete source tag
    await conn.execute("DELETE FROM tags WHERE id = ?", (source_id,))
    await conn.commit()
    return True


async def async_delete_tag(conn: aiosqlite.Connection, tag_id: int) -> bool:
    """Delete a tag and its note associations.

    Args:
        conn: An active async SQLite connection.
        tag_id: The tag's ID.

    Returns:
        True if the tag was deleted.
    """
    await conn.execute("DELETE FROM note_tags WHERE tag_id = ?", (tag_id,))
    result = await conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    await conn.commit()
    return (result.rowcount or 0) > 0
