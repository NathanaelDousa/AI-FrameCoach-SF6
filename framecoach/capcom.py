"""Official frame data and patch notes from streetfighter.com (Capcom).

- Frame data: https://www.streetfighter.com/6/character/<name>/frame (a server-rendered table)
- Patch notes: https://www.streetfighter.com/6/buckler/en/battle_change/<version> (JSON embedded in the page)

Both pages are allowed by the site's robots.txt. Requests are spaced out to be polite.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from .characters import ROSTER, Character

BASE_URL = "https://www.streetfighter.com/6"
# The site rejects requests without a browser-like User-Agent.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0 Safari/537.36 AI-FrameCoach-SF6"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Table columns in order, after the move name column.
FRAME_COLUMNS = (
    "startup",
    "active",
    "recovery",
    "on_hit",
    "on_block",
    "cancel",
    "damage",
    "scaling",
    "drive_gain_hit",
    "drive_loss_block",
    "drive_loss_punish",
    "super_gain",
    "properties",
    "notes",
)

# Controller icons -> numpad notation.
_ICONS = {
    "key-d": "2",
    "key-dr": "3",
    "key-r": "6",
    "key-ur": "9",
    "key-u": "8",
    "key-ul": "7",
    "key-l": "4",
    "key-dl": "1",
    "key-nutral": "5",
    "key-plus": "+",
    "key-or": "or",
    "arrow_3": ">",
    "icon_punch": "P",
    "icon_punch_l": "LP",
    "icon_punch_m": "MP",
    "icon_punch_h": "HP",
    "icon_kick": "K",
    "icon_kick_l": "LK",
    "icon_kick_m": "MK",
    "icon_kick_h": "HK",
}
_BUTTONS = {"P", "K", "LP", "MP", "HP", "LK", "MK", "HK"}
_CATEGORIES = {"調整": "Adjustment", "不具合修正": "Bug fix", "調整・不具合修正": "Adjustment / bug fix"}


class NotPublishedError(ValueError):
    """The page exists but has no frame data yet (e.g. a character that isn't released)."""


def _fetch(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# --- Frame data ---------------------------------------------------------------


def render_input(tokens: list[str]) -> str:
    """["2", "3", "6", "+", "P", "P"] -> "236PP"; ["2", "+", "LP"] -> "2LP"; ["LP", "LK"] -> "LP+LK"."""
    parts: list[str] = []
    buttons: list[str] = []

    def flush() -> None:
        if buttons:
            same = len(set(buttons)) == 1 and buttons[0] in ("P", "K")
            parts.append("".join(buttons) if same else "+".join(buttons))
            buttons.clear()

    for token in tokens:
        if token in _BUTTONS:
            buttons.append(token)
            continue
        flush()
        if token == "+":
            continue
        if token.isdigit() and parts and parts[-1].isdigit():
            parts[-1] += token  # consecutive directions form one motion: 236
        else:
            parts.append(token)
    flush()
    text = " ".join(parts)
    text = re.sub(r"(\d) (?=(?:[LMH]?[PK]))", r"\1", text)  # "236 P" -> "236P"
    return re.sub(r"\( ", "(", re.sub(r" \)", ")", text))


def _input_tokens(cell: Tag) -> list[str]:
    classic = cell.find("p")
    if classic is None:
        return []
    tokens: list[str] = []
    for node in classic.descendants:
        if isinstance(node, Tag) and node.name == "img":
            name = Path(node.get("src", "")).stem
            if name in _ICONS:
                tokens.append(_ICONS[name])
        elif isinstance(node, NavigableString):
            text = _clean(str(node))
            # The strength letter printed next to each button icon is redundant.
            if text and text not in ("L", "M", "H"):
                tokens.append(text)
    return tokens


def _cell_text(cell: Tag) -> str:
    return " / ".join(_clean(s) for s in cell.stripped_strings)


def parse_frame_page(html: str, name: str) -> list[dict]:
    """Parse the frame data table into one dict per move."""
    table = BeautifulSoup(html, "html.parser").find("table")
    if table is None:
        raise NotPublishedError(f"no frame data table for {name}")
    moves: list[dict] = []
    section = ""
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) == 1:
            section = _clean(cells[0].get_text(" "))
            continue
        if len(cells) != 1 + len(FRAME_COLUMNS):
            continue  # header rows
        name_cell = cells[0].find("span")
        move = {
            "section": section,
            "move": _clean(name_cell.get_text(" ") if name_cell else cells[0].get_text(" ")),
            "input": render_input(_input_tokens(cells[0])),
        }
        for key, cell in zip(FRAME_COLUMNS, cells[1:], strict=True):
            move[key] = _cell_text(cell)
        moves.append(move)
    if not moves:
        raise ValueError(f"no moves found for {name}")
    return moves


def scrape_frame_data(out_dir: Path, characters: list[Character], patch: str = "", delay: float = 1.5) -> list[str]:
    """Download frame data for each character. Returns the names that failed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    failed, unpublished = [], []
    for char in characters:
        url = f"{BASE_URL}/character/{char.capcom_url_name}/frame"
        try:
            moves = parse_frame_page(_fetch(url), char.name)
        except NotPublishedError:
            print(f"- {char.name}: no frame data published yet, skipping")
            unpublished.append(char.name)
            continue
        except (requests.RequestException, ValueError) as exc:
            print(f"x {char.name}: {exc}")
            failed.append(char.name)
            continue
        finally:
            time.sleep(delay)
        data = {"character": char.name, "source": "capcom", "url": url, "patch": patch, "moves": moves}
        (out_dir / f"{char.slug}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(f"ok {char.name}: {len(moves)} moves")
    if characters and len(unpublished) == len(characters) > 1:
        # Every page empty means the site changed, not that nobody is released.
        return unpublished
    return failed


# --- Patch notes ------------------------------------------------------------


def _next_data(html: str) -> dict:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise ValueError("page data not found - the page layout may have changed")
    return json.loads(match.group(1))


def _html_to_text(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text or "")
    text = re.sub(r"<[^>]+>", "", text)
    return "\n".join(_clean(line) for line in text.splitlines()).strip()


def _version_date(version_id: str) -> str:
    """ "20260803" -> "2026-08-03"; "202506" -> "2025-06"."""
    if len(version_id) == 8:
        return f"{version_id[:4]}-{version_id[4:6]}-{version_id[6:]}"
    return f"{version_id[:4]}-{version_id[4:6]}"


def _version_title(version_id: str, fallback: str) -> str:
    """Build the title from the version id; Capcom's own titles contain typos (20250205 is "02.05.2024")."""
    if len(version_id) == 8 and version_id.isdigit():
        return f"{version_id[4:6]}.{version_id[6:]}.{version_id[:4]} update"
    return fallback


def parse_patch_page(html: str) -> dict:
    """Turn one battle change page into {version, title, date, overview, general, characters}."""
    adjust = _next_data(html)["props"]["pageProps"]["adjust"]
    by_patch_id = {c.patch_name: c.name for c in ROSTER}

    def changes(details: list[dict]) -> list[dict]:
        return [
            {
                "move": _clean(_html_to_text(detail.get("title", ""))),
                "type": _CATEGORIES.get(body.get("category", ""), "Adjustment"),
                "change": _html_to_text(body.get("text", "")),
            }
            for detail in details
            for body in detail.get("body", [])
        ]

    concepts = {p["title"]: _html_to_text(p.get("text", "")) for p in adjust.get("policy", [])}
    characters = {}
    for fighter in adjust.get("fighter", []):
        fid = fighter.get("fighter_tool_name") or fighter.get("fighter_id", "").lower()
        name = by_patch_id.get(fid, fighter.get("fighter_id", fid))
        characters[name] = {"concept": concepts.get(fid, ""), "changes": changes(fighter.get("detail", []))}

    version = adjust.get("current_version", "")
    return {
        "version": version,
        "title": _version_title(version, adjust.get("title", "")),
        "date": _version_date(version),
        "overview": concepts.get("Overall Concept", ""),
        "general": changes(adjust.get("common", [])),
        "characters": characters,
    }


def list_patch_versions() -> list[str]:
    adjust = _next_data(_fetch(f"{BASE_URL}/buckler/en/battle_change"))["props"]["pageProps"]["adjust"]
    return [v["id"] for v in adjust.get("versions", [])]


def scrape_patches(out_dir: Path, only_new: bool = True, delay: float = 1.5) -> list[str]:
    """Download patch notes. Existing versions are skipped unless only_new=False. Returns new versions."""
    out_dir.mkdir(parents=True, exist_ok=True)
    added = []
    for version in list_patch_versions():
        path = out_dir / f"{version}.json"
        if only_new and path.exists():
            continue
        try:
            patch = parse_patch_page(_fetch(f"{BASE_URL}/buckler/en/battle_change/{version}"))
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"x patch {version}: {exc}")
            continue
        path.write_text(json.dumps(patch, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(f"ok patch {patch['title']}: {len(patch['characters'])} characters changed")
        added.append(version)
        time.sleep(delay)
    return added


def latest_patch_title(patches_dir: Path) -> str:
    files = sorted(patches_dir.glob("*.json"))
    if not files:
        return ""
    return json.loads(files[-1].read_text(encoding="utf-8")).get("title", "")
