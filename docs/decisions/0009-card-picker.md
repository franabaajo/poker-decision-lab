# 0009 — Card picker

**Status:** Accepted (2026-10-31)

## Options
- Clickable 52-card grid.
- Grid plus typed text (`AsQs`, `Js8d4s`), kept in sync.
- Typed text only.

## Decision
A clickable 52-card grid (4 suit rows × 13 ranks). Clicking fills the highlighted slot and moves to the next empty one; board cards fill left to right; used cards are disabled, so duplicates cannot be picked. A four-colour deck (♠ black, ♥ red, ♦ blue, ♣ green) makes suits easy to tell apart.

## Consequences
- The UI prevents most mistakes, but the server still validates every spot (`POST /api/spot/validate`); the engine is the single source of truth.
- The text parser exists in the engine anyway (tests, notebooks, API), so adding typed input later is cheap.
