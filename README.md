# AI FrameCoach SF6

**FrameCoach SF6** is an AI coaching assistant for **Street Fighter 6**. It combines frame data for the whole roster, character stats and written guides with a local LLM (via [Ollama](https://ollama.com)), so you can ask things like:

- "What are Zangief's best anti-airs?"
- "How plus is JP's OD Amnesia on hit?"
- "What is the startup of Cammy's cr.HP?"
- "Give me Ken's oki after a corner combo"

Everything runs locally: no API keys, no cloud.

---

## How it works

```
ultimateframedata.com ──scrape──▶ data/framedata/*.json ─┐
video transcripts ──rewrite (LLM)──▶ data/guides/*.txt ──┼─ingest─▶ ChromaDB (chroma/)
                                                         │
question ─▶ detect character(s) ─▶ search (filtered by character) ─▶ Ollama ─▶ streamed answer + sources
```

- **Frame data** (1,378 moves for 26 characters), **stats** (health, walk speed, ...) and **guides** are embedded with [Sentence Transformers](https://www.sbert.net/) and stored in [ChromaDB](https://www.trychroma.com/) with metadata (`character`, `source`, `move`).
- **Character detection** understands names and nicknames (`Gief`, `Chun-Li`, `Bison`, `AKI`, `DJ`, ...), or you can pick a character in the UI.
- **Notation**: `2HP`, `cr.MK` and `j.HK` are understood. When a move is named, its exact frame data is always included.
- Answers stream in token by token, and every answer shows the sources it was based on.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/download) with a model pulled, e.g. `ollama pull gemma3`

## Quick start

```bash
git clone https://github.com/NathanaelDousa/AI-FrameCoach-SF6
cd AI-FrameCoach-SF6

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .

ollama pull gemma3                 # any chat model works, see Configuration
python -m framecoach ingest        # build the search index (first run downloads the embedding model)
python -m framecoach serve         # open http://localhost:5000
```

After `pip install -e .` you can also type `framecoach` instead of `python -m framecoach`.

## Commands

| Command | What it does |
| --- | --- |
| `framecoach serve [--host 0.0.0.0] [--port 5000]` | Run the web app |
| `framecoach ask "Ryu 2HP on block?" [--character Ryu] [--show-context]` | Ask from the terminal |
| `framecoach ingest` | Rebuild the search index. Run it after changing anything in `data/` |
| `framecoach scrape [ryu ken ...] [--stats-only]` | Re-download frame data and stats from ultimateframedata.com |
| `framecoach rewrite [--overwrite]` | Clean up raw transcripts in `data/transcripts/` into `data/guides/` using an LLM |

## Configuration

Set these as environment variables:

| Variable | Default | |
| --- | --- | --- |
| `FRAMECOACH_MODEL` | `gemma3` | Ollama model used for answers (`mistral`, `llama3.1`, `qwen2.5`, ...) |
| `OLLAMA_HOST` | `http://localhost:11434` | Where Ollama is running |
| `FRAMECOACH_EMBED_MODEL` | `all-MiniLM-L6-v2` | Sentence Transformers model. Re-run `ingest` after changing it |
| `FRAMECOACH_FRAMEDATA_K` / `FRAMECOACH_GUIDE_K` | `8` / `4` | How many frame data / guide snippets go into the prompt |
| `FRAMECOACH_DATA_DIR` / `FRAMECOACH_DB_DIR` | `data/` / `chroma/` | Data and index locations |
| `FRAMECOACH_REWRITE_MODEL` | `llama3` | Model used by `rewrite` |

## API

`POST /api/ask` with `{"question": "...", "character": "Ryu" (optional), "stream": false}`

```json
{"answer": "...", "characters": ["Ryu"], "sources": [{"label": "Ryu - Crouching Heavy Punch (frame data)", "text": "..."}]}
```

With `"stream": true` the response is newline-delimited JSON: one `meta` event (characters and sources), then `token` events, then `done` or `error`.

## Adding content

- **A guide**: drop a `.txt` file in `data/guides/` whose name starts with the character slug (`ryu`, `chunli`, `ehonda`, `mbison`, ...), e.g. `ryu oki setups.txt`. Separate topics with blank lines. Then run `framecoach ingest`.
- **A new character**: add them to `ROSTER` in `framecoach/characters.py`, then run `framecoach scrape <slug>` and `framecoach ingest`.

## Project layout

```
framecoach/
  characters.py   roster, aliases, character detection
  documents.py    frame data / stats / guides -> documents with metadata
  ingest.py       builds the ChromaDB index
  rag.py          retrieval + prompt
  llm.py          Ollama client (streaming)
  server.py       Flask app + API
  scrape.py       ultimateframedata.com scraper
  rewrite.py      transcript -> guide rewriter
  cli.py          command line
  templates/ static/   web UI
data/
  framedata/      scraped JSON per character + characters_stats.json
  guides/         cleaned-up guide text used by the coach
  transcripts/    raw video transcripts (input for `rewrite`)
tests/
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check framecoach tests && ruff format framecoach tests
```

The tests use a small fake embedder and a fake LLM, so they don't need Ollama or a model download.

## Credits

Frame data and stats come from [ultimateframedata.com](https://ultimateframedata.com/sf6). Guides are based on community video guides.
