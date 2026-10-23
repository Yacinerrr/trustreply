"""A thin wrapper around the LLM provider, so the rest of the code never touches the SDK.

Keeping this boundary small means tests can use a fake client (no network, no API key) and
the provider can be swapped later without touching the drafting logic.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

DEFAULT_MODEL = "claude-sonnet-5-5"  # Anthropic
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_MAX_TOKENS = 1024
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 60


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

    provider = "Anthropic"

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


def _error_message(error: urllib.error.HTTPError) -> str:
    """Pull a readable message out of an HTTP error body."""
    try:
        raw = error.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - best effort only
        return str(error.reason)
    try:
        message = json.loads(raw).get("error", {}).get("message")
    except (json.JSONDecodeError, AttributeError):
        message = None
    return message or raw.strip()[:200] or str(error.reason)


class GroqClient:
    """Calls Groq's OpenAI-compatible chat completions API (standard library only)."""

    provider = "Groq"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        env_model = os.environ.get("TRUSTREPLY_MODEL")
        if model is None and env_model and env_model.lower().startswith("claude"):
            raise LLMError(
                f"TRUSTREPLY_MODEL is set to '{env_model}', which is an Anthropic model. "
                "Delete that line from your .env to use Groq's default model."
            )
        self.model = model or env_model or DEFAULT_GROQ_MODEL
        self._api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self._api_key:
            raise LLMError(
                "No Groq API key found. Copy .env.example to .env, set GROQ_API_KEY, "
                "and run the command again from the same folder."
            )

    def complete(self, system: str, user: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_completion_tokens": DEFAULT_MAX_TOKENS,
                "temperature": 0,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            GROQ_URL,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                # Groq's edge can reject Python's default User-Agent, so identify ourselves.
                "User-Agent": "trustreply/0.1 (+https://github.com/Yacinerrr/trustreply)",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            hint = ""
            if error.code in (400, 404):
                hint = " Check TRUSTREPLY_MODEL in your .env (delete it to use the default)."
            elif error.code == 429:
                hint = " You have hit a rate limit; wait a minute and try again."
            raise LLMError(
                f"Groq request failed ({error.code}): {_error_message(error)}.{hint}"
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise LLMError(f"Could not reach Groq: {error}") from error
        except json.JSONDecodeError as error:
            raise LLMError("Groq returned a reply that could not be read.") from error

        try:
            return body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError("Groq returned an unexpected response format.") from error


def get_client() -> LLMClient:
    """Build the client for the configured provider (.env is loaded if present).

    TRUSTREPLY_PROVIDER=groq|anthropic chooses explicitly. Otherwise Groq is used when only
    a Groq key is present, and Anthropic in every other case.
    """
    load_env_file()
    provider = os.environ.get("TRUSTREPLY_PROVIDER", "").strip().lower()
    if not provider:
        only_groq = bool(os.environ.get("GROQ_API_KEY")) and not os.environ.get("ANTHROPIC_API_KEY")
        provider = "groq" if only_groq else "anthropic"
    if provider == "groq":
        return GroqClient()
    if provider == "anthropic":
        return AnthropicClient()
    raise LLMError(f"Unknown TRUSTREPLY_PROVIDER '{provider}'. Use 'groq' or 'anthropic'.")
