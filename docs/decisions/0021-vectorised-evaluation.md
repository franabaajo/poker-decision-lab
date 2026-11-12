# 0021 — Speed up with NumPy vectorisation

**Status:** Accepted (2026-11-10)

## Options
- **A.** NumPy vectorisation: score thousands of hands per call with array operations.
- **B.** Numba: compile the existing Python evaluator to machine code.
- **C.** Precomputed lookup tables only.

## Decision
A, combined with two small lookup tables (8,192 entries each) for straights and top-five ranks.

- `src/pokerlab/evaluator_fast.py` — `evaluate_batch(cards)` scores an (N, 5..7) array of hands in one call.
- Exact and Monte Carlo equity (`equity.py`) score every (combo, runout) showdown in one batch.
- The multi-street model (`multistreet.py`) keeps weights as arrays and solves the river for all river cards at once.

## Why not B
Numba is a heavy dependency that loads compiled libraries at run time; Windows Smart App Control already blocks unsigned executables on the development machine. Vectorisation also demonstrates array programming, which is directly relevant to data-science and quant work.

## Verification
- The readable pure-Python implementations are kept in `pokerlab.evaluator` and `pokerlab.reference.*` as oracles.
- The fast evaluator must equal the reference on every 5-card hand, on random 5-, 6- and 7-card hands and on `hypothesis`-generated hands.
- Exact equity and the multi-street EV must equal the reference to ~1e-12; golden values recorded from the M6 reference are pinned in the tests.

## Consequences
Monte Carlo now uses NumPy's random generator, so a given seed produces a different (equally valid) sample than in M4–M6. Results for a fixed seed remain reproducible.
