from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "node_modules",
    "venv",
    ".venv",
    "env",
    "dist",
    "build",
    "target",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "coverage",
    ".next",
    "out",
}

LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".xml": "XML",
    ".html": "HTML",
    ".css": "CSS",
    ".sh": "Shell",
    ".sql": "SQL",
}

CONFIG_FILES = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "pom.xml",
    "go.mod",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "Makefile",
}

ENTRY_FILENAMES = {
    "main.py",
    "__main__.py",
    "app.py",
    "manage.py",
    "server.js",
    "index.js",
    "main.ts",
    "index.ts",
    "main.go",
}

TEXT_EXTENSIONS = set(LANGUAGE_BY_EXTENSION) | {".txt", ".ini", ".cfg", ".conf"}


@dataclass
class FileInfo:
    path: str
    size: int
    language: str


@dataclass
class ConfigInfo:
    path: str
    kind: str
    summary: list[str] = field(default_factory=list)


@dataclass
class EntryPoint:
    path: str
    reason: str


@dataclass
class AnalysisResult:
    repo_path: str
    repo_name: str
    total_files: int
    total_bytes: int
    languages: dict[str, int]
    files: list[FileInfo]
    configs: list[ConfigInfo]
    entry_points: list[EntryPoint]
    readmes: list[str]
    top_dirs: dict[str, int]
    core_files: list[str]
    tree_lines: list[str]
    mermaid: str
    run_commands: list[str]
    study_route: list[str]
    questions: list[str]


def analyze_repository(repo_path: str | os.PathLike[str], max_files: int = 5000) -> AnalysisResult:
    root = Path(repo_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {root}")

    files: list[FileInfo] = []
    language_counts: Counter[str] = Counter()
    top_dirs: Counter[str] = Counter()
    total_bytes = 0

    for path in _iter_files(root, max_files=max_files):
        rel = path.relative_to(root).as_posix()
        size = _safe_size(path)
        language = detect_language(path)
        files.append(FileInfo(path=rel, size=size, language=language))
        total_bytes += size
        if language != "Other":
            language_counts[language] += 1
        first_part = rel.split("/", 1)[0]
        if first_part != rel:
            top_dirs[first_part] += 1

    files.sort(key=lambda item: item.path)
    configs = identify_configs(root, files)
    entry_points = identify_entry_points(root, files, configs)
    readmes = [f.path for f in files if Path(f.path).name.lower().startswith("readme")]
    core_files = choose_core_files(files, configs, entry_points)
    tree_lines = build_tree(files)
    mermaid = build_mermaid(files)
    run_commands = guess_run_commands(configs, entry_points)
    study_route = build_study_route(readmes, configs, entry_points, core_files)
    questions = build_questions(configs, entry_points, language_counts)

    return AnalysisResult(
        repo_path=str(root),
        repo_name=root.name,
        total_files=len(files),
        total_bytes=total_bytes,
        languages=dict(language_counts.most_common()),
        files=files,
        configs=configs,
        entry_points=entry_points,
        readmes=readmes,
        top_dirs=dict(top_dirs.most_common(12)),
        core_files=core_files,
        tree_lines=tree_lines,
        mermaid=mermaid,
        run_commands=run_commands,
        study_route=study_route,
        questions=questions,
    )


def detect_language(path: Path) -> str:
    if path.name == "Dockerfile":
        return "Docker"
    if path.name == "Makefile":
        return "Make"
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "Other")


def identify_configs(root: Path, files: Iterable[FileInfo]) -> list[ConfigInfo]:
    configs: list[ConfigInfo] = []
    for file_info in files:
        name = Path(file_info.path).name
        if name not in CONFIG_FILES:
            continue
        path = root / file_info.path
        configs.append(ConfigInfo(path=file_info.path, kind=name, summary=_summarize_config(path, name)))
    return configs


