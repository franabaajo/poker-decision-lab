"""Card representation and parsing.

Every card is a plain ``int`` in ``0..51`` (ADR 0010)::

    card = rank * 4 + suit

    rank: 0 = deuce, 1 = three, ..., 8 = ten, 9 = jack, 10 = queen, 11 = king, 12 = ace
    suit: 0 = clubs, 1 = diamonds, 2 = hearts, 3 = spades

So ``2c = 0``, ``2d = 1``, ..., ``As = 51``. Recovering the parts is cheap
arithmetic (``card // 4``, ``card % 4``), which works element-wise on NumPy
arrays too. That matters later, when millions of simulated hands are evaluated.

Strings such as ``"As"`` or ``"A♠"`` exist only at the edges (user input, API,
display); the engine itself only ever handles integers.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

RANKS = "23456789TJQKA"
SUITS = "cdhs"
SUIT_SYMBOLS = "♣♦♥♠"
RANK_NAMES = (
    "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "jack", "queen", "king", "ace",
)  # fmt: skip
SUIT_NAMES = ("clubs", "diamonds", "hearts", "spades")

NUM_RANKS = 13
NUM_SUITS = 4
NUM_CARDS = 52
DECK: tuple[int, ...] = tuple(range(NUM_CARDS))

_SYMBOL_TO_SUIT = {sym: i for i, sym in enumerate(SUIT_SYMBOLS)}
# Accept "10" as well as "T"; one card = rank token + suit token.
_CARD_TOKEN = re.compile(r"(10|[2-9TJQKA])([CDHS♣♦♥♠])", re.IGNORECASE)


class CardError(ValueError):
    """Base class for invalid card input."""


class InvalidCardError(CardError):
    """A string that does not describe a card."""


class DuplicateCardError(CardError):
    """The same card was used more than once."""


def make_card(rank: int, suit: int) -> int:
    """Build a card from rank (0-12) and suit (0-3) indices."""
    if not (0 <= rank < NUM_RANKS and 0 <= suit < NUM_SUITS):
        raise InvalidCardError(f"rank {rank} / suit {suit} out of range")
    return rank * NUM_SUITS + suit


def rank_of(card: int) -> int:
    """Rank index 0 (deuce) .. 12 (ace)."""
    return card // NUM_SUITS


def suit_of(card: int) -> int:
    """Suit index 0 (clubs) .. 3 (spades)."""
    return card % NUM_SUITS


def check_card(card: int) -> None:
    # bool is a subclass of int; reject it explicitly.
    if not isinstance(card, int) or isinstance(card, bool) or not 0 <= card < NUM_CARDS:
        raise InvalidCardError(f"{card!r} is not a card id (expected an int 0-51)")


def card_to_str(card: int) -> str:
    """``51 -> "As"``."""
    check_card(card)
    return RANKS[rank_of(card)] + SUITS[suit_of(card)]


def card_to_pretty(card: int) -> str:
    """``51 -> "A♠"``."""
    check_card(card)
    return RANKS[rank_of(card)] + SUIT_SYMBOLS[suit_of(card)]


def card_name(card: int) -> str:
    """``51 -> "ace of spades"`` (used for accessibility labels)."""
    check_card(card)
    return f"{RANK_NAMES[rank_of(card)]} of {SUIT_NAMES[suit_of(card)]}"


def _token_to_card(rank_tok: str, suit_tok: str) -> int:
    rank_tok = "T" if rank_tok == "10" else rank_tok.upper()
    rank = RANKS.index(rank_tok)
    suit = (
        _SYMBOL_TO_SUIT[suit_tok] if suit_tok in _SYMBOL_TO_SUIT else SUITS.index(suit_tok.lower())
    )
    return make_card(rank, suit)


def parse_card(text: str) -> int:
    """Parse one card: ``"As"``, ``"as"``, ``"A♠"``, ``"10h"`` or ``"Th"``."""
    if not isinstance(text, str):
        raise InvalidCardError(f"{text!r} is not a string")
    match = _CARD_TOKEN.fullmatch(text.strip())
    if match is None:
        raise InvalidCardError(
            f"{text!r} is not a card. Use rank (2-9, T, J, Q, K, A) + suit (c, d, h, s), e.g. 'As'."
        )
    return _token_to_card(*match.groups())


def parse_cards(text: str) -> list[int]:
    """Parse several cards: ``"AsQs"``, ``"As Qs"``, ``"A♠, Q♠"`` -> ``[51, 43]``.

    Does not check for duplicates; use :func:`ensure_unique` for that.
    """
    if not isinstance(text, str):
        raise InvalidCardError(f"{text!r} is not a string")
    cleaned = re.sub(r"[\s,]+", "", text)
    cards: list[int] = []
    pos = 0
    while pos < len(cleaned):
        match = _CARD_TOKEN.match(cleaned, pos)
        if match is None:
            raise InvalidCardError(f"Could not read a card at {cleaned[pos:]!r} in {text!r}.")
        cards.append(_token_to_card(*match.groups()))
        pos = match.end()
    return cards


def ensure_unique(cards: Iterable[int]) -> None:
    """Raise :class:`DuplicateCardError` if any card appears more than once."""
    counts = Counter(cards)
    duplicates = sorted(card for card, n in counts.items() if n > 1)
    if duplicates:
        listed = ", ".join(card_to_str(c) for c in duplicates)
        noun = "card is" if len(duplicates) == 1 else "cards are"
        raise DuplicateCardError(f"The following {noun} used more than once: {listed}.")


def remaining_deck(dead: Iterable[int]) -> list[int]:
    """All cards not in ``dead`` (the cards already visible), in id order."""
    dead_set = set(dead)
    return [c for c in DECK if c not in dead_set]
