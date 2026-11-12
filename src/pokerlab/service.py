"""Application service: the app's operations as plain JSON-in / JSON-out functions.

Two front doors use this module (ADR 0025):

- the FastAPI server (``app/main.py``) wraps each function in an HTTP endpoint;
- the static website runs the same functions inside the visitor's browser with
  Pyodide (Python compiled to WebAssembly), through :func:`dispatch`.

So the browser demo and the local server run exactly the same, tested code.
Functions take and return only JSON-compatible values (str, int, float, bool,
None, list, dict). Invalid user input is reported as ``{"valid": False, "error": ...}``
rather than raised, so the UI can show the message.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

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
from pokerlab.decision import DecisionError, Situation, decide, explain
from pokerlab.equity import EquityError, EquityResult, calculate_equity
from pokerlab.multistreet import MultiStreetError, analyse_call
from pokerlab.multistreet import explain as explain_multistreet
from pokerlab.profiles import PROFILES
from pokerlab.ranges import CLASS_COMBOS, Range, RangeError
from pokerlab.spot import Spot

METHODS = ("auto", "exact", "monte_carlo")
MIN_SAMPLES, MAX_SAMPLES = 1_000, 500_000


class ServiceError(ValueError):
    """Invalid request parameters (outside what the UI can send)."""


_USER_ERRORS = (CardError, RangeError, EquityError, DecisionError, ServiceError)


# --- Simple lookups -------------------------------------------------------------------


def health() -> dict[str, str]:
    return {"status": "ok", "version": pokerlab.__version__}


def list_cards() -> list[dict[str, Any]]:
    """The 52-card deck in engine order."""
    return [
        {
            "id": c,
            "code": card_to_str(c),
            "pretty": card_to_pretty(c),
            "name": card_name(c),
            "rank": RANKS[rank_of(c)],
            "suit": SUITS[suit_of(c)],
        }
        for c in DECK
    ]


def list_presets() -> list[dict[str, Any]]:
    """Preset opponent profiles: range and later-street betting style."""
    return [
        {
            "key": p.key,
            "name": p.name,
            "description": p.description,
            "notation": p.notation,
            "combos": p.range.combo_count(),
            "percent": round(100 * p.range.fraction(), 1),
            "bet_fraction": p.strategy.bet_fraction,
            "value_share": p.strategy.value_share,
            "bluff_share": p.strategy.bluff_share,
        }
        for p in PROFILES.values()
    ]


# --- Validation of cards and ranges ---------------------------------------------------------


def _spot(hero: list[str], board: list[str]) -> Spot:
    return Spot(tuple(parse_card(c) for c in hero), tuple(parse_card(c) for c in board))


def _range(notation: str | None, weights: dict[str, float] | None) -> Range:
    return Range(weights) if weights is not None else Range.parse(notation or "")


def validate_spot(hero: list[str], board: list[str] | None = None) -> dict[str, Any]:
    """Check that the cards form a legal spot."""
    try:
        spot = _spot(hero, board or [])
    except CardError as exc:
        return {"valid": False, "error": str(exc), "street": None, "hero": [], "board": []}
    return {
        "valid": True,
        "error": None,
        "street": spot.street.label,
        "hero": [card_to_str(c) for c in spot.hero],
        "board": [card_to_str(c) for c in spot.board],
    }


def analyse_range(
    notation: str | None = None,
    weights: dict[str, float] | None = None,
    hero: list[str] | None = None,
    board: list[str] | None = None,
) -> dict[str, Any]:
    """Parse a range (text or grid weights), apply card removal, return grid and counts."""
    try:
        rng = _range(notation, weights)
        dead = {parse_card(c) for c in (*(hero or []), *(board or []))}
    except (RangeError, CardError) as exc:
        return {"valid": False, "error": str(exc)}
    grid = [
        {
            "label": label,
            "weight": weight,
            "combos": len(CLASS_COMBOS[label]),
            "live": sum(1 for a, b in CLASS_COMBOS[label] if a not in dead and b not in dead),
        }
        for label, weight in rng.iter_grid()
    ]
    return {
        "valid": True,
        "error": None,
        "notation": rng.to_notation(),
        "combos": rng.combo_count(),
        "live_combos": rng.live_combo_count(dead),
        "percent": round(100 * rng.fraction(), 1),
        "grid": grid,
    }


# --- Equity and the decision -------------------------------------------------------------


def _check_equity_params(method: str, samples: int, seed: int | None) -> None:
    if method not in METHODS:
        raise ServiceError(f"Unknown method {method!r}; use one of {', '.join(METHODS)}.")
    if not MIN_SAMPLES <= samples <= MAX_SAMPLES:
        raise ServiceError(f"Samples must be between {MIN_SAMPLES:,} and {MAX_SAMPLES:,}.")
    if seed is not None and not 0 <= seed < 2**32:
        raise ServiceError("The seed must be between 0 and 2^32 - 1.")


def _equity_fields(result: EquityResult) -> dict[str, Any]:
    return {
        "valid": True,
        "error": None,
        "win": result.win,
        "tie": result.tie,
        "lose": result.lose,
        "equity": result.equity,
        "std_error": result.estimate.std_error,
        "ci95": list(result.ci95),
        "method": result.method,
        "n": result.estimate.n,
        "live_combos": result.live_combos,
        "seed": result.seed,
        "elapsed_ms": round(result.elapsed_s * 1000, 1),
        "by_class": [
            {"label": c.label, "share": c.share, "equity": c.equity, "win": c.win, "tie": c.tie}
            for c in result.by_class.values()
        ],
    }


def equity(
    hero: list[str],
    board: list[str] | None = None,
    range_notation: str | None = None,
    range_weights: dict[str, float] | None = None,
    method: str = "auto",
    samples: int = 50_000,
    seed: int | None = None,
) -> dict[str, Any]:
    """Hero's win / tie / lose probabilities and equity against the opponent range."""
    try:
        _check_equity_params(method, samples, seed)
        spot, rng = _spot(hero, board or []), _range(range_notation, range_weights)
        result = calculate_equity(spot, rng, method, samples, seed)  # type: ignore[arg-type]
    except _USER_ERRORS as exc:
        return {"valid": False, "error": str(exc)}
    return _equity_fields(result)


