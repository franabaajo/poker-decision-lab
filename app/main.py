"""FastAPI application: JSON API under /api, static frontend at /.

Run locally with:
    uv run uvicorn app.main:app --reload
"""

from pathlib import Path
from typing import Literal

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
from pokerlab.equity import EquityError, calculate_equity
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


class EquityIn(BaseModel):
    hero: list[str] = Field(examples=[["As", "Qs"]])
    board: list[str] = Field(default_factory=list, examples=[["Js", "8d", "4s"]])
    range_notation: str | None = Field(default=None, examples=["77+, ATs+, KTs+, QJs, AJo+, KQo"])
    range_weights: dict[str, float] | None = None
    method: Literal["auto", "exact", "monte_carlo"] = "auto"
    samples: int = Field(default=50_000, ge=1_000, le=500_000)
    seed: int | None = Field(default=None, ge=0, lt=2**32)


class ClassEquityOut(BaseModel):
    label: str
    share: float = Field(description="Fraction of the live, weighted range")
    equity: float
    win: float
    tie: float


class EquityOut(BaseModel):
    valid: bool
    error: str | None = None
    win: float = 0
    tie: float = 0
    lose: float = 0
    equity: float = 0
    std_error: float = 0
    ci95: tuple[float, float] = (0, 0)
    method: str = ""
    n: int = Field(0, description="Monte Carlo samples, or showdowns enumerated (exact)")
    live_combos: float = 0
    seed: int | None = None
    elapsed_ms: float = 0
    by_class: list[ClassEquityOut] = []


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


@app.post("/api/equity")
def equity(body: EquityIn) -> EquityOut:
    """Hero's win / tie / lose probabilities and equity against the opponent range."""
    try:
        spot = Spot(
            tuple(parse_card(c) for c in body.hero),
            tuple(parse_card(c) for c in body.board),
        )
        rng = (
            Range(body.range_weights)
            if body.range_weights is not None
            else Range.parse(body.range_notation or "")
        )
        result = calculate_equity(spot, rng, body.method, body.samples, body.seed)
    except (CardError, RangeError, EquityError) as exc:
        return EquityOut(valid=False, error=str(exc))
    return EquityOut(
        valid=True,
        win=result.win,
        tie=result.tie,
        lose=result.lose,
        equity=result.equity,
        std_error=result.estimate.std_error,
        ci95=result.ci95,
        method=result.method,
        n=result.estimate.n,
        live_combos=result.live_combos,
        seed=result.seed,
        elapsed_ms=round(result.elapsed_s * 1000, 1),
        by_class=[
            ClassEquityOut(label=c.label, share=c.share, equity=c.equity, win=c.win, tie=c.tie)
            for c in result.by_class.values()
        ],
    )


# Mounted last so that /api/* routes take precedence over static files.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
