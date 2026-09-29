"""Command line entry point: ``python -m framecoach <command>``."""

from __future__ import annotations

import argparse
import sys

from .config import Settings


def cmd_scrape(args: argparse.Namespace, settings: Settings) -> None:
    from .scrape import scrape_characters, scrape_stats

    if not args.stats_only:
        scrape_characters(settings.framedata_dir, args.characters or None)
    if args.stats_only or not args.characters:
        scrape_stats(settings.stats_file)


def cmd_rewrite(args: argparse.Namespace, settings: Settings) -> None:
    from .llm import OllamaClient
    from .rewrite import rewrite_folder

    client = OllamaClient(settings.ollama_url, settings.rewrite_model, settings.ollama_timeout)
    rewrite_folder(client, settings.transcripts_dir, settings.guides_dir, settings.rewrite_model, args.overwrite)


def cmd_ingest(args: argparse.Namespace, settings: Settings) -> None:
    from .ingest import build_index

    counts = build_index(settings)
    summary = ", ".join(f"{n} {source}" for source, n in sorted(counts.items()))
    print(f"Indexed {sum(counts.values())} documents ({summary}) into {settings.db_dir}")


def cmd_ask(args: argparse.Namespace, settings: Settings) -> None:
    from .llm import LLMError, make_client
    from .rag import Retriever, build_messages
    from .store import IndexMissingError, SentenceTransformerEmbedder, open_collection
    from .user_settings import SettingsStore

    user = SettingsStore().load()
    provider = args.provider or user.provider or "ollama"
    try:
        client = make_client(
            provider,
            args.model or user.model_for(provider),
            user.key_for(provider),
            settings.ollama_url,
            settings.ollama_timeout,
        )
    except LLMError as exc:
        sys.exit(f"{exc} (or run `framecoach serve` and use the settings screen)")

    question = " ".join(args.question)
    try:
        retriever = Retriever(open_collection(settings), SentenceTransformerEmbedder(settings.embed_model), settings)
    except IndexMissingError as exc:
        sys.exit(str(exc))
    names = retriever.resolve_characters(question, args.character)
    hits = retriever.retrieve(question, names)
    if args.show_context:
        for hit in hits:
            print(f"--- {hit.label()} (distance {hit.distance:.3f})\n{hit.text}\n")
    try:
        for text in client.stream_chat(build_messages(question, hits)):
            print(text, end="", flush=True)
        print()
    except LLMError as exc:
        sys.exit(str(exc))


def cmd_serve(args: argparse.Namespace, settings: Settings) -> None:
    import os
    import threading
    import webbrowser

    from .server import LOOPBACK_HOSTS, create_app
    from .store import IndexMissingError, open_collection

    try:
        open_collection(settings)
    except IndexMissingError:
        print("No search index yet, building it now (the first time takes a few minutes)...")
        cmd_ingest(args, settings)

    local = args.host in ("127.0.0.1", "localhost", "::1")
    app = create_app(settings, trusted_hosts=LOOPBACK_HOSTS if local else None)
    url = f"http://{'localhost' if local else args.host}:{args.port}"
    # With --debug the reloader starts the app twice; only open the browser once.
    if not args.no_browser and not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.5, webbrowser.open, [url]).start()
    print(f"FrameCoach is running at {url} (press Ctrl+C to stop)")
    app.run(host=args.host, port=args.port, debug=args.debug)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="framecoach", description="AI FrameCoach for Street Fighter 6")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scrape", help="download frame data and stats from ultimateframedata.com")
    p.add_argument("characters", nargs="*", help="character slugs, e.g. ryu chunli (default: all)")
    p.add_argument("--stats-only", action="store_true", help="only scrape the character stats page")
    p.set_defaults(func=cmd_scrape)

    p = sub.add_parser("rewrite", help="clean up raw transcripts in data/transcripts into data/guides")
    p.add_argument("--overwrite", action="store_true", help="redo guides that already exist")
    p.set_defaults(func=cmd_rewrite)

    p = sub.add_parser("ingest", help="(re)build the search index")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("ask", help="ask a question from the terminal")
    p.add_argument("question", nargs="+")
    p.add_argument("--character", help="restrict the search to this character, e.g. 'Chun Li'")
    p.add_argument("--show-context", action="store_true", help="print the retrieved documents")
    p.add_argument(
        "--provider", choices=["ollama", "anthropic", "openai", "deepseek"], help="override the saved choice"
    )
    p.add_argument("--model", help="override the saved model")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("serve", help="run the web app")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--debug", action="store_true", help="Flask debug mode (never expose this publicly)")
    p.add_argument("--no-browser", action="store_true", help="don't open the browser automatically")
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    args.func(args, Settings())


if __name__ == "__main__":
    main()
