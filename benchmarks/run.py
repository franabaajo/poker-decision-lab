"""Benchmark the reference (pure Python) engines against the vectorised ones (ADR 0023).

Run with:
    uv run python benchmarks/run.py

Prints a Markdown table (median of several runs) ready to paste into the README.
Times depend on the machine; the speed-up column is the meaningful part.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable

import numpy as np

from pokerlab import equity, multistreet
from pokerlab.decision import Situation
from pokerlab.evaluator import evaluate
from pokerlab.evaluator_fast import evaluate_batch
from pokerlab.profiles import PROFILES
from pokerlab.reference import equity as ref_equity
from pokerlab.reference import multistreet as ref_multistreet
from pokerlab.spot import Spot


def timed(fn: Callable[[], object], repeats: int) -> float:
    """Median wall-clock seconds over ``repeats`` runs (after one warm-up run)."""
    fn()
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def main() -> None:
    flop = Spot.from_strings("AsQs", "Js8d4s")
    preflop = Spot.from_strings("AsQs")
    balanced, aggressive = PROFILES["balanced"], PROFILES["aggressive"]
    situation = Situation(pot=100, bet=50, stack=500)

    gen = np.random.default_rng(0)
    hands = np.argsort(gen.random((200_000, 52)), axis=1)[:, :7]
    hand_lists = hands.tolist()

    cases = [
        (
            "Evaluate 200,000 seven-card hands",
            lambda: [evaluate(h) for h in hand_lists],
            lambda: evaluate_batch(hands),
            1,
        ),
        (
            "Exact equity, flop, Balanced range",
            lambda: ref_equity.exact_equity(flop, balanced.range),
            lambda: equity.exact_equity(flop, balanced.range),
            3,
        ),
        (
            "Monte Carlo equity, preflop, 50,000 deals",
            lambda: ref_equity.monte_carlo_equity(preflop, balanced.range, 50_000, seed=1),
            lambda: equity.monte_carlo_equity(preflop, balanced.range, 50_000, seed=1),
            3,
        ),
        (
            "Turn + river model, flop, Aggressive",
            lambda: ref_multistreet.analyse_call(
                flop, aggressive.range, situation, aggressive.strategy
            ),
            lambda: multistreet.analyse_call(
                flop, aggressive.range, situation, aggressive.strategy
            ),
            3,
        ),
    ]

    print("| Task | Reference (pure Python) | Vectorised (NumPy) | Speed-up |")
    print("|---|---:|---:|---:|")
    for name, slow, fast, repeats in cases:
        t_slow, t_fast = timed(slow, repeats), timed(fast, repeats)
        print(f"| {name} | {t_slow:.2f} s | {t_fast:.3f} s | {t_slow / t_fast:.0f}x |")


if __name__ == "__main__":
    main()
