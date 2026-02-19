"""SQLite connection manager with sqlite-vec extension support."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import aiosqlite
import sqlite_vec

from cortex.config import get_settings


def _load_extensions(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension into a connection."""
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def get_sync_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a synchronous SQLite connection with extensions loaded.

    Args:
        db_path: Path to the database file. Uses settings default if None.

    Returns:
        A configured SQLite connection.
    """
    if db_path is None:
        db_path = get_settings().db_full_path

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _load_extensions(conn)
    return conn


@contextmanager
def sync_db(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for synchronous database access.

    Args:
        db_path: Path to the database file. Uses settings default if None.

    Yields:
        A configured SQLite connection.
    """
    conn = get_sync_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def get_async_connection(db_path: Path | None = None) -> aiosqlite.Connection:
    """Get an async SQLite connection with extensions loaded.

    Args:
        db_path: Path to the database file. Uses settings default if None.

    Returns:
        A configured async SQLite connection.
    """
    if db_path is None:
        db_path = get_settings().db_full_path

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")

    # Load sqlite-vec via the underlying sync connection
    raw_conn = conn._connection  # noqa: SLF001
    if raw_conn is not None:
        _load_extensions(raw_conn)

    return conn


def init_vec_table(conn: sqlite3.Connection) -> None:
    """Create the sqlite-vec virtual table for note embeddings.

    Args:
        conn: An active SQLite connection with sqlite-vec loaded.
    """
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS note_embeddings USING vec0(
            note_id TEXT PRIMARY KEY,
            embedding FLOAT[384]
        )
    """)
    conn.commit()
