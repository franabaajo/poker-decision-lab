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

**Vectorised.** Weights are NumPy arrays over the opponent's combos, and the
river is solved for all river cards at once as a (river cards x combos) matrix,
so the whole flop tree takes well under a second (ADR 0021). The readable
one-combo-at-a-time version is kept in :mod:`pokerlab.reference.multistreet`
and the tests require both to agree.

The EV of calling the current bet is ``-call + V(after the call)``. When the
opponent never bets again this reduces exactly to M5's ``equity * pot - call``;
a test checks that.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from pokerlab.cards import remaining_deck
from pokerlab.decision import Situation
from pokerlab.evaluator_fast import evaluate_batch
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
    groups = _Groups(np.asarray(strengths))
    return groups.bet_probabilities(np.asarray(weights, dtype=float), strategy).tolist()


class _Groups:
    """Combos sorted strongest first and grouped by equal strength (for one board)."""

    def __init__(self, scores: np.ndarray):
        self.order = np.argsort(-scores, kind="stable")
        sorted_scores = scores[self.order]
        self.starts = np.flatnonzero(np.r_[True, sorted_scores[1:] != sorted_scores[:-1]])
        self.group_of_sorted = np.repeat(
            np.arange(len(self.starts)), np.diff(np.r_[self.starts, len(scores)])
        )

    def bet_probabilities(self, weights: np.ndarray, strategy: Strategy) -> np.ndarray:
        total = weights.sum()
        probs = np.zeros(len(weights))
        if total <= 0:
            return probs
        mass = np.add.reduceat(weights[self.order], self.starts)
        hi = np.cumsum(mass)
        lo = hi - mass
        value_end = strategy.value_share * total
        bluff_start = total - strategy.bluff_share * (1.0 - strategy.value_share) * total
        overlap = np.clip(np.minimum(hi, value_end) - lo, 0, None) + np.clip(
            hi - np.maximum(lo, bluff_start), 0, None
        )
        p_group = np.divide(overlap, mass, out=np.zeros_like(mass), where=mass > 0)
        probs[self.order] = np.minimum(1.0, p_group)[self.group_of_sorted]
        return probs


