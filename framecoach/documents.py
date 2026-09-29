"""Turn the raw data files into documents that can be embedded and searched.

Every document carries metadata (character, source, ...) so retrieval can filter
on it, and every document's text starts with the character name so the
embedding itself also knows who it is about.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .characters import BY_NAME, BY_SLUG, Character, character_from_filename, normalize

# all-MiniLM-L6-v2 truncates input after ~256 tokens (roughly 1000 characters).
MAX_CHUNK_CHARS = 800

_MISSING = {"", "-", "--", "n/a"}

# (JSON key, label) in the order they should appear in the document text.
_FRAME_FIELDS = (
    ("startup", "Startup"),
    ("activeframes", "Active"),
    ("recovery", "Recovery"),
    ("totalframes", "Total frames"),
    ("onhit", "On hit"),
    ("onblock", "On block"),
    ("basedamage", "Damage"),
    ("attacktype", "Hits"),
    ("cancellable", "Cancel"),
    ("whichhitbox", "Hitbox"),
    ("notes", "Notes"),
)


@dataclass
class Document:
    id: str
    text: str
    metadata: dict[str, str | int] = field(default_factory=dict)


def _clean(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in _MISSING else text


def _resolve(name: str, fallback_slug: str = "") -> Character | None:
    if name in BY_NAME:
        return BY_NAME[name]
    slug = normalize(name).replace(" ", "")
    return BY_SLUG.get(slug) or BY_SLUG.get(fallback_slug)


def move_to_text(character: str, move: dict) -> str:
    parts = [f"{label}: {value}" for key, label in _FRAME_FIELDS if (value := _clean(move.get(key)))]
    return f"{character} - {_clean(move.get('move')) or 'Unknown move'} (frame data)\n" + "\n".join(parts)


def load_framedata(framedata_dir: Path) -> Iterator[Document]:
    for path in sorted(framedata_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "moves" not in data:
            continue  # e.g. characters_stats.json
        char = _resolve(data.get("character", ""), path.stem)
        name = char.name if char else data.get("character", path.stem)
        slug = char.slug if char else path.stem
        for index, move in enumerate(data["moves"]):
            yield Document(
                id=f"framedata:{slug}:{index}",
                text=move_to_text(name, move),
                metadata={
                    "character": name,
                    "source": "framedata",
                    "move": _clean(move.get("move")) or "Unknown move",
                    "file": path.name,
                },
            )


def load_stats(stats_file: Path) -> Iterator[Document]:
    if not stats_file.exists():
        return
    stats = json.loads(stats_file.read_text(encoding="utf-8"))
    for raw_name, values in stats.items():
        char = _resolve(raw_name)
        name = char.name if char else raw_name
        lines = [f"{key}: {value}" for key, value in values.items() if _clean(value)]
        yield Document(
            id=f"stats:{char.slug if char else normalize(raw_name)}",
            text=f"{name} - character stats\n" + "\n".join(lines),
            metadata={"character": name, "source": "stats", "file": stats_file.name},
        )


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    """Split a paragraph that is too long, preferring sentence boundaries."""
    pieces: list[str] = []
    current = ""
    # Fall back to words for transcripts without punctuation.
    units = re.split(r"(?<=[.!?])\s+", paragraph)
    if any(len(u) > max_chars for u in units):
        units = paragraph.split()
    for unit in units:
        if current and len(current) + len(unit) + 1 > max_chars:
            pieces.append(current)
            current = unit
        else:
            current = f"{current} {unit}" if current else unit
    if current:
        pieces.append(current)
    return pieces


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Group paragraphs into chunks of at most ``max_chars`` characters."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        for piece in _split_long(paragraph, max_chars) if len(paragraph) > max_chars else [paragraph]:
            if current and len(current) + len(piece) + 2 > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


def load_guides(guides_dir: Path, max_chars: int = MAX_CHUNK_CHARS) -> Iterator[Document]:
    for path in sorted(guides_dir.glob("*.txt")):
        char = character_from_filename(path.name)
        if char is None:
            print(f"Skipping {path.name}: could not tell which character it is about")
            continue
        for index, chunk in enumerate(chunk_text(path.read_text(encoding="utf-8"), max_chars)):
            yield Document(
                id=f"guide:{path.stem}:{index}",
                text=f"{char.name} guide ({path.stem})\n{chunk}",
                metadata={"character": char.name, "source": "guide", "file": path.name},
            )


def load_all(framedata_dir: Path, stats_file: Path, guides_dir: Path) -> list[Document]:
    return [*load_framedata(framedata_dir), *load_stats(stats_file), *load_guides(guides_dir)]
