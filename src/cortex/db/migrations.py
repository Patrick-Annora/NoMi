"""Database schema creation and migration runner."""

import sqlite3
from pathlib import Path

from cortex.db.connection import get_sync_connection, init_vec_table


SCHEMA_PATH = Path(__file__).parent / "schema.sql"
CURRENT_VERSION = 1


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version from the database.

    Args:
        conn: An active SQLite connection.

    Returns:
        The current schema version, or 0 if uninitialized.
    """
    try:
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def run_migrations(db_path: Path | None = None) -> None:
    """Create or migrate the database schema.

    Args:
        db_path: Path to the database file. Uses settings default if None.
    """
    conn = get_sync_connection(db_path)
    try:
        current = get_schema_version(conn)

        if current < 1:
            _apply_initial_schema(conn)

        # Create sqlite-vec virtual table
        init_vec_table(conn)

        conn.commit()
    finally:
        conn.close()


def _apply_initial_schema(conn: sqlite3.Connection) -> None:
    """Apply the initial schema from schema.sql.

    Args:
        conn: An active SQLite connection.
    """
    schema_sql = SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (1,))
