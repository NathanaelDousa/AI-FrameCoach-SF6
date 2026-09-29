import hashlib
import math
import re
import shutil
from pathlib import Path

import pytest

from framecoach.config import Settings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class HashEmbedder:
    """Deterministic bag-of-words embedder so tests don't need to download a model."""

    dims = 512

    def embed(self, texts):
        vectors = []
        for text in texts:
            vec = [0.0] * self.dims
            for word in re.findall(r"[a-z0-9+-]+", text.lower()):
                vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dims] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


@pytest.fixture
def embedder():
    return HashEmbedder()


@pytest.fixture
def small_data(tmp_path):
    """A copy of a few real characters' data."""
    data = tmp_path / "data"
    (data / "framedata").mkdir(parents=True)
    (data / "guides").mkdir()
    for slug in ("ryu", "ken", "zangief", "chunli"):
        shutil.copy(DATA_DIR / "framedata" / f"{slug}.json", data / "framedata")
    shutil.copy(DATA_DIR / "framedata" / "characters_stats.json", data / "framedata")
    for name in ("Zangief.txt", "ryu2.txt", "Ken OKI.txt"):
        shutil.copy(DATA_DIR / "guides" / name, data / "guides")
    (data / "patches").mkdir()
    for version in ("20260803", "20260317", "202506"):
        shutil.copy(DATA_DIR / "patches" / f"{version}.json", data / "patches")
    return data


@pytest.fixture
def settings(tmp_path, small_data):
    return Settings(data_dir=small_data, db_dir=tmp_path / "chroma", framedata_results=5, guide_results=3)
