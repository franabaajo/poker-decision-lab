// Entry point for the frontend. Plain ES modules, no build step (ADR 0006).

import { getCards, getHealth, validateSpot } from "./api.js";
import { CardPicker } from "./cardPicker.js";

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

async function onSpotChange({ hero, board }) {
  $("analyse").disabled = true;
  if (hero.length < 2) {
    setStatus("info", `Pick your ${2 - hero.length === 2 ? "two hole cards" : "second hole card"}.`);
    return;
  }
  const id = ++requestId;
  try {
    const result = await validateSpot(hero, board);
    if (id !== requestId) return;
    if (result.valid) {
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
  onSpotChange(picker.value);
}

init().catch((err) => {
  setStatus("error", "Failed to load the card deck from the server.");
  console.error(err);
});
