// Opponent-range panel: preset chips, grid and text box, kept in sync (ADR 0005).
//
// Every edit (preset, grid stroke, text) is sent to the server, which returns the
// normalised notation plus per-class counts; all three views are redrawn from that.

import { analyseRange, getPresets } from "./api.js";
import { RangeGrid } from "./rangeGrid.js";

const $ = (id) => document.getElementById(id);

export class RangePanel {
  constructor() {
    this.weights = {};
    this.dead = { hero: [], board: [] };
    this.presets = [];
    this.activePreset = null;
    this.requestId = 0;
    this.liveCombos = 0;
    this.onChange = null; // set by main.js
    this.style = "balanced"; // opponent betting style on later streets
    this.grid = new RangeGrid($("range-grid"), (weights) => {
      this.activePreset = null;
      this.#analyse({ weights });
    });
  }

  async init(defaultPreset = "balanced") {
    this.presets = await getPresets();
    this.#buildPresetChips();
    this.#bindControls();
    await this.selectPreset(defaultPreset);
  }

  /** Called when the visible cards change, so card removal is recomputed. */
  setDeadCards(hero, board) {
    this.dead = { hero, board };
    this.#analyse({ weights: this.weights }, { keepText: true });
  }

  async selectPreset(key) {
    const preset = this.presets.find((p) => p.key === key);
    if (!preset) return;
    this.activePreset = key;
    this.setStyle(key);
    await this.#analyse({ notation: preset.notation });
  }

  /** Betting style on the turn and river; a preset sets it, but it can be changed alone. */
  setStyle(key) {
    const preset = this.presets.find((p) => p.key === key);
    if (!preset) return;
    this.style = key;
    for (const b of $("style").querySelectorAll("button")) {
      b.classList.toggle("is-on", b.dataset.style === key);
    }
    const pct = (x) => `${Math.round(100 * x)}%`;
    const size = { 0.5: "½ pot", 1: "a full pot" }[preset.bet_fraction] ??
      (Math.abs(preset.bet_fraction - 2 / 3) < 1e-9 ? "⅔ pot" : `${pct(preset.bet_fraction)} of the pot`);
    $("style-description").textContent =
      `Bets ${size} with their strongest ${pct(preset.value_share)} of hands, ` +
      `bluffs with ${pct(preset.bluff_share)} of the rest, checks otherwise.`;
    this.onChange?.();
  }

  // --- internals --------------------------------------------------------------------

  #buildPresetChips() {
    const box = $("presets");
    box.innerHTML = "";
    for (const p of this.presets) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip";
      btn.dataset.key = p.key;
      btn.textContent = `${p.name} · ~${Math.round(p.percent)}%`;
      btn.title = `${p.description} (${p.combos} combos = ${p.percent}% of all hands)`;
      btn.addEventListener("click", () => this.selectPreset(p.key));
      box.appendChild(btn);
    }
    const custom = document.createElement("span");
    custom.className = "chip chip--custom";
    custom.dataset.key = "custom";
    custom.textContent = "Custom";
    box.appendChild(custom);
  }

  #bindControls() {
    for (const btn of $("style").querySelectorAll("button")) {
      btn.addEventListener("click", () => this.setStyle(btn.dataset.style));
    }
    for (const btn of $("paint-weights").querySelectorAll("button")) {
      btn.addEventListener("click", () => {
        this.grid.paintWeight = Number(btn.dataset.w);
        for (const b of $("paint-weights").querySelectorAll("button")) {
          b.classList.toggle("is-on", b === btn);
        }
      });
    }
    $("range-clear").addEventListener("click", () => {
      this.activePreset = null;
      this.#analyse({ weights: {} });
    });

    const text = $("range-text");
    let timer = null;
    text.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        this.activePreset = null;
        this.#analyse({ notation: text.value }, { fromText: true });
      }, 400);
    });
    text.addEventListener("blur", () => {
      // Tidy the text into normalised notation once the user leaves the box.
      if (text.getAttribute("aria-invalid") !== "true") text.value = this.notation ?? text.value;
    });
  }

  async #analyse(source, { fromText = false, keepText = false } = {}) {
    const id = ++this.requestId;
    let result;
    try {
      result = await analyseRange({ ...source, ...this.dead });
    } catch (err) {
      console.error(err);
      this.#summary("error", "Could not reach the server to analyse the range.");
      return;
    }
    if (id !== this.requestId) return; // a newer edit is already in flight

    const text = $("range-text");
    if (!result.valid) {
      text.setAttribute("aria-invalid", "true");
      $("range-text-error").textContent = result.error;
      return;
    }
    text.setAttribute("aria-invalid", "false");
    $("range-text-error").textContent = "";

    this.weights = Object.fromEntries(
      result.grid.filter((c) => c.weight > 0).map((c) => [c.label, c.weight]),
    );
    this.notation = result.notation;
    this.grid.render(result.grid);
    // Don't rewrite the box while the user is typing in it.
    if (!fromText && !(keepText && document.activeElement === text)) text.value = result.notation;
    this.liveCombos = result.live_combos;
    this.#renderPresetState();
    this.#renderSummary(result);
    this.onChange?.();
  }

  #renderPresetState() {
    for (const chip of $("presets").children) {
      const key = chip.dataset.key;
      chip.classList.toggle("chip--on", key === (this.activePreset ?? "custom"));
    }
    const preset = this.presets.find((p) => p.key === this.activePreset);
    $("preset-description").textContent = preset
      ? preset.description
      : "Custom range: edited by hand.";
  }

  #renderSummary(result) {
    if (result.combos === 0) {
      this.#summary("error", "The range is empty: select at least one hand.");
      return;
    }
    const fmt = (x) => (Number.isInteger(x) ? x : x.toFixed(1));
    const removed = result.combos - result.live_combos;
    let text = `${fmt(result.combos)} combos (${result.percent}% of all hands)`;
    if (removed > 0) text += ` · ${fmt(result.live_combos)} still possible after removing the cards shown`;
    this.#summary(result.live_combos > 0 ? "ok" : "error", text);
  }

  #summary(kind, text) {
    const el = $("range-summary");
    el.className = `status status--${kind}`;
    el.textContent = text;
  }
}
