"""M4 API tests: equity endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def post(**body):
    response = client.post("/api/equity", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_exact_on_the_turn():
    r = post(hero=["As", "Qs"], board=["Js", "8d", "4s", "2c"], range_notation="TT+")
    assert r["valid"] is True
    assert r["method"] == "exact"
    assert r["std_error"] == 0
    assert r["win"] + r["tie"] + r["lose"] == pytest.approx(1)
    assert r["equity"] == pytest.approx(r["win"] + r["tie"] / 2)
    assert sum(c["share"] for c in r["by_class"]) == pytest.approx(1)


def test_monte_carlo_preflop_is_reproducible_with_seed():
    body = dict(hero=["As", "Ah"], range_notation="KK", samples=2_000, seed=5)
    a, b = post(**body), post(**body)
    assert a["method"] == "monte_carlo"
    assert a["equity"] == b["equity"] and a["seed"] == 5
    lo, hi = a["ci95"]
    assert lo < a["equity"] < hi


def test_range_weights_from_the_grid():
    r = post(hero=["As", "Qs"], board=["Js", "8d", "4s", "2c"], range_weights={"KK": 1})
    assert r["valid"] and r["live_combos"] == 6


@pytest.mark.parametrize(
    "body",
    [
        dict(hero=["As", "As"], range_notation="KK"),  # duplicate
        dict(hero=["As", "Ah"], board=["Ad", "Ac", "2s"], range_notation="AA"),  # empty range
        dict(hero=["As", "Qs"], range_notation="AKx"),  # bad notation
        dict(hero=["As", "Qs"], range_notation="KK", method="exact"),  # exact preflop
    ],
)
def test_errors_are_reported(body):
    r = post(**body)
    assert r["valid"] is False and r["error"]


def test_sample_limits_are_enforced():
    response = client.post(
        "/api/equity", json=dict(hero=["As", "Qs"], range_notation="KK", samples=10)
    )
    assert response.status_code == 422
