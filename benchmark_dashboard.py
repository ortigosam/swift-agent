import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


RESULTS_DIR = Path("benchmark_results")


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Benchmark Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
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
      --purple: #a371f7;
    }

    * {
      box-sizing: border-box;
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

    h2 {
      margin: 0 0 16px;
      font-size: 18px;
    }

    code {
      color: #79c0ff;
    }

    main {
      padding: 24px;
      display: grid;
      gap: 24px;
    }

    .subtitle,
    .small,
    .muted {
      color: var(--muted);
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
    input,
    button {
      background: var(--panel-2);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      min-width: 180px;
    }

    button {
      min-width: auto;
      cursor: pointer;
    }

    button:hover {
      border-color: var(--accent);
    }

    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 36px;
    }

    .checkbox-label input {
      min-width: auto;
    }

    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
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
      font-size: 24px;
      font-weight: 700;
      margin-top: 6px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
      gap: 24px;
    }

    .panel {
      padding: 18px;
      overflow: auto;
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
      cursor: pointer;
    }

    tr:hover td {
      background: rgba(47, 129, 247, .08);
    }

    .ok {
      color: var(--green);
      font-weight: 700;
    }

    .fail {
      color: var(--red);
      font-weight: 700;
    }

    .warn {
      color: var(--yellow);
      font-weight: 700;
    }

    .pill {
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 2px 8px;
      background: var(--panel-2);
    }

    details {
      max-width: 1100px;
    }

    summary {
      cursor: pointer;
      color: #79c0ff;
    }

    pre {
      background: #010409;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      overflow: auto;
      max-height: 460px;
      white-space: pre-wrap;
      line-height: 1.35;
    }

    .answer {
      max-width: 520px;
      white-space: normal;
    }

    .negative {
      color: var(--green);
    }

    .positive {
      color: var(--red);
    }

    .neutral {
      color: var(--muted);
    }
  </style>
