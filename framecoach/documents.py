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


def capcom_move_to_text(character: str, move: dict, patch: str = "") -> str:
    """Official Capcom frame data, e.g. "Ryu - L Hadoken (236LP) [Special Moves]"."""

    def get(key: str) -> str:
        return _clean(move.get(key))

    title = f"{character} - {get('move') or 'Unknown move'}"
    if get("input"):
        title += f" ({get('input')})"
    if get("section"):
        title += f" [{get('section')}]"
    title += f" official frame data{f', as of the {patch}' if patch else ''}"

    lines = [
        " | ".join(
            f"{label}: {v}"
            for label, key in (("Startup", "startup"), ("Active", "active"), ("Recovery", "recovery"))
            if (v := get(key))
        ),
        " | ".join(
            f"{label}: {v}" for label, key in (("On hit", "on_hit"), ("On block", "on_block")) if (v := get(key))
        ),
        " | ".join(
            f"{label}: {v}"
            for label, key in (("Cancel", "cancel"), ("Damage", "damage"), ("Scaling", "scaling"))
            if (v := get(key))
        ),
    ]
    drive = [
        f"{v} {label}"
        for label, key in (
            ("on hit", "drive_gain_hit"),
            ("on block", "drive_loss_block"),
            ("on punish counter", "drive_loss_punish"),
        )
        if (v := get(key))
    ]
    if drive:
        lines.append("Drive gauge: " + ", ".join(drive))
    if get("super_gain"):
        lines.append(f"Super gauge gain: {get('super_gain')}")
    if get("properties"):
        lines.append(f"Properties: {get('properties')}")
    if get("notes"):
        lines.append(f"Notes: {get('notes')}")
    return "\n".join([title, *(line for line in lines if line)])


def load_framedata(framedata_dir: Path) -> Iterator[Document]:
    for path in sorted(framedata_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "moves" not in data:
            continue  # e.g. characters_stats.json
        char = _resolve(data.get("character", ""), path.stem)
        name = char.name if char else data.get("character", path.stem)
        slug = char.slug if char else path.stem
        official = data.get("source") == "capcom"
        for index, move in enumerate(data["moves"]):
            metadata = {
                "character": name,
                "source": "framedata",
                "move": _clean(move.get("move")) or "Unknown move",
                "file": path.name,
            }
            if official:
                metadata["input"] = _clean(move.get("input"))
            yield Document(
                id=f"framedata:{slug}:{index}",
                text=capcom_move_to_text(name, move, data.get("patch", "")) if official else move_to_text(name, move),
                metadata=metadata,
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


def _patch_change_lines(changes: list[dict]) -> list[str]:
    return [f"- {c['move']} ({c['type']}): {c['change']}" for c in changes]


def load_patches(patches_dir: Path, max_chars: int = MAX_CHUNK_CHARS) -> Iterator[Document]:
    """One or more documents per character per patch, newest information labelled with its date."""
    if not patches_dir.exists():
        return
    for path in sorted(patches_dir.glob("*.json")):
        patch = json.loads(path.read_text(encoding="utf-8"))
        version, title, date = patch["version"], patch["title"], patch.get("date", "")
        sections = {"All characters": (patch.get("overview", ""), patch.get("general", []))}
        sections.update({name: (c.get("concept", ""), c.get("changes", [])) for name, c in patch["characters"].items()})
        for name, (concept, changes) in sections.items():
            body = "\n\n".join(p for p in (concept, "\n".join(_patch_change_lines(changes))) if p)
            if not body:
                continue
            header = f"{name} - balance changes in the {title} (released {date})"
            for index, chunk in enumerate(chunk_text(body, max_chars)):
                yield Document(
                    id=f"patch:{version}:{normalize(name).replace(' ', '')}:{index}",
                    text=f"{header}\n{chunk}",
                    metadata={
                        "character": name,
                        "source": "patch",
                        "version": version,
                        "date": date,
                        "patch": title,
                        "file": path.name,
                    },
                )


def load_all(
    framedata_dir: Path, stats_file: Path, guides_dir: Path, patches_dir: Path | None = None
) -> list[Document]:
    return [
        *load_framedata(framedata_dir),
        *load_stats(stats_file),
        *load_guides(guides_dir),
        *(load_patches(patches_dir) if patches_dir else []),
    ]
