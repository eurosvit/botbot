"""HTML-шаблон дашборда торгівлі (окремо, щоб не засмічувати web.py)."""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Торговий дашборд</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📈</text></svg>">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background:#0e1116; color:#e6edf3; }
  header { padding:16px 24px; border-bottom:1px solid #222b36; display:flex;
           align-items:center; gap:16px; flex-wrap:wrap; }
  h1 { font-size:18px; margin:0; }
  .badge { padding:2px 10px; border-radius:999px; font-size:12px; font-weight:600;
           background:#1f6feb33; color:#79c0ff; }
  .wrap { padding:24px; max-width:1100px; margin:0 auto; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }
  .card { background:#161b22; border:1px solid #222b36; border-radius:12px; padding:16px; }
  .card .label { font-size:12px; color:#8b949e; text-transform:uppercase; letter-spacing:.04em; }
  .card .value { font-size:24px; font-weight:700; margin-top:6px; }
  .pos { color:#3fb950; } .neg { color:#f85149; }
  .panel { background:#161b22; border:1px solid #222b36; border-radius:12px;
           padding:16px; margin-top:20px; }
  canvas { width:100% !important; max-height:320px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { text-align:right; padding:8px 10px; border-bottom:1px solid #222b36; }
  th:first-child, td:first-child { text-align:left; }
  th { color:#8b949e; font-weight:600; }
  .muted { color:#8b949e; font-size:12px; }
  .empty { color:#8b949e; padding:24px; text-align:center; }
  .optbar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-top:10px; }
  .optbar input, .optbar select { background:#0e1116; color:#e6edf3; border:1px solid #2b3947;
      border-radius:8px; padding:8px 10px; font-size:13px; }
  .optbar button { background:#1f6feb; color:#fff; border:0; border-radius:8px; padding:8px 16px;
      font-size:13px; font-weight:600; cursor:pointer; }
  .optbar button:disabled { opacity:.5; cursor:default; }
  tr.best td { background:#1f6feb22; }
</style>
</head>
<body>
<header>
  <h1>🤖 Торговий дашборд</h1>
  <span class="badge" id="mode">…</span>
  <span class="muted" id="meta"></span>
  <span class="muted" id="updated" style="margin-left:auto"></span>
</header>
<div class="wrap">
  <div class="cards" id="cards"></div>

  <div class="panel">
    <div class="label muted">Крива капіталу</div>
    <canvas id="equityChart"></canvas>
  </div>

  <div class="panel">
    <div class="label muted">Підбір параметрів (оптимізація на історії)</div>
    <div class="optbar">
      <input id="optSymbol" placeholder="BTC/USDT" value="BTC/USDT">
      <select id="optStrategy">
        <option value="ema_rsi">ema_rsi</option>
        <option value="macd">macd</option>
        <option value="bollinger">bollinger</option>
        <option value="donchian">donchian</option>
      </select>
      <select id="optMarket">
        <option value="spot">spot (long)</option>
        <option value="swap">swap (long+short)</option>
      </select>
      <input id="optCandles" type="number" value="400" title="к-сть свічок" style="width:90px">
      <button id="optBtn" onclick="runOptimize()">Підібрати ▶</button>
      <span class="muted" id="optStatus"></span>
    </div>
    <table id="optTable" style="margin-top:12px">
      <thead><tr>
        <th>score</th><th>дохід%</th><th>B&amp;H%</th><th>просадка%</th>
        <th>win%</th><th>угод</th><th>параметри</th>
      </tr></thead>
      <tbody><tr><td colspan="7" class="empty">натисни «Підібрати», щоб прогнати оптимізацію</td></tr></tbody>
    </table>
  </div>

  <div class="panel">
    <div class="label muted">Останні закриті угоди</div>
    <table id="tradesTable">
      <thead><tr>
        <th>Пара</th><th>К-сть</th><th>Вхід</th><th>Вихід</th>
        <th>PnL</th><th>%</th><th>Причина</th><th>Закрито</th>
      </tr></thead>
      <tbody><tr><td colspan="8" class="empty">завантаження…</td></tr></tbody>
    </table>
  </div>
  <p class="muted">Оновлюється автоматично кожні 15 c. Дані: paper/live режим бота.</p>
</div>

<script>
const fmt = (n, d=2) => (n===null||n===undefined||isNaN(n)) ? "—" : Number(n).toLocaleString("uk-UA",{minimumFractionDigits:d,maximumFractionDigits:d});
const cls = n => n>0 ? "pos" : n<0 ? "neg" : "";
let chart;

async function load() {
  try {
    const [st, eq, tr] = await Promise.all([
      fetch("status").then(r=>r.json()),
      fetch("equity.json").then(r=>r.json()),
      fetch("trades.json").then(r=>r.json()),
    ]);
    renderHeader(st);
    renderCards(st, eq);
    renderChart(eq);
    renderTrades(tr);
    document.getElementById("updated").textContent = "оновлено " + new Date().toLocaleTimeString("uk-UA");
  } catch(e) {
    document.getElementById("meta").textContent = "помилка завантаження: " + e;
  }
}

function renderHeader(st) {
  document.getElementById("mode").textContent = (st.mode||"?").toUpperCase();
  document.getElementById("meta").textContent =
    `${st.exchange||""} · ${(st.symbols||[]).join(", ")} · ${st.timeframe||""}`;
}

function renderCards(st, eq) {
  const start = eq.length ? eq[0].equity : null;
  const cur = st.equity;
  const retPct = (start && cur) ? (cur/start-1)*100 : null;
  const cards = [
    {label:"Капітал", value: fmt(cur), c:""},
    {label:"Дохідність", value: retPct===null?"—":(retPct>0?"+":"")+fmt(retPct)+"%", c:cls(retPct)},
    {label:"PnL сьогодні", value:(st.pnl_today>0?"+":"")+fmt(st.pnl_today), c:cls(st.pnl_today)},
    {label:"Реалізований PnL", value:(st.total_realized_pnl>0?"+":"")+fmt(st.total_realized_pnl), c:cls(st.total_realized_pnl)},
    {label:"Закритих угод", value: st.closed_trades ?? 0, c:""},
    {label:"Відкритих позицій", value:(st.open_positions||[]).length, c:""},
  ];
  document.getElementById("cards").innerHTML = cards.map(c =>
    `<div class="card"><div class="label">${c.label}</div><div class="value ${c.c}">${c.value}</div></div>`
  ).join("");
}

function renderChart(eq) {
  const labels = eq.map(p => new Date(p.ts).toLocaleString("uk-UA",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}));
  const data = eq.map(p => p.equity);
  const ctx = document.getElementById("equityChart");
  if (chart) { chart.data.labels=labels; chart.data.datasets[0].data=data; chart.update(); return; }
  chart = new Chart(ctx, {
    type:"line",
    data:{ labels, datasets:[{ label:"Капітал", data, borderColor:"#3fb950",
      backgroundColor:"#3fb95022", fill:true, tension:.25, pointRadius:0, borderWidth:2 }]},
    options:{ responsive:true, plugins:{legend:{display:false}},
      scales:{ x:{ ticks:{color:"#8b949e",maxTicksLimit:8}, grid:{color:"#222b36"} },
               y:{ ticks:{color:"#8b949e"}, grid:{color:"#222b36"} } } }
  });
}

function renderTrades(tr) {
  const tb = document.querySelector("#tradesTable tbody");
  if (!tr.length) { tb.innerHTML = `<tr><td colspan="8" class="empty">ще немає закритих угод</td></tr>`; return; }
  tb.innerHTML = tr.map(t => `<tr>
    <td>${t.symbol}</td><td>${fmt(t.qty,4)}</td><td>${fmt(t.entry_price)}</td>
    <td>${fmt(t.exit_price)}</td>
    <td class="${cls(t.pnl)}">${(t.pnl>0?"+":"")+fmt(t.pnl)}</td>
    <td class="${cls(t.pnl_pct)}">${(t.pnl_pct>0?"+":"")+fmt(t.pnl_pct)}%</td>
    <td>${t.reason_close||""}</td>
    <td>${t.closed_at ? new Date(t.closed_at).toLocaleString("uk-UA",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}) : ""}</td>
  </tr>`).join("");
}

async function runOptimize() {
  const btn = document.getElementById("optBtn");
  const status = document.getElementById("optStatus");
  const tb = document.querySelector("#optTable tbody");
  const symbol = document.getElementById("optSymbol").value.trim() || "BTC/USDT";
  const strategy = document.getElementById("optStrategy").value;
  const market = document.getElementById("optMarket").value;
  const candles = document.getElementById("optCandles").value || 800;
  const shorts = market === "swap" ? "true" : "false";
  btn.disabled = true; status.textContent = "виконується… (тягне історію + багато бектестів)";
  tb.innerHTML = `<tr><td colspan="7" class="empty">рахуємо…</td></tr>`;
  try {
    const q = new URLSearchParams({symbol, strategy, candles, market_type:market, allow_shorts:shorts});
    const r = await fetch("optimize.json?" + q.toString());
    const d = await r.json();
    if (d.status === "error") throw new Error(d.message);
    if (!d.results || !d.results.length) { tb.innerHTML = `<tr><td colspan="7" class="empty">немає результатів</td></tr>`; }
    else {
      tb.innerHTML = d.results.map((x,i) => `<tr class="${i===0?'best':''}">
        <td>${x.score===null?'—':fmt(x.score)}</td>
        <td class="${cls(x.total_return_pct)}">${(x.total_return_pct>0?'+':'')+fmt(x.total_return_pct)}</td>
        <td>${(x.buy_hold_return_pct>0?'+':'')+fmt(x.buy_hold_return_pct)}</td>
        <td>${fmt(x.max_drawdown_pct)}</td>
        <td>${fmt(x.win_rate,1)}</td>
        <td>${x.trades}</td>
        <td style="text-align:left">${Object.entries(x.params).map(([k,v])=>k+'='+v).join(' ')}</td>
      </tr>`).join("");
    }
    status.textContent = `${d.symbol} · ${d.strategy} · ${d.candles} свічок`;
  } catch(e) {
    tb.innerHTML = `<tr><td colspan="7" class="empty">помилка: ${e.message||e}</td></tr>`;
    status.textContent = "";
  } finally { btn.disabled = false; }
}

load();
setInterval(load, 15000);
</script>
</body>
</html>
"""
