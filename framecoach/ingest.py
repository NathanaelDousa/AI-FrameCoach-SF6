"""Build the vector index from the frame data, character stats and guides."""

from __future__ import annotations

from collections import Counter

from .config import Settings
from .documents import load_all
from .store import Embedder, SentenceTransformerEmbedder, recreate_collection

BATCH_SIZE = 256


def build_index(settings: Settings, embedder: Embedder | None = None) -> Counter:
    """Rebuild the collection from scratch and return the number of documents per source."""
    embedder = embedder or SentenceTransformerEmbedder(settings.embed_model)
    docs = load_all(settings.framedata_dir, settings.stats_file, settings.guides_dir)
    if not docs:
        raise SystemExit(f"No data found in {settings.data_dir}")

    collection = recreate_collection(settings)
    for start in range(0, len(docs), BATCH_SIZE):
        batch = docs[start : start + BATCH_SIZE]
        texts = [d.text for d in batch]
        collection.add(
            ids=[d.id for d in batch],
            documents=texts,
            metadatas=[d.metadata for d in batch],
            embeddings=embedder.embed(texts),
        )
    return Counter(str(d.metadata["source"]) for d in docs)
