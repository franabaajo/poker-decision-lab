"""FastAPI application: JSON API under /api, static frontend at /.

Run locally with:
    uv run uvicorn app.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import pokerlab

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Poker Decision Lab",
    version=pokerlab.__version__,
    description="Educational call/fold analysis for heads-up Texas Hold'em. Not a gambling tool.",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness check used by the frontend, tests and the deployment platform."""
    return {"status": "ok", "version": pokerlab.__version__}


# Mounted last so that /api/* routes take precedence over static files.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
