"""Build the vector index from the frame data, stats, guides and patch notes."""

from __future__ import annotations

import hashlib
from collections import Counter

from .config import Settings
from .documents import load_all
from .store import Embedder, SentenceTransformerEmbedder, recreate_collection

BATCH_SIZE = 256
FINGERPRINT_FILE = "data-fingerprint.txt"


def data_fingerprint(settings: Settings) -> str:
    """A hash of every data file, so we can tell when the index is out of date."""
    digest = hashlib.sha256(settings.embed_model.encode())
    for folder in (settings.framedata_dir, settings.guides_dir, settings.patches_dir):
        for path in sorted(folder.glob("*")) if folder.exists() else []:
            if path.is_file():
                digest.update(path.name.encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def index_is_current(settings: Settings) -> bool:
    try:
        return (settings.db_dir / FINGERPRINT_FILE).read_text().strip() == data_fingerprint(settings)
    except FileNotFoundError:
        return False


def build_index(settings: Settings, embedder: Embedder | None = None) -> Counter:
    """Rebuild the collection from scratch and return the number of documents per source."""
    embedder = embedder or SentenceTransformerEmbedder(settings.embed_model)
    docs = load_all(settings.framedata_dir, settings.stats_file, settings.guides_dir, settings.patches_dir)
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
    (settings.db_dir / FINGERPRINT_FILE).write_text(data_fingerprint(settings))
    return Counter(str(d.metadata["source"]) for d in docs)
