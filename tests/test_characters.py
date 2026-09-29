import pytest

from framecoach.characters import ROSTER, character_from_filename, detect_characters
from framecoach.config import PROJECT_ROOT


def names(text):
    return [c.name for c in detect_characters(text)]


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What are Zangief's best anti-airs?", ["Zangief"]),
        ("How do I beat gief?", ["Zangief"]),
        ("Chun-Li st.MP frame data", ["Chun Li"]),
        ("chunli combos", ["Chun Li"]),
        ("What does A.K.I. do on wakeup", ["A.K.I."]),
        ("E. Honda headbutt", ["E. Honda"]),
        ("Is Bison's scissors safe?", ["M. Bison"]),
        ("Dee Jay vs Ken matchup", ["Dee Jay", "Ken"]),
        ("Ken vs Ryu", ["Ken", "Ryu"]),
        ("Is Ed good?", ["Ed"]),
        ("C. Viper vs Sagat", ["C. Viper", "Sagat"]),
        ("how to beat viper", ["C. Viper"]),
    ],
)
def test_detects_characters(question, expected):
    assert names(question) == expected


@pytest.mark.parametrize("question", ["Is this move punished?", "I need help with spacing", "token kenny"])
def test_no_false_positives(question):
    assert names(question) == []


def test_every_frame_data_file_matches_a_roster_slug():
    slugs = {c.slug for c in ROSTER}
    files = {p.stem for p in (PROJECT_ROOT / "data" / "framedata").glob("*.json")} - {"characters_stats"}
    assert files <= slugs
    # Everyone except characters Capcom hasn't published frame data for yet.
    assert len(slugs - files) <= 2


def test_every_guide_maps_to_a_character():
    unmapped = [p.name for p in (PROJECT_ROOT / "data" / "guides").glob("*.txt") if not character_from_filename(p.name)]
    assert unmapped == []
