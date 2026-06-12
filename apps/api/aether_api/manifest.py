"""Integrity manifest for deployment (Sprint 10 Stage B item 6).

The manifest is the CONTRACT the Stage D deployed-integrity verifier checks
against: SHA-256 of every served committed artifact, keyed by serving path.
It lives in the package (not in scripts/) so the generator script, the
staleness guard test, and the Stage D verifier all share one enumeration —
three consumers of one truth, never three route lists drifting apart.

Two endpoint classes (Stage A §4):
- ``raw_endpoints``      stream a single committed file; the verifier holds
                         them to BYTE-IDENTITY (hash of the transport-decoded
                         response body == the manifest hash).
- ``composed_endpoints`` re-serialize multiple committed sources; the verifier
                         holds them to DEEP-EQUALITY against those sources at
                         the pinned SHA. The manifest records each source
                         file's hash so drift in any input is detectable.

``generated_at_commit`` is provenance (which tree generated this manifest),
NOT the verifier's pin — Stage D pins via /api/version. The staleness guard
compares the endpoint tables only, so regenerating at a new commit with
unchanged artifacts is not a spurious diff.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from . import config, loaders

MANIFEST_FILENAME = "artifacts.manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    """Path relative to the data root (== repo root in a checkout/image)."""
    return str(path.resolve().relative_to(config.data_root().resolve()))


def _file_entry(path: Path) -> dict[str, Any]:
    return {"source": _rel(path), "sha256": _sha256(path), "bytes": path.stat().st_size}


def _event_composed_sources(event_id: str) -> list[Path]:
    """Every committed file the composed detail/summary payloads read from.

    Mirrors loaders.py: q_estimate/air_lane gate activation; stage_a_report,
    diagnostics, k-provenance, validation/lst/uhi, the benchmark YAML and
    bounds.json feed the EventDetail/EventSummary composition.
    """
    stage_a = config.stage_a_dir(event_id)
    stage_b = config.stage_b_dir(event_id)
    candidates = [
        stage_b / "q_estimate.json",
        stage_b / "diagnostics.json",
        stage_b / "air_lane.json",
        stage_b / "validation.json",
        stage_b / "lst_lane.json",
        stage_b / "uhi.json",
        stage_a / "stage_a_report.json",
        stage_a / "hitran_k" / "hitran_k_sat_provenance.json",
        config.benchmark_yaml(event_id),
        config.assets_dir(event_id) / "bounds.json",
    ]
    return [p for p in candidates if p.exists()]


def raw_endpoint_files() -> dict[str, Path]:
    """Serving path -> committed file, for every raw-streaming endpoint."""
    mapping: dict[str, Path] = {}
    for event_id in loaders.EVENT_IDS:
        adir = config.assets_dir(event_id)
        for url, path in [
            (f"/api/events/{event_id}/enhancement.png", adir / "enhancement.png"),
            (f"/api/events/{event_id}/nasa.png", adir / "nasa.png"),
            (f"/api/events/{event_id}/diff.png", adir / "diff.png"),
            (f"/api/events/{event_id}/bounds", adir / "bounds.json"),
            (f"/api/events/{event_id}/mask.geojson", adir / "mask.geojson"),
        ]:
            if path.exists():
                mapping[url] = path
        bounds_path = adir / "bounds.json"
        if bounds_path.exists():
            for layer in json.loads(bounds_path.read_text()).get("layers", []):
                layer_file = adir / f"{layer}.png"
                if layer_file.exists():
                    mapping[f"/api/events/{event_id}/layers/{layer}.png"] = layer_file
        hypotheses = loaders.hypotheses_path(event_id)
        if hypotheses is not None:
            mapping[f"/api/events/{event_id}/hypotheses"] = hypotheses
        factors = loaders.factor_hypotheses_path(event_id)
        if factors is not None:
            mapping[f"/api/events/{event_id}/factor-hypotheses"] = factors
    return mapping


def build_manifest() -> dict[str, Any]:
    """Deterministic manifest dict (sorted keys; no timestamps)."""
    raw = {url: _file_entry(path) for url, path in sorted(raw_endpoint_files().items())}

    composed: dict[str, Any] = {}
    all_sources: dict[str, Path] = {}
    for event_id in loaders.EVENT_IDS:
        sources = _event_composed_sources(event_id)
        composed[f"/api/events/{event_id}"] = {"sources": sorted(_rel(p) for p in sources)}
        for p in sources:
            all_sources[_rel(p)] = p
    composed["/api/events"] = {"sources": sorted(all_sources)}

    return {
        "generated_at_commit": _git_head(),
        "raw_endpoints": raw,
        "composed_endpoints": composed,
        "composed_sources": {
            rel: {"sha256": _sha256(p), "bytes": p.stat().st_size}
            for rel, p in sorted(all_sources.items())
        },
    }


def _git_head() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=config.data_root(),
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def render(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def manifest_path() -> Path:
    return config.data_root() / MANIFEST_FILENAME
