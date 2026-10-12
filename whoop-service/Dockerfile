# Pinned to a digest, not a floating tag, so a rebuild can't silently change the base image.
FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS builder

RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY core ./core
COPY services ./services
COPY api ./api
COPY workers ./workers
COPY alembic ./alembic
COPY alembic.ini ./

FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS runtime
# Pull Debian security fixes published after the digest was pinned; the image scan fails on fixable HIGH/CRITICAL CVEs.
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --shell /bin/false appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
