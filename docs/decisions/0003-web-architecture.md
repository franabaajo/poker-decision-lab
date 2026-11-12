# 0003 — Web architecture and hosting

**Status:** Accepted (2026-10-31); hosting part superseded by [ADR 0024](0024-hosting-github-pages.md)

## Options
- **Streamlit** (Community Cloud): fastest, Python-only, generic look, awkward card picker.
- **FastAPI + custom frontend** in one Docker container on Hugging Face Spaces (free CPU Basic: 2 vCPU, 16 GB RAM; sleeps after 48 h without visits, wakes on the next visit).
- Render free tier was considered but spins down after 15 minutes idle, giving demo visitors frequent cold starts.

## Decision
FastAPI + custom frontend on Hugging Face Spaces.

## Consequences
- The engine (`src/pokerlab`) is pure Python and never imports the web layer (`app/`); a test enforces this.
- The API is a clear contract that notebooks or other clients can also use.
