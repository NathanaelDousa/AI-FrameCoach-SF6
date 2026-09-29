"""Minimal Ollama client."""

from __future__ import annotations

import json
from collections.abc import Iterator

import requests


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]]) -> str:
        return "".join(self.stream_chat(messages))

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
            raise OllamaError(f"Could not reach Ollama at {self.base_url}. Is it running? (ollama serve)") from exc
        except requests.Timeout as exc:
            raise OllamaError("Ollama took too long to respond.") from exc

        with response:
            if response.status_code == 404:
                raise OllamaError(f"Model '{self.model}' not found. Pull it with: ollama pull {self.model}")
            if response.status_code != 200:
                raise OllamaError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")
            try:
                for line in response.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise OllamaError(chunk["error"])
                    if text := chunk.get("message", {}).get("content"):
                        yield text
                    if chunk.get("done"):
                        break
            except requests.RequestException as exc:
                raise OllamaError(f"Lost connection to Ollama: {exc}") from exc

    def generate(self, prompt: str, model: str | None = None) -> str:
        """Single-shot completion, used by the transcript rewriter."""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model or self.model, "prompt": prompt, "stream": False},
                timeout=(5, self.timeout),
            )
        except requests.RequestException as exc:
            raise OllamaError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")
        return response.json().get("response", "").strip()
