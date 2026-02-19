"""Search agent — query understanding, retrieval, and synthesis."""

import json
import logging
import struct
from typing import Any, AsyncIterator

import aiosqlite

from cortex.ai.embeddings import encode_text
from cortex.ai.ollama_client import OllamaClient
from cortex.ai.prompts import (
    AGENT_SYSTEM_PROMPT,
    SYNTHESIS_SIGNALS,
    agent_context_prompt,
)
from cortex.config import get_settings
from cortex.db.queries.search import keyword_search, semantic_search

logger = logging.getLogger(__name__)


def select_model(query: str, preference: str = "auto") -> str:
    """Pick the right model for the query.

    Args:
        query: The user's search query.
        preference: User preference — 'auto', 'local', or 'claude'.

    Returns:
        The model to use: 'ollama' or 'claude'.
    """
    if preference == "local":
        return "ollama"
    if preference == "claude":
        settings = get_settings()
        if settings.has_anthropic_key:
            return "claude"
        return "ollama"

    # Auto mode: synthesis → Claude, retrieval → local
    if any(signal in query.lower() for signal in SYNTHESIS_SIGNALS):
        settings = get_settings()
        if settings.has_anthropic_key:
            return "claude"
    return "ollama"


async def agent_search(
    conn: aiosqlite.Connection,
    query: str,
    model_preference: str = "auto",
    category: str | None = None,
    tag: str | None = None,
    date_after: str | None = None,
    date_before: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run the full agent search pipeline with streaming.

    Yields SSE-compatible event dicts:
    - {"event": "token", "data": {"text": "..."}}
    - {"event": "citations", "data": {"note_ids": [...]}}
    - {"event": "done", "data": {"model_used": "...", "notes_searched": N, "notes_cited": M}}

    Args:
        conn: An active async SQLite connection.
        query: The natural language query.
        model_preference: Model preference ('auto', 'local', 'claude').
        category: Optional category filter.
        tag: Optional tag filter.
        date_after: Optional date lower bound.
        date_before: Optional date upper bound.

    Yields:
        SSE event dictionaries.
    """
    # Step 1: Retrieve relevant notes via semantic + keyword search
    query_embedding = encode_text(query)
    semantic_results = await semantic_search(
        conn, query_embedding, limit=10,
        category=category, tag=tag,
        date_after=date_after, date_before=date_before,
    )

    try:
        keyword_results = await keyword_search(conn, query, limit=5)
    except Exception:
        keyword_results = []

    # Merge and deduplicate
    seen_ids: set[str] = set()
    context_notes: list[dict[str, Any]] = []
    for note in semantic_results + keyword_results:
        if note["id"] not in seen_ids:
            seen_ids.add(note["id"])
            context_notes.append(note)

    context_notes = context_notes[:15]  # Cap at 15 notes for context

    if not context_notes:
        yield {
            "event": "token",
            "data": {"text": "I couldn't find any relevant notes for that query."},
        }
        yield {
            "event": "done",
            "data": {"model_used": "none", "notes_searched": 0, "notes_cited": 0},
        }
        return

    # Step 2: Select model and generate response
    model = select_model(query, model_preference)
    context_prompt = agent_context_prompt(query, context_notes)
    cited_ids: list[str] = [n["id"] for n in context_notes]

    if model == "claude":
        async for event in _stream_claude(context_prompt, cited_ids, len(context_notes)):
            yield event
    else:
        async for event in _stream_ollama(context_prompt, cited_ids, len(context_notes)):
            yield event


async def _stream_ollama(
    prompt: str,
    cited_ids: list[str],
    notes_searched: int,
) -> AsyncIterator[dict[str, Any]]:
    """Stream a response from Ollama.

    Args:
        prompt: The full prompt with context.
        cited_ids: Note IDs referenced in context.
        notes_searched: Number of notes searched.

    Yields:
        SSE event dictionaries.
    """
    client = OllamaClient()
    try:
        async for token in client.generate_stream(
            prompt=prompt,
            system=AGENT_SYSTEM_PROMPT,
            temperature=0.3,
        ):
            yield {"event": "token", "data": {"text": token}}

        yield {"event": "citations", "data": {"note_ids": cited_ids}}
        yield {
            "event": "done",
            "data": {
                "model_used": "ollama",
                "notes_searched": notes_searched,
                "notes_cited": len(cited_ids),
            },
        }
    except Exception as e:
        logger.error(f"Ollama streaming failed: {e}")
        yield {
            "event": "token",
            "data": {"text": f"Error querying local model: {e}"},
        }
        yield {
            "event": "done",
            "data": {"model_used": "ollama", "notes_searched": notes_searched, "notes_cited": 0},
        }


async def _stream_claude(
    prompt: str,
    cited_ids: list[str],
    notes_searched: int,
) -> AsyncIterator[dict[str, Any]]:
    """Stream a response from Claude.

    Args:
        prompt: The full prompt with context.
        cited_ids: Note IDs referenced in context.
        notes_searched: Number of notes searched.

    Yields:
        SSE event dictionaries.
    """
    settings = get_settings()
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        with client.messages.stream(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            system=AGENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield {"event": "token", "data": {"text": text}}

        yield {"event": "citations", "data": {"note_ids": cited_ids}}
        yield {
            "event": "done",
            "data": {
                "model_used": "claude",
                "notes_searched": notes_searched,
                "notes_cited": len(cited_ids),
            },
        }
    except Exception as e:
        logger.error(f"Claude streaming failed: {e}")
        yield {
            "event": "token",
            "data": {"text": f"Error querying Claude: {e}"},
        }
        yield {
            "event": "done",
            "data": {"model_used": "claude", "notes_searched": notes_searched, "notes_cited": 0},
        }
