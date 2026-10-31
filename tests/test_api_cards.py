"""M1 API tests: deck listing and spot validation."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_cards_endpoint_returns_full_deck_in_engine_order():
    cards = client.get("/api/cards").json()
    assert len(cards) == 52
    assert [c["id"] for c in cards] == list(range(52))
    assert cards[51] == {
        "id": 51,
        "code": "As",
        "pretty": "A♠",
        "name": "ace of spades",
        "rank": "A",
        "suit": "s",
    }


def validate(hero, board=()):
    response = client.post("/api/spot/validate", json={"hero": list(hero), "board": list(board)})
    assert response.status_code == 200
    return response.json()


def test_valid_flop_spot():
    result = validate(["As", "Qs"], ["Js", "8d", "4s"])
    assert result["valid"] is True
    assert result["street"] == "Flop"
    assert result["error"] is None


def test_board_defaults_to_preflop():
    response = client.post("/api/spot/validate", json={"hero": ["As", "Qs"]})
    assert response.json()["street"] == "Preflop"


def test_input_is_normalised():
    result = validate(["a♠", "10h"])
    assert result["hero"] == ["As", "Th"]


def test_duplicate_is_reported_not_raised():
    result = validate(["As", "Qs"], ["As", "8d", "4s"])
    assert result["valid"] is False
    assert "As" in result["error"]


def test_bad_card_text():
    result = validate(["As", "Xx"])
    assert result["valid"] is False
    assert "not a card" in result["error"]


def test_wrong_board_size():
    result = validate(["As", "Qs"], ["Js", "8d"])
    assert result["valid"] is False
    assert "0, 3, 4 or 5" in result["error"]


def test_malformed_body_is_422():
    assert client.post("/api/spot/validate", json={"board": []}).status_code == 422
