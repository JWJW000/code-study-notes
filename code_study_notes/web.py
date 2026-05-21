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




def load_open_design_tokens() -> str:
    """Load tokens adapted from nexu-io/open-design/design-systems/vercel."""
    candidates = [
        Path(__file__).resolve().parents[1] / "open-design" / "vercel-tokens.css",
        Path.cwd() / "open-design" / "vercel-tokens.css",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return ""


CSS = load_open_design_tokens() + """
/*
 * UI integration note:
 * - Design tokens are adapted from nexu-io/open-design/design-systems/vercel/tokens.css.
 * - Components follow Open Design's Vercel reference: white canvas, shadow-as-border,
 *   Geist-like type hierarchy, sparse spacing, and functional blue accent.
 */
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--fg);
  font-family: var(--font-body);
  line-height: var(--leading-body);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
a { color: var(--accent); text-decoration: none; }
.shell { max-width: var(--container-max); margin: 0 auto; padding: var(--space-6) var(--container-gutter-desktop) var(--space-12); }
.nav { display: flex; justify-content: space-between; align-items: center; min-height: 52px; color: var(--fg-2); }
.brand { display: flex; align-items: center; gap: var(--space-3); font-weight: 600; }
.mark { width: 18px; height: 18px; border-radius: var(--radius-sm); background: var(--fg); box-shadow: var(--elev-ring); }
.nav-links { display: flex; gap: var(--space-5); font-size: var(--text-sm); }
.hero { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: var(--space-8); align-items: end; padding: var(--section-y-tablet) 0 var(--space-8); }
.eyebrow { color: var(--accent); margin: 0 0 var(--space-3); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: .08em; font-weight: 600; }
h1 { margin: 0; max-width: 900px; font-family: var(--font-display); font-size: clamp(38px, 7vw, var(--text-4xl)); line-height: var(--leading-tight); letter-spacing: var(--tracking-display); font-weight: 600; }
.subhead { max-width: 720px; color: var(--fg-2); font-size: var(--text-lg); line-height: 1.65; margin: var(--space-5) 0 0; }
.panel, .hero-panel {
  background: var(--surface);
  box-shadow: var(--elev-raised);
  border-radius: var(--radius-md);
}
.hero-panel { padding: var(--space-6); display: grid; gap: var(--space-3); }
.hero-panel span, .metric span { color: var(--muted); font-size: var(--text-xs); }
.hero-panel strong { color: var(--fg-2); line-height: 1.45; overflow-wrap: anywhere; font-weight: 500; }
.hero-panel b { font-size: var(--text-2xl); color: var(--fg); }
.grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(320px, .55fr); gap: var(--space-5); }
.panel { padding: var(--space-6); }
form { display: grid; gap: var(--space-3); }
label { color: var(--fg); font-weight: 600; font-size: var(--text-sm); }
.input-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-3); }
input {
  min-height: 44px;
  width: 100%;
  color: var(--fg);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0 var(--space-4);
  font-size: var(--text-sm);
  outline: none;
}
input:focus { box-shadow: var(--focus-ring); border-color: transparent; }
button {
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--fg);
  color: var(--bg);
  padding: 0 var(--space-5);
  font-weight: 600;
  cursor: pointer;
  transition: transform var(--motion-fast) var(--ease-standard), opacity var(--motion-fast) var(--ease-standard);
}
button:hover { transform: translateY(-1px); }
.hint, .report-head p { color: var(--muted); line-height: 1.6; margin: 0; }
.metrics { display: grid; gap: var(--space-4); }
.metrics h2, .report-head h2 { margin: 0; font-size: var(--text-xl); }
.metric { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-soft); padding-top: var(--space-4); }
.metric strong { color: var(--fg); font-size: var(--text-xl); }
.mini-list { color: var(--fg-2); line-height: 1.7; margin: 0; padding-left: var(--space-5); }
.report-panel { margin-top: var(--space-5); }
.report-head { display: flex; justify-content: space-between; align-items: start; margin-bottom: var(--space-4); }
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 70vh;
  overflow: auto;
  margin: 0;
  color: var(--fg-2);
  background: #fafafa;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  line-height: 1.6;
  font-family: var(--font-mono);
}
.error { border: 1px solid color-mix(in oklab, var(--danger), white 40%); color: var(--danger); background: color-mix(in oklab, var(--danger), white 92%); padding: var(--space-4); border-radius: var(--radius-sm); }
code { color: var(--accent); font-family: var(--font-mono); }
@media (max-width: 880px) {
  .shell { padding-inline: var(--container-gutter-tablet); }
  .hero, .grid { grid-template-columns: 1fr; }
  .nav { align-items: flex-start; gap: var(--space-3); flex-direction: column; }
}
@media (max-width: 560px) {
  .shell { padding-inline: var(--container-gutter-phone); }
  .input-row { grid-template-columns: 1fr; }
  button { min-height: 44px; }
}
"""
