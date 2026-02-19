"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Cortex application settings."""

    # Database
    db_path: str = "data/cortex.db"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout: int = 30

    # Anthropic (optional)
    anthropic_api_key: str = ""

    # Server
    host: str = "127.0.0.1"
    port: int = 8833

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def db_full_path(self) -> Path:
        """Resolve the database path relative to the project root."""
        path = Path(self.db_path)
        if not path.is_absolute():
            path = Path(__file__).parent.parent.parent / path
        return path

    @property
    def has_anthropic_key(self) -> bool:
        """Check if an Anthropic API key is configured."""
        return bool(self.anthropic_api_key)


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
