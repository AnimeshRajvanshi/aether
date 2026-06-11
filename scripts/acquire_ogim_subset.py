"""Acquire OGIM v2.7 and extract a committable per-event regional subset.

OGIM v2.7 is a single 3.08 GB GeoPackage on Zenodo — far too large to commit.
This script downloads it once into the gitignored cache, verifies its SHA-256,
and extracts every feature within an EVENT's regional bbox into a small,
committable GeoJSON FeatureCollection (+ provenance), so source attribution is
reproducible offline without re-downloading 3 GB.

Nothing is altered: features are copied verbatim (real attributes, real WGS84
geometry) from the OGIM GeoPackage.

Event-parameterized (Sprint 7 generality): the region bbox + output filenames
come from the EVENTS registry below — one shared code path, no per-event fork.

    uv run python scripts/acquire_ogim_subset.py [<event_id>]

defaulting to Goturdepe for back-compat. Goturdepe's committed outputs are
unchanged (same bbox, same filenames) so re-running it reproduces them verbatim.

Dataset: O'Brien, M., Omara, M., Himmelberger, A., & Gautam, R. (2025).
OGIM database (OGIM_v2.7). Zenodo. doi:10.5281/zenodo.15103476
Methods: Omara, M. et al. (2023). ESSD 15, 3761-3790. doi:10.5194/essd-15-3761-2023
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import shapely
from aether_causal.ogim import _gpb_to_geometry, feature_layers

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("~/.aether_cache/ogim").expanduser()
GPKG = CACHE / "OGIM_v2.7.gpkg"
OUT_DIR = REPO_ROOT / "packages" / "causal" / "aether_causal" / "resources" / "ogim"

ZENODO_URL = "https://zenodo.org/api/records/15103476/files/OGIM_v2.7.gpkg/content"
EXPECTED_SHA256 = "6025432af1fa748bb1306edfcecb6ea296de9f9946eec57395e8779be19bc365"


@dataclass(frozen=True)
class EventOGIM:
    """Per-event OGIM extraction config — region bbox + committed artifact names."""

    region_bbox: tuple[float, float, float, float]  # (min_lon, min_lat, max_lon, max_lat)
    subset_filename: str
    provenance_filename: str
    region_label: str


# One registry, no fork. Goturdepe keeps its EXACT original bbox + filenames so its
# committed artifacts are byte-reproducible and untouched.
EVENTS: dict[str, EventOGIM] = {
    "turkmenistan_goturdepe_2022_08_15": EventOGIM(
        region_bbox=(52.5, 38.5, 55.0, 40.0),
        subset_filename="ogim_v2.7_goturdepe_region.geojson",
        provenance_filename="provenance.json",
        region_label="Goturdepe-Barsagelmez producing area (38.5-40.0 N, 52.5-55.0 E)",
    ),
    # Permian / Carlsbad NM, EMIT 2022-08-26. Regional bbox = plume bbox buffered to
    # ~+/-0.30 deg (~28-33 km half-width) to cover the back-projection wedge search
    # radius (Goturdepe's was ~25 km). DENSE coverage: ~12k features expected.
    "permian_basin_2022": EventOGIM(
        region_bbox=(-104.45, 31.95, -103.85, 32.55),
        subset_filename="ogim_v2.7_permian_basin_region.geojson",
        provenance_filename="ogim_v2.7_permian_basin_region.provenance.json",
        region_label="Permian Basin / Carlsbad NM producing area (EMIT 2022-08-26)",
    ),
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    if GPKG.exists() and _sha256(GPKG) == EXPECTED_SHA256:
        print(f"OGIM already present and verified: {GPKG}")
        return
    print(f"Downloading OGIM v2.7 (~3 GB) -> {GPKG} ...")
    urllib.request.urlretrieve(ZENODO_URL, GPKG)  # trusted Zenodo URL
    digest = _sha256(GPKG)
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"SHA-256 mismatch: got {digest}, expected {EXPECTED_SHA256}")
    print("Download verified.")


def _rtree_ids(
    conn: sqlite3.Connection, table: str, geom: str, bbox: tuple[float, float, float, float]
) -> list[int] | None:
    rtree = f"rtree_{table}_{geom}"
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (rtree,)
    ).fetchone():
        return None
    mnlon, mnlat, mxlon, mxlat = bbox
    return [
        r[0]
        for r in conn.execute(
            f'SELECT id FROM "{rtree}" WHERE minx<=? AND maxx>=? AND miny<=? AND maxy>=?',
            (mxlon, mnlon, mxlat, mnlat),
        ).fetchall()
    ]


def _extract(region_bbox: tuple[float, float, float, float]) -> dict[str, object]:
    conn = sqlite3.connect(f"file:{GPKG}?mode=ro", uri=True)
    features: list[dict[str, object]] = []
    per_layer: dict[str, int] = {}
    try:
        for table, geom_col, srs in feature_layers(conn):
            if srs != 4326:
                continue  # only WGS84 spatial layers (Data_Catalog is non-spatial)
            ids = _rtree_ids(conn, table, geom_col, region_bbox)
            if ids is not None and not ids:
                continue
            cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
            attr_cols = [c for c in cols if c != geom_col]
            select = ", ".join(f'"{c}"' for c in [*attr_cols, geom_col])
            if ids is not None:
                ph = ",".join("?" * len(ids))
                rows = conn.execute(
                    f'SELECT {select} FROM "{table}" WHERE "{cols[0]}" IN ({ph})', ids
                ).fetchall()
            else:
                rows = conn.execute(f'SELECT {select} FROM "{table}"').fetchall()
            count = 0
            for row in rows:
                attrs = dict(zip(attr_cols, row[: len(attr_cols)], strict=True))
                blob = row[len(attr_cols)]
                if blob is None:
                    continue
                geom = _gpb_to_geometry(blob)
                # honest bbox filter on the actual geometry envelope
                gminx, gminy, gmaxx, gmaxy = geom.bounds
                if (
                    gmaxx < region_bbox[0]
                    or gminx > region_bbox[2]
                    or gmaxy < region_bbox[1]
                    or gminy > region_bbox[3]
                ):
                    continue
                features.append(
                    {
                        "type": "Feature",
                        "properties": {"ogim_layer": table, **attrs},
                        "geometry": shapely.geometry.mapping(geom),
                    }
                )
                count += 1
            if count:
                per_layer[table] = count
    finally:
        conn.close()
    return {
        "type": "FeatureCollection",
        "features": features,
        "_per_layer": per_layer,
    }


def main() -> int:
    event_id = sys.argv[1] if len(sys.argv) > 1 else "turkmenistan_goturdepe_2022_08_15"
    if event_id not in EVENTS:
        raise SystemExit(f"unknown event_id {event_id!r}; known: {sorted(EVENTS)}")
    cfg = EVENTS[event_id]

    _download()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fc = _extract(cfg.region_bbox)
    per_layer = fc.pop("_per_layer")
    n = len(fc["features"])  # type: ignore[arg-type]

    subset_path = OUT_DIR / cfg.subset_filename
    subset_path.write_text(json.dumps(fc, ensure_ascii=False, default=str))

    provenance = {
        "dataset": "OGIM_v2.7 (Oil and Gas Infrastructure Mapping database)",
        "doi": "10.5281/zenodo.15103476",
        "methods_doi": "10.5194/essd-15-3761-2023",
        "source_url": ZENODO_URL,
        "source_sha256": EXPECTED_SHA256,
        "event_id": event_id,
        "region_label": cfg.region_label,
        "region_bbox_min_lon_min_lat_max_lon_max_lat": list(cfg.region_bbox),
        "crs": "EPSG:4326",
        "total_features_in_subset": n,
        "features_per_layer": per_layer,
        "geometry_note": "Features copied verbatim from OGIM; full geometry retained.",
        "license": "OGIM is public-domain (EDF/MethaneSAT).",
    }
    (OUT_DIR / cfg.provenance_filename).write_text(json.dumps(provenance, indent=2))

    print(f"[{event_id}] {cfg.region_label}")
    print(f"Wrote {subset_path.relative_to(REPO_ROOT)}  ({n} features)")
    for layer, c in sorted(per_layer.items()):
        print(f"  {layer:40s} {c:>6}")
    print(f"Wrote {(OUT_DIR / cfg.provenance_filename).relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