def identify_entry_points(root: Path, files: Iterable[FileInfo], configs: list[ConfigInfo]) -> list[EntryPoint]:
    entries: list[EntryPoint] = []
    seen: set[str] = set()

    def add(path: str, reason: str) -> None:
        if path not in seen:
            seen.add(path)
            entries.append(EntryPoint(path=path, reason=reason))

    file_paths = {item.path for item in files}
    for rel in sorted(file_paths):
        name = Path(rel).name
        if name in ENTRY_FILENAMES:
            add(rel, f"conventional entry filename: {name}")
        if rel.startswith("src/main/java/") and rel.endswith(".java"):
            add(rel, "Java source under src/main/java")
        if rel.startswith("cmd/") and rel.endswith(".go"):
            add(rel, "Go command package under cmd/")

    for config in configs:
        path = root / config.path
        if Path(config.path).name == "Dockerfile":
            for instruction in _docker_entry_instructions(path):
                add(config.path, instruction)
        if Path(config.path).name == "package.json":
            for script_name in _package_scripts(path):
                add(config.path, f"npm script: {script_name}")

    return entries[:20]


def choose_core_files(files: list[FileInfo], configs: list[ConfigInfo], entries: list[EntryPoint]) -> list[str]:
    selected: list[str] = []
    for path in [c.path for c in configs] + [e.path for e in entries]:
        if path not in selected:
            selected.append(path)
    source_candidates = [
        item.path
        for item in files
        if item.language in {"Python", "JavaScript", "TypeScript", "Java", "Go"}
        and not item.path.startswith(("tests/", "test/"))
    ]
    for path in source_candidates[:12]:
        if path not in selected:
            selected.append(path)
    return selected[:20]


def build_tree(files: list[FileInfo], max_lines: int = 120) -> list[str]:
    tree: dict[str, dict] = {}
    for item in files:
        node = tree
        for part in item.path.split("/"):
            node = node.setdefault(part, {})
    lines: list[str] = []

    def walk(node: dict[str, dict], prefix: str = "") -> None:
        if len(lines) >= max_lines:
            return
        names = sorted(node)
        for index, name in enumerate(names):
            connector = "`-- " if index == len(names) - 1 else "|-- "
            lines.append(f"{prefix}{connector}{name}")
            child_prefix = prefix + ("    " if index == len(names) - 1 else "|   ")
            if node[name]:
                walk(node[name], child_prefix)

    walk(tree)
    if len(files) > max_lines:
        lines.append("... tree truncated ...")
    return lines


def build_mermaid(files: list[FileInfo], max_nodes: int = 45) -> str:
    edges: set[tuple[str, str]] = set()
    labels: dict[str, str] = {"root": "repo"}
    for item in files:
        parts = item.path.split("/")
        first = parts[0]
        labels[first] = first
        edges.add(("root", first))
        if len(parts) > 1:
            second = f"{first}/{parts[1]}"
            labels[second] = parts[1]
            edges.add((first, second))

    lines = ["graph TD", '  root["repo"]']
    node_ids = {"root": "root"}

    def node_id(key: str) -> str:
        if key not in node_ids:
            node_ids[key] = f"n{len(node_ids)}"
        return node_ids[key]

    count = 0
    for parent, child in sorted(edges, key=lambda edge: (edge[0] != "root", edge[0], edge[1])):
        if count >= max_nodes:
            lines.append('  root --> more["..."]')
            return "\n".join(lines)
        parent_id = node_id(parent)
        child_id = node_id(child)
        lines.append(f'  {parent_id} --> {child_id}["{_escape_label(labels[child])}"]')
        count += 1
    return "\n".join(lines)


