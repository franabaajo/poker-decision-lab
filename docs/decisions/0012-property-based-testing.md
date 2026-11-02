# 0012 — Property-based testing with hypothesis

**Status:** Accepted (2026-11-01)

## Decision
Use `hypothesis` (test-only dependency) alongside example-based pytest tests. Properties checked for the evaluator:

- Card order never changes the score.
- Relabelling suits never changes the score.
- Adding a card never makes a hand worse.
- The score always equals the best 5-card subset.

## Consequences
Hundreds of generated cases per run, with automatic shrinking of failures to a minimal example. The same approach will be reused for ranges (M3) and the equity engine (M4).
