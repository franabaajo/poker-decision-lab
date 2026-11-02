"""M3 API tests: presets and range analysis."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_presets():
    presets = client.get("/api/ranges/presets").json()
    assert [p["key"] for p in presets] == ["tight", "balanced", "aggressive"]
    assert all(0 < p["percent"] < 100 for p in presets)


def analyse(**body):
    response = client.post("/api/ranges/analyse", json=body)
    assert response.status_code == 200
    return response.json()


def test_analyse_notation():
    result = analyse(notation="AA, AKs:0.5")
    assert result["valid"] is True
    assert result["notation"] == "AA, AKs:0.5"
    assert result["combos"] == 8
    assert len(result["grid"]) == 169
    assert result["grid"][0] == {"label": "AA", "weight": 1.0, "combos": 6, "live": 6}


def test_analyse_weights_from_grid_gives_compact_notation():
    result = analyse(weights={"AKs": 1, "AQs": 1, "AJs": 1, "ATs": 1})
    assert result["notation"] == "ATs+"


def test_card_removal():
    result = analyse(notation="AA", hero=["As", "Qs"], board=["Js", "8d", "4s"])
    assert result["combos"] == 6
    assert result["live_combos"] == 3
    aa = result["grid"][0]
    assert aa["live"] == 3


def test_errors_are_reported():
    result = analyse(notation="AKx")
    assert result["valid"] is False
    assert "AKx" in result["error"]
    assert analyse(weights={"ZZ": 1})["valid"] is False
    assert analyse(notation="AA", hero=["Xx"])["valid"] is False
