"""Equity of the hero's hand against an opponent range.

**Equity** = P(win) + ½ · P(split pot): the share of the final pot the hero
collects on average if the hand is played to showdown with no more betting.

Two methods compute it:

Exact enumeration
    For every live opponent combo, deal every possible remaining board ("runout")
    and count the outcomes. On the flop that is C(45,2) = 990 runouts per combo,
    on the turn 44, on the river 1. The answer has no sampling error.

Monte Carlo
    Repeat many times: draw an opponent combo (with probability proportional to
    its weight), then draw a random runout from the cards still in the deck, and
    score the showdown. The answer is an estimate with a standard error and a 95%
    confidence interval (see :mod:`pokerlab.stats`). Preflop, where exact
    enumeration would need C(48,5) = 1,712,304 runouts per combo, this is the only
    practical option.

Sampling order matters for correctness: we draw the opponent's hand from combos
that do not clash with the visible cards, *then* the runout from what is left.
Drawing a runout that clashes with the chosen combo is rejected and redrawn, which
is equivalent to drawing uniformly from the valid runouts.
"""

from __future__ import annotations

import itertools
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from math import comb
from typing import Literal

from pokerlab.cards import remaining_deck
from pokerlab.evaluator import evaluate
from pokerlab.ranges import Range, class_of_combo
from pokerlab.spot import Spot, Street
from pokerlab.stats import Estimate, estimate_from_counts

Method = Literal["auto", "exact", "monte_carlo"]

#: "auto" uses exact enumeration when (live combos x runouts) is at most this many
#: showdowns (a few seconds in pure Python; M7 makes this faster), else Monte Carlo.
EXACT_WORK_LIMIT = 300_000
DEFAULT_SAMPLES = 50_000


class EquityError(ValueError):
    """The calculation cannot be done (e.g. no opponent hands remain)."""


@dataclass(frozen=True)
class ClassResult:
    """Hero's results against one hand class of the opponent range."""

    label: str
    share: float  # fraction of the (weighted, live) range this class makes up
    win: float
    tie: float

    @property
    def equity(self) -> float:
        return self.win + 0.5 * self.tie


@dataclass(frozen=True)
class EquityResult:
    win: float
    tie: float
    lose: float
    method: Literal["exact", "monte_carlo"]
    estimate: Estimate  # equity, its standard error (0 for exact) and n
    live_combos: float  # weighted opponent combos after card removal
    by_class: dict[str, ClassResult] = field(default_factory=dict)
    seed: int | None = None  # Monte Carlo seed: rerun with it to reproduce the result
    elapsed_s: float = 0.0

    @property
    def equity(self) -> float:
        return self.win + 0.5 * self.tie

    @property
    def ci95(self) -> tuple[float, float]:
        return self.estimate.ci95


def _live_combos(spot: Spot, rng: Range) -> list[tuple[tuple[int, int], float]]:
    combos = rng.combos(spot.dead_cards)
    if not combos:
        raise EquityError(
            "The opponent range has no possible hands left after removing the cards shown."
        )
    return combos


def runouts_per_combo(spot: Spot) -> int:
    """Number of possible remaining boards once the opponent's 2 cards are also known."""
    return comb(52 - len(spot.dead_cards) - 2, spot.cards_to_come)


def exact_work(spot: Spot, rng: Range) -> int:
    """Showdowns exact enumeration would evaluate: live combos x runouts."""
    return len(rng.combos(spot.dead_cards)) * runouts_per_combo(spot)


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


# --- Entry point ------------------------------------------------------------------------


def calculate_equity(
    spot: Spot,
    rng: Range,
    method: Method = "auto",
    samples: int = DEFAULT_SAMPLES,
    seed: int | None = None,
) -> EquityResult:
    """Hero equity vs the range. ``auto`` = exact when cheap enough, else Monte Carlo."""
    if method == "auto":
        cheap = spot.street is not Street.PREFLOP and exact_work(spot, rng) <= EXACT_WORK_LIMIT
        method = "exact" if cheap else "monte_carlo"
    if method == "exact":
        return exact_equity(spot, rng)
    if method == "monte_carlo":
        return monte_carlo_equity(spot, rng, samples=samples, seed=seed)
    raise EquityError(f"Unknown method {method!r}.")


def _class_results(acc: dict[str, list[float]], total_w: float) -> dict[str, ClassResult]:
    return {
        label: ClassResult(label, share=w / total_w, win=win / w, tie=tie / w)
        for label, (w, win, tie) in sorted(acc.items())
    }
