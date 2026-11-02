"""M2: cross-check against `treys`, an independent open-source evaluator.

`treys` is used ONLY here, as an oracle; the app never depends on it (ADR 0011).
It scores hands from 1 (royal flush) to 7462 (worst high card): LOWER is better,
the opposite of our convention.
"""

import random

import treys

from pokerlab.cards import card_to_str
from pokerlab.evaluator import Category, category_of, evaluate

_EVALUATOR = treys.Evaluator()

# treys rank classes: 0 = royal flush, 1 = straight flush ... 9 = high card.
# We treat a royal flush as the best straight flush, so 0 and 1 map to the same category.
_TREYS_CLASS_TO_CATEGORY = {
    0: Category.STRAIGHT_FLUSH,
    1: Category.STRAIGHT_FLUSH,
    2: Category.QUADS,
    3: Category.FULL_HOUSE,
    4: Category.FLUSH,
    5: Category.STRAIGHT,
    6: Category.TRIPS,
    7: Category.TWO_PAIR,
    8: Category.PAIR,
    9: Category.HIGH_CARD,
}


def treys_score(cards: list[int]) -> int:
    """Score with treys (lower is better). Cards are our ints, converted via "As"-style strings."""
    tc = [treys.Card.new(card_to_str(c)) for c in cards]
    return _EVALUATOR.evaluate(tc[2:], tc[:2])  # (board, hand)


def test_same_category_on_random_seven_card_hands():
    rng = random.Random(7)
    for _ in range(10_000):
        hand = rng.sample(range(52), 7)
        expected = _TREYS_CLASS_TO_CATEGORY[_EVALUATOR.get_rank_class(treys_score(hand))]
        assert category_of(evaluate(hand)) is expected, [card_to_str(c) for c in hand]


def test_same_showdown_winner_on_random_heads_up_hands():
    """Deal hero and villain 2 cards each plus a shared 5-card board; both evaluators must agree."""
    rng = random.Random(11)
    for _ in range(10_000):
        cards = rng.sample(range(52), 9)
        hero, villain, board = cards[:2], cards[2:4], cards[4:]
        ours = evaluate(hero + board) - evaluate(villain + board)
        theirs = treys_score(villain + board) - treys_score(
            hero + board
        )  # flipped: lower is better
        assert (ours > 0) == (theirs > 0) and (ours == 0) == (theirs == 0), [
            card_to_str(c) for c in cards
        ]
