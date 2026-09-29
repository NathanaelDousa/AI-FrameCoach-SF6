# AI FrameCoach SF6

**FrameCoach SF6** is an AI coaching assistant for **Street Fighter 6**. It combines frame data for the whole roster, character stats and written guides with a local LLM (via [Ollama](https://ollama.com)), so you can ask things like:

- "What are Zangief's best anti-airs?"
- "How plus is JP's OD Amnesia on hit?"
- "What is the startup of Cammy's cr.HP?"
- "Give me Ken's oki after a corner combo"

Run it **fully local and free** with [Ollama](https://ollama.com), or use a **cloud API**: Claude, OpenAI or DeepSeek. The first time you open the app it asks which one you want, and you can switch at any time.

---

## How it works

```
streetfighter.com (Capcom) ──update──▶ data/framedata/*.json + data/patches/*.json ─┐
video transcripts ──rewrite (LLM)──▶ data/guides/*.txt ────────────────────────────┼─ingest─▶ ChromaDB (chroma/)
                                                                                    │
question ─▶ detect character(s) ─▶ search (filtered by character) ─▶ your model ─▶ streamed answer + sources
```

- **Official frame data** from Capcom for 31 characters (2,400+ moves): startup, active frames, recovery, hit/block advantage, cancels, damage, drive and super gauge, properties, invincibility notes and inputs in numpad notation (`236P`, `623HP`).
- **Every patch since launch** (21 balance updates from Capcom's battle change list), so the coach can answer "what changed for Ken last patch?" and knows newer info beats older guides.
- **Guides** and character **stats** (health, walk speed, ...) add strategy on top.
- Everything is embedded with [Sentence Transformers](https://www.sbert.net/) and stored in [ChromaDB](https://www.trychroma.com/) with metadata (`character`, `source`, `move`, patch `date`).
- **Character detection** understands names and nicknames (`Gief`, `Chun-Li`, `Bison`, `Viper`, `AKI`, `DJ`, ...), or you can pick a character in the UI.
- **Notation**: `2HP`, `cr.MK`, `j.HK` and motion inputs like `623HP` are understood. When a move is named, its exact frame data is always included.
- Answers stream in token by token, and every answer shows the sources it was based on.

## Always up to date

- A GitHub Action checks Capcom every Monday and opens a pull request when frame data or patch notes change.
- To grab the newest data yourself right away: `framecoach update`.
- `framecoach serve` / `start.bat` notices when the data changed and rebuilds the search index automatically.

## Quick start (Windows)

1. Install Python and Git. Open **PowerShell** and run:
   ```powershell
   winget install Python.Python.3.12
   winget install Git.Git
   ```
   Close PowerShell and open it again so it finds the new programs.
2. Download the project:
   ```powershell
   git clone https://github.com/NathanaelDousa/AI-FrameCoach-SF6
   cd AI-FrameCoach-SF6
   ```
3. Double-click **`start.bat`** in the project folder, or run `.\start.bat` in PowerShell.
   The first run installs everything and builds the search index, which takes a few minutes. Then your browser opens.
4. Choose **Local model** or **Cloud API** in the popup.
   - **Local:** install [Ollama](https://ollama.com/download), then run `ollama pull gemma3`. It's free and private, but you need a decent graphics card for fast answers.
   - **Cloud API:** paste a key from [Claude](https://console.anthropic.com/settings/keys), [OpenAI](https://platform.openai.com/api-keys) or [DeepSeek](https://platform.deepseek.com/api_keys). It's fast on any PC and you pay per question (usually fractions of a cent).

Next time, just double-click `start.bat` again. After pulling a new version, run `start.bat --update`.

## Quick start (macOS / Linux)

```bash
git clone https://github.com/NathanaelDousa/AI-FrameCoach-SF6
cd AI-FrameCoach-SF6
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
framecoach serve        # builds the index on first run and opens http://localhost:5000
```

## Models and API keys

- Switch model or provider any time with the model button in the top right.
- API keys are saved in your user profile, **not** in the project folder, so they never end up on GitHub:
  - Windows: `%APPDATA%\FrameCoach\config.json`
  - macOS: `~/Library/Application Support/FrameCoach/config.json`
  - Linux: `~/.config/framecoach/config.json`
- Keys can also come from the environment variables `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `DEEPSEEK_API_KEY`.
- The web app only accepts requests from your own browser tab on `localhost`. Other websites can't read or use your keys.

## Commands

| Command | What it does |
| --- | --- |
| `framecoach serve [--port 5000] [--no-browser]` | Run the web app (builds the index first if needed) |
| `framecoach ask "Ryu 2HP on block?" [--character Ryu] [--provider deepseek] [--model ...]` | Ask from the terminal, using your saved model unless you override it |
| `framecoach ingest` | Rebuild the search index. Run it after changing anything in `data/` |
| `framecoach update [ryu ken ...]` | Download the latest official frame data and new patch notes from Capcom, then rebuild the index |
| `framecoach scrape [--stats-only]` | Older source: character stats (and frame data) from ultimateframedata.com |
| `framecoach rewrite [--overwrite]` | Clean up raw transcripts in `data/transcripts/` into `data/guides/` using Ollama |

## Configuration

Optional environment variables:

| Variable | Default | |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://localhost:11434` | Where Ollama is running |
| `FRAMECOACH_EMBED_MODEL` | `all-MiniLM-L6-v2` | Sentence Transformers model. Re-run `ingest` after changing it |
| `FRAMECOACH_FRAMEDATA_K` / `FRAMECOACH_GUIDE_K` / `FRAMECOACH_PATCH_K` | `8` / `4` / `3` | How many frame data / guide / patch note snippets go into the prompt |
| `FRAMECOACH_DATA_DIR` / `FRAMECOACH_DB_DIR` | `data/` / `chroma/` | Data and index locations |
| `FRAMECOACH_CONFIG_DIR` | see above | Where your model choice and API keys are saved |
| `FRAMECOACH_REWRITE_MODEL` | `llama3` | Model used by `rewrite` |

## API

- `GET /api/settings` / `POST /api/settings` read and change the model choice (keys are only ever returned masked).
- `POST /api/models` lists the models a provider offers.
- `POST /api/ask` takes `{"question": "...", "character": "Ryu" (optional), "stream": false}`

```json
{"answer": "...", "characters": ["Ryu"], "sources": [{"label": "Ryu - Crouching Heavy Punch (frame data)", "text": "..."}]}
```

With `"stream": true` the response is newline-delimited JSON: one `meta` event (characters and sources), then `token` events, then `done` or `error`.

## Adding content

- **A guide**: drop a `.txt` file in `data/guides/` whose name starts with the character slug (`ryu`, `chunli`, `ehonda`, `mbison`, ...), e.g. `ryu oki setups.txt`. Separate topics with blank lines. Then run `framecoach ingest`.
- **A new character**: add them to `ROSTER` in `framecoach/characters.py`, then run `framecoach update <slug>`.

## Project layout

```
framecoach/
  characters.py   roster, aliases, character detection
  documents.py    frame data / stats / guides -> documents with metadata
  ingest.py       builds the ChromaDB index
  rag.py          retrieval + prompt
  llm.py          model providers: Ollama, Claude, OpenAI, DeepSeek
  user_settings.py  saved model choice + API keys
  server.py       Flask app + API
  capcom.py       official frame data + patch notes scraper (streetfighter.com)
  scrape.py       ultimateframedata.com scraper (character stats)
  rewrite.py      transcript -> guide rewriter
  cli.py          command line
  templates/ static/   web UI
data/
  framedata/      official frame data per character + characters_stats.json
  patches/        Capcom battle change notes, one file per update
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

The tests use a fake embedder, fake models and local fake servers, so they need no Ollama, API keys or downloads.

## Credits

Frame data and patch notes come from Capcom's official [Street Fighter 6 site](https://www.streetfighter.com/6/character) and [battle change list](https://www.streetfighter.com/6/buckler/en/battle_change). Character stats come from [ultimateframedata.com](https://ultimateframedata.com/sf6). Guides are based on community video guides. Street Fighter is a trademark of Capcom; this is an unofficial fan project.
