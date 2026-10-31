# 0004 — Model turn and river play

**Status:** Accepted (2026-10-31)

## Context
Equity-based EV (`equity × final pot − call`) is exact only if no further betting happens, e.g. when the bet is all-in. On the flop, two more streets of betting follow.

## Options
1. Opponent follows a profile strategy on later streets; hero best-responds with call/fold.
2. As 1, plus hero may bet when checked to (roughly double the work).
3. Exact only when all-in, otherwise show a warning.

## Decision
Option 1. Effective stacks are an input; an all-in bet is computed exactly. Otherwise the opponent bets or checks on the turn and river according to the selected profile (bet size, value and bluff thresholds), the opponent range is narrowed by those actions, and the hero's optimal call/fold policy is found by backward induction. The app reports both the naive equity EV and the multi-street EV.

## Consequences
The result is still conditional on modelled opponent behaviour, but the assumptions are explicit and adjustable.
