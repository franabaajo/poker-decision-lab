"""M3 property-based tests for ranges (ADR 0012)."""

from hypothesis import given
from hypothesis import strategies as st

from pokerlab.ranges import HAND_CLASSES, TOTAL_COMBOS, Range

weights = st.sampled_from([0.0, 0.0, 0.25, 0.5, 1.0])  # 0 twice: ranges are usually sparse
ranges = st.dictionaries(st.sampled_from(HAND_CLASSES), weights).map(Range)
dead_cards = st.lists(st.integers(0, 51), max_size=7, unique=True)


@given(rng=ranges)
def test_notation_round_trip(rng):
    """Whatever the grid looks like, text -> range -> text loses nothing."""
    assert Range.parse(rng.to_notation()) == rng


@given(rng=ranges, dead=dead_cards)
def test_card_removal_never_adds_combos(rng, dead):
    assert 0 <= rng.live_combo_count(dead) <= rng.combo_count() <= TOTAL_COMBOS


@given(rng=ranges, dead=dead_cards)
def test_live_combos_avoid_dead_cards(rng, dead):
    dead_set = set(dead)
    for (a, b), w in rng.combos(dead):
        assert a not in dead_set and b not in dead_set
        assert 0 < w <= 1
