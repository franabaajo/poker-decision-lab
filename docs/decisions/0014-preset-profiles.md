# 0014 — Preset opponent profiles

**Status:** Accepted (2026-11-02)

## Decision
Three nested presets (each looser one contains the tighter one), defined in `src/pokerlab/profiles.py`:

| Preset | Range | Combos | Share |
|---|---|---|---|
| Tight | `77+, ATs+, KTs+, QJs, AJo+, KQo` | 128 | 9.7% |
| Balanced | `55+, A2s+, K9s+, Q9s+, J9s+, T9s, 98s, 87s, A9o+, KTo+, QJo` | 264 | 19.9% |
| Aggressive | `22+, A2s+, K5s+, Q7s+, J7s+, T7s+, 96s+, 85s+, 75s+, 64s+, 54s, A5o+, K9o+, Q9o+, J9o+, T9o` | 478 | 36.0% |

## Consequences
They are simple, documented starting points rather than empirically fitted ranges; users can edit any of them in the grid. Tests pin the sizes to the agreed bands (~10%, ~20%, ~35%).
