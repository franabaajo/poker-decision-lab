"""M6 tests: opponent betting rule, Bayesian narrowing and the multi-street EV."""

import pytest

from pokerlab.decision import Situation
from pokerlab.equity import exact_equity
from pokerlab.multistreet import MultiStreetError, analyse_call, bet_probabilities, explain
from pokerlab.profiles import PROFILES, Strategy
from pokerlab.ranges import Range
from pokerlab.spot import Spot

NEVER_BETS = Strategy(bet_fraction=0.5, value_share=0.0, bluff_share=0.0)
TIGHT = PROFILES["tight"].strategy


def spot(hero, board=""):
    return Spot.from_strings(hero, board)


# --- The opponent's betting rule ------------------------------------------------------------


def test_betting_share_is_exactly_value_plus_bluffs():
    strengths = list(range(100))  # all different
    weights = [1.0] * 100
    s = Strategy(bet_fraction=0.5, value_share=0.3, bluff_share=0.1)
    probs = bet_probabilities(strengths, weights, s)
    assert sum(probs) == pytest.approx(100 * s.bet_share)  # 30 value + 7 bluffs
    assert probs[99] == 1 and probs[70] == 1  # strongest 30 bet
    assert probs[69] == 0 and probs[7] == 0  # middle checks
    assert probs[6] == 1 and probs[0] == 1  # weakest 7 bluff


def test_equal_strengths_get_equal_probabilities():
    strengths = [5, 5, 5, 5, 1, 1, 1, 1]  # two groups of 4
    probs = bet_probabilities(strengths, [1.0] * 8, Strategy(0.5, value_share=0.25, bluff_share=0))
    assert probs[:4] == [0.5] * 4  # 2 combos' worth of mass spread over the tied group
    assert sum(probs) == pytest.approx(2)


def test_weights_are_respected():
    probs = bet_probabilities(
        [3, 2, 1], [0.0, 1.0, 1.0], Strategy(0.5, value_share=0.5, bluff_share=0)
    )
    assert probs[1] == 1 and probs[2] == 0


def test_strategy_validation():
    with pytest.raises(ValueError):
        Strategy(bet_fraction=0, value_share=0.3, bluff_share=0.1)
    with pytest.raises(ValueError):
        Strategy(bet_fraction=0.5, value_share=1.3, bluff_share=0.1)


# --- Consistency with the showdown-only model (M5) ------------------------------------------


@pytest.mark.parametrize("board", ["Js8d4s", "Js8d4s2c"])
def test_no_later_betting_reduces_to_m5(board):
    s, rng, sit = spot("AsQs", board), Range.parse("TT+, AJs+, KQo, 76s"), Situation(100, 50, 500)
    result = analyse_call(s, rng, sit, NEVER_BETS)
    naive = exact_equity(s, rng).equity * sit.final_pot - sit.call
    assert result.ev_call == pytest.approx(naive)
    assert result.ev_showdown == pytest.approx(naive)
    assert result.realization == pytest.approx(1.0)


def test_all_in_reduces_to_m5():
    s, rng = spot("AsQs", "Js8d4s"), Range.parse("TT+, AJs+, KQo")
    sit = Situation(pot=100, bet=200, stack=200)  # calling puts the hero all-in
    result = analyse_call(s, rng, sit, PROFILES["aggressive"].strategy)
    assert result.ev_call == pytest.approx(result.ev_showdown)
    assert result.stats["bet_turn"] == 0


def test_river_has_no_later_streets():
    s, rng, sit = spot("AsQs", "Js8d4s2c3h"), Range.parse("TT+, AJs+"), Situation(100, 50, 500)
    result = analyse_call(s, rng, sit, TIGHT)
    assert result.later_streets == 0
    assert result.ev_call == pytest.approx(exact_equity(s, rng).equity * 200 - 50)


# --- Closed-form cases --------------------------------------------------------------------


