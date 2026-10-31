"""M1 tests: card encoding, parsing, formatting and duplicate detection."""

import pytest

from pokerlab.cards import (
    DECK,
    RANKS,
    SUITS,
    DuplicateCardError,
    InvalidCardError,
    card_name,
    card_to_pretty,
    card_to_str,
    ensure_unique,
    make_card,
    parse_card,
    parse_cards,
    rank_of,
    remaining_deck,
    suit_of,
)

# --- Encoding -----------------------------------------------------------------


def test_deck_has_52_distinct_cards():
    assert len(DECK) == 52
    assert sorted(DECK) == list(range(52))


def test_every_rank_suit_pair_appears_exactly_once():
    pairs = {(rank_of(c), suit_of(c)) for c in DECK}
    assert pairs == {(r, s) for r in range(13) for s in range(4)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [("2c", 0), ("2d", 1), ("2h", 2), ("2s", 3), ("3c", 4), ("Tc", 32), ("As", 51)],
)
def test_known_encodings(text, expected):
    assert parse_card(text) == expected


def test_make_card_inverts_rank_and_suit():
    for card in DECK:
        assert make_card(rank_of(card), suit_of(card)) == card


@pytest.mark.parametrize(("rank", "suit"), [(-1, 0), (13, 0), (0, -1), (0, 4)])
def test_make_card_rejects_out_of_range(rank, suit):
    with pytest.raises(InvalidCardError):
        make_card(rank, suit)


def test_higher_rank_means_higher_id():
    """Ordering by id groups cards by rank, which later code relies on."""
    for card in DECK[:-4]:
        assert rank_of(card + 4) == rank_of(card) + 1


# --- Formatting and parsing ---------------------------------------------------


def test_round_trip_string_and_pretty_for_all_cards():
    for card in DECK:
        assert parse_card(card_to_str(card)) == card
        assert parse_card(card_to_pretty(card)) == card


@pytest.mark.parametrize("text", ["As", "as", "AS", "A♠", " As ", "a♠"])
def test_parse_card_accepts_variants(text):
    assert parse_card(text) == 51


@pytest.mark.parametrize("text", ["10h", "Th", "th", "10♥"])
def test_ten_can_be_written_as_10_or_t(text):
    assert parse_card(text) == make_card(RANKS.index("T"), SUITS.index("h"))


@pytest.mark.parametrize("bad", ["", "A", "s", "1s", "Ax", "AsK", "11s", "Ass", "♠A"])
def test_parse_card_rejects_garbage(bad):
    with pytest.raises(InvalidCardError):
        parse_card(bad)


def test_parse_card_rejects_non_strings():
    with pytest.raises(InvalidCardError):
        parse_card(51)  # type: ignore[arg-type]


def test_card_name():
    assert card_name(51) == "ace of spades"
    assert card_name(0) == "two of clubs"


@pytest.mark.parametrize("bad", [-1, 52, 3.0, True, "As"])
def test_formatting_rejects_non_card_ids(bad):
    with pytest.raises(InvalidCardError):
        card_to_str(bad)


@pytest.mark.parametrize("text", ["AsQs", "As Qs", "As, Qs", "A♠Q♠", "a♠ q♠", "  AsQs  "])
def test_parse_cards_separators(text):
    assert parse_cards(text) == [51, 43]


def test_parse_cards_empty_is_empty_list():
    assert parse_cards("") == []
    assert parse_cards("   ") == []


def test_parse_cards_with_ten():
    assert [card_to_str(c) for c in parse_cards("10h9h8h")] == ["Th", "9h", "8h"]


def test_parse_cards_reports_position_of_error():
    with pytest.raises(InvalidCardError, match="Xx"):
        parse_cards("AsXxQs")


# --- Duplicates and remaining deck -----------------------------------------------


def test_ensure_unique_accepts_distinct_cards():
    ensure_unique([0, 1, 2, 51])
    ensure_unique([])


def test_ensure_unique_names_the_duplicate():
    with pytest.raises(DuplicateCardError, match="As"):
        ensure_unique(parse_cards("AsQsAs"))


def test_ensure_unique_lists_all_duplicates():
    with pytest.raises(DuplicateCardError, match="Qs, As"):
        ensure_unique(parse_cards("AsQsAsQs"))


def test_remaining_deck_removes_dead_cards():
    dead = parse_cards("AsQsJs8d4s")
    rest = remaining_deck(dead)
    assert len(rest) == 47
    assert not set(dead) & set(rest)
    assert sorted(rest + dead) == list(DECK)
