"""Preset opponent profiles (ADR 0014).

Each profile is a range: the hands this kind of opponent is assumed to hold when
they make the bet being analysed. They are deliberately simple, documented
starting points; users can edit them in the range grid.

Each profile also carries a simple betting rule for the turn and river
(ADR 0018, 0019): bet a fixed fraction of the pot with the strongest part of the
current range (value bets) and with part of the weakest (bluffs); check the rest.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokerlab.ranges import Range


@dataclass(frozen=True)
class Strategy:
    """How the opponent bets on later streets.

    bet_fraction  bet size as a fraction of the pot (capped by the stack)
    value_share   share of the current range, strongest first, that bets for value
    bluff_share   share of the *remaining* range, weakest first, that bets as a bluff
    """

    bet_fraction: float
    value_share: float
    bluff_share: float

    def __post_init__(self) -> None:
        if self.bet_fraction <= 0:
            raise ValueError("bet_fraction must be positive")
        for name in ("value_share", "bluff_share"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

    @property
    def bet_share(self) -> float:
        """Fraction of the range that bets: value + bluffs."""
        return self.value_share + self.bluff_share * (1.0 - self.value_share)


@dataclass(frozen=True)
class Profile:
    key: str
    name: str
    description: str
    notation: str
    strategy: Strategy

    @property
    def range(self) -> Range:
        return Range.parse(self.notation)


PROFILES: dict[str, Profile] = {
    p.key: p
    for p in [
        Profile(
            key="tight",
            name="Tight",
            description="Only bets strong hands: big pairs, strong aces, a few suited broadways.",
            notation="77+, ATs+, KTs+, QJs, AJo+, KQo",
            strategy=Strategy(bet_fraction=0.5, value_share=0.30, bluff_share=0.10),
        ),
        Profile(
            key="balanced",
            name="Balanced",
            description="Strong hands plus medium pairs, suited aces and broadways, "
            "and some suited connectors.",
            notation="55+, A2s+, K9s+, Q9s+, J9s+, T9s, 98s, 87s, A9o+, KTo+, QJo",
            strategy=Strategy(bet_fraction=2 / 3, value_share=0.35, bluff_share=0.25),
        ),
        Profile(
            key="aggressive",
            name="Aggressive",
            description="Bets a wide range: all pairs, most suited hands and many weak "
            "offsuit hands, including plenty of bluffs and draws.",
            notation="22+, A2s+, K5s+, Q7s+, J7s+, T7s+, 96s+, 85s+, 75s+, 64s+, 54s, "
            "A5o+, K9o+, Q9o+, J9o+, T9o",
            strategy=Strategy(bet_fraction=1.0, value_share=0.45, bluff_share=0.50),
        ),
    ]
}
