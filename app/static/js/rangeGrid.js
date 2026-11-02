// 13x13 range grid. Each cell is a hand class (AA, AKs, AKo, ...).
//
// - Fill height shows the weight (full = always in the range, half = 50% of the time).
// - Click a cell to set it to the selected "paint" weight; click again to remove it.
// - Click and drag to paint several cells at once.
// - Cells whose combos are all blocked by visible cards are dimmed.
//
// The grid only edits a local copy of the weights; the server (POST /api/ranges/analyse)
// is the source of truth for notation, counts and card removal.

export class RangeGrid {
  /**
   * @param {HTMLElement} el
   * @param {(weights: Record<string, number>) => void} onChange  called after each paint stroke
   */
  constructor(el, onChange) {
    this.el = el;
    this.onChange = onChange;
    this.paintWeight = 1;
    this.weights = {};
    this.cells = new Map();
    this.dragValue = null;
    window.addEventListener("pointerup", () => this.#endStroke());
  }

  /** Redraw from a server response grid: [{label, weight, combos, live}, ...] (169 cells). */
  render(grid) {
    if (this.cells.size === 0) this.#build(grid);
    this.weights = {};
    for (const cell of grid) {
      if (cell.weight > 0) this.weights[cell.label] = cell.weight;
      this.#paintCell(cell.label, cell.weight);
      const btn = this.cells.get(cell.label);
      btn.classList.toggle("rcell--blocked", cell.live === 0);
      btn.title =
        `${cell.label}: ${Math.round(cell.weight * 100)}% · ` +
        `${cell.live} of ${cell.combos} combos possible`;
    }
  }

  #build(grid) {
    this.el.innerHTML = "";
    for (const cell of grid) {
      const btn = document.createElement("button");
      btn.type = "button";
      const kind = cell.label.length === 2 ? "pair" : cell.label.endsWith("s") ? "suited" : "offsuit";
      btn.className = `rcell rcell--${kind}`;
      btn.innerHTML = `<span class="rcell__fill"></span><span class="rcell__label">${cell.label}</span>`;
      btn.setAttribute("aria-label", cell.label);
      btn.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        const current = this.weights[cell.label] ?? 0;
        this.dragValue = current === this.paintWeight ? 0 : this.paintWeight;
        this.#apply(cell.label);
      });
      btn.addEventListener("pointerenter", () => {
        if (this.dragValue !== null) this.#apply(cell.label);
      });
      btn.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          const current = this.weights[cell.label] ?? 0;
          this.dragValue = current === this.paintWeight ? 0 : this.paintWeight;
          this.#apply(cell.label);
          this.#endStroke();
        }
      });
      this.el.appendChild(btn);
      this.cells.set(cell.label, btn);
    }
  }

  #apply(label) {
    if (this.dragValue > 0) this.weights[label] = this.dragValue;
    else delete this.weights[label];
    this.#paintCell(label, this.dragValue);
  }

  #paintCell(label, weight) {
    const btn = this.cells.get(label);
    btn.style.setProperty("--w", weight);
    btn.classList.toggle("rcell--on", weight > 0);
    btn.classList.toggle("rcell--full", weight >= 1);
    btn.setAttribute("aria-pressed", weight > 0 ? "true" : "false");
  }

  #endStroke() {
    if (this.dragValue === null) return;
    this.dragValue = null;
    this.onChange({ ...this.weights });
  }
}
