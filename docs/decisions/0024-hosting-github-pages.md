# 0024 — Host the live demo on GitHub Pages

**Status:** Accepted (2026-11-12). Supersedes the hosting part of ADR 0003.

## Context
ADR 0003 chose a Docker Space on Hugging Face. By November 2026 Hugging Face's documentation
states that creating a Space that runs on compute (Gradio or Docker) requires a paid plan;
only static Spaces remain free.

## Options
- **Render free tier:** runs the existing Docker image, but 0.1 CPU / 512 MB, and it spins down after 15 minutes idle with about a minute to wake up.
- **Netlify:** static hosting only; it cannot run Python after the build.
- **Paid hosting:** e.g. an always-on Render instance or a paid Hugging Face plan.
- **Static site with the engine running in the browser** (Pyodide), on GitHub Pages.

## Decision
The static site on GitHub Pages, built by `scripts/build_site.py` and deployed by
`.github/workflows/pages.yml` after CI passes.

## Consequences
- Free, always available, no cold start (the first visit downloads Python and NumPy, about 10–20 s; later visits use the browser cache).
- Calculations run on the visitor's machine.
- The FastAPI server and the Dockerfile remain for local use and self-hosting.
