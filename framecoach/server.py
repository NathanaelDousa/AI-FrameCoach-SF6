"""Flask web app: chat UI + JSON/streaming API."""

from __future__ import annotations

import json
from collections.abc import Iterator

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from .characters import ROSTER
from .config import Settings
from .llm import OllamaClient, OllamaError
from .rag import Retriever, build_messages
from .store import IndexMissingError, SentenceTransformerEmbedder, open_collection

MAX_QUESTION_CHARS = 500


def create_app(
    settings: Settings | None = None, retriever: Retriever | None = None, llm: OllamaClient | None = None
) -> Flask:
    settings = settings or Settings()
    app = Flask(__name__)
    llm = llm or OllamaClient(settings.ollama_url, settings.model, settings.ollama_timeout)
    state: dict[str, Retriever] = {"retriever": retriever} if retriever else {}

    def get_retriever() -> Retriever:
        # Opened lazily so the page loads even before the index is built.
        if "retriever" not in state:
            state["retriever"] = Retriever(
                open_collection(settings), SentenceTransformerEmbedder(settings.embed_model), settings
            )
        return state["retriever"]

    def error(message: str, status: int) -> tuple[Response, int]:
        return jsonify({"error": message}), status

    @app.get("/")
    def index():
        return render_template("index.html", characters=[c.name for c in ROSTER])

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "model": settings.model})

    @app.get("/api/characters")
    def characters():
        return jsonify([c.name for c in ROSTER])

    @app.post("/api/ask")
    def ask():
        data = request.get_json(silent=True) or {}
        question = str(data.get("question", "")).strip()
        if not question:
            return error("Please enter a question.", 400)
        if len(question) > MAX_QUESTION_CHARS:
            return error(f"Questions are limited to {MAX_QUESTION_CHARS} characters.", 400)
        character = data.get("character") or None

        try:
            retriever = get_retriever()
            names = retriever.resolve_characters(question, character)
            hits = retriever.retrieve(question, names)
        except IndexMissingError as exc:
            return error(str(exc), 503)

        messages = build_messages(question, hits)
        sources = [{"label": h.label(), "text": h.text} for h in hits]

        if not data.get("stream"):
            try:
                answer = llm.chat(messages)
            except OllamaError as exc:
                return error(str(exc), 502)
            return jsonify({"answer": answer, "characters": names, "sources": sources})

        def events() -> Iterator[str]:
            yield json.dumps({"type": "meta", "characters": names, "sources": sources}) + "\n"
            try:
                for text in llm.stream_chat(messages):
                    yield json.dumps({"type": "token", "text": text}) + "\n"
            except OllamaError as exc:
                yield json.dumps({"type": "error", "error": str(exc)}) + "\n"
                return
            yield json.dumps({"type": "done"}) + "\n"

        return Response(stream_with_context(events()), mimetype="application/x-ndjson")

    return app
