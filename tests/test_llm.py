import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from framecoach.llm import (
    AnthropicClient,
    LLMError,
    OllamaClient,
    OpenAICompatibleClient,
    chat,
    make_client,
)
from framecoach.user_settings import SettingsStore, UserSettings, mask_key

MESSAGES = [{"role": "system", "content": "Be a coach."}, {"role": "user", "content": "Ryu jab?"}]


@contextmanager
def fake_server(status, body, content_type="application/json"):
    """A throwaway HTTP server that answers every request the same way."""

    class Handler(BaseHTTPRequestHandler):
        def _reply(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(body.encode())

        do_GET = do_POST = _reply

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


def test_make_client_validation():
    with pytest.raises(LLMError, match="API key"):
        make_client("anthropic", "claude-opus-5-5")
    with pytest.raises(LLMError, match="model"):
        make_client("openai", "", api_key="sk-test")
    with pytest.raises(LLMError, match="Unknown provider"):
        make_client("nope", "x")
    assert isinstance(make_client("anthropic", "", api_key="sk-test"), AnthropicClient)
    assert make_client("anthropic", "", api_key="sk-test").model == "claude-opus-5-5"
    deepseek = make_client("deepseek", "", api_key="sk-test")
    assert isinstance(deepseek, OpenAICompatibleClient) and deepseek.model == "deepseek-chat"
    assert "deepseek" in str(deepseek._client.base_url)
    assert make_client("ollama", "", ollama_url="http://x").model == "gemma3"


def test_ollama_streams_answer():
    lines = [{"message": {"content": "Jab "}, "done": False}, {"message": {"content": "is 4f."}, "done": True}]
    with fake_server(200, "\n".join(json.dumps(line) for line in lines)) as url:
        assert chat(OllamaClient(url, "gemma3"), MESSAGES) == "Jab is 4f."


def test_ollama_missing_model():
    with fake_server(404, "{}") as url, pytest.raises(LLMError, match="ollama pull gemma3"):
        chat(OllamaClient(url, "gemma3"), MESSAGES)


def test_ollama_not_running():
    with pytest.raises(LLMError, match="Ollama"):
        chat(OllamaClient("http://127.0.0.1:9", "gemma3"), MESSAGES)
    with pytest.raises(LLMError, match="not running"):
        OllamaClient("http://127.0.0.1:9", "gemma3").list_models()


class FakeAnthropicStream:
    def __init__(self, chunks, stop_reason="end_turn"):
        self.text_stream = iter(chunks)
        self.stop_reason = stop_reason

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return SimpleNamespace(stop_reason=self.stop_reason)


def patch_anthropic(client, stream):
    calls = []

    def fake_stream(**params):
        calls.append(params)
        return stream

    client._client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=fake_stream)))
    return calls


def test_anthropic_request_shape():
    client = AnthropicClient("sk-test", "claude-opus-5-5")
    calls = patch_anthropic(client, FakeAnthropicStream(["Jab ", "is 4f."]))
    assert chat(client, MESSAGES) == "Jab is 4f."
    params = calls[0]
    assert params["system"] == "Be a coach."
    assert params["messages"] == [{"role": "user", "content": "Ryu jab?"}]
    assert params["output_config"] == {"effort": "medium"}
    assert params["fallbacks"] == "default" and params["betas"] == ["server-side-fallback-2026-07-01"]


def test_anthropic_haiku_skips_unsupported_options():
    client = AnthropicClient("sk-test", "claude-haiku-4-5")
    calls = patch_anthropic(client, FakeAnthropicStream(["ok"]))
    chat(client, MESSAGES)
    assert "output_config" not in calls[0] and "fallbacks" not in calls[0]


def test_anthropic_refusal_is_reported():
    client = AnthropicClient("sk-test", "claude-opus-5-5")
    patch_anthropic(client, FakeAnthropicStream([], stop_reason="refusal"))
    with pytest.raises(LLMError, match="declined"):
        chat(client, MESSAGES)


def test_anthropic_bad_key_gets_friendly_error():
    body = json.dumps({"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})
    with fake_server(401, body) as url:
        client = AnthropicClient("sk-bad", "claude-opus-5-5", base_url=url)
        with pytest.raises(LLMError, match="Claude API key was rejected"):
            chat(client, MESSAGES)
        with pytest.raises(LLMError, match="Claude API key was rejected"):
            client.list_models()


def test_openai_compatible_streams_answer():
    chunks = [
        {
            "id": "1",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "m",
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}],
        }
        for text in ("Jab ", "is 4f.")
    ]
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    with fake_server(200, body, "text/event-stream") as url:
        client = OpenAICompatibleClient("sk-test", "deepseek-chat", url, "DeepSeek")
        assert chat(client, MESSAGES) == "Jab is 4f."


def test_openai_bad_key_gets_friendly_error():
    body = json.dumps({"error": {"message": "Incorrect API key", "type": "invalid_request_error"}})
    with fake_server(401, body) as url:
        client = OpenAICompatibleClient("sk-bad", "deepseek-chat", url, "DeepSeek")
        with pytest.raises(LLMError, match="DeepSeek API key was rejected"):
            chat(client, MESSAGES)


def test_openai_model_list_is_filtered():
    body = json.dumps(
        {
            "object": "list",
            "data": [
                {"id": name, "object": "model", "created": 0, "owned_by": "x"}
                for name in ("gpt-x", "text-embedding-3-small", "gpt-x-audio", "o3-mini", "dall-e-3")
            ],
        }
    )
    with fake_server(200, body) as url:
        assert OpenAICompatibleClient("sk-test", "gpt-x", url, "OpenAI").list_models() == ["gpt-x", "o3-mini"]


def test_settings_store_roundtrip(tmp_path):
    store = SettingsStore(tmp_path)
    assert store.load().configured is False
    store.save(
        UserSettings(provider="anthropic", models={"anthropic": "claude-sonnet-5-5"}, api_keys={"anthropic": "k"})
    )
    loaded = store.load()
    assert loaded.provider == "anthropic" and loaded.model_for("anthropic") == "claude-sonnet-5-5"
    assert loaded.key_for("anthropic") == "k"


def test_settings_store_ignores_garbage(tmp_path):
    (tmp_path / "config.json").write_text("{not json")
    assert SettingsStore(tmp_path).load().configured is False
    (tmp_path / "config.json").write_text(json.dumps({"provider": "skynet", "api_keys": {"x": "y"}}))
    loaded = SettingsStore(tmp_path).load()
    assert loaded.provider == "" and loaded.api_keys == {}


def test_key_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-env-12345")
    assert UserSettings().key_for("deepseek") == "from-env-12345"
    assert UserSettings(api_keys={"deepseek": "saved"}).key_for("deepseek") == "saved"


def test_mask_key():
    assert mask_key("sk-ant-abcdef123456") == "...3456"
    assert "short" not in mask_key("short")
