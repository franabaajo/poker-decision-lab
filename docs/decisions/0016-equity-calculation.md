# 0016 — How equity is calculated

**Status:** Accepted (2026-11-02)

## Decision
- **Equity** = P(win) + ½ · P(split), against the weighted, card-removed opponent range, assuming the hand goes to showdown with no further betting. Later betting is added by the multi-street model (ADR 0004).
- **Two methods**, both in `src/pokerlab/equity.py`:
  - *Exact enumeration* over every live opponent combo and every runout. No sampling error.
  - *Monte Carlo*: draw a combo proportional to its weight, then a uniform runout from the remaining cards (rejecting clashes). Reported with a standard error and a 95% normal-approximation confidence interval.
- **Auto** picks exact when it needs at most 300,000 showdowns (a few seconds in pure Python), otherwise Monte Carlo. Preflop is always Monte Carlo (1.7 million runouts per combo).
- **Defaults:** 50,000 samples (95% CI about ±0.4 points). The user can choose 10k / 50k / 200k.
- **Reproducibility:** every Monte Carlo result reports its seed; entering it reproduces the result exactly.

## Verification
- Exact equity is recomputed independently with `treys` on turn and river spots and must match to 1e-12.
- Monte Carlo must agree with exact within 4 standard errors.
- CI coverage is checked empirically: ~95% of intervals contain the true value, both on synthetic data and on a real spot.
- Known benchmark: AA vs KK preflop ≈ 82%.

## Consequences
Exact flop calculations take 1–3 s in pure Python. The performance milestone (M7) will speed up the evaluator and raise the exact-enumeration threshold.
