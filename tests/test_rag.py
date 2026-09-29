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
    assert counts["framedata"] > 100 and counts["stats"] == 26 and counts["guide"] > 5


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
