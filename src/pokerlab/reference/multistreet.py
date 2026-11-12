"""Reference (pure Python) multi-street model, kept as a test oracle and benchmark baseline.

This is the M6 implementation, one combo at a time with the readable reference
evaluator. :mod:`pokerlab.multistreet` is the vectorised version used by the app;
tests require both to give the same results (ADR 0021).
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from pokerlab.cards import remaining_deck
from pokerlab.decision import Situation
from pokerlab.evaluator import evaluate
from pokerlab.multistreet import MultiStreetError, MultiStreetResult
from pokerlab.profiles import Strategy
from pokerlab.ranges import Range
from pokerlab.spot import Spot, Street


def bet_probabilities(
    strengths: Sequence[int], weights: Sequence[float], strategy: Strategy
) -> list[float]:
    """Probability that each combo bets, given the current (weighted) range.

    Combos are ranked strongest first. The top ``value_share`` of the weight mass
    bets for value and the bottom ``bluff_share * (1 - value_share)`` bets as a
    bluff. Combos with equal strength are treated alike, so a group straddling a
    threshold gets a fractional probability. This keeps the betting share of the
    range exactly equal to ``strategy.bet_share``.
    """
    order = sorted(range(len(strengths)), key=lambda i: -strengths[i])
    return _bet_probs_sorted(order, strengths, weights, strategy)


def _bet_probs_sorted(
    order: Sequence[int],
    strengths: Sequence[int],
    weights: Sequence[float],
    strategy: Strategy,
) -> list[float]:
    probs = [0.0] * len(strengths)
    total = sum(weights)
    if total <= 0:
        return probs
    value_end = strategy.value_share * total
    bluff_start = total - strategy.bluff_share * (1.0 - strategy.value_share) * total

    cum = 0.0
    i = 0
    n = len(order)
    while i < n:
        # Collect one group of equal strength.
        j = i
        group_mass = 0.0
        s = strengths[order[i]]
        while j < n and strengths[order[j]] == s:
            group_mass += weights[order[j]]
            j += 1
        if group_mass > 0:
            lo, hi = cum, cum + group_mass
            overlap = max(0.0, min(hi, value_end) - lo) + max(0.0, hi - max(lo, bluff_start))
            p = min(1.0, overlap / group_mass)
            for k in range(i, j):
                probs[order[k]] = p
        cum += group_mass
        i = j
    return probs


class _Tree:
    """Holds the fixed inputs and score caches while the game tree is solved."""

    def __init__(self, spot: Spot, combos, strategy: Strategy):
        self.hero = list(spot.hero)
        self.board = list(spot.board)
        self.combos = [c for c, _ in combos]
        self.base_weights = [w for _, w in combos]
        self.strategy = strategy
        self.deck = remaining_deck(spot.dead_cards)
        self._opp_scores: dict[tuple[int, ...], tuple[list[int], list[int]]] = {}
        self._hero_scores: dict[tuple[int, ...], int] = {}

    # --- cached evaluation ---

    def scores(self, extra: tuple[int, ...]) -> tuple[list[int], list[int]]:
        """Opponent scores on board + extra (blocked combos get -1) and their strength order."""
        key = tuple(sorted(extra))
        cached = self._opp_scores.get(key)
        if cached is None:
            board = [*self.board, *key]
            scores = [
                -1 if (a in key or b in key) else evaluate([a, b, *board]) for a, b in self.combos
            ]
            order = sorted(range(len(scores)), key=lambda i: -scores[i])
            cached = (scores, order)
            self._opp_scores[key] = cached
        return cached

    def hero_score(self, extra: tuple[int, ...]) -> int:
        key = tuple(sorted(extra))
        if key not in self._hero_scores:
            self._hero_scores[key] = evaluate([*self.hero, *self.board, *key])
        return self._hero_scores[key]

    # --- the game ---

    def deal(self, extra, weights, pot, stack, cards_left, betting=True):
        """Average over the next card. Returns (value, stats)."""
        total = 0.0
        value = 0.0
        stats: dict[str, float] = {}
        for card in self.deck:
            if card in extra:
                continue
            w = [
                0.0 if card in combo else wt for combo, wt in zip(self.combos, weights, strict=True)
            ]
            mass = sum(w)
            if mass <= 0:
                continue
            v, st = self.act((*extra, card), w, pot, stack, cards_left - 1, betting)
            total += mass
            value += mass * v
            for k, x in st.items():
                stats[k] = stats.get(k, 0.0) + mass * x
        if total <= 0:
            return 0.0, {}
        return value / total, {k: x / total for k, x in stats.items()}

    def showdown_share(self, extra, weights) -> float:
        """Hero's expected share of the pot at showdown against the weighted range."""
        scores, _ = self.scores(extra)
        hero = self.hero_score(extra)
        total = share = 0.0
        for score, w in zip(scores, weights, strict=True):
            if w <= 0:
                continue
            total += w
            if hero > score:
                share += w
            elif hero == score:
                share += 0.5 * w
        return share / total if total > 0 else 0.0

    def act(self, extra, weights, pot, stack, cards_left, betting=True):
        """Opponent acts on board + extra; hero responds. Returns (value, stats)."""
        street = "turn" if len(self.board) + len(extra) == 4 else "river"
        size = min(self.strategy.bet_fraction * pot, stack) if betting else 0.0
        scores, order = self.scores(extra)
        if size > 0:
            probs = _bet_probs_sorted(order, scores, weights, self.strategy)
        else:
            probs = [0.0] * len(weights)

        w_bet = [w * p for w, p in zip(weights, probs, strict=True)]
        w_chk = [w - b for w, b in zip(weights, w_bet, strict=True)]
        m_bet, m_chk = sum(w_bet), sum(w_chk)
        m_total = m_bet + m_chk

        def continuation(w, pot_, stack_):
            if cards_left == 0:
                return pot_ * self.showdown_share(extra, w), {"showdown": 1.0}
            return self.deal(extra, w, pot_, stack_, cards_left, betting)

        stats: dict[str, float] = {f"bet_{street}": m_bet / m_total}
        value = 0.0
        if m_chk > 0:
            v_chk, st_chk = continuation(w_chk, pot, stack)
            value += m_chk * v_chk
            for k, x in st_chk.items():
                stats[k] = stats.get(k, 0.0) + (m_chk / m_total) * x
        if m_bet > 0:
            v_cont, st_cont = continuation(w_bet, pot + 2 * size, stack - size)
            v_call = v_cont - size
            if v_call > 0:  # call (fold is worth 0)
                value += m_bet * v_call
                for k, x in st_cont.items():
                    stats[k] = stats.get(k, 0.0) + (m_bet / m_total) * x
            else:
                stats[f"fold_{street}"] = m_bet / m_total
        return value / m_total, stats


