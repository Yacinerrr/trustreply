import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from trustreply.core import AnthropicClient, GroqClient, LLMError
from trustreply.core.llm import DEFAULT_GROQ_MODEL, GROQ_URL, get_client


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self.raw


def chat_reply(text: str) -> dict:
    return {
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": text}}],
    }


def http_error(code: int, message: str) -> urllib.error.HTTPError:
    body = json.dumps({"error": {"message": message}}).encode()
    return urllib.error.HTTPError(GROQ_URL, code, "err", {}, io.BytesIO(body))  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate from any real .env or keys on the machine running the tests."""
    for name in ("GROQ_API_KEY", "ANTHROPIC_API_KEY", "TRUSTREPLY_PROVIDER", "TRUSTREPLY_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


def stub_urlopen(monkeypatch: pytest.MonkeyPatch, outcome: object) -> dict:
    seen: dict = {}

    def fake(request: urllib.request.Request, timeout: float | None = None):
        seen["url"] = request.full_url
        seen["headers"] = {k.lower(): v for k, v in request.header_items()}
        seen["body"] = json.loads(request.data)
        seen["timeout"] = timeout
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return seen


def test_request_format(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = stub_urlopen(monkeypatch, chat_reply('{"verdict": "yes"}'))
    client = GroqClient(api_key="gsk-test")
    assert client.complete("SYSTEM", "USER") == '{"verdict": "yes"}'
    assert client.provider == "Groq"
    assert seen["url"] == GROQ_URL
    assert seen["headers"]["authorization"] == "Bearer gsk-test"
    assert seen["headers"]["user-agent"].startswith("trustreply")
    assert seen["headers"]["content-type"] == "application/json"
    body = seen["body"]
    assert body["model"] == DEFAULT_GROQ_MODEL
    assert body["messages"] == [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "USER"},
    ]
    assert body["max_completion_tokens"] > 0
    assert body["temperature"] == 0
    assert seen["timeout"] and seen["timeout"] > 0


def test_model_override_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTREPLY_MODEL", "openai/gpt-oss-120b")
    seen = stub_urlopen(monkeypatch, chat_reply("ok"))
    GroqClient(api_key="k").complete("s", "u")
    assert seen["body"]["model"] == "openai/gpt-oss-120b"


def test_anthropic_model_in_env_gives_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTREPLY_MODEL", "claude-sonnet-5-5")
    with pytest.raises(LLMError, match="Anthropic model"):
        GroqClient(api_key="k")


def test_missing_key() -> None:
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqClient()


def test_bad_key_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_urlopen(monkeypatch, http_error(401, "Invalid API Key"))
    with pytest.raises(LLMError, match=r"401.*Invalid API Key"):
        GroqClient(api_key="bad").complete("s", "u")


def test_unknown_model_error_has_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_urlopen(monkeypatch, http_error(404, "The model does not exist"))
    with pytest.raises(LLMError, match="TRUSTREPLY_MODEL"):
        GroqClient(api_key="k").complete("s", "u")


def test_rate_limit_error_has_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_urlopen(monkeypatch, http_error(429, "Rate limit reached"))
    with pytest.raises(LLMError, match="rate limit"):
        GroqClient(api_key="k").complete("s", "u")


def test_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_urlopen(monkeypatch, urllib.error.URLError("no route to host"))
    with pytest.raises(LLMError, match="Could not reach Groq"):
        GroqClient(api_key="k").complete("s", "u")


@pytest.mark.parametrize("payload", [b"<html>oops</html>", {"choices": []}, {"nothing": 1}])
def test_malformed_responses(monkeypatch: pytest.MonkeyPatch, payload: object) -> None:
    stub_urlopen(monkeypatch, payload)
    with pytest.raises(LLMError):
        GroqClient(api_key="k").complete("s", "u")


def test_null_content_becomes_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_urlopen(monkeypatch, {"choices": [{"message": {"content": None}}]})
    assert GroqClient(api_key="k").complete("s", "u") == ""


def test_provider_is_groq_when_only_groq_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "g")
    assert isinstance(get_client(), GroqClient)


def test_provider_defaults_to_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert isinstance(get_client(), AnthropicClient)
    monkeypatch.setenv("GROQ_API_KEY", "g")  # both present: Anthropic wins unless told otherwise
    assert isinstance(get_client(), AnthropicClient)


def test_explicit_provider_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("TRUSTREPLY_PROVIDER", "Groq")
    assert isinstance(get_client(), GroqClient)


def test_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTREPLY_PROVIDER", "openai")
    with pytest.raises(LLMError, match="Unknown TRUSTREPLY_PROVIDER"):
        get_client()


def test_get_client_reads_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("GROQ_API_KEY=gsk-from-file\n", encoding="utf-8")
    client = get_client()
    assert isinstance(client, GroqClient)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)  # tidy up what load_env_file set
