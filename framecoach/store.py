"""Embedding model and ChromaDB access."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import chromadb

from .config import Settings


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """Loads the sentence-transformers model on first use (it takes a few seconds)."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model.encode(list(texts), normalize_embeddings=True).tolist()


class IndexMissingError(RuntimeError):
    pass


def client(settings: Settings) -> chromadb.ClientAPI:
    settings.db_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(settings.db_dir))


def open_collection(settings: Settings) -> chromadb.Collection:
    try:
        return client(settings).get_collection(settings.collection)
    except Exception as exc:  # chromadb raises different types across versions
        raise IndexMissingError(
            f"No search index found in {settings.db_dir}. Build it first with: python -m framecoach ingest"
        ) from exc


def recreate_collection(settings: Settings) -> chromadb.Collection:
    db = client(settings)
    if settings.collection in {c.name for c in db.list_collections()}:
        db.delete_collection(settings.collection)
    return db.create_collection(settings.collection, configuration={"hnsw": {"space": "cosine"}})
