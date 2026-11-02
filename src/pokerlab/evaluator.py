"""Hand evaluator: turn 5, 6 or 7 cards into a single comparable score.

The score is an ``int`` where **higher means better**, so deciding a showdown is
just ``evaluate(hero_7) > evaluate(villain_7)``. Equal scores mean a split pot.

Score layout (bit-packed so that integer comparison = poker comparison)::

    bits 20-23   category   0 = high card ... 8 = straight flush
    bits 16-19   1st tie-break rank
    bits 12-15   2nd tie-break rank
    ...
    bits  0-3    5th tie-break rank

Tie-break ranks are listed most significant first, e.g. for two pair:
(high pair, low pair, kicker). Ranks use the engine's 0 (deuce) .. 12 (ace).

The evaluator works directly on rank and suit counts instead of trying all 21
five-card subsets of a 7-card hand. That is several times faster and is still
easy to read. Correctness is established in the tests by (1) exhaustive counts
over all 2,598,960 five-card hands, (2) agreement with brute force "best of all
5-card subsets", (3) cross-checks against the independent ``treys`` library and
(4) property-based tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import IntEnum

from pokerlab.cards import RANK_NAMES, rank_of, suit_of


class Category(IntEnum):
    HIGH_CARD = 0
    PAIR = 1
    TWO_PAIR = 2
    TRIPS = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    QUADS = 7
    STRAIGHT_FLUSH = 8

    @property
    def label(self) -> str:
        return _CATEGORY_LABELS[self]


_CATEGORY_LABELS = {
    Category.HIGH_CARD: "High card",
    Category.PAIR: "One pair",
    Category.TWO_PAIR: "Two pair",
    Category.TRIPS: "Three of a kind",
    Category.STRAIGHT: "Straight",
    Category.FLUSH: "Flush",
    Category.FULL_HOUSE: "Full house",
    Category.QUADS: "Four of a kind",
    Category.STRAIGHT_FLUSH: "Straight flush",
}

_ACE = 12
_FIVE = 3  # rank index of the five: top card of the wheel A-2-3-4-5


def _score(category: Category, ranks: Sequence[int]) -> int:
    """Pack a category and up to five tie-break ranks into one int."""
    score = int(category)
    for i in range(5):
        score = (score << 4) | (ranks[i] if i < len(ranks) else 0)
    return score


def _straight_high(rank_set: set[int]) -> int | None:
    """Highest card of the best straight in ``rank_set``, or None.

    The ace also plays low: A-2-3-4-5 (the "wheel") is a five-high straight.
    """
    for high in range(_ACE, _FIVE, -1):  # ace-high down to six-high
        if all(r in rank_set for r in range(high - 4, high + 1)):
            return high
    if _ACE in rank_set and all(r in rank_set for r in range(0, 4)):
        return _FIVE
    return None


def evaluate(cards: Sequence[int]) -> int:
    """Score the best 5-card poker hand that can be made from 5-7 cards."""
    n = len(cards)
    if not 5 <= n <= 7:
        raise ValueError(f"evaluate() needs 5 to 7 cards, got {n}")

    rank_counts = [0] * 13
    suit_cards: list[list[int]] = [[], [], [], []]
    for card in cards:
        r = rank_of(card)
        rank_counts[r] += 1
        suit_cards[suit_of(card)].append(r)

    # Flushes and straight flushes. With at most 7 cards only one suit can have 5+.
    for suited in suit_cards:
        if len(suited) >= 5:
            sf_high = _straight_high(set(suited))
            if sf_high is not None:
                return _score(Category.STRAIGHT_FLUSH, [sf_high])
            flush_score = _score(Category.FLUSH, sorted(suited, reverse=True)[:5])
            break
    else:
        flush_score = None

    # Group ranks by multiplicity, each list from highest rank to lowest.
    quads = [r for r in range(12, -1, -1) if rank_counts[r] == 4]
    trips = [r for r in range(12, -1, -1) if rank_counts[r] == 3]
    pairs = [r for r in range(12, -1, -1) if rank_counts[r] == 2]
    present = [r for r in range(12, -1, -1) if rank_counts[r] > 0]

    def kickers(exclude: set[int], k: int) -> list[int]:
        return [r for r in present if r not in exclude][:k]

    if quads:
        q = quads[0]
        return _score(Category.QUADS, [q, *kickers({q}, 1)])

    if trips and (len(trips) >= 2 or pairs):
        t = trips[0]
        # The pair may come from a second set of trips: KKK QQQ x = kings full of queens.
        p = max([*trips[1:], *pairs])
        return _score(Category.FULL_HOUSE, [t, p])

    if flush_score is not None:
        return flush_score

    st_high = _straight_high(set(present))
    if st_high is not None:
        return _score(Category.STRAIGHT, [st_high])

    if trips:
        t = trips[0]
        return _score(Category.TRIPS, [t, *kickers({t}, 2)])

    if len(pairs) >= 2:
        hi, lo = pairs[0], pairs[1]
        # A third pair can still provide the kicker.
        return _score(Category.TWO_PAIR, [hi, lo, *kickers({hi, lo}, 1)])

    if pairs:
        p = pairs[0]
        return _score(Category.PAIR, [p, *kickers({p}, 3)])

    return _score(Category.HIGH_CARD, present[:5])


def category_of(score: int) -> Category:
    """The hand category encoded in a score."""
    return Category(score >> 20)


def tiebreak_ranks(score: int) -> tuple[int, ...]:
    """The five tie-break rank slots encoded in a score (unused slots are 0)."""
    return tuple((score >> shift) & 0xF for shift in (16, 12, 8, 4, 0))


def describe(score: int) -> str:
    """Human-readable text, e.g. ``"Flush, ace high"`` or ``"Full house, kings full of queens"``."""
    cat = category_of(score)
    r = tiebreak_ranks(score)

    def name(rank: int) -> str:
        return RANK_NAMES[rank]

    def plural(rank: int) -> str:
        return "sixes" if rank == 4 else f"{RANK_NAMES[rank]}s"

    match cat:
        case Category.STRAIGHT_FLUSH:
            return "Royal flush" if r[0] == _ACE else f"Straight flush, {name(r[0])} high"
        case Category.QUADS:
            return f"Four of a kind, {plural(r[0])}"
        case Category.FULL_HOUSE:
            return f"Full house, {plural(r[0])} full of {plural(r[1])}"
        case Category.FLUSH:
            return f"Flush, {name(r[0])} high"
        case Category.STRAIGHT:
            return f"Straight, {name(r[0])} high"
        case Category.TRIPS:
            return f"Three of a kind, {plural(r[0])}"
        case Category.TWO_PAIR:
            return f"Two pair, {plural(r[0])} and {plural(r[1])}"
        case Category.PAIR:
            return f"One pair, {plural(r[0])}"
        case _:
            return f"High card, {name(r[0])}"


def compare(hand_a: Sequence[int], hand_b: Sequence[int]) -> int:
    """+1 if ``hand_a`` wins, -1 if ``hand_b`` wins, 0 for a split."""
    a, b = evaluate(hand_a), evaluate(hand_b)
    return (a > b) - (a < b)
