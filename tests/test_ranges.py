"""M3 tests: hand classes, range notation, weights, card removal and presets."""

import itertools

import pytest

from pokerlab.cards import parse_cards
from pokerlab.profiles import PROFILES
from pokerlab.ranges import (
    CLASS_COMBOS,
    HAND_CLASSES,
    TOTAL_COMBOS,
    Range,
    RangeError,
    class_of_combo,
    combos_in_class,
)

# --- Hand classes ----------------------------------------------------------------------


def test_169_classes_cover_all_1326_combos_exactly_once():
    assert len(HAND_CLASSES) == 169 == len(set(HAND_CLASSES))
    every = [combo for label in HAND_CLASSES for combo in CLASS_COMBOS[label]]
    assert len(every) == TOTAL_COMBOS == len(set(every))
    assert {frozenset(c) for c in every} == {
        frozenset(c) for c in itertools.combinations(range(52), 2)
    }


@pytest.mark.parametrize(("label", "n"), [("AA", 6), ("22", 6), ("AKs", 4), ("72o", 12)])
def test_combos_per_class(label, n):
    assert combos_in_class(label) == n


def test_class_counts_by_type():
    pairs = [c for c in HAND_CLASSES if len(c) == 2]
    suited = [c for c in HAND_CLASSES if c.endswith("s")]
    offsuit = [c for c in HAND_CLASSES if c.endswith("o")]
    assert (len(pairs), len(suited), len(offsuit)) == (13, 78, 78)


def test_grid_layout():
    """Row-major 13x13: pairs on the diagonal, suited upper right, offsuit lower left."""
    grid = [HAND_CLASSES[i * 13 : (i + 1) * 13] for i in range(13)]
    assert grid[0][:3] == ("AA", "AKs", "AQs")
    assert grid[1][:3] == ("AKo", "KK", "KQs")
    assert grid[12][12] == "22"
    assert grid[12][0] == "A2o" and grid[0][12] == "A2s"


def test_class_of_combo():
    assert class_of_combo(*parse_cards("AsKs")) == "AKs"
    assert class_of_combo(*parse_cards("KdAs")) == "AKo"
    assert class_of_combo(*parse_cards("7h7c")) == "77"


# --- Parsing ---------------------------------------------------------------------------


def labels(notation: str) -> set[str]:
    return set(Range.parse(notation).weights)


@pytest.mark.parametrize(
    ("notation", "expected"),
    [
        ("AA", {"AA"}),
        ("AKs", {"AKs"}),
        ("AKo", {"AKo"}),
        ("AK", {"AKs", "AKo"}),
        ("QQ+", {"QQ", "KK", "AA"}),
        ("ATs+", {"ATs", "AJs", "AQs", "AKs"}),
        ("KTo+", {"KTo", "KJo", "KQo"}),
        ("T9+", {"T9s", "T9o"}),
        ("99-66", {"99", "88", "77", "66"}),
        ("66-99", {"99", "88", "77", "66"}),
        ("A5s-A2s", {"A5s", "A4s", "A3s", "A2s"}),
        ("KTo-K8o", {"KTo", "K9o", "K8o"}),
        ("aks, qq", {"AKs", "QQ"}),
        ("AA KK,QQ", {"AA", "KK", "QQ"}),
        ("", set()),
    ],
)
def test_parse(notation, expected):
    assert labels(notation) == expected


def test_parse_weights():
    rng = Range.parse("AA, A5s:0.5, KQo:.25")
    assert rng.weight("AA") == 1.0
    assert rng.weight("A5s") == 0.5
    assert rng.weight("KQo") == 0.25
    assert rng.weight("72o") == 0.0


def test_later_tokens_override_earlier_ones():
    assert Range.parse("TT+, AA:0.5").weight("AA") == 0.5
    assert "AA" not in Range.parse("TT+, AA:0").weights  # weight 0 removes a class


@pytest.mark.parametrize(
    "bad",
    ["AAs", "KA", "AKx", "A", "ZZ", "AA:1.5", "AKs-QJs", "A5s-A2o", "99-6", "99-A2s", "A2s-A5s+"],
)
def test_parse_rejects_bad_notation(bad):
    with pytest.raises(RangeError):
        Range.parse(bad)


def test_constructor_validates_labels_and_weights():
    with pytest.raises(RangeError):
        Range({"AKx": 1})
    with pytest.raises(RangeError):
        Range({"AKs": 2})
    assert Range({"AKs": 0}).weights == {}


# --- Counting and card removal -----------------------------------------------------------


def test_full_range_has_all_combos():
    full = Range.full()
    assert full.combo_count() == TOTAL_COMBOS
    assert full.fraction() == 1.0


def test_weighted_combo_count():
    # AA = 6 combos, AKs at half weight = 2 effective combos
    assert Range.parse("AA, AKs:0.5").combo_count() == 8


def test_card_removal_pairs():
    aa = Range.parse("AA")
    assert aa.live_combo_count(parse_cards("As")) == 3  # A♠ held: C(3,2)
    assert aa.live_combo_count(parse_cards("AsAh")) == 1  # only A♦A♣ left
    assert aa.live_combo_count(parse_cards("AsAhAd")) == 0


def test_card_removal_suited_and_offsuit():
    assert Range.parse("AKs").live_combo_count(parse_cards("As")) == 3
    assert Range.parse("AKo").live_combo_count(parse_cards("As")) == 9  # 12 - 3 with A♠


def test_removed_combos_never_contain_dead_cards():
    dead = parse_cards("AsQsJs8d4s")
    for (a, b), _ in Range.full().combos(dead):
        assert a not in dead and b not in dead
    # 47 live cards -> C(47, 2) combos remain
    assert Range.full().live_combo_count(dead) == 47 * 46 // 2


# --- Formatting --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "notation",
    [
        "AA",
        "22+",
        "KK-QQ",
        "ATs+",
        "A5s-A2s:0.5",
        "99-66, A5s-A2s:0.5, KQs, ATo+, KQo",
    ],
)
def test_notation_round_trip(notation):
    rng = Range.parse(notation)
    assert rng.to_notation() == notation
    assert Range.parse(rng.to_notation()) == rng


def test_notation_is_compact():
    assert Range.parse("AKs, AQs, AJs, ATs").to_notation() == "ATs+"
    assert Range.parse("TT, JJ, QQ, KK, AA").to_notation() == "TT+"


# --- Presets -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "low", "high"),
    [("tight", 0.08, 0.12), ("balanced", 0.17, 0.23), ("aggressive", 0.32, 0.40)],
)
def test_preset_sizes(key, low, high):
    """Sizes agreed in ADR 0014: ~10%, ~20%, ~35% of all starting hands."""
    assert low <= PROFILES[key].range.fraction() <= high


def test_presets_are_nested():
    """Each looser profile contains every hand of the tighter one."""
    tight, balanced, aggressive = (set(PROFILES[k].range.weights) for k in PROFILES)
    assert tight <= balanced <= aggressive


def test_preset_notation_is_normalised():
    for profile in PROFILES.values():
        assert profile.range.to_notation() == profile.notation
