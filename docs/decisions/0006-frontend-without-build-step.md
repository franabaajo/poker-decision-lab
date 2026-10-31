# 0006 — Frontend without a build step

**Status:** Accepted (2026-10-31)

## Options
- Plain HTML/CSS/JavaScript (ES modules) served by FastAPI.
- React + TypeScript with Vite.

## Decision
Plain HTML/CSS/JS. No Node toolchain, simpler to debug and deploy, and the Python engine stays the centre of the project.

## Consequences
UI state is handled manually in small modules; if the UI grows a lot, migrating to a framework remains possible because the API is unchanged.
