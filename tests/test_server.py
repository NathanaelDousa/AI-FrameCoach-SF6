import json

import pytest

from framecoach.ingest import build_index
from framecoach.llm import OllamaError
from framecoach.rag import Retriever
from framecoach.server import create_app
from framecoach.store import open_collection


class FakeLLM:
    def __init__(self, fail=False):
        self.fail = fail
        self.messages = None

    def stream_chat(self, messages):
        self.messages = messages
        if self.fail:
            raise OllamaError("Could not reach Ollama")
        yield "Use "
        yield "**SPD**."

    def chat(self, messages):
        return "".join(self.stream_chat(messages))


@pytest.fixture
def retriever(settings, embedder):
    build_index(settings, embedder)
    return Retriever(open_collection(settings), embedder, settings)


def make_client(settings, retriever, llm):
    return create_app(settings, retriever=retriever, llm=llm).test_client()


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
