"""M2: property-based tests with `hypothesis` (ADR 0012).

Instead of hand-picked examples, hypothesis generates many random hands and checks
rules that must hold for EVERY hand. When a rule fails, it shrinks the failing
hand to the simplest example it can find.
"""

import itertools

from hypothesis import given, settings
from hypothesis import strategies as st

from pokerlab.evaluator import evaluate

# A hand = 5 to 7 distinct card ids.
hands = st.lists(st.integers(0, 51), min_size=5, max_size=7, unique=True)


@given(hand=hands, data=st.data())
def test_card_order_does_not_matter(hand, data):
    shuffled = data.draw(st.permutations(hand))
    assert evaluate(shuffled) == evaluate(hand)


@given(hand=hands, suit_perm=st.permutations([0, 1, 2, 3]))
def test_relabelling_suits_does_not_matter(hand, suit_perm):
    """Suits have no ranking in poker: swapping e.g. all hearts <-> spades changes nothing."""
    relabelled = [(c // 4) * 4 + suit_perm[c % 4] for c in hand]
    assert evaluate(relabelled) == evaluate(hand)


@given(
    hand=st.lists(st.integers(0, 51), min_size=5, max_size=6, unique=True), extra=st.integers(0, 51)
)
def test_adding_a_card_never_makes_the_hand_worse(hand, extra):
    if extra in hand:
        return
    assert evaluate([*hand, extra]) >= evaluate(hand)


@settings(max_examples=300)
@given(hand=hands)
def test_equals_best_five_card_subset(hand):
    """Definition of a poker hand: the best 5 of the available cards."""
    assert evaluate(hand) == max(evaluate(s) for s in itertools.combinations(hand, 5))