</head>
<body>
  <header>
    <h1>Benchmark Dashboard</h1>
    <div class="subtitle">Results from <code>benchmark_results/*.jsonl</code> and logs from <code>benchmark_results/logs/*.log</code></div>
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
        Result
        <select id="passFilter">
          <option value="">All</option>
          <option value="pass">Passed</option>
          <option value="fail">Failed</option>
          <option value="parse_error">Parse errors</option>
        </select>
      </label>
      <label>
        Search
        <input id="searchFilter" placeholder="task, mode, answer, file...">
      </label>
      <label class="checkbox-label">
        <input id="latestOnlyFilter" type="checkbox" checked>
        Latest per task/mode
      </label>
      <button id="reloadButton" type="button">Reload</button>
    </section>

    <section class="cards" id="cards"></section>

    <section class="grid">
      <div class="panel">
        <h2>Aggregate by mode</h2>
        <table>
          <thead>
            <tr>
              <th>Mode</th>
              <th>Runs</th>
              <th>Passed</th>
              <th>Pass rate</th>
              <th>Task time</th>
              <th>Number of tokens used</th>
              <th>Input tokens</th>
              <th>Output tokens</th>
              <th>Tool calls</th>
              <th>Cost of tokens approx.</th>
            </tr>
          </thead>
          <tbody id="aggregateBody"></tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>Benchmark records</h2>
      <div class="small">Click column headers to sort. Details include answer, evaluation, evidence packet, tool history and raw JSON.</div>
      <table>
        <thead>
          <tr>
            <th data-sort="timestamp">Timestamp</th>
            <th data-sort="source_file">Source</th>
            <th data-sort="mode">Mode</th>
            <th data-sort="task_id">Task</th>
            <th data-sort="category">Category</th>
            <th data-sort="difficulty">Difficulty</th>
            <th data-sort="passed">Passed</th>
            <th data-sort="status">Status</th>
            <th data-sort="task_time_ms">Task time</th>
            <th data-sort="latency_ms">Latency</th>
            <th data-sort="evidence_build_ms">Evidence build</th>
            <th data-sort="total_tokens">Tokens</th>
            <th data-sort="input_tokens">Input</th>
            <th data-sort="output_tokens">Output</th>
            <th data-sort="tool_calls">Tools</th>
            <th data-sort="token_cost">Token cost approx.</th>
            <th data-sort="llm_calls">LLM calls</th>
            <th data-sort="missing_count">Missing</th>
            <th data-sort="evidence_items">Evidence</th>
            <th>Answer / details</th>
          </tr>
        </thead>
        <tbody id="recordsBody"></tbody>
      </table>
    </section>

    <section class="grid">
      <div class="panel">
        <h2>Benchmark log files</h2>
        <table>
          <thead>
            <tr>
              <th>File</th>
              <th>Size</th>
              <th>Modified</th>
              <th>Preview</th>
            </tr>
          </thead>
          <tbody id="logsBody"></tbody>
        </table>
      </div>
      <div class="panel">
        <h2>Selected log tail</h2>
        <pre id="logPreview">Select a log preview.</pre>
      </div>
    </section>
  </main>

  <script>
    const state = {
      records: [],
      logs: [],
      visible: [],
      sortKey: "timestamp",
      sortDirection: "desc"
    };

    const nf = new Intl.NumberFormat();
    const money = new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 6
    });
    const tokenPricesUsdPerMillion = {
      "gpt-5-mini": {
        input: 0.25,
        output: 2.00
      }
    };

    function usage(record, key) {
      return Number(record?.usage?.[key] || 0);
    }

    function totalTokens(record) {
      const total = usage(record, "total_tokens");
      return total || usage(record, "input_tokens") + usage(record, "output_tokens");
    }

    function taskTimeMs(record) {
      const explicit = Number(record.task_time_ms || 0);
      if (explicit) return explicit;
      return Number(record.latency_ms || 0)
        + Number(record.indexed_evidence_build_latency_ms || 0);
    }

    function tokenCost(record) {
      const estimated = Number(record?.usage?.estimated_cost || 0);
      if (estimated) return estimated;

      const recorded = Number(record?.usage?.cost || 0);
      if (recorded) return recorded;

      const model = record.model || "gpt-5-mini";
      const prices = tokenPricesUsdPerMillion[model];
      if (!prices) return 0;

      return (
        usage(record, "input_tokens") / 1_000_000 * prices.input
        + usage(record, "output_tokens") / 1_000_000 * prices.output
      );
    }

    function llmCalls(record) {
      return Array.isArray(record.llm_invocations)
        ? record.llm_invocations.length
        : 0;
    }

    function evidenceItems(record) {
      return Array.isArray(record?.evidence_packet?.items)
        ? record.evidence_packet.items.length
        : 0;
    }

    function evidenceFacts(record) {
      return Array.isArray(record?.evidence_packet?.facts)
        ? record.evidence_packet.facts.length
        : 0;
    }

    function missingCount(record) {
      const evaluation = record.evaluation || {};
      return ["missing_mentions", "missing_files", "missing_symbols"]
        .reduce((sum, key) => sum + (Array.isArray(evaluation[key]) ? evaluation[key].length : 0), 0);
    }

    function sortValue(record, key) {
      if (key === "total_tokens") return totalTokens(record);
      if (key === "input_tokens") return usage(record, "input_tokens");
      if (key === "output_tokens") return usage(record, "output_tokens");
      if (key === "task_time_ms") return taskTimeMs(record);
      if (key === "token_cost") return tokenCost(record);
      if (key === "llm_calls") return llmCalls(record);
      if (key === "missing_count") return missingCount(record);
      if (key === "evidence_items") return evidenceItems(record) + evidenceFacts(record);
      if (key === "evidence_build_ms") return Number(record.indexed_evidence_build_latency_ms || 0);
      return record[key];
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

    function latestRecords(records) {
      const map = new Map();

      for (const record of records) {
        if (record.parse_error) {
          map.set(`parse:${record.source_file}:${record.source_line}`, record);
          continue;
        }

        const key = `${record.task_id || "unknown"}|${record.mode || "unknown"}`;
        const current = map.get(key);

        if (!current || String(record.timestamp || "") >= String(current.timestamp || "")) {
          map.set(key, record);
        }
      }

      return [...map.values()];
    }

    function filteredRecords() {
      const mode = modeFilter.value;
      const task = taskFilter.value;
      const pass = passFilter.value;
      const search = searchFilter.value.trim().toLowerCase();
      const source = latestOnlyFilter.checked
        ? latestRecords(state.records)
        : [...state.records];

      return source.filter(record => {
        if (mode && record.mode !== mode) return false;
        if (task && record.task_id !== task) return false;
        if (pass === "pass" && record.passed !== true) return false;
        if (pass === "fail" && record.passed !== false) return false;
        if (pass === "parse_error" && !record.parse_error) return false;
        if (!search) return true;

        return JSON.stringify(record).toLowerCase().includes(search);
      });
    }

    function applyFilters() {
      const direction = state.sortDirection === "asc" ? 1 : -1;
      state.visible = filteredRecords().sort((a, b) => {
        const av = sortValue(a, state.sortKey);
        const bv = sortValue(b, state.sortKey);

        if (typeof av === "number" || typeof bv === "number") {
          return (Number(av || 0) - Number(bv || 0)) * direction;
        }

        return String(av || "").localeCompare(String(bv || "")) * direction;
      });

      render();
    }

    function renderCards() {
      const records = state.visible.filter(r => !r.parse_error);
      const input = records.reduce((sum, r) => sum + usage(r, "input_tokens"), 0);
      const output = records.reduce((sum, r) => sum + usage(r, "output_tokens"), 0);
      const total = records.reduce((sum, r) => sum + totalTokens(r), 0);
      const tools = records.reduce((sum, r) => sum + Number(r.tool_calls || 0), 0);
      const passed = records.filter(r => r.passed === true).length;
      const latency = records.reduce((sum, r) => sum + Number(r.latency_ms || 0), 0);
      const avgLatency = records.length ? Math.round(latency / records.length) : 0;

      cards.innerHTML = [
        ["Visible records", state.visible.length],
        ["Passed", `${passed}/${records.length}`],
        ["Pass rate", records.length ? `${((passed / records.length) * 100).toFixed(1)}%` : "0.0%"],
        ["Avg latency", `${nf.format(avgLatency)} ms`],
        ["Total tokens", nf.format(total)],
        ["Input tokens", nf.format(input)],
        ["Output tokens", nf.format(output)],
        ["Tool calls", nf.format(tools)],
      ].map(([label, value]) => `
        <div class="card">
          <div class="label">${label}</div>
          <div class="value">${value}</div>
        </div>
      `).join("");
    }

    function groupedBy(records, keyFn) {
      return records.reduce((map, record) => {
        const key = keyFn(record);
        const values = map.get(key) || [];
        values.push(record);
        map.set(key, values);
        return map;
      }, new Map());
    }

    function renderAggregate() {
      const records = state.visible.filter(r => !r.parse_error);
      const rows = [...groupedBy(
        records,
        r => r.mode || "unknown"
      ).entries()].sort(([a], [b]) => a.localeCompare(b));

      aggregateBody.innerHTML = rows.map(([mode, records]) => {
        const runs = records.length;
        const passed = records.filter(r => r.passed === true).length;
        const modePassRate = passRate(records);
        const taskTime = records.reduce((sum, r) => sum + taskTimeMs(r), 0);
        const tokenTotal = records.reduce((sum, r) => sum + totalTokens(r), 0);
        const inputTokens = records.reduce((sum, r) => sum + usage(r, "input_tokens"), 0);
        const outputTokens = records.reduce((sum, r) => sum + usage(r, "output_tokens"), 0);
        const tokenCostTotal = records.reduce((sum, r) => sum + tokenCost(r), 0);
        const tools = records.reduce((sum, r) => sum + Number(r.tool_calls || 0), 0);

        return `
          <tr>
            <td><span class="pill">${escapeHtml(mode)}</span></td>
            <td>${runs}</td>
            <td class="${passed === runs ? "ok" : "warn"}">${passed}/${runs}</td>
            <td>${(modePassRate * 100).toFixed(1)}%</td>
            <td>
              <strong>${nf.format(taskTime)} ms total</strong>
              <br><span class="small">${nf.format(Math.round(taskTime / Math.max(1, runs)))} ms avg</span>
              ${taskTimeList(records)}
            </td>
            <td>${nf.format(tokenTotal)}</td>
            <td>${nf.format(inputTokens)}</td>
            <td>${nf.format(outputTokens)}</td>
            <td>${nf.format(tools)}</td>
            <td>${money.format(tokenCostTotal)}</td>
          </tr>
        `;
      }).join("");
    }

    function passRate(records) {
      if (!records.length) return 0;
      return records.filter(r => r.passed === true).length / records.length;
    }

    function taskTimeList(records) {
      return records
        .slice()
        .sort((a, b) => String(a.task_id || "").localeCompare(String(b.task_id || "")))
        .map(record => {
          const agentLatency = Number(record.latency_ms || 0);
          const buildLatency = record.indexed_evidence_build_latency_ms === null || record.indexed_evidence_build_latency_ms === undefined
            ? ""
            : `, build ${nf.format(Number(record.indexed_evidence_build_latency_ms || 0))} ms`;

          return `
            <div>
              <code>${escapeHtml(record.task_id || "unknown")}</code>:
              ${nf.format(taskTimeMs(record))} ms
              <span class="small">(agent ${nf.format(agentLatency)} ms${buildLatency})</span>
            </div>
          `;
        })
        .join("");
    }

    function renderComparison() {
      const records = state.visible.filter(r => !r.parse_error);
      const byTask = groupedBy(records, r => r.task_id || "unknown");
      const rows = [];

      for (const [task, taskRecords] of byTask.entries()) {
        const baseline = taskRecords.find(r => r.mode === "baseline");
        const chunking = taskRecords.find(r => r.mode === "evidence_packet");
        const embeddings = taskRecords.find(r => r.mode === "evidence_packet_vector");

        if (!baseline || (!chunking && !embeddings)) continue;

        rows.push({ task, baseline, chunking, embeddings });
      }

      comparisonBody.innerHTML = rows.sort((a, b) => a.task.localeCompare(b.task)).map(row => {
        const chunkLatencyDelta = row.chunking
          ? Number(row.chunking.latency_ms || 0) - Number(row.baseline.latency_ms || 0)
          : null;
        const embeddingLatencyDelta = row.embeddings
          ? Number(row.embeddings.latency_ms || 0) - Number(row.baseline.latency_ms || 0)
          : null;
        const chunkTokenDelta = row.chunking
          ? totalTokens(row.chunking) - totalTokens(row.baseline)
          : null;
        const embeddingTokenDelta = row.embeddings
          ? totalTokens(row.embeddings) - totalTokens(row.baseline)
          : null;
        const chunkBuild = row.chunking
          ? Number(row.chunking.indexed_evidence_build_latency_ms || 0)
          : null;
        const embeddingBuild = row.embeddings
          ? Number(row.embeddings.indexed_evidence_build_latency_ms || 0)
          : null;
        const chunkMissingDelta = row.chunking
          ? missingCount(row.chunking) - missingCount(row.baseline)
          : null;
        const embeddingMissingDelta = row.embeddings
          ? missingCount(row.embeddings) - missingCount(row.baseline)
          : null;

        return `
          <tr>
            <td>${escapeHtml(row.task)}</td>
            <td class="${row.baseline.passed ? "ok" : "fail"}">${row.baseline.passed ? "pass" : "fail"}</td>
            ${statusCell(row.chunking)}
            ${statusCell(row.embeddings)}
            ${deltaCell(chunkLatencyDelta, " ms")}
            ${deltaCell(embeddingLatencyDelta, " ms")}
            ${deltaCell(chunkBuild, " ms")}
            ${deltaCell(embeddingBuild, " ms")}
            ${deltaCell(chunkTokenDelta)}
            ${deltaCell(embeddingTokenDelta)}
            <td>
              chunking: ${formatNullableDelta(chunkMissingDelta)}
              <br>
              embeddings: ${formatNullableDelta(embeddingMissingDelta)}
            </td>
          </tr>
        `;
      }).join("");
    }

    function renderRecords() {
      recordsBody.innerHTML = state.visible.map(record => {
        if (record.parse_error) {
          return `
            <tr>
              <td></td>
              <td>${escapeHtml(record.source_file || "")}:${record.source_line || ""}</td>
              <td colspan="17" class="fail">Parse error: ${escapeHtml(record.parse_error)}</td>
              <td><pre>${escapeHtml(record.raw_line || "")}</pre></td>
            </tr>
          `;
        }

        const missing = missingCount(record);
        const evidence = `${evidenceItems(record)} items / ${evidenceFacts(record)} facts`;

        return `
          <tr>
            <td>${escapeHtml(record.timestamp || "")}</td>
            <td>${escapeHtml(shortSource(record))}</td>
            <td><span class="pill">${escapeHtml(record.mode || "")}</span></td>
            <td>${escapeHtml(record.task_id || "")}</td>
            <td>${escapeHtml(record.category || "")}</td>
            <td>${escapeHtml(record.difficulty || "")}</td>
            <td class="${record.passed ? "ok" : "fail"}">${record.passed === true ? "pass" : "fail"}</td>
            <td>${escapeHtml(record.status || "")}</td>
            <td>${nf.format(taskTimeMs(record))} ms</td>
            <td>${nf.format(Number(record.latency_ms || 0))} ms</td>
            <td>${record.indexed_evidence_build_latency_ms === null || record.indexed_evidence_build_latency_ms === undefined ? "n/a" : nf.format(Number(record.indexed_evidence_build_latency_ms || 0)) + " ms"}</td>
            <td>${nf.format(totalTokens(record))}</td>
            <td>${nf.format(usage(record, "input_tokens"))}</td>
            <td>${nf.format(usage(record, "output_tokens"))}</td>
            <td>${nf.format(Number(record.tool_calls || 0))}</td>
            <td>${money.format(tokenCost(record))}</td>
            <td>${nf.format(llmCalls(record))}</td>
            <td class="${missing ? "fail" : "ok"}">${missing}</td>
            <td>${evidence}</td>
            <td class="answer">
              <details>
                <summary>${escapeHtml(answerPreview(record.answer || ""))}</summary>
                <h3>Answer</h3>
                <pre>${escapeHtml(record.answer || "")}</pre>
                <h3>Evaluation</h3>
                <pre>${escapeHtml(JSON.stringify(record.evaluation || {}, null, 2))}</pre>
                <h3>Expected</h3>
                <pre>${escapeHtml(JSON.stringify(record.expected || {}, null, 2))}</pre>
                <h3>Evidence packet</h3>
                <pre>${escapeHtml(JSON.stringify(record.evidence_packet || null, null, 2))}</pre>
                <h3>Tool history</h3>
                <pre>${escapeHtml(JSON.stringify(record.tool_history || [], null, 2))}</pre>
                <h3>Raw JSON</h3>
                <pre>${escapeHtml(JSON.stringify(record, null, 2))}</pre>
              </details>
            </td>
          </tr>
        `;
      }).join("");
    }

    function renderLogs() {
      logsBody.innerHTML = state.logs.map(log => `
        <tr>
          <td>${escapeHtml(log.name)}</td>
          <td>${nf.format(log.size_bytes)} bytes</td>
          <td>${escapeHtml(log.modified_at)}</td>
          <td><button type="button" data-log="${escapeHtml(log.name)}">Show tail</button></td>
        </tr>
      `).join("");

      logsBody.querySelectorAll("button[data-log]").forEach(button => {
        button.addEventListener("click", () => loadLogTail(button.dataset.log));
      });
    }

    function render() {
      renderCards();
      renderAggregate();
      renderRecords();
      renderLogs();
    }

    function formatDelta(value) {
      return `${value >= 0 ? "+" : ""}${nf.format(value)}`;
    }

    function deltaClass(value) {
      if (value < 0) return "negative";
      if (value > 0) return "positive";
      return "neutral";
    }

    function statusCell(record) {
      if (!record) return `<td class="neutral">n/a</td>`;
      return `<td class="${record.passed ? "ok" : "fail"}">${record.passed ? "pass" : "fail"}</td>`;
    }

    function deltaCell(value, suffix = "") {
      if (value === null) return `<td class="neutral">n/a</td>`;
      return `<td class="${deltaClass(value)}">${formatDelta(value)}${suffix}</td>`;
    }

    function formatNullableDelta(value) {
      return value === null ? "n/a" : formatDelta(value);
    }

    function shortSource(record) {
      const file = record.source_file || "";
      const line = record.source_line || "";
      return `${file.replace(/^.*benchmark_results\//, "")}${line ? ":" + line : ""}`;
    }

    function answerPreview(answer) {
      const compact = String(answer || "").replace(/\s+/g, " ").trim();
      return compact ? compact.slice(0, 90) : "Details";
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    async function loadLogTail(name) {
      const response = await fetch(`/api/log-tail?name=${encodeURIComponent(name)}&lines=240`);
      const payload = await response.json();
      logPreview.textContent = payload.content || payload.error || "No log content.";
    }

    async function load() {
      const [resultsResponse, logsResponse] = await Promise.all([
        fetch("/api/results"),
        fetch("/api/logs")
      ]);
      const resultsPayload = await resultsResponse.json();
      const logsPayload = await logsResponse.json();
      state.records = resultsPayload.records || [];
      state.logs = logsPayload.logs || [];
      fillFilters();
      applyFilters();

      if (state.logs[0]) {
        await loadLogTail(state.logs[0].name);
      }
    }

    modeFilter.addEventListener("change", applyFilters);
    taskFilter.addEventListener("change", applyFilters);
    passFilter.addEventListener("change", applyFilters);
    searchFilter.addEventListener("input", applyFilters);
    latestOnlyFilter.addEventListener("change", applyFilters);
    reloadButton.addEventListener("click", load);

    document.querySelectorAll("th[data-sort]").forEach(th => {
      th.addEventListener("click", () => {
        const key = th.dataset.sort;
        if (state.sortKey === key) {
          state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
        } else {
          state.sortKey = key;
          state.sortDirection = "asc";
        }
        applyFilters();
      });
    });

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


def load_logs() -> list[dict]:
    logs_dir = RESULTS_DIR / "logs"

    if not logs_dir.exists():
        return []

    logs = []

    for path in sorted(
        logs_dir.glob("*.log"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        stat = path.stat()
        logs.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )

    return logs


def read_log_tail(
    name: str,
    lines: int,
) -> str:
    logs_dir = (RESULTS_DIR / "logs").resolve()
    path = (logs_dir / name).resolve()

    if logs_dir not in path.parents or path.suffix != ".log":
        raise ValueError("Invalid log path.")

    if not path.exists():
        raise FileNotFoundError(name)

    with path.open("r", encoding="utf-8", errors="replace") as file:
        return "".join(file.readlines()[-lines:])


class DashboardHandler(BaseHTTPRequestHandler):

    def do_HEAD(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_headers(
                content_type="text/html; charset=utf-8",
                content_length=len(HTML.encode("utf-8")),
            )
            return

        if parsed.path in {
            "/api/results",
            "/api/logs",
            "/api/log-tail",
        }:
            self._send_headers(
                content_type="application/json; charset=utf-8",
                content_length=0,
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

        if parsed.path == "/api/logs":
            self._send_json(
                {
                    "logs": load_logs(),
                }
            )
            return

        if parsed.path == "/api/log-tail":
            self._send_log_tail(parsed.query)
            return

        self.send_error(404)

    def log_message(self, format, *args):
        return

    def _send_log_tail(
        self,
        query: str,
    ):
        params = parse_qs(query)
        name = params.get("name", [""])[0]
        lines = int(params.get("lines", ["240"])[0])

        try:
            content = read_log_tail(
                name=name,
                lines=max(
                    1,
                    min(
                        lines,
                        2000,
                    ),
                ),
            )
        except (FileNotFoundError, ValueError) as error:
            self._send_json(
                {
                    "error": str(error),
                }
            )
            return

        self._send_json(
            {
                "name": name,
                "content": content,
            }
        )

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
    global RESULTS_DIR

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument(
        "--results-dir",
        default=str(RESULTS_DIR),
        help="Directory containing benchmark JSONL files and logs/.",
    )
    args = parser.parse_args()

    RESULTS_DIR = Path(args.results_dir)

    server = ThreadingHTTPServer(
        (args.host, args.port),
        DashboardHandler,
    )

    print(
        "Benchmark dashboard running at "
        f"http://{args.host}:{args.port}"
    )
    print(f"Reading benchmark data from {RESULTS_DIR.resolve()}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping benchmark dashboard")


if __name__ == "__main__":
    main()
