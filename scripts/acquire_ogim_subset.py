"""Acquire OGIM v2.7 and extract the committable Goturdepe regional subset.

OGIM v2.7 is a single 3.08 GB GeoPackage on Zenodo — far too large to commit.
This script downloads it once into the gitignored cache, verifies its SHA-256,
and extracts every feature within the event's regional bbox into a small,
committable GeoJSON FeatureCollection (+ provenance), so source attribution is
reproducible offline without re-downloading 3 GB.

Nothing is altered: features are copied verbatim (real attributes, real WGS84
geometry) from the OGIM GeoPackage.

Dataset: O'Brien, M., Omara, M., Himmelberger, A., & Gautam, R. (2025).
OGIM database (OGIM_v2.7). Zenodo. doi:10.5281/zenodo.15103476
Methods: Omara, M. et al. (2023). ESSD 15, 3761-3790. doi:10.5194/essd-15-3761-2023

Run from the repo root:  uv run python scripts/acquire_ogim_subset.py
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.request
from pathlib import Path

import shapely
from aether_causal.ogim import _gpb_to_geometry, feature_layers

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("~/.aether_cache/ogim").expanduser()
GPKG = CACHE / "OGIM_v2.7.gpkg"
OUT_DIR = REPO_ROOT / "packages" / "causal" / "aether_causal" / "resources" / "ogim"

ZENODO_URL = "https://zenodo.org/api/records/15103476/files/OGIM_v2.7.gpkg/content"
EXPECTED_SHA256 = "6025432af1fa748bb1306edfcecb6ea296de9f9946eec57395e8779be19bc365"

# Regional subset bbox (min_lon, min_lat, max_lon, max_lat) per the task brief
# (38.5-40.0 N, 52.5-55.0 E) covering the Goturdepe-Barsagelmez producing area.
REGION_BBOX = (52.5, 38.5, 55.0, 40.0)


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


def _extract() -> dict[str, object]:
    conn = sqlite3.connect(f"file:{GPKG}?mode=ro", uri=True)
    features: list[dict[str, object]] = []
    per_layer: dict[str, int] = {}
    try:
        for table, geom_col, srs in feature_layers(conn):
            if srs != 4326:
                continue  # only WGS84 spatial layers (Data_Catalog is non-spatial)
            ids = _rtree_ids(conn, table, geom_col, REGION_BBOX)
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
                    gmaxx < REGION_BBOX[0]
                    or gminx > REGION_BBOX[2]
                    or gmaxy < REGION_BBOX[1]
                    or gminy > REGION_BBOX[3]
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
    _download()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fc = _extract()
    per_layer = fc.pop("_per_layer")
    n = len(fc["features"])  # type: ignore[arg-type]

    subset_path = OUT_DIR / "ogim_v2.7_goturdepe_region.geojson"
    subset_path.write_text(json.dumps(fc, ensure_ascii=False, default=str))

    provenance = {
        "dataset": "OGIM_v2.7 (Oil and Gas Infrastructure Mapping database)",
        "doi": "10.5281/zenodo.15103476",
        "methods_doi": "10.5194/essd-15-3761-2023",
        "source_url": ZENODO_URL,
        "source_sha256": EXPECTED_SHA256,
        "region_bbox_min_lon_min_lat_max_lon_max_lat": list(REGION_BBOX),
        "crs": "EPSG:4326",
        "total_features_in_subset": n,
        "features_per_layer": per_layer,
        "geometry_note": "Features copied verbatim from OGIM; full geometry retained.",
        "license": "OGIM is public-domain (EDF/MethaneSAT).",
    }
    (OUT_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2))

    print(f"Wrote {subset_path.relative_to(REPO_ROOT)}  ({n} features)")
    for layer, c in sorted(per_layer.items()):
        print(f"  {layer:38s} {c:>4}")
    print(f"Wrote {(OUT_DIR / 'provenance.json').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
