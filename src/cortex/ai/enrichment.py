"""Ollama-powered tagging and enrichment pipeline."""

import json
import logging
from typing import Any

from cortex.ai.embeddings import encode_text, store_embedding
from cortex.ai.ollama_client import OllamaClient
from cortex.ai.prompts import EXTRACTION_SYSTEM_PROMPT, extraction_user_prompt
from cortex.db.connection import get_sync_connection
from cortex.db.queries.notes import get_unenriched_notes, update_note_enrichment

logger = logging.getLogger(__name__)


async def enrich_note(note_id: str, raw_text: str) -> dict[str, Any] | None:
    """Run the full enrichment pipeline on a note.

    Generates embedding and extracts metadata via Ollama.

    Args:
        note_id: The note's hex ID.
        raw_text: The raw text of the note.

    Returns:
        The extracted metadata dict, or None if enrichment failed.
    """
    conn = get_sync_connection()
    try:
        # Step 1: Generate and store embedding
        try:
            embedding = encode_text(raw_text)
            store_embedding(conn, note_id, embedding)
        except Exception as e:
            logger.warning(f"Embedding generation failed for note {note_id}: {e}")

        # Step 2: Extract metadata via Ollama
        try:
            metadata = await _extract_metadata(raw_text)
            if metadata:
                update_note_enrichment(
                    conn,
                    note_id,
                    summary=metadata.get("summary", ""),
                    category=metadata.get("category", "uncategorized"),
                    sentiment=metadata.get("sentiment", "neutral"),
                    is_journal=metadata.get("is_journal", False),
                    tags=metadata.get("tags", []),
                )
                return metadata
        except Exception as e:
            logger.warning(f"Metadata extraction failed for note {note_id}: {e}")

        return None
    finally:
        conn.close()


async def _extract_metadata(raw_text: str) -> dict[str, Any] | None:
    """Extract metadata from note text using Ollama.

    Args:
        raw_text: The raw note text.

    Returns:
        Parsed metadata dict, or None on failure.
    """
    client = OllamaClient()
    prompt = extraction_user_prompt(raw_text)

    response = await client.generate(
        prompt=prompt,
        system=EXTRACTION_SYSTEM_PROMPT,
        temperature=0.1,
    )

    # Parse JSON response — handle common issues
    response = response.strip()
    if response.startswith("```"):
        lines = response.split("\n")
        response = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        data = json.loads(response)
        # Validate expected structure
        if not isinstance(data.get("tags"), list):
            data["tags"] = []
        if data.get("category") not in {
            "business", "personal", "idea", "journal",
            "meeting", "task", "reference",
        }:
            data["category"] = "uncategorized"
        if data.get("sentiment") not in {"positive", "negative", "neutral", "mixed"}:
            data["sentiment"] = "neutral"
        return data
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse Ollama response: {e}")
        return None


async def enrich_note_embedding_only(note_id: str, raw_text: str) -> None:
    """Generate and store just the embedding for a note (no Ollama).

    Args:
        note_id: The note's hex ID.
        raw_text: The raw text of the note.
    """
    conn = get_sync_connection()
    try:
        embedding = encode_text(raw_text)
        store_embedding(conn, note_id, embedding)
    finally:
        conn.close()


def enrich_pending_notes_sync() -> int:
    """Synchronously enrich all unenriched notes (for CLI retry command).

    Returns:
        The number of notes enriched.
    """
    import asyncio

    conn = get_sync_connection()
    try:
        unenriched = get_unenriched_notes(conn)
        if not unenriched:
            return 0

        count = 0
        for note in unenriched:
            try:
                result = asyncio.run(enrich_note(note["id"], note["raw_text"]))
                if result:
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to enrich note {note['id']}: {e}")
        return count
    finally:
        conn.close()
