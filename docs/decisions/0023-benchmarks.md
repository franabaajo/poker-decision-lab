# 0023 — How benchmarks are run

**Status:** Accepted (2026-11-10)

## Options
- A small script that times reference vs vectorised code and prints a Markdown table.
- `pytest-benchmark`.

## Decision
The script: `uv run python benchmarks/run.py`. It reports the median of several runs and the speed-up, ready to paste into the README. No extra dependency.
