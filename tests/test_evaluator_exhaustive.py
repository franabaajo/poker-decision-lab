"""M2: evaluate all C(52,5) = 2,598,960 five-card hands and compare with known totals.

These counts are standard combinatorics results (see any probability textbook or
https://en.wikipedia.org/wiki/Poker_probability). A single misclassified hand
anywhere in the deck makes this test fail.

Takes ~20-30 s, so it is marked ``slow``: skip it locally with ``-m "not slow"``.
CI always runs it.
"""

import itertools
from collections import Counter

import pytest

from pokerlab.evaluator import Category, category_of, evaluate

EXPECTED_COUNTS = {
    Category.STRAIGHT_FLUSH: 40,  # includes the 4 royal flushes
    Category.QUADS: 624,
    Category.FULL_HOUSE: 3_744,
    Category.FLUSH: 5_108,
    Category.STRAIGHT: 10_200,
    Category.TRIPS: 54_912,
    Category.TWO_PAIR: 123_552,
    Category.PAIR: 1_098_240,
    Category.HIGH_CARD: 1_302_540,
}

# Hands that differ only in suits are equally strong; there are exactly
# 7,462 distinct strength classes of five-card hands.
EXPECTED_DISTINCT_STRENGTHS = 7_462


@pytest.mark.slow
def test_all_five_card_hands():
    counts: Counter[Category] = Counter()
    distinct: set[int] = set()
    for hand in itertools.combinations(range(52), 5):
        score = evaluate(hand)
        counts[category_of(score)] += 1
        distinct.add(score)

    assert sum(counts.values()) == 2_598_960
    assert dict(counts) == EXPECTED_COUNTS
    assert len(distinct) == EXPECTED_DISTINCT_STRENGTHS
