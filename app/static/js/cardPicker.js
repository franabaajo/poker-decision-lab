// Card picker: 2 hero slots, 5 board slots and a 52-card grid.
//
// Rules
// - Clicking a grid card puts it in the active slot, then moves to the next empty slot.
// - Board cards are always filled left to right (flop, turn, river).
// - Clicking a filled slot removes its card and makes that slot active.
// - Cards already used are disabled in the grid, so a duplicate cannot be picked.
//   The server still validates every spot; the UI is a convenience, not the authority.

const SUIT_ORDER = ["s", "h", "d", "c"]; // grid rows
const RANK_ORDER = "AKQJT98765432"; // grid columns
const SUIT_SYMBOL = { s: "♠", h: "♥", d: "♦", c: "♣" };

export class CardPicker {
  /**
   * @param {object} opts
   * @param {HTMLElement} opts.heroEl   container for the 2 hero slots
   * @param {HTMLElement} opts.boardEl  container for the 5 board slots
   * @param {HTMLElement} opts.gridEl   container for the 52-card grid
   * @param {Array} opts.cards          deck from /api/cards
   * @param {Function} opts.onChange    called with {hero, board} (arrays of codes)
   */
  constructor({ heroEl, boardEl, gridEl, cards, onChange }) {
    this.heroEl = heroEl;
    this.boardEl = boardEl;
    this.gridEl = gridEl;
    this.cards = new Map(cards.map((c) => [c.code, c]));
    this.onChange = onChange;
    this.hero = [null, null];
    this.board = [null, null, null, null, null];
    this.active = { group: "hero", index: 0 };
    this.#buildGrid();
    this.render();
  }

  // --- public API ---------------------------------------------------------------

  /** Replace all cards, e.g. to load an example. Codes like "As". */
  set(heroCodes, boardCodes = []) {
    this.hero = [0, 1].map((i) => heroCodes[i] ?? null);
    this.board = [0, 1, 2, 3, 4].map((i) => boardCodes[i] ?? null);
    this.#moveToNextEmpty();
    this.#changed();
  }

  clear(group = null) {
    if (group === null || group === "hero") this.hero = [null, null];
    if (group === null || group === "board") this.board = [null, null, null, null, null];
    this.#moveToNextEmpty();
    this.#changed();
  }

  get value() {
    return { hero: this.hero.filter(Boolean), board: this.board.filter(Boolean) };
  }

  // --- interaction ----------------------------------------------------------------

  #pick(code) {
    if (this.#used().has(code) || this.active === null) return;
    const { group, index } = this.active;
    if (group === "hero") this.hero[index] = code;
    else this.board[this.board.indexOf(null)] = code; // always leftmost empty board slot
    this.#moveToNextEmpty();
    this.#changed();
  }

  #slotClicked(group, index) {
    if (group === "hero") {
      this.hero[index] = null;
      this.active = { group, index };
    } else {
      if (this.board[index] !== null) {
        // Remove and shift later board cards left, keeping the board contiguous.
        this.board.splice(index, 1);
        this.board.push(null);
      }
      this.active = { group, index: this.board.indexOf(null) };
    }
    this.#changed();
  }

  #moveToNextEmpty() {
    const h = this.hero.indexOf(null);
    if (h !== -1) this.active = { group: "hero", index: h };
    else if (this.board.includes(null)) this.active = { group: "board", index: this.board.indexOf(null) };
    else this.active = null;
  }

  #used() {
    return new Set([...this.hero, ...this.board].filter(Boolean));
  }

  #changed() {
    this.render();
    this.onChange?.(this.value);
  }

  // --- rendering ------------------------------------------------------------------

  #buildGrid() {
    this.gridEl.innerHTML = "";
    this.gridButtons = new Map();
    for (const suit of SUIT_ORDER) {
      for (const rank of RANK_ORDER) {
        const card = this.cards.get(rank + suit);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `pcard pcard--${suit}`;
        btn.innerHTML = `<span class="pcard__rank">${rank}</span><span class="pcard__suit">${SUIT_SYMBOL[suit]}</span>`;
        btn.setAttribute("aria-label", card.name);
        btn.addEventListener("click", () => this.#pick(card.code));
        this.gridEl.appendChild(btn);
        this.gridButtons.set(card.code, btn);
      }
    }
  }

  #renderSlots(container, group, codes, labels) {
    container.innerHTML = "";
    codes.forEach((code, index) => {
      const btn = document.createElement("button");
      btn.type = "button";
      const isActive = this.active?.group === group && this.active.index === index;
      btn.className = "slot" + (isActive ? " slot--active" : "");
      if (code) {
        const suit = code[1];
        btn.classList.add("pcard", `pcard--${suit}`);
        btn.innerHTML = `<span class="pcard__rank">${code[0]}</span><span class="pcard__suit">${SUIT_SYMBOL[suit]}</span>`;
        btn.setAttribute("aria-label", `${labels[index]}: ${this.cards.get(code).name}. Click to remove.`);
        btn.title = "Click to remove";
      } else {
        btn.innerHTML = `<span class="slot__label">${labels[index]}</span>`;
        btn.setAttribute("aria-label", `${labels[index]}: empty`);
      }
      btn.addEventListener("click", () => this.#slotClicked(group, index));
      container.appendChild(btn);
    });
  }

  render() {
    this.#renderSlots(this.heroEl, "hero", this.hero, ["Card 1", "Card 2"]);
    this.#renderSlots(this.boardEl, "board", this.board, ["Flop", "Flop", "Flop", "Turn", "River"]);
    const used = this.#used();
    const full = this.active === null;
    for (const [code, btn] of this.gridButtons) {
      btn.disabled = used.has(code) || full;
      btn.classList.toggle("pcard--used", used.has(code));
    }
  }
}
