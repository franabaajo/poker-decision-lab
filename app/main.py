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


# Mounted last so that /api/* routes take precedence over static files.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
