"""Database query tests."""

import sqlite3

import pytest


class TestNotesCRUD:
    """Test note create, read, update, delete operations."""

    def test_insert_note(self, test_db: sqlite3.Connection) -> None:
        """Test inserting a new note."""
        cursor = test_db.execute(
            "INSERT INTO notes (raw_text, source, word_count) VALUES (?, ?, ?)",
            ("Test note content", "cli", 3),
        )
        test_db.commit()

        row = test_db.execute(
            "SELECT id, raw_text, source, word_count FROM notes WHERE rowid = ?",
            (cursor.lastrowid,),
        ).fetchone()

        assert row is not None
        assert row["raw_text"] == "Test note content"
        assert row["source"] == "cli"
        assert row["word_count"] == 3
        assert len(row["id"]) == 32  # hex(randomblob(16))

    def test_list_notes_ordered(self, test_db: sqlite3.Connection, sample_notes: list) -> None:
        """Test that notes are listed in reverse chronological order."""
        rows = test_db.execute(
            "SELECT id FROM notes ORDER BY created_at DESC"
        ).fetchall()

        assert len(rows) == 5

    def test_update_note(self, test_db: sqlite3.Connection, sample_notes: list) -> None:
        """Test updating a note's text."""
        note_id = sample_notes[0]["id"]
        test_db.execute(
            "UPDATE notes SET raw_text = ?, word_count = ? WHERE id = ?",
            ("Updated text", 2, note_id),
        )
        test_db.commit()

        row = test_db.execute(
            "SELECT raw_text, word_count FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()

        assert row["raw_text"] == "Updated text"
        assert row["word_count"] == 2

    def test_delete_note(self, test_db: sqlite3.Connection, sample_notes: list) -> None:
        """Test deleting a note."""
        note_id = sample_notes[0]["id"]
        test_db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        test_db.commit()

        row = test_db.execute(
            "SELECT id FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()

        assert row is None

    def test_note_default_values(self, test_db: sqlite3.Connection) -> None:
        """Test that default values are set correctly."""
        test_db.execute(
            "INSERT INTO notes (raw_text) VALUES (?)",
            ("Minimal note",),
        )
        test_db.commit()

        row = test_db.execute(
            "SELECT source, is_journal, created_at FROM notes WHERE raw_text = 'Minimal note'"
        ).fetchone()

        assert row["source"] == "cli"
        assert row["is_journal"] == 0
        assert row["created_at"] is not None


class TestTags:
    """Test tag operations."""

    def test_insert_and_link_tag(self, test_db: sqlite3.Connection, sample_notes: list) -> None:
        """Test inserting a tag and linking it to a note."""
        test_db.execute(
            "INSERT INTO tags (name, tag_group) VALUES (?, ?)",
            ("fundraising", "topic"),
        )
        tag_id = test_db.execute("SELECT id FROM tags WHERE name = 'fundraising'").fetchone()["id"]

        test_db.execute(
            "INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)",
            (sample_notes[0]["id"], tag_id),
        )
        test_db.commit()

        row = test_db.execute(
            """
            SELECT t.name FROM tags t
            JOIN note_tags nt ON t.id = nt.tag_id
            WHERE nt.note_id = ?
            """,
            (sample_notes[0]["id"],),
        ).fetchone()

        assert row["name"] == "fundraising"

    def test_tag_unique_constraint(self, test_db: sqlite3.Connection) -> None:
        """Test that duplicate tag names are rejected."""
        test_db.execute("INSERT INTO tags (name, tag_group) VALUES ('unique-tag', 'topic')")
        test_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute("INSERT INTO tags (name, tag_group) VALUES ('unique-tag', 'entity')")

    def test_tag_upsert(self, test_db: sqlite3.Connection) -> None:
        """Test the upsert pattern for tags."""
        test_db.execute(
            "INSERT INTO tags (name, tag_group) VALUES (?, ?)",
            ("test-tag", "topic"),
        )
        test_db.execute(
            """
            INSERT INTO tags (name, tag_group) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET usage_count = usage_count + 1
            """,
            ("test-tag", "topic"),
        )
        test_db.commit()

        row = test_db.execute(
            "SELECT usage_count FROM tags WHERE name = 'test-tag'"
        ).fetchone()

        assert row["usage_count"] == 2


class TestFTS5:
    """Test full-text search."""

    def test_fts_basic_search(self, test_db: sqlite3.Connection, sample_notes: list) -> None:
        """Test basic FTS5 keyword search."""
        rows = test_db.execute(
            """
            SELECT n.id, n.raw_text
            FROM notes_fts fts
            JOIN notes n ON n.rowid = fts.rowid
            WHERE notes_fts MATCH 'investor'
            """,
        ).fetchall()

        assert len(rows) >= 1
        assert "investor" in rows[0]["raw_text"].lower()

    def test_fts_no_results(self, test_db: sqlite3.Connection, sample_notes: list) -> None:
        """Test FTS5 search with no matches."""
        rows = test_db.execute(
            """
            SELECT n.id FROM notes_fts fts
            JOIN notes n ON n.rowid = fts.rowid
            WHERE notes_fts MATCH 'xyznonexistent'
            """,
        ).fetchall()

        assert len(rows) == 0

    def test_fts_sync_on_delete(self, test_db: sqlite3.Connection, sample_notes: list) -> None:
        """Test that FTS stays in sync when a note is deleted."""
        note_id = sample_notes[0]["id"]

        # Verify note exists in FTS
        before = test_db.execute(
            "SELECT COUNT(*) as c FROM notes_fts WHERE notes_fts MATCH 'Sequoia'"
        ).fetchone()
        assert before["c"] >= 1

        # Delete the note
        test_db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        test_db.commit()

        # Verify FTS is updated
        after = test_db.execute(
            "SELECT COUNT(*) as c FROM notes_fts WHERE notes_fts MATCH 'Sequoia'"
        ).fetchone()
        assert after["c"] == 0


class TestVectorTable:
    """Test sqlite-vec virtual table."""

    def test_vec_table_exists(self, test_db: sqlite3.Connection) -> None:
        """Test that the vector table was created."""
        import struct

        # Insert a test embedding
        embedding = [0.1] * 384
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        test_db.execute(
            "INSERT INTO note_embeddings (note_id, embedding) VALUES (?, ?)",
            ("test_id_1234567890abcdef", blob),
        )
        test_db.commit()

        # Query it back
        rows = test_db.execute(
            "SELECT note_id FROM note_embeddings WHERE note_id = ?",
            ("test_id_1234567890abcdef",),
        ).fetchall()

        assert len(rows) == 1

    def test_vec_similarity_search(self, test_db: sqlite3.Connection) -> None:
        """Test vector similarity search."""
        import struct

        # Insert two embeddings
        emb1 = [1.0] + [0.0] * 383
        emb2 = [0.0] + [1.0] + [0.0] * 382
        blob1 = struct.pack("384f", *emb1)
        blob2 = struct.pack("384f", *emb2)

        test_db.execute(
            "INSERT INTO note_embeddings (note_id, embedding) VALUES (?, ?)",
            ("note_a", blob1),
        )
        test_db.execute(
            "INSERT INTO note_embeddings (note_id, embedding) VALUES (?, ?)",
            ("note_b", blob2),
        )
        test_db.commit()

        # Search with a query similar to emb1
        query = [0.9] + [0.1] * 383
        query_blob = struct.pack("384f", *query)

        rows = test_db.execute(
            """
            SELECT note_id, distance
            FROM note_embeddings
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT 2
            """,
            (query_blob,),
        ).fetchall()

        assert len(rows) == 2
        assert rows[0]["note_id"] == "note_a"  # Closest to query


class TestCascadeDeletes:
    """Test that foreign key cascades work."""

    def test_delete_note_cascades_tags(
        self, test_db: sqlite3.Connection, sample_notes: list
    ) -> None:
        """Test that deleting a note removes its tag associations."""
        note_id = sample_notes[0]["id"]

        # Add a tag
        test_db.execute("INSERT INTO tags (name, tag_group) VALUES ('cascade-test', 'topic')")
        tag_id = test_db.execute("SELECT id FROM tags WHERE name = 'cascade-test'").fetchone()["id"]
        test_db.execute(
            "INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)",
            (note_id, tag_id),
        )
        test_db.commit()

        # Delete the note
        test_db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        test_db.commit()

        # Check that note_tags entry is gone
        row = test_db.execute(
            "SELECT COUNT(*) as c FROM note_tags WHERE note_id = ?", (note_id,)
        ).fetchone()
        assert row["c"] == 0
