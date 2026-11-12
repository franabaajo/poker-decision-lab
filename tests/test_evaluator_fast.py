"""M7: the vectorised evaluator must give exactly the reference evaluator's scores."""

import itertools

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import pokerlab.evaluator_fast as fast
from pokerlab.cards import parse_cards
from pokerlab.evaluator import evaluate
from pokerlab.evaluator_fast import STRAIGHT_HIGH, TOP5, evaluate_batch


def random_hands(n: int, k: int, seed: int) -> np.ndarray:
    """n random hands of k distinct cards (a random permutation of the deck per row)."""
    gen = np.random.default_rng(seed)
    return np.argsort(gen.random((n, 52)), axis=1)[:, :k]


@pytest.mark.parametrize("k", [5, 6, 7])
def test_matches_reference_on_random_hands(k):
    hands = random_hands(30_000, k, seed=k)
    expected = np.array([evaluate(list(h)) for h in hands])
    np.testing.assert_array_equal(evaluate_batch(hands), expected)


@pytest.mark.parametrize(
    "hand",
    [
        "AsKsQsJsTs",  # royal flush
        "5c4c3c2cAc",  # steel wheel
        "Ad2c3h4s5d",  # wheel
        "AhKhQh9h7h5h2h",  # seven-card flush
        "KsKdKcQsQdQc2h",  # two sets of trips
        "AsAdKsKdQcQh2h",  # three pairs
        "9c8c7c6c5cAcKd",  # straight flush with higher flush cards
        "5s5d5cKsKdQsQd",  # trips + two pairs
        "QsKdAc2h3s",  # no wrap-around straight
    ],
)
def test_tricky_hands(hand):
    cards = parse_cards(hand)
    assert evaluate_batch(np.array([cards]))[0] == evaluate(cards)


@settings(max_examples=300)
@given(st.lists(st.integers(0, 51), min_size=5, max_size=7, unique=True))
def test_matches_reference_property(hand):
    assert evaluate_batch(np.array([hand]))[0] == evaluate(hand)


def test_all_five_card_hands_counts_and_strength_classes():
    """The same exhaustive check as for the reference, now in about a second."""
    hands = np.array(list(itertools.combinations(range(52), 5)), dtype=np.int8)
    scores = evaluate_batch(hands)
    counts = np.bincount(scores >> 20, minlength=9).tolist()
    assert counts == [1302540, 1098240, 123552, 54912, 10200, 5108, 3744, 624, 40]
    assert len(np.unique(scores)) == 7462


@pytest.mark.slow
def test_identical_to_reference_on_every_five_card_hand():
    hands = list(itertools.combinations(range(52), 5))
    scores = evaluate_batch(np.array(hands, dtype=np.int8))
    assert all(int(s) == evaluate(h) for s, h in zip(scores, hands, strict=True))


def test_chunking_gives_the_same_result(monkeypatch):
    hands = random_hands(1_000, 7, seed=99)
    whole = evaluate_batch(hands)
    monkeypatch.setattr(fast, "_MAX_ROWS", 128)
    np.testing.assert_array_equal(evaluate_batch(hands), whole)


def test_lookup_tables():
    assert STRAIGHT_HIGH[0b1111100000000] == 12  # A-K-Q-J-T
    assert STRAIGHT_HIGH[(1 << 12) | 0b1111] == 3  # wheel: five high
    assert STRAIGHT_HIGH[0b1111000000001] == -1  # A-K-Q-J + 2: no straight
    assert TOP5[0b1000000000011] == (12 << 16) | (1 << 12) | (0 << 8)  # A, 3, 2


def test_empty_and_invalid_input():
    assert evaluate_batch(np.zeros((0, 7), dtype=int)).shape == (0,)
    with pytest.raises(ValueError):
        evaluate_batch(np.zeros((3, 4), dtype=int))
    with pytest.raises(ValueError):
        evaluate_batch(np.zeros(7, dtype=int))
