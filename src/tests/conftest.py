"""Shared test fixtures."""

import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from cortex.db.connection import get_sync_connection, init_vec_table
from cortex.db.migrations import _apply_initial_schema


@pytest.fixture
def test_db() -> Generator[sqlite3.Connection, None, None]:
    """Create a temporary test database with full schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = get_sync_connection(db_path)
    _apply_initial_schema(conn)
    init_vec_table(conn)
    conn.commit()

    yield conn

    conn.close()
    db_path.unlink(missing_ok=True)


@pytest.fixture
def sample_notes(test_db: sqlite3.Connection) -> list[dict]:
    """Insert sample notes into the test database."""
    notes_data = [
        ("Met with investor from Sequoia. They want 3 months of revenue data.", "cli"),
        ("Pricing idea: tiered model with usage-based component.", "web"),
        ("Need to hire senior backend engineer. Python + FastAPI experience.", "cli"),
        ("Feeling good about the fundraising progress. Momentum building.", "cli"),
        ("Meeting notes: discussed product roadmap with engineering team.", "web"),
    ]

    results = []
    for text, source in notes_data:
        word_count = len(text.split())
        cursor = test_db.execute(
            "INSERT INTO notes (raw_text, source, word_count) VALUES (?, ?, ?)",
            (text, source, word_count),
        )
        row = test_db.execute(
            "SELECT id, raw_text, word_count, created_at FROM notes WHERE rowid = ?",
            (cursor.lastrowid,),
        ).fetchone()
        results.append(dict(row))

    test_db.commit()
    return results
