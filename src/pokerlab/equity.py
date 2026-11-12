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
that do not clash with the visible cards, *then* a uniformly random runout from the
cards still in the deck (every remaining card gets a random key; the opponent's own
cards are pushed to the end; the k smallest keys form the runout).

Both methods are vectorised with NumPy (ADR 0021): all (combo, runout) showdowns
are scored in one call to :func:`pokerlab.evaluator_fast.evaluate_batch`.
"""

from __future__ import annotations

import itertools
import time
from collections import defaultdict
from dataclasses import dataclass, field
from math import comb
from typing import Literal

import numpy as np

from pokerlab.cards import remaining_deck
from pokerlab.evaluator_fast import evaluate_batch
from pokerlab.ranges import Range, class_of_combo
from pokerlab.spot import Spot, Street
from pokerlab.stats import Estimate, estimate_from_counts

Method = Literal["auto", "exact", "monte_carlo"]

#: "auto" uses exact enumeration when (live combos x runouts) is at most this many
#: showdowns (about a second with the vectorised evaluator, ADR 0022), else Monte Carlo.
EXACT_WORK_LIMIT = 2_000_000
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


def _combo_arrays(combos) -> tuple[np.ndarray, np.ndarray]:
    cards = np.array([c for c, _ in combos], dtype=np.int64)
    weights = np.array([w for _, w in combos], dtype=float)
    return cards, weights


def _class_results_from_combos(combos, p_win: np.ndarray, p_tie: np.ndarray, share_w: np.ndarray):
    """Aggregate per-combo results into per-class results. ``share_w`` are the combo weights."""
    acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for ((a, b), _), w, pw, pt in zip(combos, share_w, p_win, p_tie, strict=True):
        cell = acc[class_of_combo(a, b)]
        cell[0] += w
        cell[1] += w * pw
        cell[2] += w * pt
    total = float(share_w.sum())
    return {
        label: ClassResult(label, share=w / total, win=win / w, tie=tie / w)
        for label, (w, win, tie) in sorted(acc.items())
        if w > 0
    }


def exact_equity(spot: Spot, rng: Range) -> EquityResult:
    if spot.street is Street.PREFLOP:
        raise EquityError("Exact enumeration preflop is too slow; use Monte Carlo.")
    start = time.perf_counter()
    combos = _live_combos(spot, rng)
    villain, weights = _combo_arrays(combos)
    board = np.array(spot.board, dtype=np.int64)
    live = np.array(remaining_deck(spot.dead_cards), dtype=np.int64)
    k = spot.cards_to_come

    # Every possible runout, and the hero's score on each (computed once).
    if k:
        runouts = np.array(list(itertools.combinations(live, k)), dtype=np.int64)
    else:  # river: a single, empty runout
        runouts = np.empty((1, 0), dtype=np.int64)
    n_c, n_r = len(villain), len(runouts)
    fixed = np.concatenate([np.array(spot.hero, dtype=np.int64), board])
    hero = evaluate_batch(np.hstack([np.broadcast_to(fixed, (n_r, len(fixed))), runouts]))

    # valid[i, j]: runout j does not use one of combo i's cards.
    valid = ~(runouts[None, :, :, None] == villain[:, None, None, :]).any(axis=(2, 3))

    # Villain scores for every (combo, runout) pair in one batch.
    cards = np.concatenate(
        [
            np.broadcast_to(villain[:, None, :], (n_c, n_r, 2)),
            np.broadcast_to(board, (n_c, n_r, len(board))),
            np.broadcast_to(runouts[None, :, :], (n_c, n_r, k)),
        ],
        axis=2,
    ).reshape(-1, 2 + len(board) + k)
    scores = evaluate_batch(cards).reshape(n_c, n_r)

    n = valid.sum(axis=1)  # the same for every combo
    p_win = ((hero[None, :] > scores) & valid).sum(axis=1) / n
    p_tie = ((hero[None, :] == scores) & valid).sum(axis=1) / n
    total_w = weights.sum()
    win = float((weights * p_win).sum() / total_w)
    tie = float((weights * p_tie).sum() / total_w)
    return EquityResult(
        win=win,
        tie=tie,
        lose=1.0 - win - tie,
        method="exact",
        estimate=Estimate(win + 0.5 * tie, 0.0, int(n.sum())),
        live_combos=float(total_w),
        by_class=_class_results_from_combos(combos, p_win, p_tie, weights),
        elapsed_s=time.perf_counter() - start,
    )


# --- Monte Carlo ------------------------------------------------------------------------

_MC_CHUNK = 50_000


def monte_carlo_equity(
    spot: Spot, rng: Range, samples: int = DEFAULT_SAMPLES, seed: int | None = None
) -> EquityResult:
    if samples < 1:
        raise EquityError("Monte Carlo needs at least 1 sample.")
    start = time.perf_counter()
    if seed is None:
        seed = int(np.random.SeedSequence().entropy % 2**32)
    gen = np.random.default_rng(seed)

    combos = _live_combos(spot, rng)
    villain, weights = _combo_arrays(combos)
    board = np.array(spot.board, dtype=np.int64)
    live = np.array(remaining_deck(spot.dead_cards), dtype=np.int64)
    k = spot.cards_to_come
    hero_cards = np.array(spot.hero, dtype=np.int64)

    # Opponent hands for all samples, proportional to weight.
    picks = gen.choice(len(villain), size=samples, p=weights / weights.sum()).astype(np.intp)
    # in_combo[i, j]: live card j belongs to combo i (those cards cannot be dealt).
    in_combo = (live[None, :, None] == villain[:, None, :]).any(axis=2)

    wins = np.zeros(len(villain))
    ties = np.zeros(len(villain))
    for lo in range(0, samples, _MC_CHUNK):
        chunk = picks[lo : lo + _MC_CHUNK]
        m = len(chunk)
        # A uniform random k-subset of the remaining cards per sample: give every card a
        # random key, push the opponent's own cards to the end, keep the k smallest keys.
        keys = gen.random((m, len(live)))
        keys[in_combo[chunk]] = 2.0
        runouts = live[np.argpartition(keys, k - 1, axis=1)[:, :k]] if k else np.empty((m, 0), int)
        common = np.hstack([np.broadcast_to(board, (m, len(board))), runouts])
        hero = evaluate_batch(np.hstack([np.broadcast_to(hero_cards, (m, 2)), common]))
        vill = evaluate_batch(np.hstack([villain[chunk], common]))
        wins += np.bincount(chunk, weights=hero > vill, minlength=len(villain))
        ties += np.bincount(chunk, weights=hero == vill, minlength=len(villain))

    counts = np.bincount(picks, minlength=len(villain)).astype(float)
    n_win, n_tie = int(wins.sum()), int(ties.sum())
    seen = counts > 0
    p_win = np.divide(wins, counts, out=np.zeros_like(wins), where=seen)
    p_tie = np.divide(ties, counts, out=np.zeros_like(ties), where=seen)
    return EquityResult(
        win=n_win / samples,
        tie=n_tie / samples,
        lose=(samples - n_win - n_tie) / samples,
        method="monte_carlo",
        estimate=estimate_from_counts(n_win, n_tie, samples - n_win - n_tie),
        live_combos=float(weights.sum()),
        by_class=_class_results_from_combos(combos, p_win, p_tie, counts),
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
