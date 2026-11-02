"""M4 tests: exact and Monte Carlo equity."""

import pytest

from pokerlab.equity import (
    EXACT_WORK_LIMIT,
    EquityError,
    calculate_equity,
    exact_equity,
    exact_work,
    monte_carlo_equity,
)
from pokerlab.ranges import Range
from pokerlab.spot import Spot


def spot(hero, board=""):
    return Spot.from_strings(hero, board)


# --- Deterministic cases ---------------------------------------------------------------


def test_river_nuts_always_wins():
    result = exact_equity(spot("Th9c", "AhKhQhJh2c"), Range.parse("AA, KK, 72o"))
    assert (result.win, result.tie, result.lose) == (1.0, 0.0, 0.0)
    assert result.estimate.std_error == 0.0


def test_board_plays_is_always_a_split():
    # Broadway straight on board and no flush possible: every hand chops.
    result = exact_equity(spot("2c3d", "AsKdQhJcTs"), Range.parse("54o, 76o"))
    assert result.tie == 1.0
    assert result.equity == 0.5


def test_river_mixed_range_counts_combos():
    # Hero has top pair; loses to the set (88: 3 live combos, the 8d is on the board)
    # and beats KQo (all 12 combos live).
    result = exact_equity(spot("AsJd", "Js8d4c2h3s"), Range.parse("88, KQo"))
    assert result.live_combos == 15
    assert result.lose == pytest.approx(3 / 15)
    assert result.win == pytest.approx(12 / 15)


# --- Weights and per-class results ------------------------------------------------------


def test_weighted_range_is_a_weighted_average():
    s = spot("AsQs", "Js8d4s2c")
    aa = exact_equity(s, Range.parse("AA"))
    kk = exact_equity(s, Range.parse("KK"))
    mixed = exact_equity(s, Range.parse("AA, KK:0.5"))
    w_aa, w_kk = aa.live_combos * 1.0, kk.live_combos * 0.5
    expected = (w_aa * aa.equity + w_kk * kk.equity) / (w_aa + w_kk)
    assert mixed.equity == pytest.approx(expected)


def test_class_results_add_up_to_the_total():
    result = exact_equity(spot("AsQs", "Js8d4s2c"), Range.parse("TT+, AJs+, KQo, 76s"))
    assert sum(c.share for c in result.by_class.values()) == pytest.approx(1.0)
    weighted = sum(c.share * c.equity for c in result.by_class.values())
    assert weighted == pytest.approx(result.equity)


# --- Monte Carlo vs exact ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("hero", "board", "notation"),
    [
        ("AsQs", "Js8d4s", "77+, ATs+, KTs+, QJs, AJo+, KQo"),  # flop
        ("KhKd", "Qs7h2c9d", "55+, A2s+, KTo+"),  # turn
    ],
)
def test_monte_carlo_agrees_with_exact(hero, board, notation):
    s, rng = spot(hero, board), Range.parse(notation)
    exact = exact_equity(s, rng)
    mc = monte_carlo_equity(s, rng, samples=20_000, seed=42)
    # Within 4 standard errors: a false alarm has probability ~0.006%.
    assert abs(mc.equity - exact.equity) < 4 * mc.estimate.std_error
    lo, hi = mc.ci95
    assert hi - lo < 0.02


def test_monte_carlo_ci_coverage_on_a_real_spot():
    """Repeat a small simulation 100 times: ~95 intervals should contain the exact equity."""
    s, rng = spot("AsQs", "Js8d4s2c"), Range.parse("TT+, AJs+, KQo, 76s, 65s")
    truth = exact_equity(s, rng).equity
    hits = sum(
        lo <= truth <= hi
        for lo, hi in (monte_carlo_equity(s, rng, 1_000, seed=i).ci95 for i in range(100))
    )
    assert hits >= 88  # P(hits < 88) is about 1% if coverage is really 95%


def test_preflop_aces_vs_kings_is_about_82_percent():
    """Well-known figure: AA vs KK all-in preflop has ~82% equity."""
    result = monte_carlo_equity(spot("AsAh"), Range.parse("KK"), samples=20_000, seed=7)
    assert result.equity == pytest.approx(0.82, abs=0.015)


def test_same_seed_same_result_different_seed_different_result():
    s, rng = spot("AsQs"), Range.parse("TT+, AQs+")
    a = monte_carlo_equity(s, rng, 2_000, seed=1)
    b = monte_carlo_equity(s, rng, 2_000, seed=1)
    c = monte_carlo_equity(s, rng, 2_000, seed=2)
    assert (a.win, a.tie) == (b.win, b.tie)
    assert (a.win, a.tie) != (c.win, c.tie)


def test_seed_is_reported_when_not_given():
    result = monte_carlo_equity(spot("AsQs"), Range.parse("AA"), 100)
    assert isinstance(result.seed, int)
    again = monte_carlo_equity(spot("AsQs"), Range.parse("AA"), 100, seed=result.seed)
    assert again.win == result.win


# --- Method selection and errors ----------------------------------------------------------


def test_auto_uses_monte_carlo_preflop():
    assert calculate_equity(spot("AsQs"), Range.parse("AA"), samples=200).method == "monte_carlo"


def test_auto_uses_exact_when_cheap():
    s, rng = spot("AsQs", "Js8d4s2c"), Range.parse("TT+")
    assert exact_work(s, rng) <= EXACT_WORK_LIMIT
    assert calculate_equity(s, rng).method == "exact"


def test_auto_uses_monte_carlo_when_exact_is_too_expensive():
    s, rng = spot("AsQs", "Js8d4s"), Range.full()
    assert exact_work(s, rng) > EXACT_WORK_LIMIT
    assert calculate_equity(s, rng, samples=500).method == "monte_carlo"


def test_empty_range_after_card_removal():
    with pytest.raises(EquityError, match="no possible hands"):
        calculate_equity(spot("AsAh", "AdAc2s"), Range.parse("AA"))


def test_exact_preflop_is_refused():
    with pytest.raises(EquityError):
        exact_equity(spot("AsQs"), Range.parse("AA"))


def test_unknown_method():
    with pytest.raises(EquityError):
        calculate_equity(spot("AsQs", "Js8d4s"), Range.parse("AA"), method="magic")  # type: ignore[arg-type]
