"""Reference (pure Python) equity calculations, kept as a test oracle and benchmark baseline.

This is the M4 implementation: one hand at a time with the readable reference
evaluator. :mod:`pokerlab.equity` is the vectorised version used by the app;
tests require both to give the same results (ADR 0021).
"""

from __future__ import annotations

import itertools
import random
import time
from collections import defaultdict

from pokerlab.cards import remaining_deck
from pokerlab.equity import DEFAULT_SAMPLES, ClassResult, EquityError, EquityResult, _live_combos
from pokerlab.evaluator import evaluate
from pokerlab.ranges import Range, class_of_combo
from pokerlab.spot import Spot, Street
from pokerlab.stats import Estimate, estimate_from_counts

# --- Exact enumeration --------------------------------------------------------------------


def exact_equity(spot: Spot, rng: Range) -> EquityResult:
    if spot.street is Street.PREFLOP:
        raise EquityError("Exact enumeration preflop is too slow; use Monte Carlo.")
    start = time.perf_counter()
    combos = _live_combos(spot, rng)
    board = list(spot.board)
    live = remaining_deck(spot.dead_cards)

    # The hero's score depends only on the runout, so compute it once per runout.
    runouts = list(itertools.combinations(live, spot.cards_to_come))
    hero_scores = [evaluate([*spot.hero, *board, *r]) for r in runouts]

    class_acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])  # weight, win, tie
    total_w = win_acc = tie_acc = 0.0
    showdowns = 0
    for (a, b), w in combos:
        wins = ties = n = 0
        for runout, hero_score in zip(runouts, hero_scores, strict=True):
            if a in runout or b in runout:
                continue
            villain_score = evaluate([a, b, *board, *runout])
            n += 1
            if hero_score > villain_score:
                wins += 1
            elif hero_score == villain_score:
                ties += 1
        showdowns += n
        p_win, p_tie = wins / n, ties / n
        total_w += w
        win_acc += w * p_win
        tie_acc += w * p_tie
        acc = class_acc[class_of_combo(a, b)]
        acc[0] += w
        acc[1] += w * p_win
        acc[2] += w * p_tie

    win, tie = win_acc / total_w, tie_acc / total_w
    return EquityResult(
        win=win,
        tie=tie,
        lose=1.0 - win - tie,
        method="exact",
        estimate=Estimate(win + 0.5 * tie, 0.0, showdowns),
        live_combos=total_w,
        by_class=_class_results(class_acc, total_w),
        elapsed_s=time.perf_counter() - start,
    )


# --- Monte Carlo ------------------------------------------------------------------------


def monte_carlo_equity(
    spot: Spot, rng: Range, samples: int = DEFAULT_SAMPLES, seed: int | None = None
) -> EquityResult:
    if samples < 1:
        raise EquityError("Monte Carlo needs at least 1 sample.")
    start = time.perf_counter()
    if seed is None:
        seed = random.SystemRandom().randrange(2**32)
    gen = random.Random(seed)

    combos = _live_combos(spot, rng)
    board = list(spot.board)
    live = remaining_deck(spot.dead_cards)
    k = spot.cards_to_come
    hero = list(spot.hero)

    # Draw all opponent hands up front, proportional to weight.
    picks = gen.choices(range(len(combos)), weights=[w for _, w in combos], k=samples)

    wins = ties = losses = 0
    class_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # n, win, tie
    for i in picks:
        a, b = combos[i][0]
        while True:  # rejection: redraw runouts that use the opponent's cards
            runout = gen.sample(live, k)
            if a not in runout and b not in runout:
                break
        hero_score = evaluate([*hero, *board, *runout])
        villain_score = evaluate([a, b, *board, *runout])
        counts = class_counts[class_of_combo(a, b)]
        counts[0] += 1
        if hero_score > villain_score:
            wins += 1
            counts[1] += 1
        elif hero_score == villain_score:
            ties += 1
            counts[2] += 1
        else:
            losses += 1

    by_class = {
        label: ClassResult(label, share=n / samples, win=w / n, tie=t / n)
        for label, (n, w, t) in sorted(class_counts.items())
    }
    return EquityResult(
        win=wins / samples,
        tie=ties / samples,
        lose=losses / samples,
        method="monte_carlo",
        estimate=estimate_from_counts(wins, ties, losses),
        live_combos=sum(w for _, w in combos),
        by_class=by_class,
        seed=seed,
        elapsed_s=time.perf_counter() - start,
    )


def _class_results(acc: dict[str, list[float]], total_w: float) -> dict[str, ClassResult]:
    return {
        label: ClassResult(label, share=w / total_w, win=win / w, tie=tie / w)
        for label, (w, win, tie) in sorted(acc.items())
    }
