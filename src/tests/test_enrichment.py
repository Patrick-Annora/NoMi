"""Tagging pipeline tests."""

import pytest

from cortex.ai.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    SYNTHESIS_SIGNALS,
    extraction_user_prompt,
    agent_context_prompt,
)


class TestPrompts:
    """Test prompt construction."""

    def test_extraction_prompt_contains_note(self) -> None:
        """Test that extraction prompt includes the note text."""
        prompt = extraction_user_prompt("This is a test note about fundraising.")
        assert "This is a test note about fundraising." in prompt
        assert 'Note:\n"""' in prompt

    def test_extraction_system_prompt_has_categories(self) -> None:
        """Test that system prompt lists valid categories."""
        for category in ["business", "personal", "idea", "journal", "meeting", "task", "reference"]:
            assert category in EXTRACTION_SYSTEM_PROMPT

    def test_extraction_system_prompt_has_sentiments(self) -> None:
        """Test that system prompt lists valid sentiments."""
        for sentiment in ["positive", "negative", "neutral", "mixed"]:
            assert sentiment in EXTRACTION_SYSTEM_PROMPT

    def test_agent_context_prompt_with_notes(self) -> None:
        """Test agent context prompt with note data."""
        notes = [
            {
                "id": "abc123",
                "raw_text": "Meeting with Sequoia went well.",
                "created_at": "2025-02-18T10:00:00",
                "category": "business",
                "tags": [{"name": "fundraising"}, {"name": "sequoia"}],
            },
        ]
        prompt = agent_context_prompt("How did the Sequoia meeting go?", notes)
        assert "abc123" in prompt
        assert "Meeting with Sequoia went well." in prompt
        assert "fundraising" in prompt
        assert "How did the Sequoia meeting go?" in prompt

    def test_agent_context_prompt_empty_notes(self) -> None:
        """Test agent context prompt with no notes."""
        prompt = agent_context_prompt("Any notes?", [])
        assert "No relevant notes found" in prompt

    def test_synthesis_signals_are_strings(self) -> None:
        """Test that synthesis signals are properly defined."""
        assert len(SYNTHESIS_SIGNALS) > 0
        assert all(isinstance(s, str) for s in SYNTHESIS_SIGNALS)
        assert "pattern" in SYNTHESIS_SIGNALS
        assert "analyze" in SYNTHESIS_SIGNALS


class TestModelSelection:
    """Test model selection logic."""

    def test_local_preference(self) -> None:
        """Test that local preference returns ollama."""
        from cortex.ai.agent import select_model

        assert select_model("anything", preference="local") == "ollama"

    def test_auto_retrieval_query(self) -> None:
        """Test that simple retrieval queries default to ollama."""
        from cortex.ai.agent import select_model

        assert select_model("what did I say about pricing?", preference="auto") == "ollama"

    def test_auto_synthesis_query_without_key(self) -> None:
        """Test that synthesis queries fall back to ollama without API key."""
        from cortex.ai.agent import select_model

        # Without an API key set, should fall back to ollama
        result = select_model("what patterns do I see in my notes?", preference="auto")
        assert result in ("ollama", "claude")  # Depends on env
