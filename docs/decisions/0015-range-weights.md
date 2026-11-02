# 0015 — Partial weights in ranges

**Status:** Accepted (2026-11-02)

## Options
- Every hand class is fully in or out of the range.
- Each class has a weight between 0 and 1: the fraction of the time the opponent holds it in this spot.

## Decision
Weights, rounded to 0.1%. Notation `A5s:0.5`; the grid shows partial cells as partly filled and offers 100% / 50% / 25% painting.

## Why
Real opponents mix: they might bet a weak hand as a bluff only some of the time. Weights let a range express that, and the multi-street model (M6) needs mixed frequencies for bluffing.

## Consequences
Every calculation weights each combo: a class at 50% counts as half as many combos. Card removal applies per combo before weighting.
