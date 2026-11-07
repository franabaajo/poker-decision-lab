# 0017 — Pot odds, EV and the verdict

**Status:** Accepted (2026-11-02)

## Decision
- **Inputs:** pot before the bet, the opponent's bet, and the effective stack (the smaller stack behind, before the bet). A bet larger than the stack is capped: the hero calls `min(bet, stack)` and the excess goes back.
- **EV is measured relative to folding:** EV(fold) = 0 and EV(call) = equity × (pot + 2·call) − call. Chips already in the pot are sunk.
- **Break-even equity** = call / (pot + 2·call); **pot odds** are shown as (pot + call) : call.
- **Verdict uses the confidence interval:** *Call* if the whole 95% CI of equity is above break-even, *Fold* if it is entirely below, otherwise *Too close to call*. With exact enumeration the CI is a single point.
- **Assumptions are stated in every explanation:** the assumed range, one opponent, and, unless the bet is all-in, no further betting (until M6).

## Consequences
- When the bet is all-in the EV is exact. Otherwise it is the "equity-only" EV that the multi-street model (M6) will refine.
- The EV chart shows the whole linear relationship between equity and EV, so the user sees how much margin the decision has, not just the verdict.
