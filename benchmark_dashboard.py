import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


RESULTS_DIR = Path("benchmark_results")


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Benchmark Dashboard</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #0d1117;
      --panel: #161b22;
      --panel-2: #21262d;
      --text: #e6edf3;
      --muted: #8b949e;
      --border: #30363d;
      --accent: #2f81f7;
      --green: #3fb950;
      --red: #f85149;
      --yellow: #d29922;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    header {
      padding: 24px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(135deg, #161b22, #0d1117);
    }

    h1 {
      margin: 0 0 8px;
      font-size: 28px;
    }

    .subtitle {
      color: var(--muted);
    }

    main {
      padding: 24px;
      display: grid;
      gap: 24px;
    }

    .controls,
    .cards,
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
    }

    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      padding: 16px;
      align-items: end;
    }

    label {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .05em;
    }

    select,
    input {
      background: var(--panel-2);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      min-width: 180px;
    }

    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1px;
      overflow: hidden;
    }

    .card {
      padding: 18px;
      background: var(--panel);
    }

    .card .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .05em;
    }

    .card .value {
      font-size: 28px;
      font-weight: 700;
      margin-top: 6px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 24px;
    }

    .panel {
      padding: 18px;
      overflow: auto;
    }

    .panel h2 {
      margin: 0 0 16px;
      font-size: 18px;
    }

    svg {
      width: 100%;
      min-height: 320px;
      background: #0d1117;
      border-radius: 8px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      white-space: nowrap;
    }

    th,
    td {
      border-bottom: 1px solid var(--border);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }

    th {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .04em;
      position: sticky;
      top: 0;
      background: var(--panel);
      z-index: 1;
    }

    tr:hover td {
      background: rgba(47, 129, 247, .08);
    }

    .ok {
      color: var(--green);
      font-weight: 600;
    }

    .fail {
      color: var(--red);
      font-weight: 600;
    }

    details {
      max-width: 900px;
    }

    pre {
      background: #010409;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      overflow: auto;
      max-height: 420px;
      white-space: pre-wrap;
    }

    .small {
      color: var(--muted);
      font-size: 12px;
    }
  </style>
