"""FastAPI application: JSON API under /api, static frontend at /.

Run locally with:
    uv run uvicorn app.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import pokerlab
from pokerlab.cards import (
    DECK,
    RANKS,
    SUITS,
    CardError,
    card_name,
    card_to_pretty,
    card_to_str,
    parse_card,
    rank_of,
    suit_of,
)
from pokerlab.profiles import PROFILES
from pokerlab.ranges import CLASS_COMBOS, Range, RangeError
from pokerlab.spot import Spot

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Poker Decision Lab",
    version=pokerlab.__version__,
    description="Educational call/fold analysis for heads-up Texas Hold'em. Not a gambling tool.",
)


# --- Schemas ----------------------------------------------------------------------


class CardOut(BaseModel):
    id: int = Field(description="Engine id 0-51 (rank * 4 + suit)")
    code: str = Field(description='Short code, e.g. "As"')
    pretty: str = Field(description='With suit symbol, e.g. "A♠"')
    name: str = Field(description='e.g. "ace of spades"')
    rank: str
    suit: str


class SpotIn(BaseModel):
    hero: list[str] = Field(examples=[["As", "Qs"]])
    board: list[str] = Field(default_factory=list, examples=[["Js", "8d", "4s"]])


class SpotValidation(BaseModel):
    valid: bool
    error: str | None = None
    street: str | None = None
    hero: list[str] = []
    board: list[str] = []


class PresetOut(BaseModel):
    key: str
    name: str
    description: str
    notation: str
    combos: float
    percent: float


class RangeIn(BaseModel):
    """Give either ``notation`` (text) or ``weights`` (from the grid)."""

    notation: str | None = Field(default=None, examples=["TT+, AKs, A5s:0.5"])
    weights: dict[str, float] | None = Field(default=None, examples=[{"AA": 1, "A5s": 0.5}])
    hero: list[str] = Field(default_factory=list, description="Cards removed from the range")
    board: list[str] = Field(default_factory=list)


class GridCell(BaseModel):
    label: str
    weight: float
    combos: int = Field(description="Combos in this class (6, 4 or 12)")
    live: int = Field(description="Combos still possible after card removal")


class RangeOut(BaseModel):
    valid: bool
    error: str | None = None
    notation: str = ""
    combos: float = Field(0, description="Weighted combos, ignoring card removal")
    live_combos: float = Field(0, description="Weighted combos after card removal")
    percent: float = Field(0, description="Share of all 1,326 starting hands")
    grid: list[GridCell] = []


# --- Routes -----------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness check used by the frontend, tests and the deployment platform."""
    return {"status": "ok", "version": pokerlab.__version__}


@app.get("/api/cards")
def list_cards() -> list[CardOut]:
    """The 52-card deck in engine order. The frontend builds its card picker from this."""
    return [
        CardOut(
            id=c,
            code=card_to_str(c),
            pretty=card_to_pretty(c),
            name=card_name(c),
            rank=RANKS[rank_of(c)],
            suit=SUITS[suit_of(c)],
        )
        for c in DECK
    ]


@app.post("/api/spot/validate")
def validate_spot(spot_in: SpotIn) -> SpotValidation:
    """Check that the cards form a legal spot.

    Invalid input is a normal answer (valid=false), not an HTTP error.
    """
    try:
        spot = Spot(
            tuple(parse_card(c) for c in spot_in.hero),
            tuple(parse_card(c) for c in spot_in.board),
        )
    except CardError as exc:
        return SpotValidation(valid=False, error=str(exc))
    return SpotValidation(
        valid=True,
        street=spot.street.label,
        hero=[card_to_str(c) for c in spot.hero],
        board=[card_to_str(c) for c in spot.board],
    )


@app.get("/api/ranges/presets")
def list_presets() -> list[PresetOut]:
    """The preset opponent profiles and their ranges."""
    return [
        PresetOut(
            key=p.key,
            name=p.name,
            description=p.description,
            notation=p.notation,
            combos=p.range.combo_count(),
            percent=round(100 * p.range.fraction(), 1),
        )
        for p in PROFILES.values()
    ]


@app.post("/api/ranges/analyse")
def analyse_range(range_in: RangeIn) -> RangeOut:
    """Parse a range (text or grid weights) and apply card removal.

    Returns the normalised notation and per-class counts so the grid, the text box
    and the summary can all be redrawn from one answer.
    """
    try:
        if range_in.weights is not None:
            rng = Range(range_in.weights)
        else:
            rng = Range.parse(range_in.notation or "")
        dead = {parse_card(c) for c in (*range_in.hero, *range_in.board)}
    except (RangeError, CardError) as exc:
        return RangeOut(valid=False, error=str(exc))

    grid = [
        GridCell(
            label=label,
            weight=weight,
            combos=len(CLASS_COMBOS[label]),
            live=sum(1 for a, b in CLASS_COMBOS[label] if a not in dead and b not in dead),
        )
        for label, weight in rng.iter_grid()
    ]
    return RangeOut(
        valid=True,
        notation=rng.to_notation(),
        combos=rng.combo_count(),
        live_combos=rng.live_combo_count(dead),
        percent=round(100 * rng.fraction(), 1),
        grid=grid,
    )


# Mounted last so that /api/* routes take precedence over static files.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
