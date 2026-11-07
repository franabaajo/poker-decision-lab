"""M5 API tests: full analysis (equity + decision)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TURN = dict(hero=["As", "Qs"], board=["Js", "8d", "4s", "2c"], range_notation="TT+, AJs+")


def post(**body):
    response = client.post("/api/analyse", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_full_analysis():
    r = post(**TURN, pot=100, bet=50, stack=500)
    assert r["valid"] is True
    d = r["decision"]
    assert d["call"] == 50 and d["final_pot"] == 200
    assert d["break_even_equity"] == pytest.approx(0.25)
    assert d["pot_odds"] == pytest.approx(3)
    assert d["ev_call"] == pytest.approx(r["equity"] * 200 - 50)
    assert d["verdict"] in {"call", "fold", "close"}
    assert "200 chips" in d["explanation"]
    assert d["is_all_in"] is False


def test_all_in_bet_is_capped_by_stack():
    d = post(**TURN, pot=100, bet=300, stack=200)["decision"]
    assert d["call"] == 200 and d["returned"] == 100 and d["is_all_in"] is True


def test_invalid_amounts_rejected_by_schema():
    response = client.post("/api/analyse", json=dict(**TURN, pot=100, bet=0, stack=500))
    assert response.status_code == 422


def test_equity_errors_still_reported():
    r = post(
        hero=["As", "Ah"], board=["Ad", "Ac", "2s"], range_notation="AA", pot=10, bet=5, stack=50
    )
    assert r["valid"] is False and r["decision"] is None
