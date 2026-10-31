"""A *spot*: the known cards of one decision (hero's hole cards + the board).

Pot, bet and stack sizes are added in M5; this module only owns card validity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pokerlab.cards import CardError, card_to_str, check_card, ensure_unique, parse_cards


class Street(Enum):
    PREFLOP = 0
    FLOP = 3
    TURN = 4
    RIVER = 5

    @property
    def label(self) -> str:
        return self.name.capitalize()


_STREET_BY_BOARD_SIZE = {s.value: s for s in Street}


class SpotError(CardError):
    """The combination of hero cards and board is not a legal situation."""


@dataclass(frozen=True)
class Spot:
    """Hero's two hole cards and 0, 3, 4 or 5 community cards, all distinct."""

    hero: tuple[int, int]
    board: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        # Normalise lists to tuples so the dataclass stays hashable/immutable.
        object.__setattr__(self, "hero", tuple(self.hero))
        object.__setattr__(self, "board", tuple(self.board))

        if len(self.hero) != 2:
            raise SpotError(f"You need exactly 2 hole cards (got {len(self.hero)}).")
        if len(self.board) not in _STREET_BY_BOARD_SIZE:
            raise SpotError(
                f"The board must have 0, 3, 4 or 5 cards (got {len(self.board)}). "
                "The flop is dealt as three cards at once."
            )
        for card in (*self.hero, *self.board):
            check_card(card)
        ensure_unique(self.dead_cards)

    @classmethod
    def from_strings(cls, hero: str, board: str = "") -> Spot:
        """``Spot.from_strings("AsQs", "Js8d4s")``."""
        return cls(tuple(parse_cards(hero)), tuple(parse_cards(board)))

    @property
    def dead_cards(self) -> tuple[int, ...]:
        """Cards that can no longer be dealt to anyone else."""
        return (*self.hero, *self.board)

    @property
    def street(self) -> Street:
        return _STREET_BY_BOARD_SIZE[len(self.board)]

    @property
    def cards_to_come(self) -> int:
        """How many community cards are still to be dealt."""
        return 5 - len(self.board)

    def __str__(self) -> str:
        hero = "".join(card_to_str(c) for c in self.hero)
        board = "".join(card_to_str(c) for c in self.board) or "-"
        return f"{hero} | {board} ({self.street.label})"
