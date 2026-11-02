// Results panel: win/tie/lose bar, equity with confidence interval, plain-language
// explanation and a 13x13 heatmap of the hero's equity against each hand class.

const $ = (id) => document.getElementById(id);
const pct = (x, digits = 1) => `${(100 * x).toFixed(digits)}%`;
const GRID_RANKS = "AKQJT98765432";

function gridLabels() {
  const labels = [];
  for (let i = 0; i < 13; i++) {
    for (let j = 0; j < 13; j++) {
      const a = GRID_RANKS[Math.min(i, j)];
      const b = GRID_RANKS[Math.max(i, j)];
      labels.push(i === j ? a + b : a + b + (j > i ? "s" : "o"));
    }
  }
  return labels;
}

export function renderStatus(kind, text) {
  const el = $("results-status");
  el.className = `status status--${kind}`;
  el.textContent = text;
  el.hidden = !text;
}

export function markStale() {
  const body = $("results-body");
  if (!body.hidden) {
    body.classList.add("is-stale");
    renderStatus("info", "Inputs changed: click Analyse to update the results.");
  }
}

export function renderEquity(r) {
  const body = $("results-body");
  body.hidden = false;
  body.classList.remove("is-stale");

  $("bar-win").style.width = pct(r.win, 3);
  $("bar-tie").style.width = pct(r.tie, 3);
  $("bar-lose").style.width = pct(r.lose, 3);
  $("p-win").textContent = pct(r.win);
  $("p-tie").textContent = pct(r.tie);
  $("p-lose").textContent = pct(r.lose);

  $("v-equity").textContent = pct(r.equity);
  const exact = r.method === "exact";
  $("v-ci").textContent = exact
    ? "exact: no sampling error"
    : `95% CI ${pct(r.ci95[0])} – ${pct(r.ci95[1])}`;

  const n = r.n.toLocaleString("en");
  const secs = (r.elapsed_ms / 1000).toFixed(2);
  $("method-info").textContent = exact
    ? `Exact enumeration: every opponent hand and every remaining board, ${n} showdowns in ${secs} s.`
    : `Monte Carlo: ${n} random deals in ${secs} s · standard error ${pct(r.std_error, 2)} · seed ${r.seed} (enter it in the settings to reproduce this exact result).`;

  $("explain").textContent = explain(r);
  renderHeatmap(r.by_class);
  renderStatus("ok", "");
}

function explain(r) {
  const combos = Number.isInteger(r.live_combos) ? r.live_combos : r.live_combos.toFixed(1);
  const sorted = [...r.by_class].sort((a, b) => b.share * (1 - b.equity) - a.share * (1 - a.equity));
  const worst = sorted.slice(0, 3).filter((c) => c.equity < 0.5).map((c) => c.label);
  let text =
    `Against the ${combos} opponent hands you assumed, you would win ${pct(r.win, 0)} of showdowns ` +
    `and split ${pct(r.tie, 0)}, so on average you collect ${pct(r.equity)} of the pot.`;
  if (worst.length) text += ` Most of your losses come from ${worst.join(", ")}.`;
  text += " This assumes the hand goes to showdown with no more betting; pot odds and EV follow in M5.";
  return text;
}

function renderHeatmap(byClass) {
  const map = new Map(byClass.map((c) => [c.label, c]));
  const box = $("heatmap");
  box.innerHTML = "";
  for (const label of gridLabels()) {
    const cell = document.createElement("div");
    cell.className = "hcell";
    cell.textContent = label;
    const c = map.get(label);
    if (c) {
      cell.classList.add("hcell--in");
      // 0% -> red (hue 5), 50% -> amber, 100% -> green (hue 140)
      const hue = 5 + 135 * c.equity;
      cell.style.background = `hsl(${hue} 55% 55%)`;
      cell.title = `${label}: ${pct(c.share)} of the range · your equity ${pct(c.equity)} (win ${pct(c.win)}, split ${pct(c.tie)})`;
    }
    box.appendChild(cell);
  }
}
