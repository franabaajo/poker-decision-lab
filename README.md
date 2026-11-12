# Poker Decision Lab

[![CI](https://github.com/franabaajo/poker-decision-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/franabaajo/poker-decision-lab/actions/workflows/ci.yml)

An educational analyser for one heads-up Texas Hold'em decision: **facing a bet, should you call or fold?**

You enter your hole cards, the board, the pot, the bet, effective stacks and an assumed opponent range. The engine estimates your equity (by exact enumeration or Monte Carlo, with confidence intervals), compares it with the break-even equity implied by the pot odds, and computes the expected value of folding and calling, including play on later streets under an explicit opponent model.

> **Not a gambling tool.** It does not know anyone's cards, does not connect to live games and guarantees nothing. Every result is conditional on the assumed opponent range and strategy.

**Status:** milestone M7 (performance). See the [roadmap](#roadmap).

## Quick start

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/franabaajo/poker-decision-lab.git
cd poker-decision-lab
uv sync                                       # creates .venv with exact locked versions
uv run uvicorn app.main:app --reload          # open http://127.0.0.1:8000
```

Development:

```bash
uv run pytest                 # all tests (includes a ~25 s exhaustive check)
uv run pytest -m "not slow"   # quick run
uv run ruff check .           # lint
uv run ruff format .          # format
uv run python benchmarks/run.py   # speed: reference vs vectorised
```

Docker (same image as the deployment):

```bash
docker build -t poker-decision-lab .
docker run -p 7860:7860 poker-decision-lab    # open http://127.0.0.1:7860
```

## Architecture

```
app/            FastAPI routes + static frontend (HTML/CSS/JS, no build step)
src/pokerlab/   Probability and decision engine: pure Python/NumPy, no web imports
tests/          pytest suite
docs/decisions/ Architecture Decision Records
```

The engine never imports the web layer, which keeps it testable, benchmarkable and usable from notebooks. Design decisions are recorded in [`docs/decisions/`](docs/decisions/README.md).

## Performance

The engine was first written as readable pure Python, one hand at a time, and verified.
M7 then vectorised it with NumPy: thousands of hands are scored per call using array
operations and small lookup tables. The original code is kept in `pokerlab.reference`
and the tests require both versions to give identical results.

| Task | Reference (pure Python) | Vectorised (NumPy) | Speed-up |
|---|---:|---:|---:|
| Evaluate 200,000 seven-card hands | 1.25 s | 0.112 s | 11x |
| Exact equity, flop, Balanced range | 1.30 s | 0.139 s | 9x |
| Monte Carlo equity, preflop, 50,000 deals | 0.84 s | 0.093 s | 9x |
| Turn + river model, flop, Aggressive | 3.26 s | 0.577 s | 6x |

Measured with `benchmarks/run.py` on a 2-vCPU cloud machine; times vary by machine.

## Roadmap

- [x] **M0** Scaffold: uv project, CI, FastAPI + frontend skeleton, Docker, deployment
- [x] **M1** Cards, validation and card picker
- [x] **M2** Hand evaluator, verified against exhaustive 5-card category counts
- [x] **M3** Ranges, combos, card removal; presets + range grid
- [x] **M4** Equity engine: exact enumeration + Monte Carlo with confidence intervals
- [x] **M5** Pot odds, break-even equity and single-decision EV; results page
- [x] **M6** Multi-street model: opponent profiles, hero best response, realised EV
- [x] **M7** Performance benchmarks and optimisation
- [ ] **M8** Mathematical write-up, research notebook, polished docs

### Planned extensions (after the MVP)

- **Raise option:** Fold / Call / Raise on the current decision, with an opponent response rule per style
- **Multiway pots:** equity against two or more opponents
- **Sensitivity analysis:** how the decision changes as the opponent's range and style vary
- Board-aware hand strength for the opponent's betting rule (values draws)

## License

MIT
