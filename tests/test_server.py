import json

import pytest

from framecoach.ingest import build_index
from framecoach.llm import LLMError
from framecoach.rag import Retriever
from framecoach.server import create_app
from framecoach.store import open_collection
from framecoach.user_settings import SettingsStore


class FakeLLM:
    def __init__(self, fail=False):
        self.fail = fail
        self.messages = None

    def stream_chat(self, messages):
        self.messages = messages
        if self.fail:
            raise LLMError("Could not reach Ollama")
        yield "Use "
        yield "**SPD**."

    def chat(self, messages):
        return "".join(self.stream_chat(messages))


@pytest.fixture
def retriever(settings, embedder):
    build_index(settings, embedder)
    return Retriever(open_collection(settings), embedder, settings)


def make_client(settings, retriever, llm, tmp_path=None):
    store = SettingsStore(tmp_path) if tmp_path else None
    return create_app(settings, retriever=retriever, llm=llm, store=store).test_client()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Never touch the real user config, and ignore API keys from the environment."""
    monkeypatch.setenv("FRAMECOACH_CONFIG_DIR", str(tmp_path / "config"))
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_index_page(settings, retriever):
    response = make_client(settings, retriever, FakeLLM()).get("/")
    assert response.status_code == 200
    assert b"Zangief" in response.data


def test_ask_json(settings, retriever):
    llm = FakeLLM()
    response = make_client(settings, retriever, llm).post("/api/ask", json={"question": "Zangief anti-air?"})
    data = response.get_json()
    assert response.status_code == 200
    assert data["answer"] == "Use **SPD**."
    assert data["characters"] == ["Zangief"]
    assert data["sources"] and "Zangief" in llm.messages[1]["content"]


def test_ask_stream(settings, retriever):
    response = make_client(settings, retriever, FakeLLM()).post(
        "/api/ask", json={"question": "Ryu jab", "stream": True}
    )
    events = [json.loads(line) for line in response.data.decode().splitlines()]
    assert [e["type"] for e in events] == ["meta", "token", "token", "done"]


def test_ask_stream_reports_llm_errors(settings, retriever):
    response = make_client(settings, retriever, FakeLLM(fail=True)).post(
        "/api/ask", json={"question": "Ryu jab", "stream": True}
    )
    events = [json.loads(line) for line in response.data.decode().splitlines()]
    assert events[-1] == {"type": "error", "error": "Could not reach Ollama"}


def test_ask_json_reports_llm_errors(settings, retriever):
    response = make_client(settings, retriever, FakeLLM(fail=True)).post("/api/ask", json={"question": "Ryu jab"})
    assert response.status_code == 502


@pytest.mark.parametrize("body", [{}, {"question": "   "}, {"question": "x" * 501}, None])
def test_ask_validates_input(settings, retriever, body):
    client = make_client(settings, retriever, FakeLLM())
    response = client.post("/api/ask", json=body) if body is not None else client.post("/api/ask", data="nope")
    assert response.status_code == 400


def test_missing_index_returns_503(settings):
    client = create_app(settings, llm=FakeLLM()).test_client()
    response = client.post("/api/ask", json={"question": "Ryu jab"})
    assert response.status_code == 503
    assert "ingest" in response.get_json()["error"]


# --- settings ---------------------------------------------------------------


@pytest.fixture
def app_client(settings, retriever, tmp_path):
    """An app that picks its model from the saved settings, like the real one."""
    return create_app(settings, retriever=retriever, store=SettingsStore(tmp_path / "cfg")).test_client()


def test_first_launch_is_unconfigured(app_client):
    data = app_client.get("/api/settings").get_json()
    assert data["configured"] is False
    assert {p["id"] for p in data["providers"]} == {"ollama", "anthropic", "openai", "deepseek"}


def test_health_before_choosing_a_model(app_client):
    assert app_client.get("/api/health").get_json() == {"status": "ok", "provider": None, "model": None}


def test_ask_before_choosing_a_model(app_client):
    response = app_client.post("/api/ask", json={"question": "Ryu jab"})
    assert response.status_code == 400
    assert "Choose a model" in response.get_json()["error"]


def test_choose_local_model(app_client):
    response = app_client.post("/api/settings", json={"provider": "ollama", "model": "llama3.1"})
    data = response.get_json()
    assert response.status_code == 200 and data["configured"] and data["provider"] == "ollama"
    assert app_client.get("/api/health").get_json()["model"] == "llama3.1"


def test_api_provider_needs_a_key(app_client):
    response = app_client.post("/api/settings", json={"provider": "anthropic", "model": "claude-opus-5-5"})
    assert response.status_code == 400
    assert "API key" in response.get_json()["error"]


def test_api_key_is_saved_but_never_sent_back(app_client, tmp_path):
    key = "sk-ant-secret-key-1234"
    response = app_client.post("/api/settings", json={"provider": "anthropic", "api_key": key})
    assert response.status_code == 200
    assert key not in response.get_data(as_text=True)
    assert key not in app_client.get("/api/settings").get_data(as_text=True)
    claude = next(p for p in response.get_json()["providers"] if p["id"] == "anthropic")
    assert claude["has_key"] and claude["key_hint"] == "...1234" and claude["model"] == "claude-opus-5-5"
    assert SettingsStore(tmp_path / "cfg").load().api_keys["anthropic"] == key


def test_switching_provider_keeps_other_keys(app_client, tmp_path):
    app_client.post("/api/settings", json={"provider": "deepseek", "api_key": "sk-deepseek-abcdefgh"})
    app_client.post("/api/settings", json={"provider": "ollama"})
    saved = SettingsStore(tmp_path / "cfg").load()
    assert saved.provider == "ollama" and saved.api_keys["deepseek"] == "sk-deepseek-abcdefgh"
    # Switching back needs no new key.
    assert app_client.post("/api/settings", json={"provider": "deepseek"}).status_code == 200


def test_openai_needs_a_model(app_client):
    response = app_client.post("/api/settings", json={"provider": "openai", "api_key": "sk-openai-12345678"})
    assert response.status_code == 400
    assert "model" in response.get_json()["error"]


def test_unknown_provider_rejected(app_client):
    assert app_client.post("/api/settings", json={"provider": "skynet"}).status_code == 400


def test_cross_origin_posts_are_blocked(app_client):
    response = app_client.post("/api/settings", json={"provider": "ollama"}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    same = app_client.post("/api/settings", json={"provider": "ollama"}, headers={"Origin": "http://localhost"})
    assert same.status_code == 200


def test_trusted_hosts_block_dns_rebinding(settings, retriever, tmp_path):
    from framecoach.server import LOOPBACK_HOSTS

    app = create_app(settings, retriever=retriever, store=SettingsStore(tmp_path), trusted_hosts=LOOPBACK_HOSTS)
    client = app.test_client()
    assert client.get("/api/settings", headers={"Host": "localhost:5000"}).status_code == 200
    assert client.get("/api/settings", headers={"Host": "evil.example"}).status_code == 400


def test_models_endpoint_reports_errors(app_client):
    response = app_client.post("/api/models", json={"provider": "openai"})
    assert response.status_code == 502
    assert "API key" in response.get_json()["error"]
