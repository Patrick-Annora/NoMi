"""Ollama HTTP client wrapper for local LLM interactions."""

import json
from collections.abc import AsyncIterator

import httpx

from cortex.config import get_settings


class OllamaClient:
    """HTTP client for the Ollama API."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        """Initialize the Ollama client.

        Args:
            base_url: The Ollama API base URL. Defaults to settings.
            model: The model to use. Defaults to settings.
        """
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = settings.ollama_timeout

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.1,
    ) -> str:
        """Generate a completion from Ollama.

        Args:
            prompt: The user prompt.
            system: Optional system prompt.
            temperature: Sampling temperature.

        Returns:
            The generated text response.
        """
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        """Stream a completion from Ollama.

        Args:
            prompt: The user prompt.
            system: Optional system prompt.
            temperature: Sampling temperature.

        Yields:
            Text chunks as they arrive.
        """
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/generate", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token

    async def is_available(self) -> bool:
        """Check if Ollama is running and accessible.

        Returns:
            True if Ollama is available.
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def has_model(self) -> bool:
        """Check if the configured model is available in Ollama.

        Returns:
            True if the model is pulled and ready.
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code != 200:
                    return False
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                return any(self.model in m for m in models)
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
