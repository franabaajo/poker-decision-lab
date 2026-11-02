"""Opponent ranges: which hands the opponent might hold, and how often.

Vocabulary
----------
- **Combo**: one exact pair of hole cards, e.g. A♠K♠. There are C(52,2) = 1,326.
- **Hand class**: combos that are strategically identical before the flop.
  There are 169 classes:

  ========  ==========  ======================  ================
  Kind      Example     Combos per class        Classes
  ========  ==========  ======================  ================
  Pair      ``QQ``      6  (C(4,2) suit pairs)  13
  Suited    ``AKs``     4  (one per suit)       78
  Offsuit   ``AKo``     12 (4 x 3 suit choices) 78
  ========  ==========  ======================  ================

  13*6 + 78*4 + 78*12 = 1,326.

- **Range**: a weight in [0, 1] for each class (ADR 0005, 0013, 0015). Weight 1
  means "always holds this hand when betting here", 0.5 means "half the time".
  The range describes the opponent's hands *given that they made this bet*.

- **Card removal**: combos that use a card the hero holds or that is on the
  board are impossible and are dropped (:meth:`Range.combos`).

Text notation (standard poker shorthand)
----------------------------------------
``AA``, ``AKs``, ``AKo``; ``AK`` = both AKs and AKo;
``TT+`` = TT..AA; ``ATs+`` = ATs, AJs, AQs, AKs (kicker rises, top card fixed);
``99-66`` and ``A5s-A2s`` = inclusive spans; ``:w`` sets a weight, e.g. ``A5s:0.5``.
Tokens are separated by commas or spaces; later tokens override earlier ones.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field

from pokerlab.cards import NUM_CARDS, RANKS, rank_of, suit_of

# Grid order: ace first, as in every poker range chart.
GRID_RANKS = RANKS[::-1]  # "AKQJT98765432"
TOTAL_COMBOS = 1326


class RangeError(ValueError):
    """Invalid range notation or weights."""


# --- Hand classes ---------------------------------------------------------------------


def _r(ch: str) -> int:
    """Rank character -> engine rank index (0 = deuce .. 12 = ace)."""
    return RANKS.index(ch)


def class_label(hi: int, lo: int, suited: bool) -> str:
    """Rank indices -> label. ``class_label(12, 11, True) == "AKs"``; pairs ignore ``suited``."""
    if hi < lo:
        hi, lo = lo, hi
    if hi == lo:
        return RANKS[hi] * 2
    return RANKS[hi] + RANKS[lo] + ("s" if suited else "o")


def _all_classes() -> list[str]:
    """The 169 class labels in grid order: row by row, pairs on the diagonal,
    suited above it (upper right) and offsuit below it (lower left)."""
    labels = []
    for i, row_rank in enumerate(GRID_RANKS):
        for j, col_rank in enumerate(GRID_RANKS):
            hi, lo = _r(row_rank), _r(col_rank)
            labels.append(class_label(hi, lo, suited=j > i))
    return labels


HAND_CLASSES: tuple[str, ...] = tuple(_all_classes())
_CLASS_SET = frozenset(HAND_CLASSES)


def class_of_combo(c1: int, c2: int) -> str:
    """The class a combo belongs to: (As, Ks) -> "AKs"."""
    return class_label(rank_of(c1), rank_of(c2), suit_of(c1) == suit_of(c2))


def _build_class_combos() -> dict[str, tuple[tuple[int, int], ...]]:
    table: dict[str, list[tuple[int, int]]] = {label: [] for label in HAND_CLASSES}
    for a, b in itertools.combinations(range(NUM_CARDS), 2):
        table[class_of_combo(a, b)].append((b, a))  # higher card id first
    return {label: tuple(combos) for label, combos in table.items()}


CLASS_COMBOS: Mapping[str, tuple[tuple[int, int], ...]] = _build_class_combos()


def combos_in_class(label: str) -> int:
    """6 for pairs, 4 for suited, 12 for offsuit."""
    return len(CLASS_COMBOS[label])


# --- Parsing ---------------------------------------------------------------------------

_TOKEN = re.compile(
    r"""^(?P<a>[2-9TJQKA])(?P<b>[2-9TJQKA])(?P<s>[so]?)       # first class
         (?:(?P<plus>\+)|-(?P<c>[2-9TJQKA])(?P<d>[2-9TJQKA])(?P<s2>[so]?))?   # + or span
         (?::(?P<w>\d*\.?\d+))?$""",  # optional weight
    re.VERBOSE,
)


def _expand_token(token: str) -> tuple[list[str], float]:
    """One notation token -> (class labels, weight)."""
    m = _TOKEN.match(token.upper().replace("S", "s").replace("O", "o"))
    if m is None:
        raise RangeError(
            f"Could not read {token!r}. Examples of valid tokens: AA, AKs, AKo, TT+, ATs+, 99-66, "
            "A5s-A2s, AQo:0.5"
        )
    a, b, s = _r(m["a"]), _r(m["b"]), m["s"]
    weight = float(m["w"]) if m["w"] else 1.0
    if not 0.0 <= weight <= 1.0:
        raise RangeError(f"Weight in {token!r} must be between 0 and 1.")

    if a == b:  # pairs
        if s:
            raise RangeError(f"{token!r}: a pair cannot be suited or offsuit.")
        if m["plus"]:
            ranks = range(a, 13)
        elif m["c"]:
            c, d = _r(m["c"]), _r(m["d"])
            if c != d or m["s2"]:
                raise RangeError(f"{token!r}: a pair span must end in a pair, e.g. 99-66.")
            ranks = range(min(a, c), max(a, c) + 1)
        else:
            ranks = range(a, a + 1)
        return [RANKS[r] * 2 for r in ranks], weight

    if a < b:
        raise RangeError(f"{token!r}: write the higher card first, e.g. {m['b']}{m['a']}{s}.")
    suits = [s] if s else ["s", "o"]
    if m["plus"]:
        kickers = range(b, a)  # ATs+ -> T..K
    elif m["c"]:
        c, d = _r(m["c"]), _r(m["d"])
        if c != a or (m["s2"] or s) != s or c <= d:
            raise RangeError(
                f"{token!r}: a span must keep the same top card and type, e.g. A5s-A2s or KTo-K8o."
            )
        kickers = range(min(b, d), max(b, d) + 1)
    else:
        kickers = range(b, b + 1)
    return [RANKS[a] + RANKS[k] + suit for k in kickers for suit in suits], weight


@dataclass(frozen=True)
class Range:
    """Weights for the 169 hand classes. Classes not listed have weight 0."""

    weights: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        clean: dict[str, float] = {}
        for label, w in self.weights.items():
            if label not in _CLASS_SET:
                raise RangeError(f"{label!r} is not a hand class (e.g. AA, AKs, AKo).")
            w = round(float(w), 3)  # frequencies to 0.1%; keeps notation round trips exact
            if not 0.0 <= w <= 1.0:
                raise RangeError(f"Weight for {label} must be between 0 and 1 (got {w}).")
            if w > 0:
                clean[label] = w
        object.__setattr__(self, "weights", clean)

    # --- construction ---

    @classmethod
    def parse(cls, notation: str) -> Range:
        """``Range.parse("TT+, AKs, A5s:0.5")``. Later tokens override earlier ones."""
        weights: dict[str, float] = {}
        for token in re.split(r"[\s,]+", notation.strip()):
            if not token:
                continue
            labels, w = _expand_token(token)
            for label in labels:
                weights[label] = w
        return cls(weights)

    @classmethod
    def full(cls) -> Range:
        return cls(dict.fromkeys(HAND_CLASSES, 1.0))

    # --- queries ---

    def weight(self, label: str) -> float:
        return self.weights.get(label, 0.0)

    def __len__(self) -> int:
        """Number of classes with positive weight."""
        return len(self.weights)

    def combo_count(self) -> float:
        """Weighted number of combos, ignoring card removal. Full range = 1326."""
        return sum(w * combos_in_class(label) for label, w in self.weights.items())

    def fraction(self) -> float:
        """Share of all 1,326 starting hands (weighted)."""
        return self.combo_count() / TOTAL_COMBOS

    def combos(self, dead: Iterable[int] = ()) -> list[tuple[tuple[int, int], float]]:
        """Every possible combo with its weight, excluding combos that use a dead card."""
        dead_set = set(dead)
        return [
            (combo, w)
            for label, w in self.weights.items()
            for combo in CLASS_COMBOS[label]
            if combo[0] not in dead_set and combo[1] not in dead_set
        ]

    def live_combo_count(self, dead: Iterable[int] = ()) -> float:
        """Weighted number of combos still possible given the dead cards."""
        return sum(w for _, w in self.combos(dead))

    def iter_grid(self) -> Iterator[tuple[str, float]]:
        """(label, weight) for all 169 classes in grid order."""
        for label in HAND_CLASSES:
            yield label, self.weight(label)

    # --- formatting ---

    def to_notation(self) -> str:
        """Compact notation that parses back to exactly this range."""
        parts: list[str] = []

        def fmt(text: str, w: float) -> str:
            return text if w == 1.0 else f"{text}:{w:g}"

        # Pairs, from AA down; group runs of equal weight.
        pairs = [(r, self.weight(RANKS[r] * 2)) for r in range(12, -1, -1)]
        for run in _runs(pairs):
            top, bottom, w = run
            hi, lo = RANKS[top] * 2, RANKS[bottom] * 2
            if top == bottom:
                parts.append(fmt(hi, w))
            elif top == 12:
                parts.append(fmt(f"{lo}+", w))
            else:
                parts.append(fmt(f"{hi}-{lo}", w))

        # Suited, then offsuit; for each top card, group kicker runs of equal weight.
        for suffix in ("s", "o"):
            for hi in range(12, 0, -1):
                kickers = [
                    (k, self.weight(RANKS[hi] + RANKS[k] + suffix)) for k in range(hi - 1, -1, -1)
                ]
                for top, bottom, w in _runs(kickers):
                    a = RANKS[hi] + RANKS[top] + suffix
                    b = RANKS[hi] + RANKS[bottom] + suffix
                    if top == bottom:
                        parts.append(fmt(a, w))
                    elif top == hi - 1:
                        parts.append(fmt(f"{b}+", w))
                    else:
                        parts.append(fmt(f"{a}-{b}", w))
        return ", ".join(parts)

    def __str__(self) -> str:
        return self.to_notation()


def _runs(items: list[tuple[int, float]]) -> Iterator[tuple[int, int, float]]:
    """Group consecutive (rank, weight) items with equal positive weight.

    ``items`` are ordered from high rank to low; yields (top_rank, bottom_rank, weight).
    """
    i = 0
    while i < len(items):
        rank, w = items[i]
        if w == 0:
            i += 1
            continue
        j = i
        while j + 1 < len(items) and items[j + 1][1] == w:
            j += 1
        yield rank, items[j][0], w
        i = j + 1
