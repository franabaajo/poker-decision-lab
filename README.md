# Poker Decision Lab

[![CI](https://github.com/franabaajo/poker-decision-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/franabaajo/poker-decision-lab/actions/workflows/ci.yml)

An educational analyser for one heads-up Texas Hold'em decision: **facing a bet, should you call or fold?**

You enter your hole cards, the board, the pot, the bet, effective stacks and an assumed opponent range. The engine estimates your equity (by exact enumeration or Monte Carlo, with confidence intervals), compares it with the break-even equity implied by the pot odds, and computes the expected value of folding and calling, including play on later streets under an explicit opponent model.

> **Not a gambling tool.** It does not know anyone's cards, does not connect to live games and guarantees nothing. Every result is conditional on the assumed opponent range and strategy.

**Status:** milestone M1 (cards, validation and card picker). See the [roadmap](#roadmap).

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
uv run pytest                 # tests
uv run ruff check .           # lint
uv run ruff format .          # format
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

## Roadmap

- [x] **M0** Scaffold: uv project, CI, FastAPI + frontend skeleton, Docker, deployment
- [x] **M1** Cards, validation and card picker
- [ ] **M2** Hand evaluator, verified against exhaustive 5-card category counts
- [ ] **M3** Ranges, combos, card removal; presets + range grid
- [ ] **M4** Equity engine: exact enumeration + Monte Carlo with confidence intervals
- [ ] **M5** Pot odds, break-even equity and single-decision EV; results page
- [ ] **M6** Multi-street model: opponent profiles, hero best response, realised EV
- [ ] **M7** Performance benchmarks and optimisation
- [ ] **M8** Mathematical write-up, research notebook, polished docs

## License

MIT
