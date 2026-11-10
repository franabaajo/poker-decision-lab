"""Multi-street model: what calling is worth when betting continues on the turn and river.

M5's EV assumes the hand goes to showdown with no more betting. In reality the
opponent can bet again on each later street, and the hero must call or fold
each time. This module plays that out exactly (ADR 0004, 0018-0020).

The game after the hero calls
-----------------------------
For each remaining street (turn, then river):

1. The next card is dealt.
2. The opponent bets or checks according to their :class:`~pokerlab.profiles.Strategy`:
   they rank the hands they can hold by current made-hand strength and bet a
   fixed fraction of the pot with the strongest ``value_share`` of the range plus
   the weakest ``bluff_share`` of the rest. Everything else checks.
3. If they bet, the hero calls or folds, whichever is worth more.
   If they check, the hero checks (the hero never bets or raises; ADR 0004).

At the end, the remaining players show down.

How it is computed
------------------
**Bayesian narrowing.** The opponent's range is a set of weights. When they bet,
each combo's weight is multiplied by its probability of betting; when they check,
by its probability of checking. So a bet shifts the range towards strong hands and
bluffs, and a check towards the middle.

**Card removal.** After the opponent's combo is fixed, every remaining card is
equally likely to come next, and the number of possible next cards is the same
for every combo. So P(next card = c) is proportional to the total weight of the
combos that do not contain c, and conditioning on c simply drops those combos.

**Backward induction.** ``V(node)`` is the expected number of chips the hero
collects from that point on, minus the chips the hero still puts in. Folding is
worth 0. Solving from the river backwards gives the hero's best call/fold choice
at every decision, assuming the hero knows the opponent's strategy (a best
response; this is optimistic, and the explanation says so).

The EV of calling the current bet is ``-call + V(after the call)``. When the
opponent never bets again this reduces exactly to M5's ``equity * pot - call``;
a test checks that.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field

from pokerlab.cards import remaining_deck
from pokerlab.decision import Situation
from pokerlab.evaluator import evaluate
from pokerlab.profiles import Strategy
from pokerlab.ranges import Range
from pokerlab.spot import Spot, Street


class MultiStreetError(ValueError):
    """The multi-street model cannot be applied (e.g. preflop or empty range)."""


@dataclass(frozen=True)
class MultiStreetResult:
    ev_call: float  # EV of calling now, relative to folding, with later betting
    ev_showdown: float  # EV of calling if nobody bets again (M5's number)
    equity: float  # raw showdown equity against the range
    call: float  # chips the hero puts in to call now
    pot_after_call: float
    later_streets: int  # 0 on the river, 1 on the turn, 2 on the flop
    stats: dict[str, float] = field(default_factory=dict)  # probabilities, given the hero calls
    elapsed_s: float = 0.0

    @property
    def realized_equity(self) -> float:
        """The equity that would give ``ev_call`` if there were no more betting."""
        return (self.ev_call + self.call) / self.pot_after_call

    @property
    def realization(self) -> float:
        """Realised equity / raw equity: 1.0 means later betting changes nothing."""
        return self.realized_equity / self.equity if self.equity else 0.0


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


def _frac(x: float) -> str:
    named = {0.5: "half the pot", 1.0: "the full pot"}
    for value, text in named.items():
        if abs(x - value) < 1e-9:
            return text
    if abs(x - 2 / 3) < 1e-9:
        return "two thirds of the pot"
    return f"{x:.0%} of the pot"


def explain(result: MultiStreetResult, strategy: Strategy, style_name: str) -> str:
    """Plain-language explanation of the multi-street result."""
    c, pot = result.call, result.pot_after_call
    parts = [
        f"Calling costs {_chips(c)} and makes the pot {_chips(pot)}. "
        f"If nobody bet again, your {result.equity:.1%} equity would make the call worth "
        f"{_chips(result.ev_showdown, signed=True)}."
    ]
    if result.later_streets == 0:
        parts.append("This is the river, so no more betting can follow.")
    elif result.stats.get("bet_turn", 0) == 0 and result.stats.get("bet_river", 0) == 0:
        parts.append("No chips are left behind, so no more betting can follow.")
    else:
        streets = "the turn and river" if result.later_streets == 2 else "the river"
        folds = result.stats["fold_turn"] + result.stats["fold_river"]
        parts.append(
            f"But betting continues on {streets}: a {style_name.lower()} opponent is assumed "
            f"to bet {_frac(strategy.bet_fraction)} with their strongest "
            f"{strategy.value_share:.0%} of hands plus {strategy.bluff_share:.0%} of the rest "
            f"as bluffs. Choosing the better of call or fold each time, you fold before "
            f"showdown {folds:.0%} of the time, and calling now is worth "
            f"{_chips(result.ev_call, signed=True)} overall."
        )
        if result.realization >= 1.005:
            parts.append(
                f"You realise {result.realization:.0%} of your raw equity: the extra bets you "
                "collect when ahead outweigh the pots you give up when you fold."
            )
        elif result.realization <= 0.995:
            parts.append(
                f"You realise only {result.realization:.0%} of your raw equity: later bets "
                "force you to give up some pots you would have won or split at showdown."
            )
    verdict = "Call" if result.ev_call > 0 else "Fold"
    parts.append(
        f"Mathematical decision: {verdict}. This holds under the range and betting style you "
        "assumed, against one opponent, and assumes you respond optimally to that style."
    )
    return " ".join(parts)


def _chips(x: float, signed: bool = False) -> str:
    text = f"{x:+,.1f}" if signed else f"{x:,.1f}"
    return f"{text.removesuffix('.0')} chips"
