"""Vectorised hand evaluator: score many hands at once with NumPy (ADR 0021).

Same scores as :func:`pokerlab.evaluator.evaluate` (the readable reference), but
for a whole array of hands in one call::

    evaluate_batch(np.array([[51, 47, 43, 39, 35, 0, 1], ...]))  ->  array of scores

How it works
------------
Instead of looping over hands, every step operates on all N hands together:

1. ``ranks = cards // 4`` and ``suits = cards % 4`` for the whole (N, k) array.
2. Per-hand rank and suit counts with one ``np.bincount`` over a flattened index.
3. A 13-bit mask per hand of the ranks present (bit r set if rank r appears),
   and another for the ranks of the flush suit.
4. Two precomputed 8,192-entry lookup tables turn a 13-bit mask into
   "highest straight card" and "top five ranks, packed", so straights,
   flushes and kickers need no loops.
5. Each category's score is computed for every hand, and ``np.select`` keeps
   the one matching the hand's actual category, in poker priority order.

Correctness: the tests require identical scores to the reference evaluator on
every 5-card hand and on millions of random 6- and 7-card hands.
"""

from __future__ import annotations

import numpy as np

_RANKS = np.arange(13)
_MAX_ROWS = 250_000  # process in chunks to bound memory use


def _build_tables() -> tuple[np.ndarray, np.ndarray]:
    """STRAIGHT_HIGH[mask]: top rank of the best straight (-1 if none).
    TOP5[mask]: the highest (up to) five ranks in the mask, packed 4 bits each,
    most significant first, exactly like the score's tie-break slots."""
    straight = np.full(1 << 13, -1, dtype=np.int64)
    top5 = np.zeros(1 << 13, dtype=np.int64)
    for mask in range(1 << 13):
        for high in range(12, 3, -1):
            window = 0b11111 << (high - 4)
            if mask & window == window:
                straight[mask] = high
                break
        else:
            wheel = (1 << 12) | 0b1111  # A-2-3-4-5
            if mask & wheel == wheel:
                straight[mask] = 3
        packed, n = 0, 0
        for r in range(12, -1, -1):
            if mask >> r & 1 and n < 5:
                packed |= r << (4 * (4 - n))
                n += 1
        top5[mask] = packed
    return straight, top5


STRAIGHT_HIGH, TOP5 = _build_tables()

HIGH_CARD, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)


def _slots(mask: np.ndarray, first: int, count: int) -> np.ndarray:
    """Top ``count`` ranks of ``mask``, placed in tie-break slots ``first..first+count-1``."""
    keep = ((1 << (4 * count)) - 1) << (4 * (5 - first - count))
    return (TOP5[mask] >> (4 * first)) & keep


def _highest(cond: np.ndarray) -> np.ndarray:
    """Index of the highest rank where ``cond`` (N, 13) is true; -1 where none."""
    idx = 12 - np.argmax(cond[:, ::-1], axis=1)
    return np.where(cond.any(axis=1), idx, -1)


def evaluate_batch(cards: np.ndarray) -> np.ndarray:
    """Scores (int64, higher is better) for an (N, k) array of hands, 5 <= k <= 7."""
    cards = np.asarray(cards)
    if cards.ndim != 2 or not 5 <= cards.shape[1] <= 7:
        raise ValueError(f"expected an (N, 5..7) array of cards, got shape {cards.shape}")
    if len(cards) > _MAX_ROWS:
        return np.concatenate(
            [_evaluate(cards[i : i + _MAX_ROWS]) for i in range(0, len(cards), _MAX_ROWS)]
        )
    return _evaluate(cards)


def _evaluate(cards: np.ndarray) -> np.ndarray:
    n = len(cards)
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    cards = cards.astype(np.int64, copy=False)
    ranks, suits = cards // 4, cards % 4
    rows = np.arange(n)[:, None]

    # 1. Counts per rank and per suit, for all hands at once.
    rank_counts = np.bincount((rows * 13 + ranks).ravel(), minlength=n * 13).reshape(n, 13)
    suit_counts = np.bincount((rows * 4 + suits).ravel(), minlength=n * 4).reshape(n, 4)

    # 2. 13-bit masks of the ranks present, overall and in the flush suit.
    bits = 1 << ranks
    present = (rank_counts > 0) @ (1 << _RANKS)
    flush_suit = suit_counts.argmax(axis=1)
    has_flush = suit_counts.max(axis=1) >= 5
    flush_bits = np.bitwise_or.reduce(np.where(suits == flush_suit[:, None], bits, 0), axis=1)

    # 3. Multiplicities: highest quads / trips / pairs.
    quad = _highest(rank_counts == 4)
    trips_cond = rank_counts == 3
    trip1 = _highest(trips_cond)
    trip2 = _highest(trips_cond & (trip1[:, None] != _RANKS))
    pair_cond = rank_counts == 2
    pair1 = _highest(pair_cond)
    pair2 = _highest(pair_cond & (pair1[:, None] != _RANKS))

    def without(*rs: np.ndarray) -> np.ndarray:
        mask = present.copy()
        for r in rs:
            mask &= ~np.where(r >= 0, 1 << np.maximum(r, 0), 0)
        return mask

    sf_high = np.where(has_flush, STRAIGHT_HIGH[flush_bits], -1)
    st_high = STRAIGHT_HIGH[present]
    fh_pair = np.maximum(trip2, pair1)

    def score(cat: int, body: np.ndarray) -> np.ndarray:
        return (cat << 20) | body

    conditions = [
        sf_high >= 0,
        quad >= 0,
        (trip1 >= 0) & (fh_pair >= 0),
        has_flush,
        st_high >= 0,
        trip1 >= 0,
        pair2 >= 0,
        pair1 >= 0,
    ]
    choices = [
        score(STRAIGHT_FLUSH, np.maximum(sf_high, 0) << 16),
        score(QUADS, (np.maximum(quad, 0) << 16) | _slots(without(quad), 1, 1)),
        score(FULL_HOUSE, (np.maximum(trip1, 0) << 16) | (np.maximum(fh_pair, 0) << 12)),
        score(FLUSH, TOP5[flush_bits]),
        score(STRAIGHT, np.maximum(st_high, 0) << 16),
        score(TRIPS, (np.maximum(trip1, 0) << 16) | _slots(without(trip1), 1, 2)),
        score(
            TWO_PAIR,
            (np.maximum(pair1, 0) << 16)
            | (np.maximum(pair2, 0) << 12)
            | _slots(without(pair1, pair2), 2, 1),
        ),
        score(PAIR, (np.maximum(pair1, 0) << 16) | _slots(without(pair1), 1, 3)),
    ]
    return np.select(conditions, choices, default=score(HIGH_CARD, TOP5[present]))
