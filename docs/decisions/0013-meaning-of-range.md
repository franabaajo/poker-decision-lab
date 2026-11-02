# 0013 — What the opponent range means

**Status:** Accepted (2026-11-02)

## Options
- **A.** The hands the opponent could hold *given that they made this bet*, specified directly by the user or a preset.
- **B.** The hands they started with before any betting, with the app inferring which of them would bet now.

## Decision
A. This is how standard poker equity calculators work and keeps the assumption visible: what you see in the grid is exactly what the maths uses. Narrowing on later streets according to the opponent's style is handled by the multi-street model (ADR 0004, M6).
