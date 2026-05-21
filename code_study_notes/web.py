from __future__ import annotations

import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .analyzer import analyze_repository
from .report import render_markdown_report


LAST_REPORT = ""
LAST_PATH = ""


def run_server(host: str = "127.0.0.1", port: int = 8765, out_dir: str = "./out") -> None:
    output_dir = Path(out_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    class Handler(StudyNotesHandler):
        report_dir = output_dir

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Code Study Notes Web UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


class StudyNotesHandler(BaseHTTPRequestHandler):
    report_dir: Path

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            self._send_html(render_page())
            return
        if self.path == "/last-report":
            self._send_json({"path": LAST_PATH, "markdown": LAST_REPORT})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/analyze":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = parse_qs(body)
        repo_path = (params.get("repo_path") or [""])[0].strip()
        if not repo_path:
            self._send_html(render_page(error="Please enter a repository path."), HTTPStatus.BAD_REQUEST)
            return
        try:
            result = analyze_repository(repo_path)
            markdown = render_markdown_report(result)
            output_path = self.report_dir / "study-notes.md"
            output_path.write_text(markdown, encoding="utf-8")
            global LAST_REPORT, LAST_PATH
            LAST_REPORT = markdown
            LAST_PATH = str(output_path)
            self._send_html(render_page(report=markdown, report_path=str(output_path), repo_path=repo_path))
        except Exception as exc:  # noqa: BLE001 - local tool should display actionable errors.
            self._send_html(render_page(error=str(exc), repo_path=repo_path), HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, str]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def render_page(
    report: str = "",
    report_path: str = "",
    repo_path: str = "",
    error: str = "",
) -> str:
    escaped_report = html.escape(report or LAST_REPORT)
    escaped_repo = html.escape(repo_path)
    escaped_error = html.escape(error)
    escaped_path = html.escape(report_path or LAST_PATH)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Code Study Notes</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #f6f7f9; color: #20242a; }}
    header {{ background: #1f2937; color: white; padding: 22px 28px; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    form {{ display: grid; grid-template-columns: 1fr auto; gap: 12px; margin-bottom: 18px; }}
    input {{ padding: 11px 12px; border: 1px solid #c9ced6; border-radius: 6px; font-size: 15px; }}
    button {{ padding: 11px 16px; border: 0; border-radius: 6px; background: #2563eb; color: white; font-weight: 650; cursor: pointer; }}
    .error {{ background: #fff1f2; border: 1px solid #fda4af; padding: 12px; border-radius: 6px; margin-bottom: 16px; }}
    .path {{ color: #4b5563; margin: 10px 0 14px; font-size: 14px; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: white; border: 1px solid #dde2ea; border-radius: 8px; padding: 18px; line-height: 1.5; }}
    @media (max-width: 720px) {{ form {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Code Study Notes</h1>
  </header>
  <main>
    <form method="post" action="/analyze">
      <input name="repo_path" value="{escaped_repo}" placeholder="/path/to/local/repository" aria-label="Repository path">
      <button type="submit">Analyze</button>
    </form>
    {f'<div class="error">{escaped_error}</div>' if error else ''}
    {f'<div class="path">Report written to: <code>{escaped_path}</code></div>' if escaped_path else ''}
    <pre>{escaped_report or "No report yet. Enter a local repository path and run analysis."}</pre>
  </main>
</body>
</html>"""