def guess_run_commands(configs: list[ConfigInfo], entries: list[EntryPoint]) -> list[str]:
    commands: list[str] = []
    config_names = {Path(c.path).name for c in configs}
    entry_paths = {e.path for e in entries}
    if "package.json" in config_names:
        commands.extend(["npm install", "npm run dev", "npm test"])
    if "requirements.txt" in config_names:
        commands.append("python -m pip install -r requirements.txt")
    if "pyproject.toml" in config_names:
        commands.append("python -m pip install -e .")
    if any(path.endswith(("app.py", "main.py")) for path in entry_paths):
        commands.append("python app.py  # or python main.py")
    if "go.mod" in config_names:
        commands.extend(["go test ./...", "go run ./cmd/<name>"])
    if "pom.xml" in config_names:
        commands.extend(["mvn test", "mvn spring-boot:run"])
    if {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"} & config_names:
        commands.append("docker compose up --build")
    if "Dockerfile" in config_names:
        commands.append("docker build -t app . && docker run --rm app")
    return _dedupe(commands) or ["Look for README instructions or scripts in configuration files."]


def build_study_route(
    readmes: list[str], configs: list[ConfigInfo], entries: list[EntryPoint], core_files: list[str]
) -> list[str]:
    route: list[str] = []
    if readmes:
        route.append(f"Read project overview first: {readmes[0]}")
    else:
        route.append("No README found; start with directory structure and configuration files.")
    if configs:
        route.append("Review configuration and dependency files: " + ", ".join(c.path for c in configs[:6]))
    if entries:
        route.append("Trace likely runtime entry points: " + ", ".join(e.path for e in entries[:6]))
    if core_files:
        route.append("Open core modules next: " + ", ".join(core_files[:8]))
    route.append("Skim tests, examples, and CI files to understand expected behavior.")
    return route


def build_questions(
    configs: list[ConfigInfo], entries: list[EntryPoint], languages: Counter[str]
) -> list[str]:
    questions = [
        "What user problem does this repository solve, and where is that documented?",
        "Which configuration file defines the canonical way to run and test the project?",
        "Where does control flow enter the application, and what modules does it call first?",
    ]
    if not entries:
        questions.append("No obvious entry point was found; is this a library, plugin, or incomplete service?")
    if len(languages) > 1:
        questions.append("Why does the project use multiple languages, and where is each language boundary?")
    if not configs:
        questions.append("No standard dependency files were found; how are dependencies installed?")
    return questions


def _iter_files(root: Path, max_files: int) -> Iterable[Path]:
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in IGNORE_DIRS and not name.startswith(".cache")]
        for filename in filenames:
            path = Path(dirpath) / filename
            if _should_skip_file(path):
                continue
            count += 1
            if count > max_files:
                return
            yield path


def _should_skip_file(path: Path) -> bool:
    if path.name.startswith(".DS_Store"):
        return True
    try:
        if path.stat().st_size > 2_000_000:
            return True
    except OSError:
        return True
    return False


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _summarize_config(path: Path, name: str) -> list[str]:
    if name == "package.json":
        return _summarize_package_json(path)
    if name == "requirements.txt":
        return _summarize_requirements(path)
    if name == "pyproject.toml":
        return _summarize_pyproject(path)
    if name == "go.mod":
        return _summarize_go_mod(path)
    if name == "Dockerfile":
        return _docker_entry_instructions(path)
    return []


def _summarize_package_json(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return ["Could not parse package.json"]
    summary = []
    if data.get("name"):
        summary.append(f"package name: {data['name']}")
    scripts = sorted((data.get("scripts") or {}).keys())
    if scripts:
        summary.append("scripts: " + ", ".join(scripts[:10]))
    deps = sorted(set((data.get("dependencies") or {}).keys()) | set((data.get("devDependencies") or {}).keys()))
    if deps:
        summary.append("dependencies: " + ", ".join(deps[:12]))
    return summary


def _summarize_requirements(path: Path) -> list[str]:
    lines = _read_lines(path)
    deps = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    return ["dependencies: " + ", ".join(deps[:12])] if deps else []


def _summarize_pyproject(path: Path) -> list[str]:
    text = _safe_text(path)
    summary = []
    name_match = re.search(r'(?m)^name\s*=\s*["\']([^"\']+)["\']', text)
    if name_match:
        summary.append(f"project name: {name_match.group(1)}")
    if "[project]" in text:
        summary.append("uses PEP 621 [project] metadata")
    if "[tool.poetry]" in text:
        summary.append("uses Poetry metadata")
    return summary


def _summarize_go_mod(path: Path) -> list[str]:
    lines = _read_lines(path)
    summary = []
    for line in lines:
        if line.startswith("module "):
            summary.append(line.strip())
        if line.startswith("go "):
            summary.append(line.strip())
    return summary


def _docker_entry_instructions(path: Path) -> list[str]:
    instructions = []
    for line in _read_lines(path):
        stripped = line.strip()
        if stripped.upper().startswith(("CMD ", "ENTRYPOINT ")):
            instructions.append(stripped)
    return instructions


def _package_scripts(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    return sorted((data.get("scripts") or {}).keys())


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _safe_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _node_id(value: str) -> str:
    return "n" + re.sub(r"[^A-Za-z0-9_]", "_", value)


def _escape_label(value: str) -> str:
    return value.replace('"', "'")
