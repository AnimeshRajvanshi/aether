# Aether API container (Sprint 10 Stage B item 8).
#
# Multi-stage, digest-pinned, no credentials at any layer. The image bakes the
# committed artifact tree from the build checkout and the git SHA as a build
# arg (AETHER_GIT_SHA -> /api/version). Runtime config (AETHER_ALLOWED_ORIGINS)
# comes from platform env vars — startup fails loudly without it, by design.
#
#   docker build -t aether-api --build-arg GIT_SHA=$(git rev-parse HEAD) .
#   docker run -p 8080:8080 -e AETHER_ALLOWED_ORIGINS=https://aether.arkaneworks.co aether-api

# ---------------------------------------------------------------------------
# Builder: resolve ONLY aether-api's dependency closure from the frozen lock.
# The F1 split keeps the heavy scientific stack (scipy/rasterio/pandas) out —
# it lives behind the aether-eval[pipeline] extra, which the API never imports.
# ---------------------------------------------------------------------------
FROM python:3.12-slim@sha256:a39549e211a16149edf74e5fdc9ef03a6767e46cd987c5048b6659b6c9904c94 AS builder
COPY --from=ghcr.io/astral-sh/uv@sha256:03bdc89bb9798628846e60c3a9ad19006c8c3c724ccd2985a33145c039a0577b /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY eval/harness/ eval/harness/
COPY apps/api/ apps/api/
RUN uv sync --frozen --no-dev --no-editable --package aether-api

# ---------------------------------------------------------------------------
# Runtime: slim base + the venv + the committed artifact tree. Non-root.
# ---------------------------------------------------------------------------
FROM python:3.12-slim@sha256:a39549e211a16149edf74e5fdc9ef03a6767e46cd987c5048b6659b6c9904c94

ARG GIT_SHA
# AETHER_ENV=production makes missing runtime config a loud startup crash.
ENV AETHER_ENV=production \
    AETHER_GIT_SHA=${GIT_SHA} \
    AETHER_DATA_ROOT=/app/data \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv

# The committed files the composed endpoints read (raw assets ship inside the
# aether_api wheel). Same trees the suite verifies; nothing else.
COPY stage_a_outputs/ /app/data/stage_a_outputs/
COPY stage_b_outputs/ /app/data/stage_b_outputs/
COPY attribution_outputs/ /app/data/attribution_outputs/
COPY eval/benchmark/ /app/data/eval/benchmark/
COPY artifacts.manifest.json /app/data/artifacts.manifest.json

RUN useradd --create-home aether
USER aether

EXPOSE 8080
CMD ["uvicorn", "aether_api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-server-header"]
