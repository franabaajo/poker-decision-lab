# 0026 — Research notebook and documentation

**Status:** Accepted (2026-11-12)

## Decision
- `docs/math.md` derives every formula the engine uses and links each to its module and tests.
- `notebooks/report.ipynb` is a short study with four questions: Monte Carlo convergence and CI coverage; sensitivity of the decision to the opponent model (3 ranges × 3 styles); pot odds versus bet size; equity realisation by hand type. It is committed with outputs so it reads on GitHub without running.
- Notebook-only dependencies (`jupyter`, `matplotlib`) live in a separate `notebook` dependency group.
- The README shows a static screenshot and a short animated GIF of the app.
