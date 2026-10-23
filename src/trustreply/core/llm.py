"""A thin wrapper around the LLM provider, so the rest of the code never touches the SDK.

Keeping this boundary small means tests can use a fake client (no network, no API key) and
the provider can be swapped later without touching the drafting logic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_MAX_TOKENS = 1024


class LLMError(RuntimeError):
    """Raised when the model cannot be reached or is not configured."""


class LLMClient(Protocol):
    """Anything that can turn a system prompt and a user prompt into text."""

    def complete(self, system: str, user: str) -> str: ...


def load_env_file(path: str | Path = ".env") -> None:
    """Load KEY=VALUE lines from a .env file into os.environ (existing variables win).

    A tiny loader so we need no extra dependency. Quotes around values are stripped; blank
    lines and comments are ignored. Missing file is fine.
    """
    env_path = Path(path)
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and value and key not in os.environ:
            os.environ[key] = value


class AnthropicClient:
    """Calls the Anthropic Messages API."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("TRUSTREPLY_MODEL") or DEFAULT_MODEL
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise LLMError(
                "No API key found. Copy .env.example to .env, set ANTHROPIC_API_KEY, "
                "and run the command again from the same folder."
            )

    def complete(self, system: str, user: str) -> str:
        import anthropic  # imported here so tests and non-AI commands do not need it

        client = anthropic.Anthropic(api_key=self._api_key)
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIError as error:
            raise LLMError(f"The model request failed: {error}") from error
        return "".join(block.text for block in response.content if block.type == "text")


def get_client() -> LLMClient:
    """Build the default client from the environment (.env is loaded if present)."""
    load_env_file()
    return AnthropicClient()