def analyse(
    hero: list[str],
    board: list[str] | None = None,
    range_notation: str | None = None,
    range_weights: dict[str, float] | None = None,
    method: str = "auto",
    samples: int = 50_000,
    seed: int | None = None,
    pot: float = 100,
    bet: float = 50,
    stack: float = 500,
    style: str = "balanced",
) -> dict[str, Any]:
    """Equity, pot odds, fold/call EV and a verdict, including turn and river betting."""
    try:
        _check_equity_params(method, samples, seed)
        if style not in PROFILES:
            raise ServiceError(f"Unknown style {style!r}; use one of {', '.join(PROFILES)}.")
        situation = Situation(pot=pot, bet=bet, stack=stack)
        spot, rng = _spot(hero, board or []), _range(range_notation, range_weights)
        result = calculate_equity(spot, rng, method, samples, seed)  # type: ignore[arg-type]
    except _USER_ERRORS as exc:
        return {"valid": False, "error": str(exc), "decision": None, "multi_street": None}
    d = decide(situation, result.equity, result.ci95)

    profile = PROFILES[style]
    strategy = profile.strategy
    strategy_out = {
        "key": profile.key,
        "name": profile.name,
        "bet_fraction": strategy.bet_fraction,
        "value_share": strategy.value_share,
        "bluff_share": strategy.bluff_share,
        "bet_share": strategy.bet_share,
    }
    try:
        ms = analyse_call(spot, rng, situation, strategy)
    except MultiStreetError as exc:
        ms = None
        multi = {"available": False, "note": str(exc), "strategy": strategy_out}
    else:
        multi = {
            "available": True,
            "note": None,
            "ev_call": ms.ev_call,
            "ev_showdown": ms.ev_showdown,
            "realized_equity": ms.realized_equity,
            "realization": ms.realization,
            "later_streets": ms.later_streets,
            "stats": ms.stats,
            "strategy": strategy_out,
            "elapsed_ms": round(ms.elapsed_s * 1000, 1),
        }

    if ms is not None:
        verdict, label = ("call", "Call") if ms.ev_call > 0 else ("fold", "Fold")
        basis, text = "multi_street", explain_multistreet(ms, strategy, profile.name)
    else:
        verdict, label = d.verdict.value, d.verdict.label
        basis, text = "showdown", explain(d)

    return {
        **_equity_fields(result),
        "decision": {
            "call": situation.call,
            "returned": situation.returned,
            "is_all_in": situation.is_all_in,
            "final_pot": situation.final_pot,
            "break_even_equity": situation.break_even_equity,
            "pot_odds": situation.pot_odds,
            "ev_fold": d.ev_fold,
            "ev_call": d.ev_call,
            "ev_call_ci95": list(d.ev_call_ci95),
            "margin": d.margin,
            "verdict": verdict,
            "verdict_label": label,
            "verdict_basis": basis,
            "explanation": text,
        },
        "multi_street": multi,
    }


# --- Single entry point for the browser ---------------------------------------------------

OPERATIONS: dict[str, Callable[..., Any]] = {
    "health": health,
    "cards": list_cards,
    "presets": list_presets,
    "validate_spot": validate_spot,
    "analyse_range": analyse_range,
    "equity": equity,
    "analyse": analyse,
}


def dispatch(operation: str, args_json: str = "{}") -> str:
    """Run an operation by name with JSON keyword arguments; return the result as JSON.

    Used by the in-browser (Pyodide) backend: JavaScript passes strings in and gets
    a string back, which avoids converting objects between the two languages.
    """
    fn = OPERATIONS.get(operation)
    if fn is None:
        return json.dumps({"valid": False, "error": f"Unknown operation {operation!r}."})
    try:
        kwargs = json.loads(args_json or "{}")
        return json.dumps(fn(**kwargs))
    except TypeError as exc:  # unexpected or missing arguments
        return json.dumps({"valid": False, "error": f"Bad arguments for {operation}: {exc}"})
