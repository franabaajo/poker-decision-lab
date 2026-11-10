# 0018 — How the opponent bets on the turn and river

**Status:** Accepted (2026-11-10)

## Options
- **A.** A simple rule per playing style: rank the hands in the current range, bet with the strongest share (value) and with part of the weakest (bluffs), check the rest.
- **B.** A game-theory ("solver") strategy.

## Decision
A, implemented in `src/pokerlab/multistreet.py`.

- Shares are measured in weighted combos of the opponent's *current* range, so the opponent bets exactly `value + bluff × (1 − value)` of their range on every street.
- Hands of equal strength are treated alike; a group straddling a threshold bets with a fractional probability.
- After the opponent acts, their range is updated by Bayes' rule: each combo's weight is multiplied by its probability of the action taken.
- The hero never bets or raises (ADR 0004); after a check the hero checks. Facing a bet, the hero picks the better of call or fold by backward induction, i.e. a best response to the assumed strategy.

## Consequences
- The model is transparent and fast (exact over every turn and river card in about 1–4 s on the flop).
- Assuming the hero knows the opponent's strategy is optimistic; every explanation says so.
- B remains a possible extension.
