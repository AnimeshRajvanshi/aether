"""Filesystem layout for the dashboard API.

Resolves the repo data root (overridable via ``AETHER_DATA_ROOT`` for tests /
alternate deployments) and the per-event paths to committed Stage A/B outputs,
benchmark YAMLs, and the derived raster assets.
"""

from __future__ import annotations

import os
from pathlib import Path

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
