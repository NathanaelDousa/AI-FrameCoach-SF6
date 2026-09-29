from framecoach.documents import chunk_text, load_all, load_framedata, load_guides, load_stats, move_to_text


def test_move_text_is_english_and_names_the_character():
    text = move_to_text("Ryu", {"move": "Standing Light Punch", "startup": "4", "onblock": "-1", "notes": "--"})
    assert text.startswith("Ryu - Standing Light Punch")
    assert "Startup: 4" in text and "On block: -1" in text
    assert "Notes" not in text  # empty "--" values are dropped


def test_framedata_has_character_metadata(small_data):
    docs = list(load_framedata(small_data / "framedata"))
    assert {d.metadata["character"] for d in docs} == {"Ryu", "Ken", "Zangief", "Chun Li"}
    assert all(d.text.startswith(d.metadata["character"]) for d in docs)
    assert len({d.id for d in docs}) == len(docs)


def test_stats_are_loaded(small_data):
    docs = {d.metadata["character"]: d for d in load_stats(small_data / "framedata" / "characters_stats.json")}
    assert "Health: 9,000" in docs["Akuma"].text
    assert "Chun Li" in docs


def test_guides_are_chunked_with_character(small_data):
    docs = list(load_guides(small_data / "guides", max_chars=800))
    assert {d.metadata["character"] for d in docs} == {"Zangief", "Ryu", "Ken"}
    assert all(len(d.text) < 900 for d in docs)


def test_chunk_text_splits_unpunctuated_transcripts():
    text = " ".join(["word"] * 1000)
    chunks = chunk_text(text, max_chars=200)
    assert len(chunks) > 1 and all(len(c) <= 200 for c in chunks)
    assert sum(c.count("word") for c in chunks) == 1000


def test_chunk_text_keeps_small_paragraphs_together():
    assert chunk_text("a\n\nb\n\nc", max_chars=100) == ["a\n\nb\n\nc"]


def test_all_real_data_loads():
    from framecoach.config import Settings

    s = Settings()
    docs = load_all(s.framedata_dir, s.stats_file, s.guides_dir)
    sources = {d.metadata["source"] for d in docs}
    assert sources == {"framedata", "stats", "guide"}
    assert len({d.id for d in docs}) == len(docs)
