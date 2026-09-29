"""Flask web app: chat UI + JSON/streaming API."""

from __future__ import annotations

import json
from collections.abc import Iterator
from urllib.parse import urlsplit

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from .characters import ROSTER
from .config import Settings
from .llm import PROVIDERS, ChatModel, LLMError, chat, list_models, make_client
from .rag import Retriever, build_messages
from .store import IndexMissingError, SentenceTransformerEmbedder, open_collection
from .user_settings import SettingsStore

MAX_QUESTION_CHARS = 500
LOOPBACK_HOSTS = ["localhost", "127.0.0.1", "[::1]", "::1"]


def create_app(
    settings: Settings | None = None,
    retriever: Retriever | None = None,
    llm: ChatModel | None = None,
    store: SettingsStore | None = None,
    trusted_hosts: list[str] | None = None,
) -> Flask:
    """``llm`` pins one model (used by tests); normally the model comes from the user's saved settings."""
    settings = settings or Settings()
    store = store or SettingsStore()
    app = Flask(__name__)
    if trusted_hosts:
        # Blocks DNS-rebinding: a random website can't pretend to be localhost and use your API keys.
        app.config["TRUSTED_HOSTS"] = trusted_hosts
    state: dict[str, Retriever] = {"retriever": retriever} if retriever else {}

    def get_retriever() -> Retriever:
        # Opened lazily so the page loads even before the index is built.
        if "retriever" not in state:
            state["retriever"] = Retriever(
                open_collection(settings), SentenceTransformerEmbedder(settings.embed_model), settings
            )
        return state["retriever"]

    def current_llm() -> ChatModel:
        if llm is not None:
            return llm
        user = store.load()
        if not user.configured:
            raise LLMError("Choose a model first: open Settings (the gear icon).")
        return make_client(
            user.provider,
            user.model_for(user.provider),
            user.key_for(user.provider),
            settings.ollama_url,
            settings.ollama_timeout,
        )

    def error(message: str, status: int) -> tuple[Response, int]:
        return jsonify({"error": message}), status

    @app.before_request
    def same_origin_only():
        # Other websites open in your browser must not be able to change settings or spend your API credit.
        origin = request.headers.get("Origin")
        if request.method != "GET" and origin and urlsplit(origin).netloc != request.host:
            return error("Cross-origin requests are not allowed.", 403)
        return None

    @app.get("/")
    def index():
        return render_template("index.html", characters=[c.name for c in ROSTER])

    @app.get("/api/health")
    def health():
        user = store.load()
        model = user.model_for(user.provider) if user.configured else None
        return jsonify({"status": "ok", "provider": user.provider or None, "model": model})

    @app.get("/api/characters")
    def characters():
        return jsonify([c.name for c in ROSTER])

    @app.get("/api/settings")
    def get_settings():
        return jsonify(store.load().public())

    @app.post("/api/settings")
    def save_settings():
        data = request.get_json(silent=True) or {}
        provider = data.get("provider")
        if provider not in PROVIDERS:
            return error("Pick a provider.", 400)
        model = str(data.get("model") or "").strip()
        api_key = str(data.get("api_key") or "").strip()
        if len(model) > 200 or len(api_key) > 500:
            return error("That value is too long.", 400)

        user = store.load()
        if data.get("remove_key"):
            user.api_keys.pop(provider, None)
        if api_key:
            user.api_keys[provider] = api_key
        if model:
            user.models[provider] = model
        info = PROVIDERS[provider]
        if info.needs_key and not user.key_for(provider):
            return error(f"Enter an API key for {info.label}.", 400)
        if not user.model_for(provider):
            return error("Pick a model.", 400)
        user.provider = provider
        store.save(user)
        return jsonify(user.public())

    @app.post("/api/models")
    def models():
        data = request.get_json(silent=True) or {}
        provider = data.get("provider")
        if provider not in PROVIDERS:
            return error("Pick a provider.", 400)
        api_key = str(data.get("api_key") or "").strip() or store.load().key_for(provider)
        try:
            return jsonify({"models": list_models(provider, api_key, settings.ollama_url)})
        except LLMError as exc:
            return error(str(exc), 502)

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
            model = current_llm()
        except LLMError as exc:
            return error(str(exc), 400)
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
                answer = chat(model, messages)
            except LLMError as exc:
                return error(str(exc), 502)
            return jsonify({"answer": answer, "characters": names, "sources": sources})

        def events() -> Iterator[str]:
            yield json.dumps({"type": "meta", "characters": names, "sources": sources}) + "\n"
            try:
                for text in model.stream_chat(messages):
                    yield json.dumps({"type": "token", "text": text}) + "\n"
            except LLMError as exc:
                yield json.dumps({"type": "error", "error": str(exc)}) + "\n"
                return
            yield json.dumps({"type": "done"}) + "\n"

        return Response(stream_with_context(events()), mimetype="application/x-ndjson")

    return app
