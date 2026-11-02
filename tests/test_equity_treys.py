"""M4: exact equity recomputed independently with `treys` (test-only oracle, ADR 0011)."""

import itertools

import pytest
import treys

from pokerlab.cards import card_to_str, remaining_deck
from pokerlab.equity import exact_equity
from pokerlab.ranges import Range
from pokerlab.spot import Spot

_EV = treys.Evaluator()


def treys_equity(spot: Spot, rng: Range) -> float:
    """Straightforward, independent re-implementation: loop over combos and runouts."""

    def t(cards):
        return [treys.Card.new(card_to_str(c)) for c in cards]

    total_w = acc = 0.0
    for (a, b), w in rng.combos(spot.dead_cards):
        deck = [c for c in remaining_deck(spot.dead_cards) if c not in (a, b)]
        score = n = 0.0
        for runout in itertools.combinations(deck, spot.cards_to_come):
            board = t([*spot.board, *runout])
            hero, villain = _EV.evaluate(board, t(spot.hero)), _EV.evaluate(board, t([a, b]))
            score += 1.0 if hero < villain else 0.5 if hero == villain else 0.0  # lower is better
            n += 1
        total_w += w
        acc += w * score / n
    return acc / total_w


@pytest.mark.parametrize(
    ("hero", "board", "notation"),
    [
        ("AsQs", "Js8d4s2c", "77+, ATs+, KTs+, QJs, AJo+, KQo"),
        ("7h6h", "8h9cKd2h", "TT+, AK, A5s:0.5, 98s"),
        ("KcKd", "Kh7s7d3c9h", "55+, A2s+, K9s+"),
    ],
)
def test_exact_equity_matches_treys(hero, board, notation):
    s, rng = Spot.from_strings(hero, board), Range.parse(notation)
    assert exact_equity(s, rng).equity == pytest.approx(treys_equity(s, rng), abs=1e-12)
