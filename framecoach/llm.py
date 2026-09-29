"""Chat model providers: local Ollama, or the Claude, OpenAI and DeepSeek APIs.

Every provider takes the same ``[{"role": "system"|"user", "content": ...}]``
messages and yields the answer as text chunks, so the rest of the app does not
care which one is in use.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

import requests


class LLMError(RuntimeError):
    """A problem talking to the model, with a message that can be shown to the user."""


class ChatModel(Protocol):
    def stream_chat(self, messages: list[dict[str, str]]) -> Iterator[str]: ...


def chat(model: ChatModel, messages: list[dict[str, str]]) -> str:
    return "".join(model.stream_chat(messages))


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    label: str
    needs_key: bool
    default_model: str
    key_env: str = ""  # environment variable that can hold the API key
    key_url: str = ""  # where to get a key
    suggested_models: tuple[str, ...] = ()


PROVIDERS: dict[str, ProviderInfo] = {
    p.id: p
    for p in (
        ProviderInfo("ollama", "Local model (Ollama)", False, "gemma3", suggested_models=("gemma3", "llama3.1")),
        ProviderInfo(
            "anthropic",
            "Claude (Anthropic)",
            True,
            "claude-opus-5-5",
            key_env="ANTHROPIC_API_KEY",
            key_url="https://console.anthropic.com/settings/keys",
            suggested_models=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"),
        ),
        ProviderInfo(
            "openai",
            "OpenAI",
            True,
            "",  # model names change often, so the user picks from the list the API returns
            key_env="OPENAI_API_KEY",
            key_url="https://platform.openai.com/api-keys",
        ),
        ProviderInfo(
            "deepseek",
            "DeepSeek",
            True,
            "deepseek-chat",
            key_env="DEEPSEEK_API_KEY",
            key_url="https://platform.deepseek.com/api_keys",
            suggested_models=("deepseek-chat", "deepseek-reasoner"),
        ),
    )
}

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MAX_OUTPUT_TOKENS = 16000


# --- Ollama -----------------------------------------------------------------


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]]) -> str:
        return chat(self, messages)

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterator[str]:
        """Yield the answer piece by piece as Ollama generates it."""
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": True},
                stream=True,
                timeout=(5, self.timeout),
            )
        except requests.ConnectionError as exc:
            raise LLMError(
                f"Could not reach Ollama at {self.base_url}. Is it installed and running? "
                "Get it from https://ollama.com/download"
            ) from exc
        except requests.Timeout as exc:
            raise LLMError("Ollama took too long to respond.") from exc

        with response:
            if response.status_code == 404:
                raise LLMError(f"Model '{self.model}' is not installed. Run: ollama pull {self.model}")
            if response.status_code != 200:
                raise LLMError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")
            try:
                for line in response.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise LLMError(chunk["error"])
                    if text := chunk.get("message", {}).get("content"):
                        yield text
                    if chunk.get("done"):
                        break
            except requests.RequestException as exc:
                raise LLMError(f"Lost connection to Ollama: {exc}") from exc

    def generate(self, prompt: str, model: str | None = None) -> str:
        """Single-shot completion, used by the transcript rewriter."""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model or self.model, "prompt": prompt, "stream": False},
                timeout=(5, self.timeout),
            )
        except requests.RequestException as exc:
            raise LLMError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        if response.status_code != 200:
            raise LLMError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")
        return response.json().get("response", "").strip()

    def list_models(self) -> list[str]:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(
                "Ollama is not running. Install it from https://ollama.com/download, then run: ollama pull gemma3"
            ) from exc
        return sorted(m["name"] for m in response.json().get("models", []))


# --- Claude -----------------------------------------------------------------

# Models that accept the server-side refusal fallback. If a safety classifier
# declines a request, the API retries it on another model instead of failing.
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-5", "claude-fable-5-1"}
# Models without the `effort` setting.
_NO_EFFORT_MODELS = {"claude-haiku-4-5"}


def _anthropic_error(exc: Exception) -> LLMError:
    import anthropic

    if isinstance(exc, anthropic.AuthenticationError):
        return LLMError("Your Claude API key was rejected. Check it in Settings.")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return LLMError("Your Claude API key does not have access to this model.")
    if isinstance(exc, anthropic.NotFoundError):
        return LLMError("Claude model not found. Pick another model in Settings.")
    if isinstance(exc, anthropic.RateLimitError):
        return LLMError("Claude rate limit reached. Wait a moment and try again.")
    if isinstance(exc, anthropic.APIStatusError):
        return LLMError(f"Claude API error ({exc.status_code}): {exc.message}")
    if isinstance(exc, anthropic.APIConnectionError):
        return LLMError("Could not reach the Claude API. Check your internet connection.")
    return LLMError(f"Claude error: {exc}")


class AnthropicClient:
    def __init__(self, api_key: str, model: str, timeout: float = 120, base_url: str | None = None):
        import anthropic

        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, base_url=base_url)

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterator[str]:
        import anthropic

        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        params: dict = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "system": system,
            "messages": [m for m in messages if m["role"] != "system"],
        }
        if self.model not in _NO_EFFORT_MODELS:
            params["output_config"] = {"effort": "medium"}
        if self.model in _FALLBACK_MODELS:
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"

        try:
            with self._client.beta.messages.stream(**params) as stream:
                yield from stream.text_stream
                final = stream.get_final_message()
        except anthropic.AnthropicError as exc:
            raise _anthropic_error(exc) from exc
        if final.stop_reason == "refusal":
            raise LLMError("Claude declined to answer this question.")

    def list_models(self) -> list[str]:
        import anthropic

        try:
            return [m.id for m in self._client.models.list()]
        except anthropic.AnthropicError as exc:
            raise _anthropic_error(exc) from exc


# --- OpenAI and DeepSeek ------------------------------------------------------


def _openai_error(exc: Exception, name: str) -> LLMError:
    import openai

    if isinstance(exc, openai.AuthenticationError):
        return LLMError(f"Your {name} API key was rejected. Check it in Settings.")
    if isinstance(exc, openai.NotFoundError):
        return LLMError(f"{name} model not found. Pick another model in Settings.")
    if isinstance(exc, openai.RateLimitError):
        return LLMError(f"{name} rate limit reached or out of credit. Check your account.")
    if isinstance(exc, openai.APIStatusError):
        return LLMError(f"{name} API error ({exc.status_code}): {exc.message}")
    if isinstance(exc, openai.APIConnectionError):
        return LLMError(f"Could not reach the {name} API. Check your internet connection.")
    return LLMError(f"{name} error: {exc}")


# Prefixes of OpenAI models that can chat; the /models list also has embeddings, audio, images...
_OPENAI_CHAT_PREFIXES = ("gpt-", "o1", "o3", "o4", "chatgpt-")
_OPENAI_EXCLUDE = ("audio", "realtime", "tts", "transcribe", "image", "search", "embedding")


class OpenAICompatibleClient:
    """OpenAI's API, and DeepSeek's which speaks the same protocol."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None, name: str = "OpenAI", timeout=120):
        import openai

        self.model = model
        self.name = name
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def stream_chat(self, messages: list[dict[str, str]]) -> Iterator[str]:
        import openai

        try:
            stream = self._client.chat.completions.create(model=self.model, messages=messages, stream=True)
            with stream:
                for chunk in stream:
                    if chunk.choices and (text := chunk.choices[0].delta.content):
                        yield text
        except openai.OpenAIError as exc:
            raise _openai_error(exc, self.name) from exc

    def list_models(self) -> list[str]:
        import openai

        try:
            ids = sorted(m.id for m in self._client.models.list())
        except openai.OpenAIError as exc:
            raise _openai_error(exc, self.name) from exc
        if self.name != "OpenAI":
            return ids
        return [
            i for i in ids if i.startswith(_OPENAI_CHAT_PREFIXES) and not any(word in i for word in _OPENAI_EXCLUDE)
        ]


