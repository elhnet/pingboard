"""FastAPI application with background URL health checker."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

import checker
from db import get_all_urls, get_latest_checks, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stop_event = asyncio.Event()
    task = asyncio.create_task(checker.run_checker(stop_event))
    yield
    stop_event.set()
    await task


app = FastAPI(title="Pingboard", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    urls = get_all_urls()
    results = []
    for url_row in urls:
        checks = get_latest_checks(url_row["id"], n=20)
        latest = None
        if checks:
            c = checks[0]
            latest = {
                "status_code": c["status_code"],
                "latency_ms": c["response_time_ms"],
                "ok": c["status_code"] is not None and 200 <= c["status_code"] < 400,
                "checked_at": c["checked_at"],
            }
        results.append({
            "url": url_row["url"],
            "latest": latest,
            "checks": [
                {
                    "status_code": c["status_code"],
                    "latency_ms": c["response_time_ms"],
                    "ok": c["status_code"] is not None and 200 <= c["status_code"] < 400,
                    "checked_at": c["checked_at"],
                }
                for c in checks
            ],
        })
    return results


DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pingboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #0f1117; color: #e1e4e8; padding: 24px; }
  h1 { font-size: 1.4rem; margin-bottom: 16px; color: #c9d1d9; }
  .meta { font-size: 0.8rem; color: #8b949e; margin-bottom: 16px; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 8px 12px; font-size: 0.75rem; text-transform: uppercase;
       letter-spacing: 0.05em; color: #8b949e; border-bottom: 1px solid #21262d; }
  td { padding: 8px 12px; border-bottom: 1px solid #161b22; font-size: 0.875rem;
       vertical-align: middle; }
  tr:hover { background: #161b22; }
  .url { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .status-ok { color: #3fb950; }
  .status-fail { color: #f85149; }
  .status-none { color: #8b949e; }
  .latency { font-variant-numeric: tabular-nums; }
  .sparkline { display: inline-flex; gap: 2px; align-items: flex-end; }
  .spark-bar { width: 6px; height: 16px; border-radius: 1px; }
  .spark-ok { background: #238636; }
  .spark-fail { background: #da3633; }
  .spark-empty { background: #21262d; }
  #no-data { color: #8b949e; padding: 32px; text-align: center; }
</style>
</head>
<body>
<h1>Pingboard</h1>
<div class="meta">Auto-refreshes every 10s &middot; <span id="updated"></span></div>
<table>
  <thead>
    <tr>
      <th>URL</th>
      <th>Status</th>
      <th>Latency</th>
      <th>Last Checked</th>
      <th>History (last 20)</th>
    </tr>
  </thead>
  <tbody id="tbody"></tbody>
</table>
<div id="no-data">Loading&hellip;</div>
<script>
function render(data) {
  var tbody = document.getElementById("tbody");
  var noData = document.getElementById("no-data");
  if (!data || data.length === 0) {
    tbody.innerHTML = "";
    noData.style.display = "block";
    noData.textContent = "No URLs configured.";
    return;
  }
  noData.style.display = "none";
  var html = "";
  for (var i = 0; i < data.length; i++) {
    var d = data[i];
    var latest = d.latest;
    var statusClass, statusText, latencyText, checkedText;
    if (!latest) {
      statusClass = "status-none";
      statusText = "—";
      latencyText = "—";
      checkedText = "—";
    } else if (latest.ok) {
      statusClass = "status-ok";
      statusText = latest.status_code;
      latencyText = latest.latency_ms != null ? latest.latency_ms.toFixed(0) + " ms" : "—";
      checkedText = fmtTime(latest.checked_at);
    } else {
      statusClass = "status-fail";
      statusText = latest.status_code || "ERR";
      latencyText = latest.latency_ms != null ? latest.latency_ms.toFixed(0) + " ms" : "—";
      checkedText = fmtTime(latest.checked_at);
    }
    // Build sparkline: checks are newest-first, reverse so oldest is left
    var checks = (d.checks || []).slice().reverse();
    var sparks = "";
    for (var j = 0; j < 20; j++) {
      if (j < checks.length) {
        sparks += '<span class="spark-bar ' + (checks[j].ok ? "spark-ok" : "spark-fail") + '"></span>';
      } else {
        sparks += '<span class="spark-bar spark-empty"></span>';
      }
    }
    html += "<tr>"
      + '<td class="url" title="' + esc(d.url) + '">' + esc(d.url) + "</td>"
      + '<td class="' + statusClass + '">' + statusText + "</td>"
      + '<td class="latency">' + latencyText + "</td>"
      + "<td>" + checkedText + "</td>"
      + '<td><span class="sparkline">' + sparks + "</span></td>"
      + "</tr>";
  }
  tbody.innerHTML = html;
}

function fmtTime(iso) {
  if (!iso) return "—";
  var d = new Date(iso + "Z");
  return d.toLocaleTimeString();
}

function esc(s) {
  var el = document.createElement("span");
  el.textContent = s;
  return el.innerHTML;
}

function refresh() {
  fetch("/status")
    .then(function(r) { return r.json(); })
    .then(function(data) {
      render(data);
      document.getElementById("updated").textContent = "Updated " + new Date().toLocaleTimeString();
    })
    .catch(function() {});
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML
