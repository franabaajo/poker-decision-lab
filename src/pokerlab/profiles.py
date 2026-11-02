"""Preset opponent profiles (ADR 0014).

Each profile is a range: the hands this kind of opponent is assumed to hold when
they make the bet being analysed. They are deliberately simple, documented
starting points; users can edit them in the range grid.

Later milestones (M6) attach a betting strategy for the turn and river to each
profile as well.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokerlab.ranges import Range


@dataclass(frozen=True)
class Profile:
    key: str
    name: str
    description: str
    notation: str

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
        ),
        Profile(
            key="balanced",
            name="Balanced",
            description="Strong hands plus medium pairs, suited aces and broadways, "
            "and some suited connectors.",
            notation="55+, A2s+, K9s+, Q9s+, J9s+, T9s, 98s, 87s, A9o+, KTo+, QJo",
        ),
        Profile(
            key="aggressive",
            name="Aggressive",
            description="Bets a wide range: all pairs, most suited hands and many weak "
            "offsuit hands, including plenty of bluffs and draws.",
            notation="22+, A2s+, K5s+, Q7s+, J7s+, T7s+, 96s+, 85s+, 75s+, 64s+, 54s, "
            "A5o+, K9o+, Q9o+, J9o+, T9o",
        ),
    ]
}
