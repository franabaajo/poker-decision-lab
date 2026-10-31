# 0010 — Card representation

**Status:** Accepted (2026-10-31)

## Options
- An integer `0..51`, `card = rank * 4 + suit`.
- A small object with `rank` and `suit` attributes.

## Decision
Integers. `rank = card // 4`, `suit = card % 4`. Strings (`"As"`, `"A♠"`) are used only at the edges: user input, the API and display.

## Why
- The simulation engine (M4) evaluates millions of hands; plain ints avoid object overhead and can be stored in NumPy arrays, where `// 4` and `% 4` run on whole arrays at once.
- Sets of ints make card-removal checks cheap.
- Ordering by id groups cards by rank, which simplifies hand evaluation.

## Consequences
Less readable when debugging, mitigated by `card_to_str` / `card_to_pretty` and `Spot.__str__`.
