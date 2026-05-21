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
        if self.path == "/healthz":
            self._send_json({"status": "ok"})
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
    active_report = report or LAST_REPORT
    escaped_report = html.escape(active_report)
    escaped_repo = html.escape(repo_path)
    escaped_error = html.escape(error)
    escaped_path = html.escape(report_path or LAST_PATH)
    stats_html = render_stats(active_report)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Code Study Notes</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="shell">
    <nav class="nav">
      <div class="brand"><span class="mark"></span>CodeStudy Notes</div>
      <div class="nav-links"><a href="#analyze">Analyze</a><a href="#report">Report</a><a href="/healthz">Health</a></div>
    </nav>

    <header class="hero">
      <div>
        <p class="eyebrow">Repository learning intelligence</p>
        <h1>把陌生代码仓库变成可阅读的学习笔记</h1>
        <p class="subhead">扫描语言分布、入口文件、配置和目录结构，生成适合面试展示与源码阅读的 Markdown 报告。</p>
      </div>
      <div class="hero-panel">
        <span>Last report</span>
        <strong>{escaped_path or "Awaiting analysis"}</strong>
        <b>{"Ready" if active_report else "Idle"}</b>
      </div>
    </header>

    <main id="analyze" class="grid">
      <section class="panel input-panel">
        <form method="post" action="/analyze">
          <label>Repository path</label>
          <div class="input-row">
            <input name="repo_path" value="{escaped_repo}" placeholder="/path/to/local/repository" aria-label="Repository path">
            <button type="submit">Analyze</button>
          </div>
          <p class="hint">Docker 部署时默认挂载 <code>./workspace</code> 到容器内 <code>/workspace</code>，可输入 <code>/workspace</code> 分析挂载代码。</p>
        </form>
        {f'<div class="error">{escaped_error}</div>' if error else ''}
      </section>

      <aside class="panel metrics">
        <h2>Analysis snapshot</h2>
        {stats_html}
      </aside>
    </main>

    <section id="report" class="panel report-panel">
      <div class="report-head">
        <div><h2>Generated Markdown</h2><p>{f'Report written to <code>{escaped_path}</code>' if escaped_path else 'No report yet. Enter a local repository path and run analysis.'}</p></div>
      </div>
      <pre>{escaped_report or "No report yet. Enter a local repository path and run analysis."}</pre>
    </section>
  </div>
</body>
</html>"""


def render_stats(report: str) -> str:
    if not report:
        return """<div class="metric"><span>Status</span><strong>Idle</strong></div><div class="metric"><span>Output</span><strong>Markdown</strong></div>"""
    lines = report.splitlines()
    language_lines = [line for line in lines if line.startswith("- ") and ":" in line][:4]
    language_html = "".join(f"<li>{html.escape(line[2:])}</li>" for line in language_lines) or "<li>Report generated</li>"
    return f"""<div class="metric"><span>Status</span><strong>Ready</strong></div><div class="metric"><span>Lines</span><strong>{len(lines)}</strong></div><ul class="mini-list">{language_html}</ul>"""


CSS = """
:root {
  color-scheme: dark;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #08090a;
  color: #f7f8f8;
  font-feature-settings: "cv01", "ss03";
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(circle at 12% 8%, rgba(94, 106, 210, .26), transparent 34rem),
    radial-gradient(circle at 88% 20%, rgba(16, 185, 129, .12), transparent 28rem),
    linear-gradient(180deg, #111216 0%, #08090a 44%);
}
a { color: #aeb4ff; text-decoration: none; }
.shell { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 22px 0 44px; }
.nav { display: flex; justify-content: space-between; align-items: center; min-height: 52px; color: #d7d9df; }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 720; }
.mark { width: 18px; height: 18px; border-radius: 5px; background: #5e6ad2; box-shadow: 0 0 28px rgba(94,106,210,.8); }
.nav-links { display: flex; gap: 18px; font-size: 14px; }
.hero { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 26px; align-items: end; padding: 62px 0 34px; }
.eyebrow { color: #aeb4ff; margin: 0 0 12px; font-size: 13px; text-transform: uppercase; letter-spacing: .08em; }
h1 { margin: 0; max-width: 880px; font-size: clamp(38px, 7vw, 74px); line-height: .96; letter-spacing: -1.056px; font-weight: 510; }
.subhead { max-width: 720px; color: #a8acb7; font-size: 18px; line-height: 1.65; margin: 22px 0 0; }
.panel, .hero-panel {
  background: rgba(255,255,255,.058);
  border: 1px solid rgba(255,255,255,.10);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.07), 0 24px 70px rgba(0,0,0,.32);
  backdrop-filter: blur(18px);
  border-radius: 10px;
}
.hero-panel { padding: 22px; display: grid; gap: 12px; }
.hero-panel span, .metric span { color: #8f96a8; font-size: 13px; }
.hero-panel strong { color: #dfe1e7; line-height: 1.45; overflow-wrap: anywhere; }
.hero-panel b { font-size: 34px; color: #fff; }
.grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(320px, .55fr); gap: 18px; }
.panel { padding: 18px; }
form { display: grid; gap: 10px; }
label { color: #dfe1e7; font-weight: 650; font-size: 14px; }
.input-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; }
input {
  min-height: 44px;
  width: 100%;
  color: #f7f8f8;
  background: rgba(8,9,10,.72);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 7px;
  padding: 0 13px;
  font-size: 15px;
}
button {
  border: 0;
  border-radius: 7px;
  background: #5e6ad2;
  color: white;
  padding: 0 18px;
  font-weight: 720;
  cursor: pointer;
}
.hint, .report-head p { color: #9da3b2; line-height: 1.6; margin: 0; }
.metrics { display: grid; gap: 12px; }
.metrics h2, .report-head h2 { margin: 0; }
.metric { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,.08); padding-top: 12px; }
.metric strong { color: #aeb4ff; font-size: 22px; }
.mini-list { color: #c7cad3; line-height: 1.7; margin: 0; padding-left: 18px; }
.report-panel { margin-top: 18px; }
.report-head { display: flex; justify-content: space-between; align-items: start; margin-bottom: 14px; }
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 70vh;
  overflow: auto;
  margin: 0;
  color: #d6d9e4;
  background: rgba(8,9,10,.72);
  border: 1px solid rgba(255,255,255,.09);
  border-radius: 8px;
  padding: 18px;
  line-height: 1.55;
}
.error { border: 1px solid rgba(255, 120, 120, .4); color: #ffd1d1; background: rgba(120, 20, 20, .2); padding: 12px; border-radius: 7px; }
code { color: #c9ceff; }
@media (max-width: 880px) {
  .hero, .grid { grid-template-columns: 1fr; }
  .nav { align-items: flex-start; gap: 12px; flex-direction: column; }
}
@media (max-width: 560px) {
  .shell { width: min(100% - 22px, 1180px); }
  .input-row { grid-template-columns: 1fr; }
  button { min-height: 44px; }
}
"""