class _Tree:
    """Holds the fixed inputs and score caches while the game tree is solved.

    Weights are NumPy arrays over the opponent's live combos, so every step
    (betting probabilities, Bayesian update, showdown share) is a vector operation.
    """

    def __init__(self, spot: Spot, combos, strategy: Strategy):
        self.hero = np.array(spot.hero, dtype=np.int64)
        self.board = np.array(spot.board, dtype=np.int64)
        self.combos = np.array([c for c, _ in combos], dtype=np.int64)
        self.base_weights = np.array([w for _, w in combos], dtype=float)
        self.strategy = strategy
        self.deck = remaining_deck(spot.dead_cards)
        # blocks[card]: boolean mask of the combos that contain that card.
        self.blocks = {c: (self.combos == c).any(axis=1) for c in self.deck}
        self._cache: dict[tuple[int, ...], tuple[np.ndarray, int, _Groups]] = {}
        self._river_cache: dict[tuple[int, ...], dict[str, np.ndarray]] = {}

    def board_info(self, extra: tuple[int, ...]) -> tuple[np.ndarray, int, _Groups]:
        """Opponent scores on board + extra (blocked combos get -1), hero score, groups."""
        key = tuple(sorted(extra))
        cached = self._cache.get(key)
        if cached is None:
            cards = np.array(key, dtype=np.int64)
            n = len(self.combos)
            hands = np.hstack(
                [
                    self.combos,
                    np.broadcast_to(self.board, (n, len(self.board))),
                    np.broadcast_to(cards, (n, len(cards))),
                ]
            )
            scores = evaluate_batch(hands)
            for c in key:
                scores[self.blocks[c]] = -1
            hero = int(evaluate_batch(np.concatenate([self.hero, self.board, cards])[None, :])[0])
            cached = (scores, hero, _Groups(scores))
            self._cache[key] = cached
        return cached

    def river_data(self, extra: tuple[int, ...]) -> dict[str, np.ndarray]:
        """All possible river cards after board + extra, as (rivers, combos) arrays."""
        key = tuple(sorted(extra))
        data = self._river_cache.get(key)
        if data is None:
            rivers = np.array([c for c in self.deck if c not in key], dtype=np.int64)
            m, n = len(rivers), len(self.combos)
            known = np.concatenate([self.board, np.array(key, dtype=np.int64)])
            hands = np.concatenate(
                [
                    np.broadcast_to(self.combos[None, :, :], (m, n, 2)),
                    np.broadcast_to(known, (m, n, len(known))),
                    np.broadcast_to(rivers[:, None, None], (m, n, 1)),
                ],
                axis=2,
            ).reshape(m * n, -1)
            blocked = (self.combos[None, :, :] == rivers[:, None, None]).any(axis=2)
            for c in key:
                blocked |= self.blocks[c][None, :]
            scores = evaluate_batch(hands).reshape(m, n)
            scores[blocked] = -1
            hero = evaluate_batch(
                np.hstack(
                    [
                        np.broadcast_to(np.concatenate([self.hero, known]), (m, 2 + len(known))),
                        rivers[:, None],
                    ]
                )
            )
            # Strength order and equal-strength groups for every river card at once.
            order = np.argsort(-scores, axis=1, kind="stable")
            ss = np.take_along_axis(scores, order, axis=1)
            new_group = np.ones_like(ss, dtype=bool)
            new_group[:, 1:] = ss[:, 1:] != ss[:, :-1]
            pos = np.broadcast_to(np.arange(n), (m, n))
            start = np.maximum.accumulate(np.where(new_group, pos, 0), axis=1)
            end_marker = np.ones_like(ss, dtype=bool)
            end_marker[:, :-1] = new_group[:, 1:]
            end = np.minimum.accumulate(np.where(end_marker, pos, n - 1)[:, ::-1], axis=1)[:, ::-1]
            data = {
                "blocked": blocked,
                "share": (hero[:, None] > scores) + 0.5 * (hero[:, None] == scores),
                "order": order,
                "start": start,
                "end": end,
            }
            self._river_cache[key] = data
        return data

    def river_stage(self, extra, weights, pot, stack, betting=True):
        """Deal the river and play it out, for all river cards at once. Returns (value, stats).

        Equivalent to ``deal(..., cards_left=1)`` but vectorised over river cards.
        """
        d = self.river_data(extra)
        w = np.where(d["blocked"], 0.0, weights[None, :])  # (rivers, combos)
        mass = w.sum(axis=1)
        size = min(self.strategy.bet_fraction * pot, stack) if betting else 0.0
        if size > 0:
            s = self.strategy
            cum = np.zeros((w.shape[0], w.shape[1] + 1))
            np.cumsum(np.take_along_axis(w, d["order"], axis=1), axis=1, out=cum[:, 1:])
            lo = np.take_along_axis(cum, d["start"], axis=1)
            hi = np.take_along_axis(cum, d["end"] + 1, axis=1)
            group_mass = hi - lo
            total = mass[:, None]
            value_end = s.value_share * total
            bluff_start = total - s.bluff_share * (1.0 - s.value_share) * total
            overlap = np.clip(np.minimum(hi, value_end) - lo, 0, None) + np.clip(
                hi - np.maximum(lo, bluff_start), 0, None
            )
            p_sorted = np.minimum(
                1.0,
                np.divide(overlap, group_mass, out=np.zeros_like(overlap), where=group_mass > 0),
            )
            probs = np.empty_like(p_sorted)
            np.put_along_axis(probs, d["order"], p_sorted, axis=1)
        else:
            probs = np.zeros_like(w)

        w_bet = w * probs
        w_chk = w - w_bet
        m_bet, m_chk = w_bet.sum(axis=1), w_chk.sum(axis=1)
        share_bet = np.divide(
            (w_bet * d["share"]).sum(axis=1), m_bet, out=np.zeros_like(m_bet), where=m_bet > 0
        )
        share_chk = np.divide(
            (w_chk * d["share"]).sum(axis=1), m_chk, out=np.zeros_like(m_chk), where=m_chk > 0
        )
        v_call = (pot + 2 * size) * share_bet - size
        calls = (v_call > 0) & (m_bet > 0)
        values = m_chk * pot * share_chk + np.where(calls, m_bet * v_call, 0.0)

        total = mass.sum()
        if total <= 0:
            return 0.0, {}
        stats = {
            "bet_river": float(m_bet.sum() / total),
            "fold_river": float(np.where(calls, 0.0, m_bet).sum() / total),
            "showdown": float((m_chk + np.where(calls, m_bet, 0.0)).sum() / total),
        }
        return float(values.sum() / total), stats

    def deal(self, extra, weights, pot, stack, cards_left, betting=True):
        """Average over the next card. Returns (value, stats)."""
        if cards_left == 1:
            return self.river_stage(extra, weights, pot, stack, betting)
        total = value = 0.0
        stats: dict[str, float] = {}
        for card in self.deck:
            if card in extra:
                continue
            w = np.where(self.blocks[card], 0.0, weights)
            mass = w.sum()
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
        scores, hero, _ = self.board_info(extra)
        total = weights.sum()
        if total <= 0:
            return 0.0
        share = (weights * ((hero > scores) + 0.5 * (hero == scores))).sum()
        return float(share / total)

    def act(self, extra, weights, pot, stack, cards_left, betting=True):
        """Opponent acts on board + extra; hero responds. Returns (value, stats)."""
        street = "turn" if len(self.board) + len(extra) == 4 else "river"
        size = min(self.strategy.bet_fraction * pot, stack) if betting else 0.0
        if size > 0:
            _, _, groups = self.board_info(extra)
            probs = groups.bet_probabilities(weights, self.strategy)
        else:
            probs = np.zeros(len(weights))

        w_bet = weights * probs
        w_chk = weights - w_bet
        m_bet, m_chk = float(w_bet.sum()), float(w_chk.sum())
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
