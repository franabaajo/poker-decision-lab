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
from pokerlab import service

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
    bet_fraction: float
    value_share: float
    bluff_share: float


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


class AnalyseIn(EquityIn):
    pot: float = Field(ge=0, examples=[100], description="Chips in the pot before the bet")
    bet: float = Field(gt=0, examples=[50], description="The opponent's bet")
    stack: float = Field(gt=0, examples=[500], description="Effective stack before the bet")
    style: Literal["tight", "balanced", "aggressive"] = Field(
        default="balanced", description="Opponent's betting style on the turn and river"
    )


class DecisionOut(BaseModel):
    call: float
    returned: float = Field(description="Part of the bet that cannot be called")
    is_all_in: bool
    final_pot: float
    break_even_equity: float
    pot_odds: float = Field(description="X in 'X : 1'")
    ev_fold: float
    ev_call: float
    ev_call_ci95: tuple[float, float]
    margin: float = Field(description="Equity minus break-even equity")
    verdict: str
    verdict_label: str
    verdict_basis: str = Field(description="'multi_street' or 'showdown'")
    explanation: str


class StrategyOut(BaseModel):
    key: str
    name: str
    bet_fraction: float
    value_share: float
    bluff_share: float
    bet_share: float


class MultiStreetOut(BaseModel):
    available: bool
    note: str | None = None
    ev_call: float = 0
    ev_showdown: float = 0
    realized_equity: float = 0
    realization: float = 0
    later_streets: int = 0
    stats: dict[str, float] = {}
    strategy: StrategyOut | None = None
    elapsed_ms: float = 0


class AnalyseOut(EquityOut):
    decision: DecisionOut | None = None
    multi_street: MultiStreetOut | None = None


# --- Routes -----------------------------------------------------------------------
# Each endpoint validates its input with the schemas above, then calls the shared
# service layer, which the in-browser (Pyodide) version of the app also uses.


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness check used by the frontend and tests."""
    return service.health()


@app.get("/api/cards")
def list_cards() -> list[CardOut]:
    """The 52-card deck in engine order. The frontend builds its card picker from this."""
    return [CardOut(**c) for c in service.list_cards()]


@app.post("/api/spot/validate")
def validate_spot(spot_in: SpotIn) -> SpotValidation:
    """Check that the cards form a legal spot.

    Invalid input is a normal answer (valid=false), not an HTTP error.
    """
    return SpotValidation(**service.validate_spot(spot_in.hero, spot_in.board))


@app.get("/api/ranges/presets")
def list_presets() -> list[PresetOut]:
    """The preset opponent profiles and their ranges."""
    return [PresetOut(**p) for p in service.list_presets()]


@app.post("/api/ranges/analyse")
def analyse_range(range_in: RangeIn) -> RangeOut:
    """Parse a range (text or grid weights) and apply card removal.

    Returns the normalised notation and per-class counts so the grid, the text box
    and the summary can all be redrawn from one answer.
    """
    return RangeOut(**service.analyse_range(**range_in.model_dump()))


@app.post("/api/equity")
def equity(body: EquityIn) -> EquityOut:
    """Hero's win / tie / lose probabilities and equity against the opponent range."""
    return EquityOut(**service.equity(**body.model_dump()))


@app.post("/api/analyse")
def analyse(body: AnalyseIn) -> AnalyseOut:
    """Equity, pot odds, fold/call EV and a verdict, including turn and river betting."""
    return AnalyseOut(**service.analyse(**body.model_dump()))


# Mounted last so that /api/* routes take precedence over static files.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
