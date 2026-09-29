import pytest

from framecoach.ingest import build_index
from framecoach.rag import Retriever, build_messages, expand_notation
from framecoach.store import IndexMissingError, open_collection


@pytest.fixture
def retriever(settings, embedder):
    build_index(settings, embedder)
    return Retriever(open_collection(settings), embedder, settings)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Ryu 2HP startup", "Crouching Heavy Punch"),
        ("is cr.MK plus", "Crouching Medium Kick"),
        ("st. lp on block", "Standing Light Punch"),
        ("j.HK", "Jumping Heavy Kick"),
        ("what does MP do", "Medium Punch"),
    ],
)
def test_expand_notation(question, expected):
    assert expected in expand_notation(question)


def test_expand_notation_leaves_plain_questions_alone():
    assert expand_notation("How do I play Zangief?") == "How do I play Zangief?"


def test_ingest_counts(settings, embedder):
    counts = build_index(settings, embedder)
    assert counts["framedata"] > 100 and counts["stats"] == 26 and counts["guide"] > 5 and counts["patch"] > 20


def test_missing_index_gives_helpful_error(settings):
    with pytest.raises(IndexMissingError, match="ingest"):
        open_collection(settings)


def test_character_filter_only_returns_that_character(retriever):
    names = retriever.resolve_characters("What are Zangief's best anti-airs?")
    hits = retriever.retrieve("What are Zangief's best anti-airs?", names)
    assert names == ["Zangief"]
    assert hits and {h.character for h in hits} == {"Zangief"}
    assert {h.source for h in hits} >= {"framedata", "guide"}


@pytest.mark.parametrize("question", ["Ryu crouching heavy punch startup", "Ryu 2HP startup", "ryu cr.hp on block"])
def test_named_move_is_always_first(retriever, question):
    hits = retriever.retrieve(question, ["Ryu"])
    assert hits[0].move == "Crouching Heavy Punch" and hits[0].character == "Ryu"
    assert [h.move for h in hits].count("Crouching Heavy Punch") == 1


def test_longest_move_name_wins(retriever):
    hits = retriever.retrieve("Ryu crouching heavy punch", ["Ryu"])
    exact = [h for h in hits if h.distance == 0.0]
    assert [h.move for h in exact] == ["Crouching Heavy Punch"]


def test_selected_character_takes_priority(retriever):
    assert retriever.resolve_characters("how do I beat Ken?", "Zangief") == ["Zangief", "Ken"]
    assert retriever.resolve_characters("anti-airs", "Not A Character") == []


def test_no_character_searches_everything(retriever):
    hits = retriever.retrieve("best anti-air", [])
    assert hits


def test_build_messages_numbers_context(retriever):
    hits = retriever.retrieve("Ryu jab", ["Ryu"])
    messages = build_messages("Ryu jab", hits)
    assert messages[0]["role"] == "system"
    assert "[1] Ryu" in messages[1]["content"] and "Question: Ryu jab" in messages[1]["content"]


def test_input_notation_finds_the_move(retriever):
    hits = retriever.retrieve("Is Ken's 623HP invincible?", ["Ken"])
    assert hits[0].move == "H Shoryuken" and hits[0].distance == 0.0


def test_patch_question_gets_newest_notes_first(retriever):
    hits = retriever.retrieve("What changed for Ryu in the last patch?", ["Ryu"])
    patches = [h for h in hits if h.source == "patch"]
    assert hits[0].source == "patch"  # patch notes lead for "what changed" questions
    assert patches[0].patch == "08.03.2026 update" and patches[0].character == "Ryu"
    assert [h.date for h in patches] == sorted((h.date for h in patches), reverse=True)


def test_latest_update_without_character(retriever):
    hits = retriever.retrieve("What changed in the latest update?", [])
    patches = [h for h in hits if h.source == "patch"]
    assert patches and all(h.patch == "08.03.2026 update" for h in patches[:6])


def test_normal_questions_still_see_patch_notes(retriever):
    hits = retriever.retrieve("Ryu jab", ["Ryu"])
    assert hits[0].source != "patch"
    assert {h.character for h in hits if h.source == "patch"} <= {"Ryu", "All characters"}


def test_version_sort_key():
    from framecoach.rag import _version_sort_key

    assert sorted(["20250805", "202506", "20250205"], key=_version_sort_key) == ["20250205", "202506", "20250805"]


def test_index_notices_changed_data(settings, embedder):
    from framecoach.ingest import index_is_current

    assert not index_is_current(settings)
    build_index(settings, embedder)
    assert index_is_current(settings)
    (settings.guides_dir / "ryu new tech.txt").write_text("Ryu guide\n\nNew tech.", encoding="utf-8")
    assert not index_is_current(settings)
