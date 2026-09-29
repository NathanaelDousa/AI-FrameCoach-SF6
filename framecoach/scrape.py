"""Scrape frame data and character stats from ultimateframedata.com."""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

from .characters import ROSTER

BASE_URL = "https://ultimateframedata.com/sf6"
HEADERS = {"User-Agent": "AI-FrameCoach-SF6 (+https://github.com/NathanaelDousa/AI-FrameCoach-SF6)"}

MOVE_FIELDS = (
    "startup",
    "totalframes",
    "basedamage",
    "attacktype",
    "cancellable",
    "notes",
    "whichhitbox",
    "onhit",
    "onblock",
    "activeframes",
    "recovery",
)

# id of the table container on the stats page -> readable name
STAT_TABLES = {
    "walkspeed": "Walk Speed",
    "dashspeed": "Dash Speed",
    "dashdistance": "Dash Distance",
    "health": "Health",
    "prejump": "Prejump",
}


def _fetch(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _text(container: Tag, class_name: str) -> str:
    tag = container.find("div", class_=class_name)
    return tag.get_text(strip=True) if tag else ""


def parse_character_page(soup: BeautifulSoup, fallback_name: str) -> dict:
    title = soup.find("h1")
    content = soup.find(id="contentcontainer")
    if content is None:
        raise ValueError("contentcontainer not found - the page layout may have changed")
    moves = [
        {"move": _text(mc, "movename"), **{name: _text(mc, name) for name in MOVE_FIELDS}}
        for moves_div in content.find_all("div", class_="moves")
        for mc in moves_div.find_all("div", class_="movecontainer")
    ]
    return {"character": title.get_text(strip=True) if title else fallback_name, "moves": moves}


def parse_stats_page(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    stats: dict[str, dict[str, str]] = {}
    for table_id, label in STAT_TABLES.items():
        container = soup.find(id=table_id)
        table = container.find("table") if container else None
        if table is None:
            print(f"  stats table '{table_id}' not found, skipping")
            continue
        for row in table.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 2:
                stats.setdefault(cols[0].get_text(strip=True), {})[label] = cols[1].get_text(strip=True)
    return stats


def scrape_characters(out_dir: Path, slugs: list[str] | None = None, delay: float = 1.0) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug in slugs or [c.slug for c in ROSTER]:
        try:
            data = parse_character_page(_fetch(f"{BASE_URL}/{slug}"), slug)
        except (requests.RequestException, ValueError) as exc:
            print(f"x {slug}: {exc}")
            continue
        if not data["moves"]:
            print(f"x {slug}: no moves found")
            continue
        (out_dir / f"{slug}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ok {slug}: {len(data['moves'])} moves")
        time.sleep(delay)  # be polite to the site


def scrape_stats(out_file: Path) -> None:
    stats = parse_stats_page(_fetch(f"{BASE_URL}/stats"))
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ok stats for {len(stats)} characters -> {out_file}")
