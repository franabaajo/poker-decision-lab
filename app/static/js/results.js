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

export function renderAnalysis(r) {
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

  renderDecision(r);
  $("explain-range").textContent = explainRange(r);
  renderHeatmap(r.by_class);
  renderStatus("ok", "");
}

const chips = (x, signed = false) => {
  const v = Math.round(x * 10) / 10;
  const text = Math.abs(v).toLocaleString("en", { maximumFractionDigits: 1 });
  return `${signed ? (v > 0 ? "+" : v < 0 ? "−" : "") : v < 0 ? "−" : ""}${text}`;
};

function renderDecision(r) {
  const d = r.decision;
  $("v-be").textContent = pct(d.break_even_equity);
  $("v-odds").textContent = `pot odds ${d.pot_odds.toFixed(1)} : 1 · call ${chips(d.call)} to win ${chips(d.final_pot - d.call)}`;
  const ms = r.multi_street;
  if (ms?.available) {
    $("v-ev").textContent = `${chips(ms.ev_call, true)} chips`;
    $("v-ev-sub").innerHTML =
      "with turn &amp; river betting<br>" + `${chips(d.ev_call, true)} chips if nobody bets again`;
  } else {
    $("v-ev").textContent = `${chips(d.ev_call, true)} chips`;
    $("v-ev-sub").textContent =
      r.method === "exact"
        ? "showdown only, exact"
        : `showdown only · 95% CI ${chips(d.ev_call_ci95[0], true)} to ${chips(d.ev_call_ci95[1], true)}`;
  }
  const verdict = $("v-verdict");
  verdict.textContent = d.verdict_label;
  verdict.className = `stat__value verdict--${d.verdict}`;
  const m = 100 * (ms?.available ? ms.realized_equity - d.break_even_equity : d.margin);
  $("v-margin").textContent =
    `${ms?.available ? "realised " : ""}equity ${m >= 0 ? "+" : "−"}${Math.abs(m).toFixed(1)} pts vs break-even`;
  $("explain").textContent = d.explanation;
  renderAfterCall(r);
  renderEvChart(r);
}

function renderAfterCall(r) {
  const ms = r.multi_street;
  const box = $("after-call");
  if (!ms?.available || ms.later_streets === 0 || (ms.stats.bet_turn === 0 && ms.stats.bet_river === 0)) {
    box.hidden = !ms || ms.available; // show the note (e.g. preflop) when not available
    $("after-call-list").innerHTML = "";
    $("realization").textContent = ms?.available ? "" : ms?.note ?? "";
    return;
  }
  box.hidden = false;
  const s = ms.stats;
  const rows = [];
  if (ms.later_streets === 2) {
    rows.push(["Opponent bets the turn", s.bet_turn]);
    rows.push(["You fold on the turn", s.fold_turn]);
  }
  rows.push(["Opponent bets the river", s.bet_river]);
  rows.push(["You fold on the river", s.fold_river]);
  rows.push(["The hand reaches showdown", s.showdown]);
  $("after-call-list").innerHTML = rows
    .map(([label, p]) => `<li><span>${label}</span><b>${pct(p, 0)}</b></li>`)
    .join("");
  $("realization").textContent =
    `You realise ${pct(ms.realization, 0)} of your raw equity (${pct(ms.realized_equity)} instead of ${pct(r.equity)}). ` +
    `Probabilities are for the hand after you call, with the opponent's ${ms.strategy.name.toLowerCase()} betting style and your best responses.`;
}

function explainRange(r) {
  const sorted = [...r.by_class].sort((a, b) => b.share * (1 - b.equity) - a.share * (1 - a.equity));
  const worst = sorted.slice(0, 3).filter((c) => c.equity < 0.5).map((c) => c.label);
  const best = [...r.by_class]
    .sort((a, b) => b.share * b.equity - a.share * a.equity)
    .slice(0, 3)
    .filter((c) => c.equity > 0.5)
    .map((c) => c.label);
  const parts = [];
  if (worst.length) parts.push(`Most of your losses come from ${worst.join(", ")}`);
  if (best.length) parts.push(`most of your wins from ${best.join(", ")}`);
  return parts.length ? parts.join("; ") + "." : "";
}

function renderEvChart(r) {
  const d = r.decision;
  const W = 420, H = 190, L = 48, R = 12, T = 12, B = 30;
  const lo = -d.call, hi = d.final_pot - d.call; // EV at equity 0 and 1
  const x = (e) => L + e * (W - L - R);
  const y = (v) => T + ((hi - v) / (hi - lo)) * (H - T - B);
  const be = d.break_even_equity;
  const [cl, ch] = r.ci95;
  const fmt = (v) => chips(v, true);
  $("ev-chart").innerHTML = `
  <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Call EV rises linearly from ${fmt(lo)} chips at 0% equity to ${fmt(hi)} chips at 100%, crossing zero at ${pct(be)}. Your equity is ${pct(r.equity)}.">
    <polygon class="loss" points="${x(0)},${y(0)} ${x(0)},${y(lo)} ${x(be)},${y(0)}"/>
    <polygon class="gain" points="${x(be)},${y(0)} ${x(1)},${y(hi)} ${x(1)},${y(0)}"/>
    <line class="axis" x1="${L}" y1="${T}" x2="${L}" y2="${H - B}"/>
    <line class="zero" x1="${L}" y1="${y(0)}" x2="${W - R}" y2="${y(0)}"/>
    <line class="be" x1="${x(be)}" y1="${T}" x2="${x(be)}" y2="${H - B}"/>
    <line class="ev-line" x1="${x(0)}" y1="${y(lo)}" x2="${x(1)}" y2="${y(hi)}"/>
    ${ch > cl ? `<line class="ci" x1="${x(cl)}" y1="${y(d.ev_call_ci95[0])}" x2="${x(ch)}" y2="${y(d.ev_call_ci95[1])}"/>` : ""}
    <circle class="dot" cx="${x(r.equity)}" cy="${y(d.ev_call)}" r="5"/>
    ${r.multi_street?.available && Math.abs(r.multi_street.ev_call - d.ev_call) > 0.05
      ? `<circle class="dot dot--real" cx="${x(Math.min(1, Math.max(0, r.multi_street.realized_equity)))}" cy="${y(Math.min(hi, Math.max(lo, r.multi_street.ev_call)))}" r="5"/>`
      : ""}
    <text x="${L - 6}" y="${y(hi) + 4}" text-anchor="end">${fmt(hi)}</text>
    <text x="${L - 6}" y="${y(0) + 4}" text-anchor="end">0</text>
    <text x="${L - 6}" y="${y(lo) + 4}" text-anchor="end">${fmt(lo)}</text>
    <text x="${x(0)}" y="${H - 10}" text-anchor="start">0%</text>
    <text x="${x(1)}" y="${H - 10}" text-anchor="end">100% equity</text>
    <text x="${x(be)}" y="${H - 10}" text-anchor="middle">${pct(be, 0)}</text>
  </svg>`;
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
