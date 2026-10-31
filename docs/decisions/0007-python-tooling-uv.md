# 0007 — Python tooling: uv

**Status:** Accepted (2026-10-31)

## Options
- `pip` + `venv` (+ `requirements.txt`).
- `uv`: one tool for Python installs, virtual environments, dependencies and a lockfile.

## Decision
Python 3.12 managed with `uv`; `ruff` for linting and formatting; `pytest` for tests.

## Consequences
- `uv.lock` pins every transitive dependency, so laptop, CI and deployment run identical versions.
- `pyproject.toml` remains standard, so `pip install -e .` still works.
- Daily commands: `uv sync`, `uv add <pkg>`, `uv run pytest`.
