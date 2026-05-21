from __future__ import annotations

from datetime import datetime, timezone

from .analyzer import AnalysisResult


def render_markdown_report(result: AnalysisResult) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"# Code Study Notes: {result.repo_name}",
        "",
        f"- Repository: `{result.repo_path}`",
        f"- Generated at: {generated_at}",
        f"- Files scanned: {result.total_files}",
        f"- Approx size: {_format_bytes(result.total_bytes)}",
        "",
        "## Project Overview",
        "",
        _overview(result),
        "",
        "## Technology Stack",
        "",
    ]
    if result.languages:
        total_language_files = sum(result.languages.values())
        for language, count in result.languages.items():
            percent = count / total_language_files * 100 if total_language_files else 0
            lines.append(f"- {language}: {count} files ({percent:.1f}%)")
    else:
        lines.append("- No recognized source languages found.")

    lines.extend(["", "## Key Configuration", ""])
    if result.configs:
        for config in result.configs:
            lines.append(f"- `{config.path}` ({config.kind})")
            for summary in config.summary:
                lines.append(f"  - {summary}")
    else:
        lines.append("- No standard configuration files were detected.")

    lines.extend(["", "## Likely Entry Points", ""])
    if result.entry_points:
        for entry in result.entry_points:
            lines.append(f"- `{entry.path}`: {entry.reason}")
    else:
        lines.append("- No conventional entry point was detected.")

    lines.extend(["", "## Directory Structure", "", "```text"])
    lines.extend(result.tree_lines or ["(empty)"])
    lines.extend(["```", "", "## Module Relationship Sketch", "", "```mermaid"])
    lines.extend(result.mermaid.splitlines())
    lines.extend(["```", "", "## Core Files To Read", ""])
    if result.core_files:
        for path in result.core_files:
            lines.append(f"- `{path}`")
    else:
        lines.append("- No core files identified.")

    lines.extend(["", "## Suggested Reading Route", ""])
    for index, step in enumerate(result.study_route, start=1):
        lines.append(f"{index}. {step}")

    lines.extend(["", "## Guessed Run Commands", ""])
    for command in result.run_commands:
        lines.append(f"- `{command}`")

    lines.extend(["", "## Follow-Up Questions", ""])
    for question in result.questions:
        lines.append(f"- {question}")

    lines.append("")
    return "\n".join(lines)


def _overview(result: AnalysisResult) -> str:
    language = next(iter(result.languages), "unrecognized files")
    config_count = len(result.configs)
    entry_count = len(result.entry_points)
    return (
        f"This repository contains {result.total_files} scanned files. "
        f"The dominant detected language is {language}. "
        f"The analyzer found {config_count} configuration files and {entry_count} likely entry points."
    )


def _format_bytes(size: int) -> str:
    value = float(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"