def analyse_call(
    spot: Spot, rng: Range, situation: Situation, strategy: Strategy
) -> MultiStreetResult:
    """EV of calling the current bet, with turn and river betting modelled."""
    if spot.street is Street.PREFLOP:
        raise MultiStreetError(
            "Later-street betting is modelled from the flop onwards; preflop shows the "
            "showdown-only EV."
        )
    start = time.perf_counter()
    combos = rng.combos(spot.dead_cards)
    if not combos:
        raise MultiStreetError("The opponent range has no possible hands left.")

    tree = _Tree(spot, combos, strategy)
    call = situation.call
    pot = situation.final_pot
    stack = situation.stack - call
    k = spot.cards_to_come
    weights = tree.base_weights

    if k == 0:
        equity = tree.showdown_share((), weights)
        v_bet = v_none = pot * equity
        stats = {"showdown": 1.0}
    else:
        v_bet, stats = tree.deal((), weights, pot, stack, k, betting=True)
        v_none, _ = tree.deal((), weights, pot, stack, k, betting=False)
        equity = v_none / pot

    # Fill in zeros for events that never happened, so the API shape is stable.
    for key in ("bet_turn", "fold_turn", "bet_river", "fold_river", "showdown"):
        stats.setdefault(key, 0.0)

    return MultiStreetResult(
        ev_call=v_bet - call,
        ev_showdown=v_none - call,
        equity=equity,
        call=call,
        pot_after_call=pot,
        later_streets=k,
        stats=stats,
        elapsed_s=time.perf_counter() - start,
    )
