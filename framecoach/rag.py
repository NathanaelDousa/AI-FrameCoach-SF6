"""Retrieval and prompt construction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .characters import BY_NAME, detect_characters
from .config import Settings
from .store import Embedder

SYSTEM_PROMPT = """You are a world-class Street Fighter 6 coach. You explain frame data, setups and \
strategy clearly and concisely to competitive players.

Rules:
- Base your answer on the provided context. Quote frame data numbers exactly as they appear.
- If the context does not contain the answer, say so plainly instead of guessing.
- Frame advantage: positive numbers mean the attacker acts first; a move that is -4 or worse on \
block can be punished by a 4-frame normal.
- Be direct. No filler, no "in my opinion". Use short paragraphs or bullet points."""

_STRENGTH = {"l": "light", "m": "medium", "h": "heavy"}
_BUTTON = {"p": "punch", "k": "kick"}
_STANCE = {
    "2": "crouching",
    "5": "standing",
    "8": "jumping",
    "j": "jumping",
    "cr": "crouching",
    "c": "crouching",
    "st": "standing",
    "s": "standing",
}
_NOTATION = re.compile(r"(?<![a-z0-9])(cr\.?\s?|st\.?\s?|c\.|s\.|j\.?|[258])?([lmh])([pk])(?![a-z0-9])", re.IGNORECASE)


def expand_notation(question: str) -> str:
    """Append plain-English move names for notation like "2HP" or "cr.MK".

    The frame data spells moves out ("Crouching Heavy Punch"), so this helps the
    embedding match what players actually type.
    """
    expansions = []
    for stance, strength, button in _NOTATION.findall(question):
        stance = re.sub(r"[^a-z0-9]", "", stance.lower())
        words = [_STANCE.get(stance, ""), _STRENGTH[strength.lower()], _BUTTON[button.lower()]]
        expansions.append(" ".join(w for w in words if w).title())
    if not expansions:
        return question
    return f"{question} ({', '.join(dict.fromkeys(expansions))})"


@dataclass
class Hit:
    text: str
    character: str
    source: str
    file: str
    move: str | None
    distance: float

    def label(self) -> str:
        if self.source == "framedata":
            return f"{self.character} - {self.move} (frame data)"
        if self.source == "stats":
            return f"{self.character} - character stats"
        return f"{self.character} - {self.file}"


def _character_filter(names: list[str]) -> dict | None:
    if not names:
        return None
    return {"character": names[0]} if len(names) == 1 else {"character": {"$in": names}}


def _and(*clauses: dict | None) -> dict:
    present = [c for c in clauses if c]
    return present[0] if len(present) == 1 else {"$and": present}


class Retriever:
    def __init__(self, collection, embedder: Embedder, settings: Settings):
        self.collection = collection
        self.embedder = embedder
        self.settings = settings

    def resolve_characters(self, question: str, character: str | None = None) -> list[str]:
        """An explicitly chosen character wins; otherwise detect names in the question."""
        if character and character in BY_NAME:
            names = [character]
            names += [c.name for c in detect_characters(question) if c.name != character]
            return names
        return [c.name for c in detect_characters(question)]

    def retrieve(self, question: str, characters: list[str]) -> list[Hit]:
        expanded = expand_notation(question)
        embedding = self.embedder.embed([expanded])[0]
        char_filter = _character_filter(characters)
        exact = self._exact_moves(expanded, char_filter) if characters else []
        hits = self._query(
            embedding, _and(char_filter, {"source": {"$in": ["framedata", "stats"]}}), self.settings.framedata_results
        )
        hits += self._query(embedding, _and(char_filter, {"source": "guide"}), self.settings.guide_results)
        seen = {h.text for h in exact}
        return exact + sorted((h for h in hits if h.text not in seen), key=lambda h: h.distance)

    def _exact_moves(self, question: str, char_filter: dict) -> list[Hit]:
        """Frame data rows whose move name appears literally in the question.

        Embeddings struggle to tell "Crouching Light Punch" from "Crouching Heavy Punch",
        so a move that is named outright is always included.
        """
        result = self.collection.get(
            where=_and(char_filter, {"source": "framedata"}), include=["documents", "metadatas"]
        )
        text = question.lower()
        matches = [
            (doc, meta)
            for doc, meta in zip(result["documents"], result["metadatas"], strict=True)
            if re.search(rf"(?<![a-z]){re.escape(str(meta.get('move', '')).lower())}(?![a-z])", text)
        ]
        # "Crouching Heavy Punch" should not also pull in a move called just "Heavy Punch".
        names = [str(m["move"]).lower() for _, m in matches]
        return [
            self._hit(doc, meta, 0.0)
            for doc, meta in matches
            if not any(n != str(meta["move"]).lower() and str(meta["move"]).lower() in n for n in names)
        ]

    def _query(self, embedding: list[float], where: dict, k: int) -> list[Hit]:
        if k <= 0:
            return []
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return [
            self._hit(doc, meta, dist)
            for doc, meta, dist in zip(
                result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
            )
        ]

    @staticmethod
    def _hit(doc: str, meta: dict, distance: float) -> Hit:
        return Hit(
            text=doc,
            character=str(meta.get("character", "")),
            source=str(meta.get("source", "")),
            file=str(meta.get("file", "")),
            move=meta.get("move"),
            distance=float(distance),
        )


def build_messages(question: str, hits: list[Hit]) -> list[dict[str, str]]:
    if hits:
        context = "\n\n".join(f"[{i}] {hit.text}" for i, hit in enumerate(hits, start=1))
    else:
        context = "(no matching data found)"
    user = f"Context:\n{context}\n\nQuestion: {question}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]
