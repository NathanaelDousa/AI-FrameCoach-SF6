"""Runtime settings, overridable through environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: _env_path("FRAMECOACH_DATA_DIR", PROJECT_ROOT / "data"))
    db_dir: Path = field(default_factory=lambda: _env_path("FRAMECOACH_DB_DIR", PROJECT_ROOT / "chroma"))
    collection: str = field(default_factory=lambda: os.environ.get("FRAMECOACH_COLLECTION", "sf6"))
    embed_model: str = field(default_factory=lambda: os.environ.get("FRAMECOACH_EMBED_MODEL", "all-MiniLM-L6-v2"))
    ollama_url: str = field(default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/"))
    rewrite_model: str = field(default_factory=lambda: os.environ.get("FRAMECOACH_REWRITE_MODEL", "llama3"))
    ollama_timeout: float = field(default_factory=lambda: float(os.environ.get("FRAMECOACH_OLLAMA_TIMEOUT", "120")))
    framedata_results: int = field(default_factory=lambda: int(os.environ.get("FRAMECOACH_FRAMEDATA_K", "8")))
    guide_results: int = field(default_factory=lambda: int(os.environ.get("FRAMECOACH_GUIDE_K", "4")))

    @property
    def framedata_dir(self) -> Path:
        return self.data_dir / "framedata"

    @property
    def guides_dir(self) -> Path:
        return self.data_dir / "guides"

    @property
    def transcripts_dir(self) -> Path:
        return self.data_dir / "transcripts"

    @property
    def stats_file(self) -> Path:
        return self.framedata_dir / "characters_stats.json"
