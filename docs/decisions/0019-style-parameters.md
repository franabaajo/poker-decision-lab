# 0019 — Betting-style parameters

**Status:** Accepted (2026-11-10)

## Decision
| Style | Bet size | Value bets with | Bluffs with | Bets in total |
|---|---|---|---|---|
| Tight | ½ pot | strongest 30% | 10% of the rest | 37% |
| Balanced | ⅔ pot | strongest 35% | 25% of the rest | 51% |
| Aggressive | full pot | strongest 45% | 50% of the rest | 72.5% |

Bets are capped by the chips left behind. Choosing a range preset also selects the matching style, but the style can be changed independently (e.g. a tight range that bets aggressively).

## Consequences
These are documented assumptions, not fitted to data; they are shown in the app next to every result.
