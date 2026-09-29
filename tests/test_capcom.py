import json

import pytest

from framecoach.capcom import NotPublishedError, parse_frame_page, parse_patch_page, render_input
from framecoach.documents import capcom_move_to_text, load_framedata, load_patches


def icon(name):
    return f'<img alt="" src="/6/assets/images/common/controller/{name}.png"/>'


def row(name, inputs, *values):
    cells = "".join(f"<td>{v}</td>" for v in values)
    return f'<tr><td><span class="frame_arts">{name}</span><p class="frame_classic">{inputs}</p></td>{cells}</tr>'


VALUES = ["4", "4-6", "7", "4", "-1", "C", "300", "Starter scaling 20%", "250", "-500", "-2000", "300", "High"]

FRAME_HTML = f"""
<table>
  <tr><th>Move Name</th><th>Frame</th></tr>
  <tr><td class="frame_heading">Normal Moves</td></tr>
  {
    row(
        "Crouching Light Kick",
        icon("key-d") + icon("key-plus") + icon("icon_kick_l") + "L",
        *VALUES,
        "Can be rapid canceled",
    )
}
  <tr><td class="frame_heading">Special Moves</td></tr>
  {
    row(
        "OD Shoryuken",
        icon("key-r") + icon("key-d") + icon("key-dr") + icon("key-plus") + icon("icon_punch") + icon("icon_punch"),
        *VALUES,
        "<p>Completely invincible from frames 1 - 8.</p><p>Considered airborne.</p>",
    )
}
</table>
"""


def test_parse_frame_page():
    moves = parse_frame_page(FRAME_HTML, "Ryu")
    assert [m["section"] for m in moves] == ["Normal Moves", "Special Moves"]
    low_kick, dp = moves
    assert low_kick["move"] == "Crouching Light Kick" and low_kick["input"] == "2LK"
    assert low_kick["startup"] == "4" and low_kick["on_block"] == "-1" and low_kick["drive_loss_punish"] == "-2000"
    assert dp["input"] == "623PP"
    assert dp["notes"] == "Completely invincible from frames 1 - 8. / Considered airborne."


def test_unreleased_character_page():
    with pytest.raises(NotPublishedError):
        parse_frame_page("<html><body>coming soon</body></html>", "Arjun")


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["2", "3", "6", "+", "LP"], "236LP"),
        (["2", "3", "6", "2", "3", "6", "+", "P"], "236236P"),
        (["HP", ">", "HK"], "HP > HK"),
        (["(When near opponent)", "5", "or", "6", "+", "LP", "LK"], "(When near opponent) 5 or 6LP+LK"),
        (["6", "6", "or", "(", "5", "or", "6", ")", "+", "MP", "MK"], "66 or (5 or 6) MP+MK"),
    ],
)
def test_render_input(tokens, expected):
    assert render_input(tokens) == expected


def patch_page(adjust):
    data = {"props": {"pageProps": {"adjust": adjust}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'


def test_parse_patch_page():
    html = patch_page(
        {
            "title": "02.05.2024 update",  # Capcom's typo; the version id is 2025
            "current_version": "20250205",
            "policy": [
                {"title": "Overall Concept", "text": "Big changes.<br>More fun."},
                {"title": "gouki", "text": "Akuma gets <b>stronger</b>."},
            ],
            "common": [{"title": "Drive Reversal", "body": [{"category": "不具合修正", "text": "Fixed a bug."}]}],
            "fighter": [
                {
                    "fighter_id": "Gouki",
                    "fighter_tool_name": "gouki",
                    "detail": [
                        {"title": "Standing<br>Heavy Punch", "body": [{"category": "調整", "text": "-5 to -4."}]}
                    ],
                }
            ],
        }
    )
    patch = parse_patch_page(html)
    assert patch["version"] == "20250205" and patch["date"] == "2025-02-05"
    assert patch["title"] == "02.05.2025 update"
    assert patch["overview"] == "Big changes.\nMore fun."
    assert patch["general"] == [{"move": "Drive Reversal", "type": "Bug fix", "change": "Fixed a bug."}]
    akuma = patch["characters"]["Akuma"]
    assert akuma["concept"] == "Akuma gets stronger."
    assert akuma["changes"] == [{"move": "Standing Heavy Punch", "type": "Adjustment", "change": "-5 to -4."}]


def test_capcom_move_text():
    move = dict(
        zip(
            ["startup", "active", "recovery", "on_hit", "on_block"],
            ["16", "", "47 total frames", "2", "-5"],
            strict=True,
        )
    )
    text = capcom_move_to_text(
        "Ryu", {"move": "L Hadoken", "input": "236LP", "section": "Special Moves", **move}, "08.03.2026 update"
    )
    assert text.startswith("Ryu - L Hadoken (236LP) [Special Moves] official frame data, as of the 08.03.2026 update")
    assert "Startup: 16 | Recovery: 47 total frames" in text and "On block: -5" in text


def test_real_capcom_files_load(small_data):
    docs = [d for d in load_framedata(small_data / "framedata") if d.metadata["character"] == "Ryu"]
    assert len(docs) > 50
    shoryuken = next(d for d in docs if d.metadata["move"] == "H Shoryuken")
    assert shoryuken.metadata["input"] == "623HP" and "official frame data" in shoryuken.text


def test_patch_documents(small_data):
    docs = list(load_patches(small_data / "patches"))
    ryu = [d for d in docs if d.metadata["character"] == "Ryu" and d.metadata["version"] == "20260803"]
    assert ryu and ryu[0].text.startswith("Ryu - balance changes in the 08.03.2026 update (released 2026-08-03)")
    assert any(d.metadata["character"] == "All characters" for d in docs)
    assert len({d.id for d in docs}) == len(docs)
