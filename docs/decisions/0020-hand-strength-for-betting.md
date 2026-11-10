# 0020 — What "strong" means when the opponent ranks their hands

**Status:** Accepted (2026-11-10)

## Options
- **A.** Current made-hand strength (the evaluator's score on the current board).
- **B.** Each hand's equity against a random hand, which values draws.

## Decision
A. It is simple, fast and easy to explain. Draws rank as weak hands, so they appear among the bluffs, which mirrors real semi-bluffing.

## Consequences
Strong draws never bet "for value" on the turn. B is about 50× slower and is left as a possible refinement.
