"""Clean up raw video transcripts into objective guide text with a local LLM."""

from __future__ import annotations

from pathlib import Path

from .llm import LLMError, OllamaClient

REWRITE_PROMPT = """You are rewriting a transcript from a video guide about a Street Fighter 6 character.

Rewrite the text to be objective, concise and professional. Remove personal phrases such as \
"I think", "in my opinion" or "I like to" and state the information as facts or general best practice.
Keep every concrete detail: move names, frame numbers, combos, setups and situations.
Separate topics with blank lines. Respond only with the rewritten text.

---
{text}
"""


def rewrite_folder(
    client: OllamaClient, input_dir: Path, output_dir: Path, model: str, overwrite: bool = False
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(input_dir.glob("*.txt")):
        target = output_dir / path.name
        if target.exists() and not overwrite:
            print(f"- {path.name}: already rewritten, skipping (use --overwrite to redo)")
            continue
        print(f"... rewriting {path.name}")
        try:
            rewritten = client.generate(REWRITE_PROMPT.format(text=path.read_text(encoding="utf-8").strip()), model)
        except LLMError as exc:
            print(f"x {path.name}: {exc}")
            continue
        if rewritten:
            target.write_text(rewritten, encoding="utf-8")
            print(f"ok {target}")
        else:
            print(f"x {path.name}: empty response")
