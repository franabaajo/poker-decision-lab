# 0022 — Speed targets and the exact-enumeration limit

**Status:** Accepted (2026-11-10)

## Decision
Targets on the example flop (A♠Q♠ on J♠8♦4♠):

| Task | Target | Achieved |
|---|---|---|
| Exact equity vs Balanced | < 0.3 s | ~0.14 s |
| Turn + river model vs Aggressive | < 1 s | ~0.6 s |
| Monte Carlo, 50,000 deals | < 0.3 s | ~0.09 s |

"Auto" now uses exact enumeration up to 2,000,000 showdowns (was 300,000), which covers every flop range, including the full 1,326-combo range (~1.1 million showdowns, under 1 s).
