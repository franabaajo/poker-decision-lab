"""M0 smoke tests: the package imports and the web app serves its API and frontend."""

from fastapi.testclient import TestClient

import pokerlab
from app.main import app

client = TestClient(app)


def test_package_has_version():
    assert isinstance(pokerlab.__version__, str)
    assert pokerlab.__version__.count(".") == 2


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": pokerlab.__version__}


def test_frontend_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Poker Decision Lab" in response.text


def test_engine_does_not_import_web_layer():
    """Architecture rule: pokerlab must stay independent of FastAPI/the app package."""
    import pathlib

    src = pathlib.Path(pokerlab.__file__).parent
    for path in src.rglob("*.py"):
        text = path.read_text()
        assert "import fastapi" not in text and "from fastapi" not in text, path
        assert "from app" not in text and "import app" not in text, path
