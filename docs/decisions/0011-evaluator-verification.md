# 0011 — How the hand evaluator is verified

**Status:** Accepted (2026-11-01)

## Context
Every later number (equity, EV) depends on deciding showdowns correctly. A rare bug, such as a missed A-2-3-4-5 straight, would silently bias all results.

## Options
- Exhaustive check only: evaluate all 2,598,960 five-card hands and compare category totals with the known combinatorial counts.
- Exhaustive check **plus** cross-checking against an independent evaluator (`treys`) on random 7-card hands.

## Decision
Both, plus agreement with a brute-force "best of all 5-card subsets" evaluator on random 6- and 7-card hands.

- The exhaustive test catches misclassified categories anywhere in the deck, and the number of distinct strengths (7,462) also checks tie-breaking within categories.
- `treys` is a test-only dependency used as an oracle; the app never imports it.

## Consequences
The exhaustive test takes ~20–30 s and is marked `slow` (`uv run pytest -m "not slow"` skips it locally); CI always runs it.
