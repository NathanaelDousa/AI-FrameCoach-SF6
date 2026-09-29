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
    from .llm import OllamaClient, OllamaError
    from .rag import Retriever, build_messages
    from .store import IndexMissingError, SentenceTransformerEmbedder, open_collection

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
    client = OllamaClient(settings.ollama_url, settings.model, settings.ollama_timeout)
    try:
        for text in client.stream_chat(build_messages(question, hits)):
            print(text, end="", flush=True)
        print()
    except OllamaError as exc:
        sys.exit(str(exc))


def cmd_serve(args: argparse.Namespace, settings: Settings) -> None:
    from .server import create_app

    create_app(settings).run(host=args.host, port=args.port, debug=args.debug)


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
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("serve", help="run the web app")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--debug", action="store_true", help="Flask debug mode (never expose this publicly)")
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    args.func(args, Settings())


if __name__ == "__main__":
    main()