# --- Factory -----------------------------------------------------------------


def make_client(provider: str, model: str, api_key: str = "", ollama_url: str = "", timeout: float = 120):
    """Build the client for a provider. Raises LLMError for missing configuration."""
    if provider not in PROVIDERS:
        raise LLMError(f"Unknown provider '{provider}'.")
    info = PROVIDERS[provider]
    model = model or info.default_model
    if info.needs_key and not api_key:
        raise LLMError(f"No API key set for {info.label}. Add one in Settings.")
    if provider == "ollama":
        return OllamaClient(ollama_url, model, timeout)
    if not model:
        raise LLMError(f"No model selected for {info.label}. Pick one in Settings.")
    if provider == "anthropic":
        return AnthropicClient(api_key, model, timeout)
    if provider == "deepseek":
        return OpenAICompatibleClient(api_key, model, DEEPSEEK_BASE_URL, "DeepSeek", timeout)
    return OpenAICompatibleClient(api_key, model, None, "OpenAI", timeout)


def list_models(provider: str, api_key: str = "", ollama_url: str = "") -> list[str]:
    """Models available to this key (or installed in Ollama). Also a handy way to check a key works."""
    # The model name is irrelevant for listing; pass a placeholder so make_client doesn't complain.
    return make_client(provider, "list", api_key, ollama_url, timeout=15).list_models()
