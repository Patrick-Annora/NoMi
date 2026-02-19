"""Search accuracy tests."""

import sqlite3
import struct

import pytest


class TestKeywordSearch:
    """Test FTS5 keyword search."""

    def test_basic_keyword_match(
        self, test_db: sqlite3.Connection, sample_notes: list
    ) -> None:
        """Test that keyword search finds exact matches."""
        rows = test_db.execute(
            """
            SELECT n.raw_text
            FROM notes_fts fts
            JOIN notes n ON n.rowid = fts.rowid
            WHERE notes_fts MATCH 'pricing'
            """,
        ).fetchall()

        assert len(rows) >= 1
        assert any("pricing" in r["raw_text"].lower() for r in rows)

    def test_multi_word_match(
        self, test_db: sqlite3.Connection, sample_notes: list
    ) -> None:
        """Test multi-word keyword search."""
        rows = test_db.execute(
            """
            SELECT n.raw_text
            FROM notes_fts fts
            JOIN notes n ON n.rowid = fts.rowid
            WHERE notes_fts MATCH 'backend engineer'
            """,
        ).fetchall()

        assert len(rows) >= 1

    def test_boolean_and(
        self, test_db: sqlite3.Connection, sample_notes: list
    ) -> None:
        """Test boolean AND in keyword search."""
        rows = test_db.execute(
            """
            SELECT n.raw_text
            FROM notes_fts fts
            JOIN notes n ON n.rowid = fts.rowid
            WHERE notes_fts MATCH 'investor AND revenue'
            """,
        ).fetchall()

        assert len(rows) >= 1
        result_text = rows[0]["raw_text"].lower()
        assert "investor" in result_text
        assert "revenue" in result_text


class TestVectorSearch:
    """Test vector similarity search."""

    def test_similar_embeddings_ranked(self, test_db: sqlite3.Connection) -> None:
        """Test that more similar embeddings rank higher."""
        # Create three embeddings with known similarity
        emb_a = [1.0, 0.0, 0.0] + [0.0] * 381  # reference
        emb_b = [0.9, 0.1, 0.0] + [0.0] * 381  # very similar
        emb_c = [0.0, 1.0, 0.0] + [0.0] * 381  # different

        for note_id, emb in [("note_a", emb_a), ("note_b", emb_b), ("note_c", emb_c)]:
            # Insert a note
            test_db.execute(
                "INSERT INTO notes (id, raw_text, word_count) VALUES (?, ?, ?)",
                (note_id + "0" * (32 - len(note_id)), f"Note {note_id}", 2),
            )
            # Insert embedding
            blob = struct.pack("384f", *emb)
            test_db.execute(
                "INSERT INTO note_embeddings (note_id, embedding) VALUES (?, ?)",
                (note_id + "0" * (32 - len(note_id)), blob),
            )
        test_db.commit()

        # Search with query similar to emb_a
        query = [0.95, 0.05, 0.0] + [0.0] * 381
        query_blob = struct.pack("384f", *query)

        rows = test_db.execute(
            """
            SELECT note_id, distance
            FROM note_embeddings
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT 3
            """,
            (query_blob,),
        ).fetchall()

        # note_a and note_b should be closer than note_c
        note_ids = [r["note_id"] for r in rows]
        assert note_ids[0].startswith("note_a") or note_ids[0].startswith("note_b")

    def test_exclude_self_in_related(self, test_db: sqlite3.Connection) -> None:
        """Test excluding the query note from related results."""
        emb = [0.5] * 384
        blob = struct.pack("384f", *emb)

        for nid in ["aaaa", "bbbb"]:
            padded = nid + "0" * (32 - len(nid))
            test_db.execute(
                "INSERT INTO notes (id, raw_text, word_count) VALUES (?, ?, ?)",
                (padded, f"Note {nid}", 2),
            )
            test_db.execute(
                "INSERT INTO note_embeddings (note_id, embedding) VALUES (?, ?)",
                (padded, blob),
            )
        test_db.commit()

        query_id = "aaaa" + "0" * 28
        rows = test_db.execute(
            """
            SELECT note_id FROM note_embeddings
            WHERE embedding MATCH ? AND note_id != ?
            ORDER BY distance LIMIT 5
            """,
            (blob, query_id),
        ).fetchall()

        result_ids = [r["note_id"] for r in rows]
        assert query_id not in result_ids
