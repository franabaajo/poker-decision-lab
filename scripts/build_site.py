"""Build the static website (GitHub Pages) into ./site (ADR 0024, 0025).

The site is the normal frontend (app/static) plus pokerlab.zip, the Python engine,
which the page runs in the visitor's browser with Pyodide. No server is needed.

    uv run python scripts/build_site.py
    uv run python -m http.server 8001 -d site     # preview at http://localhost:8001
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
PACKAGE = ROOT / "src" / "pokerlab"
SITE = ROOT / "site"

# Reference implementations are only needed for tests and benchmarks.
EXCLUDE_DIRS = {"__pycache__", "reference"}


def build() -> Path:
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(STATIC, SITE)
    (SITE / ".nojekyll").touch()  # serve files as-is on GitHub Pages

    archive = SITE / "pokerlab.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(PACKAGE.rglob("*.py")):
            rel = path.relative_to(PACKAGE.parent)
            if EXCLUDE_DIRS & set(rel.parts):
                continue
            zf.write(path, rel.as_posix())
    files = sum(1 for p in SITE.rglob("*") if p.is_file())
    print(f"Built {SITE} ({files} files, pokerlab.zip {archive.stat().st_size / 1024:.0f} KB)")
    return SITE


if __name__ == "__main__":
    build()
