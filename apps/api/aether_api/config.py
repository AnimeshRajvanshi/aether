"""Filesystem layout + deploy-varying environment config for the dashboard API.

Resolves the repo data root (overridable via ``AETHER_DATA_ROOT`` for tests /
alternate deployments) and the per-event paths to committed Stage A/B outputs,
benchmark YAMLs, and the derived raster assets.

Deploy-varying config (Sprint 10 Stage B) comes ONLY from environment
variables, documented in ``.env.example`` and ``docs/deployment.md``. Missing
required production config fails loudly at startup — never a silent default
that "works" wrong.
"""

from __future__ import annotations

import os
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised at startup when deploy config is missing or invalid."""


# Development fallback origins (``next dev`` on :3000 against uvicorn on :8000).
_DEV_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def environment() -> str:
    """Deployment environment: 'development' (default) or 'production'."""
    env = os.environ.get("AETHER_ENV", "development").strip().lower()
    if env not in {"development", "production"}:
        raise ConfigError(
            f"AETHER_ENV must be 'development' or 'production', got {env!r}. "
            "See docs/deployment.md."
        )
    return env


def allowed_origins() -> list[str]:
    """Exact CORS origins from AETHER_ALLOWED_ORIGINS (comma-separated).

    Production REQUIRES the variable (loud failure, not a silent localhost
    default). Wildcards are rejected structurally — the guard suite asserts a
    production app refuses a foreign origin, and '*' would make that test lie.
    """
    raw = os.environ.get("AETHER_ALLOWED_ORIGINS")
    if raw is None or not raw.strip():
        if environment() == "production":
            raise ConfigError(
                "AETHER_ALLOWED_ORIGINS is required when AETHER_ENV=production "
                "(comma-separated exact origins, e.g. "
                "'https://aether.arkaneworks.co'). Refusing to start with an "
                "implicit CORS policy. See docs/deployment.md."
            )
        return list(_DEV_ORIGINS)
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    for origin in origins:
        if "*" in origin:
            raise ConfigError(
                f"Wildcard origin {origin!r} is not allowed in "
                "AETHER_ALLOWED_ORIGINS — list exact origins."
            )
        if not origin.startswith(("http://", "https://")) or origin.rstrip("/") != origin:
            raise ConfigError(
                f"Origin {origin!r} must be a bare scheme://host[:port] origin "
                "(no trailing slash, no path)."
            )
    return origins


def git_sha() -> str:
    """The git SHA baked at build time (Docker build arg → AETHER_GIT_SHA).

    Never a runtime ``git`` call. Production requires it (the /api/version
    endpoint and the UI footer are the deployed-integrity anchor — an unknown
    SHA there would be fake liveness); development honestly reports 'dev'.
    """
    sha = os.environ.get("AETHER_GIT_SHA", "").strip()
    if not sha:
        if environment() == "production":
            raise ConfigError(
                "AETHER_GIT_SHA is required when AETHER_ENV=production — it is "
                "baked as a Docker build arg (see Dockerfile / docs/deployment.md)."
            )
        return "dev"
    return sha

# This file lives at apps/api/aether_api/config.py -> repo root is three up.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Raster assets are committed inside the package so they ship with the API.
ASSETS_ROOT = Path(__file__).resolve().parent / "assets"


def data_root() -> Path:
    """Root holding stage_a_outputs/, stage_b_outputs/, eval/benchmark/."""
    override = os.environ.get("AETHER_DATA_ROOT")
    return Path(override).resolve() if override else _REPO_ROOT


def stage_a_dir(event_id: str) -> Path:
    return data_root() / "stage_a_outputs" / event_id


def stage_b_dir(event_id: str) -> Path:
    return data_root() / "stage_b_outputs" / event_id


def benchmark_yaml(event_id: str) -> Path:
    return data_root() / "eval" / "benchmark" / f"{event_id}.yaml"


def hypotheses_json(event_id: str) -> Path:
    """Committed Sprint 4 attribution artifact for an event (may not exist)."""
    return data_root() / "attribution_outputs" / event_id / "hypotheses.json"


def assets_dir(event_id: str) -> Path:
    return ASSETS_ROOT / event_id
