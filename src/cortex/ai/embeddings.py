"""Sentence-transformers embedding model loading and encoding."""

import struct
from typing import Any

from cortex.config import get_settings

# Module-level model cache
_model: Any = None


def get_embedding_model() -> Any:
    """Load or return the cached sentence-transformers model.

    Returns:
        The loaded SentenceTransformer model.
    """
    global _model  # noqa: PLW0603
    if _model is None:
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def encode_text(text: str) -> list[float]:
    """Encode a text string into an embedding vector.

    Args:
        text: The text to encode.

    Returns:
        A list of floats representing the embedding.
    """
    model = get_embedding_model()
    embedding = model.encode(text, show_progress_bar=False)
    return embedding.tolist()


def encode_texts(texts: list[str]) -> list[list[float]]:
    """Encode multiple texts into embedding vectors.

    Args:
        texts: A list of texts to encode.

    Returns:
        A list of embedding vectors.
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return [e.tolist() for e in embeddings]


def embedding_to_blob(embedding: list[float]) -> bytes:
    """Convert an embedding list to a binary blob for sqlite-vec.

    Args:
        embedding: The embedding vector as a list of floats.

    Returns:
        The binary-packed embedding.
    """
    return struct.pack(f"{len(embedding)}f", *embedding)


def store_embedding(
    conn: Any,
    note_id: str,
    embedding: list[float],
) -> None:
    """Store a note's embedding in the sqlite-vec virtual table.

    Args:
        conn: An active SQLite connection.
        note_id: The note's hex ID.
        embedding: The embedding vector.
    """
    blob = embedding_to_blob(embedding)
    conn.execute(
        "INSERT OR REPLACE INTO note_embeddings (note_id, embedding) VALUES (?, ?)",
        (note_id, blob),
    )
    conn.commit()
