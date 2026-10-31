# Single container: FastAPI serves both the JSON API and the static frontend.
# Hugging Face Spaces (Docker SDK) expects the app on port 7860 and runs as UID 1000.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

RUN useradd --create-home --uid 1000 user
USER user
WORKDIR /home/user/app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/home/user/app/.venv/bin:$PATH"

# Install dependencies first (cached layer), then the project itself.
COPY --chown=user pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=user src ./src
COPY --chown=user app ./app
RUN uv sync --frozen --no-dev

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
