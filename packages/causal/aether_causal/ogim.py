"""Read the OGIM GeoPackage with pure stdlib sqlite3 + shapely (no GDAL).

A GeoPackage is a SQLite database; feature tables store geometries as
GeoPackageBinary blobs (a small header + standard WKB). We enumerate feature
layers from ``gpkg_contents``, use each layer's R-tree index for fast bounding-
box queries, and decode geometries with shapely. This keeps OGIM access
dependency-light and fully deterministic/offline once the subset is committed.

Nothing here invents data: every returned record is a real row from the OGIM
GeoPackage, with its real attributes and real coordinates.

OGIM v2.7 — O'Brien, M., Omara, M., Himmelberger, A., & Gautam, R. (2025).
doi:10.5281/zenodo.15103476. Methods: Omara et al. (2023), ESSD 15, 3761-3790,
doi:10.5194/essd-15-3761-2023.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import shapely
from shapely.geometry.base import BaseGeometry

# Envelope indicator -> number of envelope bytes following the 8-byte GPB header.
_ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


@dataclass(frozen=True)
class OgimFeature:
    """One real OGIM record with its decoded representative lon/lat."""

    layer: str
    fid: int
    lon: float
    lat: float
    geom_type: str
    attributes: dict[str, Any]


def _gpb_to_geometry(blob: bytes) -> BaseGeometry:
    """Decode a GeoPackageBinary blob to a shapely geometry (strip GPB header)."""
    if blob[0:2] != b"GP":
        raise ValueError("not a GeoPackageBinary blob (missing 'GP' magic)")
    flags = blob[3]
    envelope_indicator = (flags >> 1) & 0x07
    env_bytes = _ENVELOPE_BYTES.get(envelope_indicator)
    if env_bytes is None:
        raise ValueError(f"reserved GPB envelope indicator {envelope_indicator}")
    wkb_start = 8 + env_bytes  # 2 magic + 1 version + 1 flags + 4 srs_id + envelope
    return shapely.from_wkb(blob[wkb_start:])


def feature_layers(conn: sqlite3.Connection) -> list[tuple[str, str, int]]:
    """Return (table_name, geometry_column, srs_id) for every feature layer."""
    rows = conn.execute(
        "SELECT c.table_name, g.column_name, g.srs_id "
        "FROM gpkg_contents c JOIN gpkg_geometry_columns g "
        "ON c.table_name = g.table_name "
        "WHERE c.data_type = 'features' ORDER BY c.table_name"
    ).fetchall()
    return [(r[0], r[1], int(r[2])) for r in rows]


def _representative_lonlat(geom: BaseGeometry) -> tuple[float, float]:
    """A single lon/lat for a feature: the point itself, else a representative
    interior point (documented: non-point geometries are summarised to a point)."""
    if geom.geom_type == "Point":
        return float(geom.x), float(geom.y)
    p = geom.representative_point()
    return float(p.x), float(p.y)


def query_bbox(
    conn: sqlite3.Connection,
    table: str,
    geom_col: str,
    bbox: tuple[float, float, float, float],
) -> list[OgimFeature]:
    """All features in ``table`` whose geometry bbox intersects ``bbox``.

    bbox = (min_lon, min_lat, max_lon, max_lat). Uses the GeoPackage R-tree
    (rtree_<table>_<geom>) for an indexed candidate scan, then decodes geometry.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    rtree = f"rtree_{table}_{geom_col}"
    # R-tree stores minx,maxx,miny,maxy per feature id; intersect with query bbox.
    has_rtree = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (rtree,)
    ).fetchone()

    cur = conn.cursor()
    if has_rtree:
        ids = [
            r[0]
            for r in cur.execute(
                f'SELECT id FROM "{rtree}" '
                "WHERE minx <= ? AND maxx >= ? AND miny <= ? AND maxy >= ?",
                (max_lon, min_lon, max_lat, min_lat),
            ).fetchall()
        ]
        if not ids:
            return []

    # column names (so we can return all attributes minus the geometry blob)
    cols = [c[1] for c in cur.execute(f'PRAGMA table_info("{table}")').fetchall()]
    pk = cols[0]  # gpkg feature tables use an INTEGER PRIMARY KEY first column
    attr_cols = [c for c in cols if c != geom_col]

    out: list[OgimFeature] = []
    select_cols = ", ".join(f'"{c}"' for c in [*attr_cols, geom_col])
    if has_rtree:
        placeholders = ",".join("?" * len(ids))
        sql = f'SELECT {select_cols} FROM "{table}" WHERE "{pk}" IN ({placeholders})'
        rows = cur.execute(sql, ids).fetchall()
    else:
        rows = cur.execute(f'SELECT {select_cols} FROM "{table}"').fetchall()

    # The R-tree returns features whose geometry envelope intersects the query
    # bbox; we report each with a representative lon/lat (the documented filter is
    # envelope intersection — downstream code applies the precise distance test).
    for row in rows:
        attrs = dict(zip(attr_cols, row[: len(attr_cols)], strict=True))
        blob = row[len(attr_cols)]
        if blob is None:
            continue
        geom = _gpb_to_geometry(blob)
        lon, lat = _representative_lonlat(geom)
        out.append(
            OgimFeature(
                layer=table,
                fid=int(attrs.get(pk, -1)) if isinstance(attrs.get(pk), int) else -1,
                lon=lon,
                lat=lat,
                geom_type=geom.geom_type,
                attributes=attrs,
            )
        )
    return out


def extract_region(
    gpkg_path: Path, bbox: tuple[float, float, float, float]
) -> dict[str, list[OgimFeature]]:
    """Extract every feature layer's features within ``bbox`` from the GeoPackage."""
    conn = sqlite3.connect(f"file:{gpkg_path}?mode=ro", uri=True)
    try:
        result: dict[str, list[OgimFeature]] = {}
        for table, geom_col, _srs in feature_layers(conn):
            feats = query_bbox(conn, table, geom_col, bbox)
            if feats:
                result[table] = feats
        return result
    finally:
        conn.close()


def layer_srs_ids(gpkg_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{gpkg_path}?mode=ro", uri=True)
    try:
        return {t: srs for t, _g, srs in feature_layers(conn)}
    finally:
        conn.close()