def test_unbeatable_hand_on_the_turn():
    """Hero holds a royal flush: every opponent bet is called and won.

    V(river) = pot (check) or pot + bet (bet), and the opponent bets exactly
    bet_share of the time, so EV = -call + pot + bet_share * bet.
    """
    s, rng = spot("AhKh", "QhJhTh2c"), Range.parse("22+, A2s+, KTo+")
    sit = Situation(pot=100, bet=50, stack=1000)
    result = analyse_call(s, rng, sit, TIGHT)
    bet = TIGHT.bet_fraction * sit.final_pot
    assert result.ev_call == pytest.approx(-50 + 200 + TIGHT.bet_share * bet)
    assert result.stats["fold_river"] == 0 and result.stats["showdown"] == 1


def test_unbeatable_hand_on_the_flop():
    s, rng = spot("AhKh", "QhJhTh"), Range.parse("22+, A2s+, KTo+")
    sit = Situation(pot=100, bet=50, stack=10_000)
    result = analyse_call(s, rng, sit, TIGHT)
    q, f = TIGHT.bet_share, TIGHT.bet_fraction

    def river(pot):
        return pot + q * f * pot

    pot = 200.0
    turn_value = (1 - q) * river(pot) + q * (river(pot + 2 * f * pot) - f * pot)
    assert result.ev_call == pytest.approx(-50 + turn_value)


def test_stack_caps_later_bets():
    """With only 20 chips behind, the opponent can bet at most 20 on the river."""
    s, rng = spot("AhKh", "QhJhTh2c"), Range.parse("22+, A2s+")
    sit = Situation(pot=100, bet=50, stack=70)
    result = analyse_call(s, rng, sit, TIGHT)
    assert result.ev_call == pytest.approx(-50 + 200 + TIGHT.bet_share * 20)


def test_drawing_dead_never_does_better_than_losing_the_call():
    # Board K-K-K-Q: the opponent's AA makes kings full of aces, which no river saves 2-3 from.
    s, rng = spot("2c3d", "KsKdKhQs"), Range.parse("AA")
    result = analyse_call(s, rng, Situation(100, 50, 500), PROFILES["aggressive"].strategy)
    assert result.equity == 0
    assert result.ev_call == pytest.approx(-50)  # folds to every later bet, never wins


# --- General properties --------------------------------------------------------------------


@pytest.mark.parametrize("key", list(PROFILES))
def test_ev_is_never_below_losing_the_call(key):
    """The hero can always fold later, so calling never costs more than the call."""
    p = PROFILES[key]
    result = analyse_call(spot("9h8h", "Ts7c2h"), p.range, Situation(60, 40, 400), p.strategy)
    assert result.ev_call >= -40 - 1e-9


def test_probabilities_are_consistent():
    p = PROFILES["balanced"]
    stats = analyse_call(spot("AsQs", "Js8d4s"), p.range, Situation(100, 50, 500), p.strategy).stats
    for value in stats.values():
        assert 0 <= value <= 1 + 1e-12
    # Every path ends in exactly one way: a fold on the turn, a fold on the river or a showdown.
    assert stats["fold_turn"] + stats["fold_river"] + stats["showdown"] == pytest.approx(1)
    assert stats["bet_turn"] == pytest.approx(p.strategy.bet_share)


def test_a_bet_narrows_the_range_towards_strong_hands_and_bluffs():
    """Bayesian narrowing: the betting part of the range is polarised."""
    strengths = list(range(20))
    probs = bet_probabilities(strengths, [1.0] * 20, TIGHT)
    betting = [s for s, p in zip(strengths, probs, strict=True) if p > 0]
    checking = [s for s, p in zip(strengths, probs, strict=True) if p == 0]
    assert max(betting) > max(checking) and min(betting) < min(checking)


def test_preflop_is_not_modelled():
    with pytest.raises(MultiStreetError):
        analyse_call(spot("AsQs"), Range.parse("AA"), Situation(100, 50, 500), TIGHT)


def test_explanation():
    p = PROFILES["tight"]
    result = analyse_call(spot("AsQs", "Js8d4s2c"), p.range, Situation(100, 50, 500), p.strategy)
    text = explain(result, p.strategy, p.name)
    assert "half the pot" in text and "30%" in text and "one opponent" in text
    assert ("Call" in text) == (result.ev_call > 0)
    river = analyse_call(spot("AsQs", "Js8d4s2c3h"), p.range, Situation(100, 50, 500), p.strategy)
    assert "no more betting" in explain(river, p.strategy, p.name)
