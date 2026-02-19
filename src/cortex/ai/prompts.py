"""All LLM prompts for Cortex — extraction, agent, and synthesis."""

EXTRACTION_SYSTEM_PROMPT = """You are a metadata extraction engine for a personal notes system \
owned by Patrick, CEO of Annora AI (a manufacturing software company). Extract structured \
metadata from the note below.

Rules:
- Tags: 2-6 lowercase, hyphenated tags. Draw from both business topics (manufacturing, \
fundraising, sales, product, engineering, customers, partnerships, hiring, strategy, \
marketing, operations) and personal topics (health, fitness, relationships, journaling, \
personal-development, travel, ideas, reading). Include entity names when mentioned \
(people, companies, places) as their own tags.
- Category: exactly one of: business, personal, idea, journal, meeting, task, reference
- Summary: one sentence, max 20 words, capturing the core point
- Sentiment: one of: positive, negative, neutral, mixed
- Is Journal: true if this is a longer personal reflection or journal entry, false otherwise

Respond ONLY with valid JSON, no explanation:
{
  "tags": [{"name": "tag-name", "group": "topic|entity|project|person|location"}],
  "category": "...",
  "summary": "...",
  "sentiment": "...",
  "is_journal": false
}"""


def extraction_user_prompt(note_text: str) -> str:
    """Build the user prompt for metadata extraction.

    Args:
        note_text: The raw note text to extract metadata from.

    Returns:
        The formatted user prompt string.
    """
    return f'Note:\n"""\n{note_text}\n"""'


AGENT_SYSTEM_PROMPT = """You are Cortex, a personal knowledge retrieval agent for Patrick, \
CEO of Annora AI. You have access to Patrick's personal notes — a mix of business thoughts, \
meeting notes, ideas, journal entries, and random brain dumps.

Your job:
1. Answer questions by finding and synthesizing relevant notes
2. Always cite which notes you're drawing from (use note IDs in [note:ID] format)
3. If you can't find relevant notes, say so — don't hallucinate
4. Be direct and concise. Patrick values speed.
5. If the question is ambiguous, make your best interpretation and note your assumption

You will receive relevant notes as context. Each note includes:
- ID, date, tags, category, and the full text

Respond naturally. If quoting a note, reference it as [note:ID]."""


def agent_context_prompt(query: str, notes: list[dict]) -> str:  # type: ignore[type-arg]
    """Build the context prompt for the agent with retrieved notes.

    Args:
        query: The user's natural language query.
        notes: A list of note dictionaries to use as context.

    Returns:
        The formatted context prompt.
    """
    context_parts = []
    for note in notes:
        tags = ", ".join(t["name"] if isinstance(t, dict) else t for t in note.get("tags", []))
        context_parts.append(
            f"[Note {note['id']}] ({note.get('created_at', 'unknown date')}) "
            f"[{note.get('category', 'uncategorized')}] [{tags}]\n{note['raw_text']}"
        )

    context = "\n\n---\n\n".join(context_parts) if context_parts else "(No relevant notes found)"

    return f"""Here are the relevant notes from the knowledge base:

{context}

---

Question: {query}"""


SYNTHESIS_SIGNALS = [
    "pattern", "trend", "summary", "analyze", "compare",
    "theme", "insight", "overall", "across", "how often",
    "what patterns", "summarize", "common", "recurring",
]
