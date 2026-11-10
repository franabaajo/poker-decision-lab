// Entry point for the frontend. Plain ES modules, no build step (ADR 0006).

import { analyseDecision, getCards, getHealth, validateSpot } from "./api.js";
import { CardPicker } from "./cardPicker.js";
import { RangePanel } from "./rangePanel.js";
import { markStale, renderAnalysis, renderStatus } from "./results.js";

const $ = (id) => document.getElementById(id);

async function checkApi() {
  const pill = $("api-status");
  try {
    const data = await getHealth();
    pill.textContent = `API: ok · v${data.version}`;
    pill.className = "pill pill--ok";
  } catch (err) {
    pill.textContent = "API: unreachable";
    pill.className = "pill pill--down";
    console.error(err);
  }
}

function setStatus(kind, text) {
  const el = $("spot-status");
  el.className = `status status--${kind}`;
  el.textContent = text;
}

let requestId = 0; // ignore out-of-order responses when the user clicks quickly
const rangePanel = new RangePanel();
const state = { spotValid: false, hero: [], board: [], method: "auto" };

function readAmounts() {
  const values = {};
  let ok = true;
  for (const [id, min] of [["pot", 0], ["bet", 0], ["stack", 0]]) {
    const input = $(id);
    const v = Number(input.value);
    const valid = input.value !== "" && Number.isFinite(v) && (id === "pot" ? v >= min : v > min);
    input.setAttribute("aria-invalid", valid ? "false" : "true");
    ok &&= valid;
    values[id] = v;
  }
  const note = $("amounts-status");
  if (!ok) {
    note.textContent = "Enter a pot of 0 or more, and a bet and stack above 0.";
  } else if (values.bet >= values.stack) {
    note.textContent =
      values.bet > values.stack
        ? `All-in: you can only call ${values.stack} chips; the other ${values.bet - values.stack} go back to the opponent. No more betting after a call, so the EV is exact.`
        : "All-in: no more betting after a call, so the EV is exact.";
  } else {
    note.textContent = "Heads-up: you against one opponent who has just bet.";
  }
  return ok ? values : null;
}

function updateAnalyseButton() {
  $("analyse").disabled = !(state.spotValid && rangePanel.liveCombos > 0 && readAmounts());
}

rangePanel.onChange = () => {
  markStale();
  updateAnalyseButton();
};

async function analyse() {
  const btn = $("analyse");
  btn.disabled = true;
  btn.textContent = "Calculating…";
  renderStatus("info", "Calculating…");
  const seed = $("seed").value === "" ? null : Number($("seed").value);
  try {
    const r = await analyseDecision({
      ...readAmounts(),
      hero: state.hero,
      board: state.board,
      range_weights: rangePanel.weights,
      method: state.method,
      style: rangePanel.style,
      samples: Number($("samples").value),
      seed,
    });
    if (r.valid) renderAnalysis(r);
    else renderStatus("error", r.error);
  } catch (err) {
    console.error(err);
    renderStatus("error", "The calculation failed: could not reach the server.");
  } finally {
    btn.textContent = "Analyse decision";
    updateAnalyseButton();
  }
}

async function onSpotChange({ hero, board }) {
  state.spotValid = false;
  state.hero = hero;
  state.board = board;
  updateAnalyseButton();
  markStale();
  rangePanel.setDeadCards(hero, board);
  if (hero.length < 2) {
    setStatus("info", `Pick your ${2 - hero.length === 2 ? "two hole cards" : "second hole card"}.`);
    return;
  }
  const id = ++requestId;
  try {
    const result = await validateSpot(hero, board);
    if (id !== requestId) return;
    if (result.valid) {
      state.spotValid = true;
      updateAnalyseButton();
      const boardText = result.board.length ? result.board.join(" ") : "no board yet";
      setStatus("ok", `${result.street}: ${result.hero.join(" ")} | ${boardText}`);
    } else {
      setStatus("error", result.error);
    }
  } catch (err) {
    if (id === requestId) setStatus("error", "Could not reach the server to validate the cards.");
    console.error(err);
  }
}

async function init() {
  checkApi();
  await rangePanel.init("balanced");
  const cards = await getCards();
  const picker = new CardPicker({
    heroEl: $("hero-slots"),
    boardEl: $("board-slots"),
    gridEl: $("card-grid"),
    cards,
    onChange: onSpotChange,
  });
  $("clear-hero").addEventListener("click", () => picker.clear("hero"));
  $("clear-board").addEventListener("click", () => picker.clear("board"));
  $("load-example").addEventListener("click", () => picker.set(["As", "Qs"], ["Js", "8d", "4s"]));
  $("analyse").addEventListener("click", analyse);
  $("samples").addEventListener("change", markStale);
  for (const id of ["pot", "bet", "stack"]) {
    $(id).addEventListener("input", () => {
      markStale();
      updateAnalyseButton();
    });
  }
  $("seed").addEventListener("input", markStale);
  for (const btn of $("method").querySelectorAll("button")) {
    btn.addEventListener("click", () => {
      state.method = btn.dataset.method;
      for (const b of $("method").querySelectorAll("button")) b.classList.toggle("is-on", b === btn);
      markStale();
    });
  }
  onSpotChange(picker.value);
}

init().catch((err) => {
  setStatus("error", "Failed to load the card deck from the server.");
  console.error(err);
});
