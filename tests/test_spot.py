"""M1 tests: validating a spot (hero cards + board)."""

import pytest

from pokerlab.cards import CardError, DuplicateCardError, parse_cards
from pokerlab.spot import Spot, SpotError, Street


@pytest.mark.parametrize(
    ("board", "street", "to_come"),
    [("", Street.PREFLOP, 5), ("Js8d4s", Street.FLOP, 2), ("Js8d4s2c", Street.TURN, 1),
     ("Js8d4s2cKh", Street.RIVER, 0)],
)  # fmt: skip
def test_valid_spots_and_streets(board, street, to_come):
    spot = Spot.from_strings("AsQs", board)
    assert spot.street is street
    assert spot.cards_to_come == to_come
    assert len(spot.dead_cards) == 2 + len(board) // 2


def test_lists_are_normalised_to_tuples():
    spot = Spot([51, 43], [0, 1, 2])  # type: ignore[arg-type]
    assert spot.hero == (51, 43)
    assert spot.board == (0, 1, 2)
    assert hash(spot)  # frozen + tuples => usable as a cache key


@pytest.mark.parametrize("hero", ["As", "AsQsJs", ""])
def test_hero_must_have_two_cards(hero):
    with pytest.raises(SpotError, match="2 hole cards"):
        Spot.from_strings(hero)


@pytest.mark.parametrize("board", ["Js", "Js8d", "Js8d4s2cKh3h"])
def test_illegal_board_sizes(board):
    with pytest.raises(SpotError, match="0, 3, 4 or 5"):
        Spot.from_strings("AsQs", board)


def test_duplicate_within_hero():
    with pytest.raises(DuplicateCardError):
        Spot.from_strings("AsAs")


def test_duplicate_between_hero_and_board():
    with pytest.raises(DuplicateCardError, match="As"):
        Spot.from_strings("AsQs", "Js8dAs")


def test_duplicate_within_board():
    with pytest.raises(DuplicateCardError, match="Js"):
        Spot.from_strings("AsQs", "JsJs4s")


def test_invalid_card_ids_rejected():
    with pytest.raises(CardError):
        Spot((51, 52))


def test_all_errors_share_a_base_class():
    """The API catches CardError once and turns any of these into a friendly message."""
    for hero, board in [("As", ""), ("AsAs", ""), ("AsQs", "Js"), ("AsXx", "")]:
        with pytest.raises(CardError):
            Spot.from_strings(hero, board)


def test_str():
    assert str(Spot.from_strings("AsQs", "Js8d4s")) == "AsQs | Js8d4s (Flop)"
    assert str(Spot(tuple(parse_cards("AsQs")))) == "AsQs | - (Preflop)"
