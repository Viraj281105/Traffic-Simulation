# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.11.16-slim-bookworm AS builder

WORKDIR /app

# Install dependencies first (layer caching)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Runtime base: interpreter, dependencies, user, entrypoint ───────────────
# Shared by the production image (default, last stage) and the development
# image (target "dev"), which runs the same runtime on bind-mounted source.
FROM python:3.11.16-slim-bookworm AS base

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set PYTHONPATH so `src.*` imports resolve correctly
ENV PYTHONPATH=/app

# Create the non-root user the app actually runs as. /app is owned by it so
# a *fresh* named volume mounted at /app/data (docker-compose.yml) is
# correctly seeded with that ownership by Docker on first creation. The
# container still starts as root (no USER switch here) because a volume
# reused from an older, root-based build of this image keeps its existing
# root ownership across restarts — docker-entrypoint.py fixes that, then
# permanently drops to appuser before the real process ever runs, so the
# application itself is still never root either way.
RUN useradd --system --create-home --home-dir /home/appuser --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

COPY backend/docker-entrypoint.py /docker-entrypoint.py

EXPOSE 8000

# Health check — hits the /health endpoint every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["python", "/docker-entrypoint.py"]

# ── Development (docker-compose.dev.yml, start.ps1 -Dev) ─────────────────────
# No source in the image: backend/src and shared are bind-mounted, and uvicorn
# reloads on change, so editing code never rebuilds this image.
FROM base AS dev
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "src"]

# ── Production (default target) ──────────────────────────────────────────────
FROM base AS production

# Copy source code and schemas
COPY --chown=appuser:appuser backend/src/ ./src/
COPY --chown=appuser:appuser shared/ ./shared/

# Code version recorded with every saved run (src/core/provenance.py). The
# build context excludes .git, so the commit is passed in instead, e.g.
# `GIT_COMMIT=$(git rev-parse HEAD) docker compose build`. Empty (the
# default) records "unknown" rather than a guess. Declared after the source
# COPY so it only invalidates the layers below.
ARG GIT_COMMIT=""
ENV GIT_COMMIT=${GIT_COMMIT}
LABEL org.opencontainers.image.revision=${GIT_COMMIT}

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
