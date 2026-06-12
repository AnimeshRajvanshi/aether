"""Sprint 9 Stage B — Delhi urban-heat-island (UHI) analysis, LST lane.

UHI_LST = mean LST(urban cells) − mean LST(rural ring), per pre-registration
§5: urban = WorldCover v200 built-up (class 50) fraction ≥ 0.5 at the 1 km
MODIS cell within 20 km of Delhi center (28.61 N, 77.21 E); rural = built-up
≤ 0.1 in the 20–40 km annulus, excluding water (80) and wetland (90 — herbaceous
wetland) majority cells. Terra ~10:30-local snapshots only (the lane's
first-class observation-time caveat); never a daily maximum.

Sensitivities (pre-registered S5): urban threshold 0.4/0.6; ring 25–45 km.
Elevation confound guard: NOT APPLIED (no 1 km elevation source in this
stack) — reported as such, with the note that the Delhi region is alluvial
plain (low relief), so the residual risk is small but unquantified here.

Landsat C2L2 ST cross-check: in-window scenes covering Delhi, ST band
(lwir11-derived ST_B10-equivalent COG asset 'lwir11', Kelvin via the USGS C2L2
scale 0.00341802 + 149.0), same masks aggregated to 30 m.

Output: stage_b_outputs/<event_id>/uhi.json
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import requests
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".aether_cache" / "sprint9_heat_stage_b"
MODIS_DIR = CACHE / "modis" / "modis-11A1-061"

EVENT_ID = "india_nw_heatwave_2022_04"
WINDOW = [date(2022, 4, d) for d in range(2, 12)]
DELHI_LAT, DELHI_LON = 28.61, 77.21
DELHI_TILE = "h24v06"  # MODIS sinusoidal tile containing Delhi (v06 = 20-30 N band)

WORLDCOVER_URL = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_N27E075_Map.tif"
)
WC_BUILT = 50
WC_WATER = 80
WC_WETLAND = 90

LST_SCALE = 0.02
URBAN_RADIUS_KM = 20.0
RING_KM = (20.0, 40.0)
URBAN_FRAC = 0.5
RURAL_FRAC = 0.1
SENS_URBAN_FRACS = (0.4, 0.6)
SENS_RING_KM = (25.0, 45.0)

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"
LANDSAT_SCALE, LANDSAT_OFFSET = 0.00341802, 149.0  # USGS C2L2 ST_B10




def dedupe_latest(items: dict[str, dict[str, Path]]) -> dict[str, dict[str, Path]]:
    """One item per (product, day, tile): keep the latest production stamp.

    MPC carries reprocessed duplicates of some granules (observed:
    MOD11A1.A2022097.h24v06.061 with two production timestamps); double-
    counting a day would silently bias day means.
    """
    best: dict[str, str] = {}
    for item_id in items:
        parts = item_id.split(".")
        key = ".".join(parts[:4])  # product.Adoy.tile.collection
        if key not in best or parts[4] > best[key].split(".")[4]:
            best[key] = item_id
    return {iid: assets for iid, assets in items.items() if iid in best.values()}


def find_delhi_modis_items() -> dict[str, dict[str, Path]]:
    out: dict[str, dict[str, Path]] = defaultdict(dict)
    for path in MODIS_DIR.glob("*.tif"):
        stem = path.stem
        if not stem.startswith("MOD11"):  # Terra only (MYD = Aqua 13:30)
            continue
        for asset in ("LST_Day_1km", "QC_Day"):
            if stem.endswith("_" + asset):
                item = stem[: -len(asset) - 1]
                if item.split(".")[2] == DELHI_TILE:
                    out[item][asset] = path
    return dedupe_latest(dict(out))


def modis_window_and_grid(
    sample_lst: Path,
) -> tuple[rasterio.windows.Window, dict[str, Any], np.ndarray]:
    """A ~±60 km window around Delhi on the MODIS sinusoidal grid.

    Returns the rasterio window, a dst-grid descriptor (transform/crs/shape),
    and the per-cell distance-to-Delhi (km).
    """
    from pyproj import Transformer

    with rasterio.open(sample_lst) as src:
        to_sinu = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
        cx, cy = to_sinu.transform(DELHI_LON, DELHI_LAT)
        half = 60_000.0
        window = from_bounds(
            cx - half, cy - half, cx + half, cy + half, src.transform
        ).round_offsets().round_lengths()
        transform = src.window_transform(window)
        h, w = int(window.height), int(window.width)
        rows = np.arange(h) + 0.5
        cols = np.arange(w) + 0.5
        xs = transform.c + cols * transform.a
        ys = transform.f + rows * transform.e
        xx, yy = np.meshgrid(xs, ys)
        dist_km = np.hypot(xx - cx, yy - cy) / 1000.0
        grid = {"crs": src.crs, "transform": transform, "shape": (h, w)}
    return window, grid, dist_km


def worldcover_fractions(grid: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """(built_fraction, water_or_wetland_fraction) on the MODIS dst grid.

    WorldCover 10 m classes are read over the Delhi neighbourhood via HTTP
    range requests and average-resampled to the 1 km sinusoidal grid.
    """
    url = "/vsicurl/" + WORLDCOVER_URL
    with rasterio.open(url) as src:
        win = from_bounds(
            DELHI_LON - 0.65, DELHI_LAT - 0.65, DELHI_LON + 0.65, DELHI_LAT + 0.65,
            src.transform,
        ).round_offsets().round_lengths()
        classes = src.read(1, window=win)
        src_transform = src.window_transform(win)
        src_crs = src.crs
    out = []
    for mask in ((classes == WC_BUILT), np.isin(classes, (WC_WATER, WC_WETLAND))):
        dst = np.zeros(grid["shape"], dtype=np.float32)
        reproject(
            source=mask.astype(np.float32),
            destination=dst,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=grid["transform"],
            dst_crs=grid["crs"],
            resampling=Resampling.average,
        )
        out.append(dst)
    return out[0], out[1]


def uhi_delta(
    lst: np.ndarray,
    built: np.ndarray,
    waterwet: np.ndarray,
    dist_km: np.ndarray,
    urban_frac: float,
    ring: tuple[float, float],
) -> dict[str, Any] | None:
    urban = (built >= urban_frac) & (dist_km <= URBAN_RADIUS_KM)
    rural = (
        (built <= RURAL_FRAC)
        & (waterwet < 0.5)
        & (dist_km >= ring[0])
        & (dist_km <= ring[1])
    )
    u = lst[urban & np.isfinite(lst)]
    r = lst[rural & np.isfinite(lst)]
    if u.size < 10 or r.size < 30:
        return None
    return {
        "uhi_k": round(float(u.mean() - r.mean()), 2),
        "urban_mean_k": round(float(u.mean()), 2),
        "rural_mean_k": round(float(r.mean()), 2),
        "n_urban_px": int(u.size),
        "n_rural_px": int(r.size),
    }


def read_masked_lst(path_lst: Path, path_qc: Path, window: rasterio.windows.Window) -> np.ndarray:
    with rasterio.open(path_lst) as src:
        raw = src.read(1, window=window).astype(np.float32)
    with rasterio.open(path_qc) as src:
        qc = src.read(1, window=window)
    lst = np.where(raw == 0, np.nan, raw * LST_SCALE)
    return np.where((qc & 0b11) == 0, lst, np.nan)


def landsat_scenes() -> list[dict[str, Any]]:
    body = {
        "collections": ["landsat-c2-l2"],
        "intersects": {"type": "Point", "coordinates": [DELHI_LON, DELHI_LAT]},
        "datetime": "2022-04-02T00:00:00Z/2022-04-11T23:59:59Z",
        "query": {"platform": {"in": ["landsat-8", "landsat-9"]}},
        "limit": 20,
    }
    r = requests.post(STAC, json=body, timeout=120)
    r.raise_for_status()
    return r.json().get("features", [])


def landsat_uhi(
    built: np.ndarray, waterwet: np.ndarray, grid: dict[str, Any], dist_km: np.ndarray
) -> list[dict[str, Any]]:
    """UHI from each in-window Landsat scene, masks aggregated to the MODIS grid.

    The ST band is average-resampled onto the same 1 km grid as the masks, so
    urban/rural cell definitions are identical between sensors.
    """
    token = requests.get(
        SAS.format(collection="landsat-c2-l2"), timeout=60
    ).json()["token"]
    out = []
    for item in landsat_scenes():
        asset = item["assets"].get("lwir11")
        if asset is None:
            continue
        url = "/vsicurl/" + asset["href"] + "?" + token
        try:
            with rasterio.open(url) as src:
                dst = np.full(grid["shape"], np.nan, dtype=np.float32)
                reproject(
                    source=rasterio.band(src, 1),
                    destination=dst,
                    dst_transform=grid["transform"],
                    dst_crs=grid["crs"],
                    resampling=Resampling.average,
                    src_nodata=0,
                    dst_nodata=np.nan,
                )
        except rasterio.errors.RasterioIOError as exc:
            out.append({"id": item["id"], "error": str(exc)[:120]})
            continue
        st_k = np.where(np.isnan(dst), np.nan, dst * LANDSAT_SCALE + LANDSAT_OFFSET)
        delta = uhi_delta(st_k, built, waterwet, dist_km, URBAN_FRAC, RING_KM)
        rec = {
            "id": item["id"],
            "datetime": item["properties"].get("datetime"),
            "platform": item["properties"].get("platform"),
            "cloud_pct": item["properties"].get("eo:cloud_cover"),
        }
        if delta:
            rec.update(delta)
        out.append(rec)
    return out


def main() -> None:
    out_dir = REPO_ROOT / "stage_b_outputs" / EVENT_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    accessed = datetime.now(UTC).strftime("%Y-%m-%d")

    items = find_delhi_modis_items()
    if not items:
        raise SystemExit(f"no MODIS {DELHI_TILE} granules in cache")
    sample = next(iter(items.values()))["LST_Day_1km"]
    window, grid, dist_km = modis_window_and_grid(sample)
    built, waterwet = worldcover_fractions(grid)

    daily = []
    sens = defaultdict(list)
    for item_id, assets in sorted(items.items()):
        ydoy = item_id.split(".")[1]
        year, dd = int(ydoy[1:5]), int(ydoy[5:8])
        day = date(year, 1, 1).fromordinal(date(year, 1, 1).toordinal() + dd - 1)
        if day not in WINDOW or "LST_Day_1km" not in assets or "QC_Day" not in assets:
            continue
        lst = read_masked_lst(assets["LST_Day_1km"], assets["QC_Day"], window)
        delta = uhi_delta(lst, built, waterwet, dist_km, URBAN_FRAC, RING_KM)
        rec = {"date": day.isoformat()}
        if delta:
            rec.update(delta)
            for uf in SENS_URBAN_FRACS:
                d2 = uhi_delta(lst, built, waterwet, dist_km, uf, RING_KM)
                if d2:
                    sens[f"urban_frac_{uf}"].append(d2["uhi_k"])
            d3 = uhi_delta(lst, built, waterwet, dist_km, URBAN_FRAC, SENS_RING_KM)
            if d3:
                sens["ring_25_45km"].append(d3["uhi_k"])
        else:
            rec["note"] = "insufficient QC-valid pixels"
        daily.append(rec)

    valid_uhi = [r["uhi_k"] for r in daily if "uhi_k" in r]
    landsat = landsat_uhi(built, waterwet, grid, dist_km)

    result = {
        "event_id": EVENT_ID,
        "lane": "LST (skin temperature) — Terra ~10:30-local snapshots; NOT daily max",
        "definition": {
            "urban": (
                f"WorldCover built-up fraction >= {URBAN_FRAC} within "
                f"{URBAN_RADIUS_KM} km of Delhi center"
            ),
            "rural": (
                f"built-up <= {RURAL_FRAC}, ring {RING_KM[0]}-{RING_KM[1]} km, "
                "water/wetland-majority excluded"
            ),
            "grid": "MODIS 1 km sinusoidal; WorldCover average-aggregated onto it",
        },
        "daily": daily,
        "window_mean_uhi_k": round(float(np.mean(valid_uhi)), 2) if valid_uhi else None,
        "window_std_uhi_k": round(float(np.std(valid_uhi)), 2) if valid_uhi else None,
        "n_valid_days": len(valid_uhi),
        "sensitivities": {
            key: {"mean_uhi_k": round(float(np.mean(vals)), 2), "n_days": len(vals)}
            for key, vals in sens.items()
        },
        "classification_uncertainty": {
            "worldcover_version": "v200 (2021 map)",
            "stationarity_assumption": "2021 land cover applied to April 2022 (stated)",
            "accuracy_note": (
                "WorldCover v200's own reported accuracy is cited in the Stage B "
                "report from the product documentation; the threshold sensitivities "
                "above are this analysis's empirical handle on classification error."
            ),
        },
        "elevation_guard": {
            "applied": False,
            "reason": (
                "no 1 km elevation source in this stack; the Delhi region is "
                "low-relief alluvial plain, so the urban-rural elevation confound "
                "is expected small but is NOT quantified here"
            ),
        },
        "landsat_cross_check": landsat,
        "provenance": {
            "modis": "MOD11A1 v061 COGs via Planetary Computer, accessed " + accessed,
            "worldcover": (
                "ESA WorldCover v200 2021 (CC BY 4.0), tile N27E075, accessed " + accessed
            ),
            "landsat": "Landsat C2L2 via Planetary Computer (lwir11 ST), accessed " + accessed,
        },
    }
    (out_dir / "uhi.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in ("daily",)}, indent=1)[:2200])
    print(f"wrote {out_dir}/uhi.json")


if __name__ == "__main__":
    main()
