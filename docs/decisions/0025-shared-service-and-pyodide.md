# 0025 — One service layer, two runtimes (server and browser)

**Status:** Accepted (2026-11-12)

## Decision
- `pokerlab/service.py` exposes the app's operations as JSON-in / JSON-out functions. FastAPI endpoints validate input with Pydantic and call it; `service.dispatch(operation, json)` is the single entry point for the browser.
- In the browser, a Web Worker (`app/static/js/pyworker.js`) loads Pyodide and NumPy from the jsDelivr CDN, unpacks `pokerlab.zip` and calls `dispatch`. The worker keeps the page responsive during calculations.
- `app/static/js/api.js` detects the mode once: if `api/health` answers JSON it uses the server, otherwise the in-browser engine.
- Asset paths are relative, so the same frontend works at `/` (FastAPI) and under `/poker-decision-lab/` (GitHub Pages).

## Verification
- `tests/test_service.py` exercises every operation through the JSON entry point.
- CI job `browser-engine` loads the built `pokerlab.zip` into Pyodide under Node.js and checks real results, including a golden value from the reference engine.

## Consequences
The demo and the local app run the same tested code. Pyodide's version is pinned in two places (`pyworker.js`, CI) and must be updated together.