</head>
<body>
  <header>
    <h1>Benchmark Dashboard</h1>
    <div class="subtitle">All records loaded from <code>benchmark_results/*.jsonl</code></div>
  </header>

  <main>
    <section class="controls">
      <label>
        Mode
        <select id="modeFilter"></select>
      </label>
      <label>
        Task
        <select id="taskFilter"></select>
      </label>
      <label>
        Search
        <input id="searchFilter" placeholder="task, mode, answer...">
      </label>
    </section>

    <section class="cards" id="cards"></section>

    <section class="grid">
      <div class="panel">
        <h2>Total tokens by record</h2>
        <svg id="tokensChart"></svg>
      </div>
      <div class="panel">
        <h2>Input tokens by mode</h2>
        <svg id="modeChart"></svg>
      </div>
    </section>

    <section class="panel">
      <h2>All benchmark records</h2>
      <div class="small">Each row includes an expandable raw JSON payload, including prompts, outputs and evidence packets.</div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Timestamp</th>
            <th>Mode</th>
            <th>Task</th>
            <th>Input</th>
            <th>Output</th>
            <th>Total</th>
            <th>Tools</th>
            <th>LLM calls</th>
            <th>Passed</th>
            <th>Latency</th>
            <th>Raw</th>
          </tr>
        </thead>
        <tbody id="recordsBody"></tbody>
      </table>
    </section>
  </main>

  <script>
    const state = {
      records: [],
      filtered: []
    };

    const nf = new Intl.NumberFormat();

    function usage(record, key) {
      return Number(record?.usage?.[key] || 0);
    }

    function llmCalls(record) {
      return Array.isArray(record.llm_invocations)
        ? record.llm_invocations.length
        : 0;
    }

    function option(value, label) {
      const node = document.createElement("option");
      node.value = value;
      node.textContent = label;
      return node;
    }

    function fillFilters() {
      const modes = [...new Set(state.records.map(r => r.mode || "unknown"))].sort();
      const tasks = [...new Set(state.records.map(r => r.task_id || "unknown"))].sort();

      modeFilter.replaceChildren(option("", "All modes"), ...modes.map(v => option(v, v)));
      taskFilter.replaceChildren(option("", "All tasks"), ...tasks.map(v => option(v, v)));
    }

    function applyFilters() {
      const mode = modeFilter.value;
      const task = taskFilter.value;
      const search = searchFilter.value.trim().toLowerCase();

      state.filtered = state.records.filter(record => {
        if (mode && record.mode !== mode) return false;
        if (task && record.task_id !== task) return false;
        if (!search) return true;

        return JSON.stringify(record).toLowerCase().includes(search);
      });

      render();
    }

    function renderCards() {
      const records = state.filtered;
      const input = records.reduce((sum, r) => sum + usage(r, "input_tokens"), 0);
      const output = records.reduce((sum, r) => sum + usage(r, "output_tokens"), 0);
      const total = records.reduce((sum, r) => sum + usage(r, "total_tokens"), 0);
      const tools = records.reduce((sum, r) => sum + Number(r.tool_calls || 0), 0);
      const passed = records.filter(r => r.passed === true).length;

      cards.innerHTML = [
        ["Records", records.length],
        ["Input tokens", nf.format(input)],
        ["Output tokens", nf.format(output)],
        ["Total tokens", nf.format(total)],
        ["Tool calls", nf.format(tools)],
        ["Passed", `${passed}/${records.length}`],
      ].map(([label, value]) => `
        <div class="card">
          <div class="label">${label}</div>
          <div class="value">${value}</div>
        </div>
      `).join("");
    }

    function renderBarChart(svg, rows, valueFn, labelFn, colorFn) {
      const width = 900;
      const height = 330;
      const margin = { top: 20, right: 20, bottom: 95, left: 70 };
      const innerWidth = width - margin.left - margin.right;
      const innerHeight = height - margin.top - margin.bottom;
      const max = Math.max(1, ...rows.map(valueFn));
      const barWidth = innerWidth / Math.max(1, rows.length);

      const bars = rows.map((row, index) => {
        const value = valueFn(row);
        const barHeight = value / max * innerHeight;
        const x = margin.left + index * barWidth + 2;
        const y = margin.top + innerHeight - barHeight;
        const label = labelFn(row);
        const color = colorFn(row, index);

        return `
          <g>
            <title>${label}: ${nf.format(value)}</title>
            <rect x="${x}" y="${y}" width="${Math.max(2, barWidth - 4)}" height="${barHeight}" fill="${color}" rx="3"></rect>
            <text x="${x + Math.max(2, barWidth - 4) / 2}" y="${height - 50}" fill="#8b949e" font-size="10" text-anchor="end" transform="rotate(-45 ${x + Math.max(2, barWidth - 4) / 2},${height - 50})">${escapeHtml(label.slice(0, 28))}</text>
          </g>
        `;
      }).join("");

      const grid = [0, .25, .5, .75, 1].map(t => {
        const y = margin.top + innerHeight - t * innerHeight;
        const label = Math.round(max * t);
        return `
          <line x1="${margin.left}" x2="${width - margin.right}" y1="${y}" y2="${y}" stroke="#30363d"></line>
          <text x="${margin.left - 8}" y="${y + 4}" fill="#8b949e" font-size="11" text-anchor="end">${nf.format(label)}</text>
        `;
      }).join("");

      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.innerHTML = `
        ${grid}
        ${bars}
      `;
    }

    function renderCharts() {
      const rows = state.filtered;

      renderBarChart(
        tokensChart,
        rows,
        record => usage(record, "total_tokens"),
        record => `${record.mode}:${record.task_id}`,
        record => record.mode === "evidence_packet" ? "#3fb950" : "#2f81f7"
      );

      const byMode = [...rows.reduce((map, record) => {
        const key = record.mode || "unknown";
        const current = map.get(key) || { mode: key, input: 0 };
        current.input += usage(record, "input_tokens");
        map.set(key, current);
        return map;
      }, new Map()).values()];

      renderBarChart(
        modeChart,
        byMode,
        row => row.input,
        row => row.mode,
        (_, index) => ["#2f81f7", "#3fb950", "#d29922", "#a371f7"][index % 4]
      );
    }

    function renderTable() {
      recordsBody.innerHTML = state.filtered.map((record, index) => `
        <tr>
          <td>${index + 1}</td>
          <td>${escapeHtml(record.timestamp || "")}</td>
          <td>${escapeHtml(record.mode || "")}</td>
          <td>${escapeHtml(record.task_id || "")}</td>
          <td>${nf.format(usage(record, "input_tokens"))}</td>
          <td>${nf.format(usage(record, "output_tokens"))}</td>
          <td>${nf.format(usage(record, "total_tokens"))}</td>
          <td>${nf.format(Number(record.tool_calls || 0))}</td>
          <td>${nf.format(llmCalls(record))}</td>
          <td class="${record.passed ? "ok" : "fail"}">${record.passed === true ? "true" : "false"}</td>
          <td>${nf.format(Number(record.latency_ms || 0))} ms</td>
          <td>
            <details>
              <summary>JSON</summary>
              <pre>${escapeHtml(JSON.stringify(record, null, 2))}</pre>
            </details>
          </td>
        </tr>
      `).join("");
    }

    function render() {
      renderCards();
      renderCharts();
      renderTable();
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    async function load() {
      const response = await fetch("/api/results");
      const payload = await response.json();
      state.records = payload.records || [];
      state.filtered = state.records;
      fillFilters();
      render();
    }

    modeFilter.addEventListener("change", applyFilters);
    taskFilter.addEventListener("change", applyFilters);
    searchFilter.addEventListener("input", applyFilters);

    load().catch(error => {
      document.body.innerHTML = `<pre>${escapeHtml(error.stack || error)}</pre>`;
    });
  </script>
</body>
</html>
"""


def load_records() -> list[dict]:
    records = []

    if not RESULTS_DIR.exists():
        return records

    for path in sorted(RESULTS_DIR.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    records.append(
                        {
                            "source_file": str(path),
                            "source_line": line_number,
                            "parse_error": str(error),
                            "raw_line": line,
                        }
                    )
                    continue

                record["source_file"] = str(path)
                record["source_line"] = line_number
                records.append(record)

    return records


class DashboardHandler(BaseHTTPRequestHandler):

    def do_HEAD(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_headers(
                content_type="text/html; charset=utf-8",
                content_length=len(HTML.encode("utf-8")),
            )
            return

        if parsed.path == "/api/results":
            body = json.dumps(
                {
                    "records": load_records(),
                },
                ensure_ascii=False,
                default=str,
            ).encode("utf-8")
            self._send_headers(
                content_type="application/json; charset=utf-8",
                content_length=len(body),
            )
            return

        self.send_error(404)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_html(HTML)
            return

        if parsed.path == "/api/results":
            self._send_json(
                {
                    "records": load_records(),
                }
            )
            return

        self.send_error(404)

    def log_message(self, format, *args):
        return

    def _send_html(self, content: str):
        body = content.encode("utf-8")
        self._send_headers(
            content_type="text/html; charset=utf-8",
            content_length=len(body),
        )
        self.wfile.write(body)

    def _send_json(self, payload: dict):
        body = json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        self._send_headers(
            content_type="application/json; charset=utf-8",
            content_length=len(body),
        )
        self.wfile.write(body)

    def _send_headers(
        self,
        content_type: str,
        content_length: int,
    ):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header(
            "Content-Length",
            str(content_length),
        )
        self.end_headers()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer(
        (args.host, args.port),
        DashboardHandler,
    )

    print(
        "Benchmark dashboard running at "
        f"http://{args.host}:{args.port}"
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping benchmark dashboard")


if __name__ == "__main__":
    main()
