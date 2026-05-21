from __future__ import annotations

import argparse
from pathlib import Path

from .analyzer import analyze_repository
from .report import render_markdown_report
from .web import run_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m code_study_notes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a local repository")
    analyze_parser.add_argument("repo_path", help="Path to a local repository")
    analyze_parser.add_argument("--out", required=True, help="Output directory for Markdown report")

    web_parser = subparsers.add_parser("web", help="Start local Web UI")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8765)
    web_parser.add_argument("--out", default="./out", help="Directory where Web UI writes reports")

    args = parser.parse_args(argv)
    if args.command == "analyze":
        return analyze_command(args.repo_path, args.out)
    if args.command == "web":
        run_server(host=args.host, port=args.port, out_dir=args.out)
        return 0
    parser.error("unknown command")
    return 2


def analyze_command(repo_path: str, out_dir: str) -> int:
    result = analyze_repository(repo_path)
    markdown = render_markdown_report(result)
    output_dir = Path(out_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "study-notes.md"
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Report written to {output_path}")
    return 0

