"""M2 tests: hand evaluator on hand-picked examples and against brute force."""

import itertools
import random

import pytest

from pokerlab.cards import parse_cards
from pokerlab.evaluator import Category, category_of, compare, describe, evaluate


def ev(text: str) -> int:
    return evaluate(parse_cards(text))


# --- Each category is recognised -------------------------------------------------------


@pytest.mark.parametrize(
    ("hand", "category"),
    [
        ("AsKsQsJsTs", Category.STRAIGHT_FLUSH),
        ("9h9d9c9sKd", Category.QUADS),
        ("KhKdKsQcQh", Category.FULL_HOUSE),
        ("AhKhQh9h2h", Category.FLUSH),
        ("Ad2c3h4s5d", Category.STRAIGHT),
        ("9s9d9cAhKd", Category.TRIPS),
        ("AsAdKsKdQc", Category.TWO_PAIR),
        ("AsAd7c4h2d", Category.PAIR),
        ("AsJd8c5h2d", Category.HIGH_CARD),
    ],
)
def test_categories(hand, category):
    assert category_of(ev(hand)) is category


# --- Tricky cases ------------------------------------------------------------------------


def test_wheel_is_the_lowest_straight():
    assert ev("Ad2c3h4s5d") < ev("2d3c4h5s6d")
    assert describe(ev("Ad2c3h4s5d")) == "Straight, five high"


def test_steel_wheel_is_the_lowest_straight_flush():
    assert ev("5c4c3c2cAc") < ev("6c5c4c3c2c")


def test_no_wraparound_straight():
    assert category_of(ev("QsKdAc2h3s")) is Category.HIGH_CARD


def test_seven_card_flush_uses_top_five_suited_cards():
    # Seven hearts: the flush is A-K-Q-9-7; the 5 and 2 don't play.
    assert ev("AhKhQh9h7h5h2h") == ev("AhKhQh9h7h")


def test_straight_flush_beats_bigger_plain_flush_cards():
    # 9-high straight flush in clubs beats a hand that also contains an ace-high flush card set.
    assert category_of(ev("9c8c7c6c5cAcKd")) is Category.STRAIGHT_FLUSH


def test_two_sets_of_trips_make_a_full_house():
    assert describe(ev("KsKdKcQsQdQc2h")) == "Full house, kings full of queens"


def test_trips_plus_two_pairs_uses_the_higher_pair():
    assert ev("5s5d5cKsKdQsQd") == ev("5s5d5cKsKd")


def test_three_pairs_kicker_can_come_from_third_pair():
    # A A K K Q Q 2: two pair aces and kings, queen kicker (beats a jack kicker).
    assert ev("AsAdKsKdQcQh2h") > ev("AsAdKsKdJcTh2h")


def test_kickers_decide_equal_pairs():
    assert ev("AsAdKc4h2d") > ev("AhAcQc4s2s")
    assert ev("AsAdKc4h3d") > ev("AhAcKd4s2s")  # third kicker


def test_quads_kicker():
    assert ev("9h9d9c9sAd") > ev("9h9d9c9sKd")


def test_flushes_compare_card_by_card():
    assert ev("AhKh9h7h3h") > ev("AsKs9s7s2s")


def test_identical_strength_in_different_suits_ties():
    assert ev("AsKsQsJs9d") == ev("AhKhQhJh9c")


def test_board_plays_split_pot():
    board = parse_cards("AsKdQhJcTs")
    assert compare([*board, *parse_cards("2c3d")], [*board, *parse_cards("4h5h")]) == 0


def test_compare_signs():
    a, b = parse_cards("AsAdKc4h2d"), parse_cards("KsKdAc4s2s")
    assert compare(a, b) == 1
    assert compare(b, a) == -1


@pytest.mark.parametrize("n", [0, 4, 8])
def test_rejects_wrong_number_of_cards(n):
    with pytest.raises(ValueError):
        evaluate(list(range(n)))


# --- Descriptions ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hand", "text"),
    [
        ("AsKsQsJsTs", "Royal flush"),
        ("9c8c7c6c5c", "Straight flush, nine high"),
        ("6h6d6c6sKd", "Four of a kind, sixes"),
        ("AhKhQh9h2h", "Flush, ace high"),
        ("9s9d9cAhKd", "Three of a kind, nines"),
        ("AsAdKsKdQc", "Two pair, aces and kings"),
        ("AsAd7c4h2d", "One pair, aces"),
        ("AsJd8c5h2d", "High card, ace"),
    ],
)
def test_describe(hand, text):
    assert describe(ev(hand)) == text


# --- Agreement with brute force --------------------------------------------------------


def best_of_subsets(cards):
    """Slow but obviously correct: try every 5-card subset and keep the best."""
    return max(evaluate(sub) for sub in itertools.combinations(cards, 5))


@pytest.mark.parametrize("n_cards", [6, 7])
def test_matches_brute_force_best_five(n_cards):
    rng = random.Random(2026)
    for _ in range(5_000):
        hand = rng.sample(range(52), n_cards)
        assert evaluate(hand) == best_of_subsets(hand), hand
