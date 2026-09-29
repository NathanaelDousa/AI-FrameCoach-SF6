"""The SF6 roster and helpers to recognise characters in free text."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Character:
    name: str  # Display name, matches the "character" field in the frame data JSON
    slug: str  # Used for file names and ultimateframedata.com URLs
    aliases: tuple[str, ...] = ()


ROSTER: tuple[Character, ...] = (
    Character("A.K.I.", "aki", ("aki",)),
    Character("Akuma", "akuma", ("gouki",)),
    Character("Blanka", "blanka"),
    Character("Cammy", "cammy"),
    Character("Chun Li", "chunli", ("chun", "chunli")),
    Character("Dee Jay", "deejay", ("deejay", "dj")),
    Character("Dhalsim", "dhalsim", ("sim",)),
    Character("E. Honda", "ehonda", ("honda", "ehonda")),
    Character("Ed", "ed"),
    Character("Elena", "elena"),
    Character("Guile", "guile"),
    Character("Jamie", "jamie"),
    Character("JP", "jp"),
    Character("Juri", "juri"),
    Character("Ken", "ken"),
    Character("Kimberly", "kimberly", ("kim",)),
    Character("Lily", "lily"),
    Character("Luke", "luke"),
    Character("M. Bison", "mbison", ("bison", "mbison", "dictator")),
    Character("Mai", "mai"),
    Character("Manon", "manon"),
    Character("Marisa", "marisa"),
    Character("Rashid", "rashid"),
    Character("Ryu", "ryu"),
    Character("Terry", "terry"),
    Character("Zangief", "zangief", ("gief",)),
)

BY_SLUG = {c.slug: c for c in ROSTER}
BY_NAME = {c.name: c for c in ROSTER}


def normalize(text: str) -> str:
    """Lowercase, drop dots and turn hyphens/underscores into spaces ("Chun-Li" -> "chun li")."""
    text = text.lower().replace(".", "")
    text = re.sub(r"[-_]", " ", text)
    return re.sub(r"\s+", " ", text)


def _build_patterns() -> list[tuple[re.Pattern[str], Character]]:
    patterns = []
    for char in ROSTER:
        terms = {normalize(char.name), char.slug, *char.aliases}
        alternatives = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
        patterns.append((re.compile(rf"(?<![a-z0-9])(?:{alternatives})(?![a-z0-9])"), char))
    return patterns


_PATTERNS = _build_patterns()


def detect_characters(text: str) -> list[Character]:
    """Return the characters mentioned in ``text``, in order of first appearance.

    Matching is on whole words only, so "Ed" does not match "punished".
    """
    norm = normalize(text)
    found: list[tuple[int, Character]] = []
    for pattern, char in _PATTERNS:
        match = pattern.search(norm)
        if match:
            found.append((match.start(), char))
    return [char for _, char in sorted(found, key=lambda item: item[0])]


def character_from_filename(filename: str) -> Character | None:
    """Guess the character from a guide file name like "chunli oki setup_structured.txt"."""
    match = re.match(r"[a-z]+", filename.lower())
    return BY_SLUG.get(match.group(0)) if match else None
