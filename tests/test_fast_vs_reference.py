"""M7: the vectorised engines must reproduce the pure-Python reference engines (ADR 0021)."""

import pytest

from pokerlab import equity, multistreet
from pokerlab.decision import Situation
from pokerlab.profiles import PROFILES
from pokerlab.reference import equity as ref_equity
from pokerlab.reference import multistreet as ref_multistreet
from pokerlab.spot import Spot

SPOTS = [
    ("AsQs", "Js8d4s", "tight"),
    ("KhKd", "Qs7h2c9d", "balanced"),
    ("7h6h", "8h9cKd", "aggressive"),
    ("AcKd", "As7s2s4h3d", "balanced"),  # river
]


@pytest.mark.parametrize(("hero", "board", "profile"), SPOTS)
def test_exact_equity_matches_reference(hero, board, profile):
    spot, rng = Spot.from_strings(hero, board), PROFILES[profile].range
    fast, ref = equity.exact_equity(spot, rng), ref_equity.exact_equity(spot, rng)
    assert fast.win == pytest.approx(ref.win, abs=1e-12)
    assert fast.tie == pytest.approx(ref.tie, abs=1e-12)
    assert fast.estimate.n == ref.estimate.n
    assert fast.by_class.keys() == ref.by_class.keys()
    for label, cls in fast.by_class.items():
        assert cls.equity == pytest.approx(ref.by_class[label].equity, abs=1e-12)
        assert cls.share == pytest.approx(ref.by_class[label].share, abs=1e-12)


def test_monte_carlo_agrees_with_reference_statistically():
    """Different random streams, same distribution: estimates agree within their errors."""
    spot, rng = Spot.from_strings("AsQs"), PROFILES["balanced"].range
    a = equity.monte_carlo_equity(spot, rng, 40_000, seed=3)
    b = ref_equity.monte_carlo_equity(spot, rng, 40_000, seed=3)
    se = (a.estimate.std_error**2 + b.estimate.std_error**2) ** 0.5
    assert abs(a.equity - b.equity) < 4 * se


@pytest.mark.slow  # the pure-Python reference takes a few seconds per spot
@pytest.mark.parametrize(("hero", "board", "profile"), SPOTS[1:])
@pytest.mark.parametrize("style", ["tight", "aggressive"])
def test_multistreet_matches_reference(hero, board, profile, style):
    spot, rng = Spot.from_strings(hero, board), PROFILES[profile].range
    sit, strategy = Situation(80, 60, 400), PROFILES[style].strategy
    fast = multistreet.analyse_call(spot, rng, sit, strategy)
    ref = ref_multistreet.analyse_call(spot, rng, sit, strategy)
    assert fast.ev_call == pytest.approx(ref.ev_call, abs=1e-9)
    assert fast.ev_showdown == pytest.approx(ref.ev_showdown, abs=1e-9)
    for key, value in ref.stats.items():
        assert fast.stats[key] == pytest.approx(value, abs=1e-12)


# Golden values produced by the M6 reference implementation before vectorising.
GOLDEN = [
    ("AsQs", "Js8d4s", 100, 50, 500, "tight", "tight", 69.90425117166784),
    ("AsQs", "Js8d4s", 100, 50, 500, "balanced", "balanced", 115.4618893478638),
    ("9h8h", "Ts7c2d", 0, 50, 500, "tight", "tight", -7.01559783876781),
    ("9h8h", "Ts7c2d", 60, 40, 150, "aggressive", "aggressive", 23.938592565954885),
    ("KcQc", "Kd7h3c2s", 80, 60, 400, "balanced", "aggressive", 196.6849529780564),
    ("7h6h", "8h9cKd", 100, 75, 300, "aggressive", "tight", 20.45344689488813),
]


@pytest.mark.parametrize(("hero", "board", "pot", "bet", "stack", "rng", "style", "ev"), GOLDEN)
def test_golden_values(hero, board, pot, bet, stack, rng, style, ev):
    result = multistreet.analyse_call(
        Spot.from_strings(hero, board),
        PROFILES[rng].range,
        Situation(pot, bet, stack),
        PROFILES[style].strategy,
    )
    assert result.ev_call == pytest.approx(ev, abs=1e-9)
