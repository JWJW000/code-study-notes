from __future__ import annotations

import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from code_study_notes import analyze_repository, render_markdown_report


def test_core_analysis() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "demo"
        root.mkdir()
        (root / "README.md").write_text("# Demo\n", encoding="utf-8")
        (root / "requirements.txt").write_text("fastapi\npytest\n", encoding="utf-8")
        (root / "package.json").write_text(
            '{"name":"demo","scripts":{"dev":"vite","test":"vitest"},"dependencies":{"react":"latest"}}',
            encoding="utf-8",
        )
        (root / "app.py").write_text("def main():\n    print('hello')\n", encoding="utf-8")
        (root / "Dockerfile").write_text("FROM python:3.11\nCMD [\"python\", \"app.py\"]\n", encoding="utf-8")
        (root / "node_modules").mkdir()
        (root / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")

        result = analyze_repository(root)
        report = render_markdown_report(result)

        assert result.total_files == 5
        assert result.languages["Python"] == 1
        assert "package.json" in {config.path for config in result.configs}
        assert "app.py" in {entry.path for entry in result.entry_points}
        assert "node_modules" not in "\n".join(result.tree_lines)
        assert "## Suggested Reading Route" in report
        assert "```mermaid" in report


if __name__ == "__main__":
    test_core_analysis()
    print("smoke test passed")
