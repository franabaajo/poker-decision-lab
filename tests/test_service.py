"""M8: the service layer shared by the FastAPI server and the in-browser (Pyodide) app."""

import json

import pytest

from pokerlab import service

TURN = dict(hero=["As", "Qs"], board=["Js", "8d", "4s", "2c"], range_notation="TT+, AJs+")


def call(operation, **kwargs):
    """Go through the same JSON entry point the browser uses."""
    return json.loads(service.dispatch(operation, json.dumps(kwargs)))


def test_every_operation_is_json_serialisable():
    assert call("health")["status"] == "ok"
    assert len(call("cards")) == 52
    assert [p["key"] for p in call("presets")] == ["tight", "balanced", "aggressive"]
    assert call("validate_spot", hero=["As", "Qs"])["street"] == "Preflop"
    assert call("analyse_range", notation="AA", hero=["As"])["live_combos"] == 3
    assert call("equity", **TURN)["method"] == "exact"
    result = call("analyse", **TURN, pot=100, bet=50, stack=500, style="tight")
    assert result["decision"]["verdict_basis"] == "multi_street"
    assert result["multi_street"]["strategy"]["key"] == "tight"


def test_analyse_matches_its_parts():
    full = call("analyse", **TURN, pot=100, bet=50, stack=500)
    eq = call("equity", **TURN)
    assert full["equity"] == pytest.approx(eq["equity"])
    assert full["decision"]["ev_call"] == pytest.approx(eq["equity"] * 200 - 50)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (dict(method="magic"), "Unknown method"),
        (dict(samples=10), "Samples must be"),
        (dict(seed=-1), "seed"),
        (dict(style="wild"), "Unknown style"),
        (dict(bet=0), "bet must be more than 0"),
        (dict(hero=["As", "As"]), "more than once"),
        (dict(range_notation="AKx"), "Could not read"),
    ],
)
def test_invalid_requests_are_reported(kwargs, message):
    body = {**TURN, "pot": 100, "bet": 50, "stack": 500, **kwargs}
    result = call("analyse", **body)
    assert result["valid"] is False
    assert message in result["error"]
    assert result["decision"] is None


def test_unknown_operation_and_bad_arguments():
    assert "Unknown operation" in call("nope")["error"]
    assert "Bad arguments" in call("equity", foo=1)["error"]


def test_monte_carlo_seed_round_trip():
    a = call("equity", hero=["As", "Ah"], range_notation="KK", samples=2_000, seed=9)
    b = call("equity", hero=["As", "Ah"], range_notation="KK", samples=2_000, seed=9)
    assert a["method"] == "monte_carlo" and a["seed"] == 9
    assert a["equity"] == b["equity"]
