# 0002 — Own engine, libraries for plumbing

**Status:** Accepted (2026-10-31)

## Decision
Implemented in this repository: card model, hand evaluator, range parser, combo and card-removal logic, exact enumeration, Monte Carlo, statistics, EV and multi-street model.

Libraries: NumPy (numerics), FastAPI/uvicorn (API), Plotly.js (charts), pytest/hypothesis/pytest-benchmark (testing). An existing evaluator (`eval7`) may be used **only in tests** as an independent oracle.

## Consequences
More code to verify, so correctness is shown by exhaustive and cross-checked tests rather than trust in a library.
