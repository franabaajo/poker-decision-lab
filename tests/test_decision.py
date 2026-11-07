"""M5 tests: pot odds, break-even equity, EV and the verdict."""

import pytest

from pokerlab.decision import DecisionError, Situation, Verdict, decide, explain


def exact(situation, equity):
    return decide(situation, equity, (equity, equity))


# --- The worked example from the project brief ------------------------------------------


def test_brief_example():
    """Pot 100, bet 50: call 50 into a final pot of 200 -> 25% needed; 35.2% equity -> +20.4."""
    s = Situation(pot=100, bet=50, stack=500)
    assert s.call == 50
    assert s.final_pot == 200
    assert s.break_even_equity == pytest.approx(0.25)
    assert s.pot_odds == pytest.approx(3.0)
    d = exact(s, 0.352)
    assert d.ev_fold == 0
    assert d.ev_call == pytest.approx(20.4)
    assert d.verdict is Verdict.CALL


@pytest.mark.parametrize(
    ("pot", "bet", "break_even"),
    [(100, 100, 1 / 3), (100, 50, 1 / 4), (100, 33, 33 / 166), (100, 200, 0.4), (0, 10, 0.5)],
)
def test_break_even_for_common_bet_sizes(pot, bet, break_even):
    """Pot-sized bet -> 33.3%, half pot -> 25%, 2x pot -> 40%."""
    assert Situation(pot, bet, 10_000).break_even_equity == pytest.approx(break_even)


def test_ev_is_zero_exactly_at_break_even():
    s = Situation(pot=120, bet=80, stack=1000)
    assert s.ev_call(s.break_even_equity) == pytest.approx(0)


def test_ev_extremes():
    s = Situation(pot=100, bet=50, stack=500)
    assert s.ev_call(0.0) == -50  # always lose: you lose your call
    assert s.ev_call(1.0) == 150  # always win: you win the pot and the bet


# --- Stacks and all-ins ---------------------------------------------------------------------


def test_bet_equal_to_stack_is_all_in():
    s = Situation(pot=100, bet=200, stack=200)
    assert s.is_all_in and s.returned == 0


def test_bet_larger_than_stack_is_capped():
    s = Situation(pot=100, bet=300, stack=200)
    assert s.call == 200 and s.returned == 100
    assert s.final_pot == 500
    assert s.break_even_equity == pytest.approx(0.4)
    assert s.is_all_in


def test_not_all_in():
    assert not Situation(pot=100, bet=50, stack=500).is_all_in


@pytest.mark.parametrize(("pot", "bet", "stack"), [(-1, 50, 100), (100, 0, 100), (100, 50, 0)])
def test_invalid_amounts(pot, bet, stack):
    with pytest.raises(DecisionError):
        Situation(pot, bet, stack)


# --- Verdict with uncertainty ---------------------------------------------------------------


def test_verdicts():
    s = Situation(pot=100, bet=50, stack=500)  # break-even 25%
    assert decide(s, 0.30, (0.29, 0.31)).verdict is Verdict.CALL
    assert decide(s, 0.20, (0.19, 0.21)).verdict is Verdict.FOLD
    assert decide(s, 0.255, (0.24, 0.27)).verdict is Verdict.CLOSE  # CI straddles 25%
    assert exact(s, 0.25).verdict is Verdict.CLOSE


def test_ev_confidence_interval_maps_from_equity():
    s = Situation(pot=100, bet=50, stack=500)
    d = decide(s, 0.352, (0.349, 0.355))
    lo, hi = d.ev_call_ci95
    assert lo == pytest.approx(0.349 * 200 - 50)
    assert hi == pytest.approx(0.355 * 200 - 50)
    assert d.margin == pytest.approx(0.102)


# --- Explanation ----------------------------------------------------------------------------


def test_explanation_mentions_the_key_numbers_and_assumptions():
    text = explain(exact(Situation(100, 50, 500), 0.352))
    for fragment in ["50 chips", "200 chips", "25.0%", "35.2%", "+20.4 chips", "one opponent"]:
        assert fragment in text
    assert "no more betting" in text


def test_explanation_for_all_in_drops_the_later_streets_caveat():
    text = explain(exact(Situation(100, 300, 200), 0.6))
    assert "goes back to the opponent" in text
    assert "no more betting" not in text


def test_explanation_for_fold_and_close():
    assert "folding is better" in explain(exact(Situation(100, 50, 500), 0.1))
    assert "too close" in explain(decide(Situation(100, 50, 500), 0.25, (0.24, 0.26)))
