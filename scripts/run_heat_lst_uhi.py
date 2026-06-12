"""Sprint 9 Stage B — LST lane (MODIS + Landsat) and the Delhi UHI analysis.

LST LANE RULES (pre-registration §4-5, gate ruling 4): every quantity here is
SKIN temperature from a **Terra ~10:30-local snapshot** — BEFORE the diurnal
LST peak (the Aqua 13:30 pass is absent for the window; measured gap). Nothing
here is a daily maximum and nothing here may be compared against the AIR lane.
The actual mean view time is computed from the granules and recorded with
every output, so the caveat is a measured number, not boilerplate.

Computations:
- L1: MOD11A1 daily LST anomaly per sinusoidal tile vs a 2013-2021 MOD11A2
  same-composite-period climatology (QC mandatory-good only), mosaicked stats
  over the event bbox + the composite-vs-daily residual measured on 2022.
- L3: MODIS LST vs ERA5 skin temperature at the overpass hour (product
  consistency between distinct-but-not-independent products).

The UHI analysis (WorldCover masks, MODIS + Landsat deltas) lives in
scripts/run_heat_uhi.py — same lane, same caveats.

Outputs: stage_b_outputs/<event_id>/lst_lane.json, anomaly_lst_window_mean.png
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import xarray as xr

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".aether_cache" / "sprint9_heat_stage_b"
MODIS_DIR = CACHE / "modis"
ARCO_V3 = "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"

EVENT_ID = "india_nw_heatwave_2022_04"
BBOX = (67.875, 22.375, 84.375, 32.875)
WINDOW = [date(2022, 4, d) for d in range(2, 12)]
BASELINE_YEARS = range(2013, 2022)

LST_SCALE = 0.02  # MOD11 LST scale factor (K); 0 = fill
VIEW_TIME_SCALE = 0.1  # hours
DELHI = (28.61, 77.21)
WORLDCOVER_TILE = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_N27E075_Map.tif"
)
URBAN_RADIUS_KM = 20.0
RING_KM = (20.0, 40.0)
URBAN_FRAC = 0.5
RURAL_FRAC = 0.1


def doy(d: date) -> int:
    return (d - date(d.year, 1, 1)).days + 1


def composite_start(d: date) -> int:
    """MOD11A2 composite period (start doy) covering day d: 8-day periods from doy 1."""
    return ((doy(d) - 1) // 8) * 8 + 1


def tile_of(item_id: str) -> str:
    return item_id.split(".")[2]


def read_masked_lst(path_lst: Path, path_qc: Path) -> np.ndarray:
    """LST_Day (K) with QC mandatory-good (bits 0-1 == 0) only; NaN elsewhere."""
    with rasterio.open(path_lst) as src:
        raw = src.read(1).astype(np.float32)
    with rasterio.open(path_qc) as src:
        qc = src.read(1)
    lst = np.where(raw == 0, np.nan, raw * LST_SCALE)
    return np.where((qc & 0b11) == 0, lst, np.nan)




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


def collect(collection: str) -> dict[str, dict[str, Path]]:
    """{item_id: {asset: path}} from the fetch cache."""
    out: dict[str, dict[str, Path]] = defaultdict(dict)
    for path in (MODIS_DIR / collection).glob("*.tif"):
        stem = path.stem
        # Terra only: the MPC collection mixes MOD (Terra ~10:30 local) and
        # MYD (Aqua ~13:30); mixing view times would corrupt the baseline.
        if not stem.startswith("MOD11"):
            continue
        for asset in ("LST_Day_1km", "QC_Day", "Day_view_time"):
            if stem.endswith("_" + asset):
                out[stem[: -len(asset) - 1]][asset] = path
    return dedupe_latest(dict(out))


def mean_view_time_local(items: dict[str, dict[str, Path]]) -> float:
    """Mean Day_view_time (local solar hours) over valid pixels, all granules."""
    vals = []
    for assets in items.values():
        vt = assets.get("Day_view_time")
        if vt is None:
            continue
        with rasterio.open(vt) as src:
            arr = src.read(1).astype(np.float32)
        arr = np.where(arr == 255, np.nan, arr * VIEW_TIME_SCALE)
        if np.isfinite(arr).any():
            vals.append(float(np.nanmean(arr)))
    return float(np.mean(vals))


def main() -> None:
    out_dir = REPO_ROOT / "stage_b_outputs" / EVENT_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    accessed = datetime.now(UTC).strftime("%Y-%m-%d")

    a1 = collect("modis-11A1-061")
    a2 = collect("modis-11A2-061")
    if not a1 or not a2:
        raise SystemExit("MODIS cache incomplete — run scripts/sprint9_fetch_modis.py first")

    # ---- climatology per (tile, composite-start-doy) from 2013-2021 A2 ----
    clim_stack: dict[tuple[str, int], list[np.ndarray]] = defaultdict(list)
    clim_meta: dict[str, rasterio.profiles.Profile] = {}
    for item_id, assets in a2.items():
        year = int(item_id.split(".")[1][1:5])
        start = int(item_id.split(".")[1][5:8])
        if year not in BASELINE_YEARS:
            continue
        if "LST_Day_1km" not in assets or "QC_Day" not in assets:
            continue
        tile = tile_of(item_id)
        clim_stack[(tile, start)].append(
            read_masked_lst(assets["LST_Day_1km"], assets["QC_Day"])
        )
        if tile not in clim_meta:
            with rasterio.open(assets["LST_Day_1km"]) as src:
                clim_meta[tile] = src.profile
    clim: dict[tuple[str, int], np.ndarray] = {}
    clim_n: dict[tuple[str, int], int] = {}
    for key, stack in clim_stack.items():
        clim[key] = np.nanmean(np.stack(stack), axis=0)
        clim_n[key] = len(stack)

    # ---- daily anomalies on native tiles; bbox-mosaic stats ----
    view_time_h = mean_view_time_local(a1)
    daily_stats = []
    window_anom_tiles: dict[str, list[np.ndarray]] = defaultdict(list)
    for item_id, assets in sorted(a1.items()):
        ydoy = item_id.split(".")[1]
        year, dd = int(ydoy[1:5]), int(ydoy[5:8])
        day = date(year, 1, 1) + (dd - 1) * (date(2000, 1, 2) - date(2000, 1, 1))
        if day not in WINDOW:
            continue
        if "LST_Day_1km" not in assets or "QC_Day" not in assets:
            continue
        tile = tile_of(item_id)
        key = (tile, composite_start(day))
        if key not in clim:
            continue
        lst = read_masked_lst(assets["LST_Day_1km"], assets["QC_Day"])
        anom = lst - clim[key]
        window_anom_tiles[tile].append(anom)
        valid_frac = float(np.isfinite(anom).mean())
        daily_stats.append(
            {
                "date": day.isoformat(),
                "tile": tile,
                "valid_frac": round(valid_frac, 3),
                "mean_anomaly_k": round(float(np.nanmean(anom)), 2)
                if np.isfinite(anom).any()
                else None,
            }
        )

    # per-day bbox aggregate (across tiles, pixel-count weighted)
    by_day: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for rec in daily_stats:
        if rec["mean_anomaly_k"] is not None:
            n_valid = int(rec["valid_frac"] * 1200 * 1200)
            by_day[str(rec["date"])].append((float(rec["mean_anomaly_k"]), n_valid))
    day_means = {
        d: round(sum(a * n for a, n in v) / max(sum(n for _, n in v), 1), 2)
        for d, v in sorted(by_day.items())
    }

    # composite-vs-daily residual (2022): A2 2022 composite minus window-mean
    # of A1 dailies, per tile/period — the baseline-construction error term.
    residuals = []
    for item_id, assets in a2.items():
        year = int(item_id.split(".")[1][1:5])
        if year != 2022 or "LST_Day_1km" not in assets or "QC_Day" not in assets:
            continue
        tile = tile_of(item_id)
        start = int(item_id.split(".")[1][5:8])
        dailies = []
        for rec_id, rec_assets in a1.items():
            ydoy = rec_id.split(".")[1]
            y2, dd2 = int(ydoy[1:5]), int(ydoy[5:8])
            day2 = date(y2, 1, 1) + (dd2 - 1) * (date(2000, 1, 2) - date(2000, 1, 1))
            if (
                y2 == 2022
                and tile_of(rec_id) == tile
                and composite_start(day2) == start
                and "LST_Day_1km" in rec_assets
                and "QC_Day" in rec_assets
            ):
                dailies.append(read_masked_lst(rec_assets["LST_Day_1km"], rec_assets["QC_Day"]))
        if not dailies:
            continue
        comp = read_masked_lst(assets["LST_Day_1km"], assets["QC_Day"])
        diff = comp - np.nanmean(np.stack(dailies), axis=0)
        if np.isfinite(diff).any():
            residuals.append(float(np.nanmean(diff)))
    composite_residual_k = round(float(np.mean(residuals)), 2) if residuals else None

    # ---- L3: MODIS LST vs ERA5 skin temperature at the overpass hour ----
    ds = xr.open_zarr(ARCO_V3, consolidated=True, storage_options={"token": "anon"})
    skt_var = "skin_temperature"
    l3 = None
    if skt_var in ds:
        # bbox mean of MODIS LST per day vs ERA5 skt at the nearest hour to the
        # measured overpass time (local ~view_time_h -> UTC at bbox-center lon).
        center_lon = (BBOX[0] + BBOX[2]) / 2
        utc_hour = round(view_time_h - center_lon / 15.0) % 24
        diffs = []
        abs_means: dict[str, list[tuple[float, int]]] = defaultdict(list)
        for item_id, assets in sorted(a1.items()):
            ydoy = item_id.split(".")[1]
            year, dd = int(ydoy[1:5]), int(ydoy[5:8])
            day = date(year, 1, 1) + (dd - 1) * (date(2000, 1, 2) - date(2000, 1, 1))
            if day not in WINDOW or "LST_Day_1km" not in assets or "QC_Day" not in assets:
                continue
            lst = read_masked_lst(assets["LST_Day_1km"], assets["QC_Day"])
            if np.isfinite(lst).any():
                abs_means[day.isoformat()].append(
                    (float(np.nanmean(lst)), int(np.isfinite(lst).sum()))
                )
        for d_iso, vals in abs_means.items():
            modis_k = sum(a * n for a, n in vals) / sum(n for _, n in vals)
            t = np.datetime64(f"{d_iso}T{utc_hour:02d}:00")
            skt = (
                ds[skt_var]
                .sel(latitude=slice(BBOX[3], BBOX[1]), longitude=slice(BBOX[0], BBOX[2]))
                .sel(time=t)
                .values
            )
            lsm = (
                ds["land_sea_mask"]
                .sel(latitude=slice(BBOX[3], BBOX[1]), longitude=slice(BBOX[0], BBOX[2]))
                .sel(time="2000-01-01T00:00", method="nearest")
                .values
            )
            era5_mean = float(np.nanmean(np.where(lsm > 0.5, skt, np.nan)))
            diffs.append(modis_k - era5_mean)
        l3 = {
            "n_days": len(diffs),
            "mean_diff_modis_minus_era5skt_k": round(float(np.mean(diffs)), 2),
            "std_diff_k": round(float(np.std(diffs)), 2),
            "era5_hour_utc": utc_hour,
            "framing": (
                "product consistency between DISTINCT-BUT-NOT-INDEPENDENT skin-"
                "temperature products (MODIS retrieval vs reanalysis surface energy "
                "balance); spatial aggregation differs (QC-valid 1 km pixels vs all "
                "land cells) — a coherence check, not a validation"
            ),
        }

    lst_lane = {
        "event_id": EVENT_ID,
        "lane": "LST (satellite skin temperature) — ceiling CROSS-CHECKED",
        "observation_time_caveat": {
            "measured_mean_day_view_time_local_h": round(view_time_h, 2),
            "statement": (
                f"All daytime LST values are Terra snapshots at ~{view_time_h:.1f} h "
                "local solar time — BEFORE the diurnal LST peak. The Aqua ~13:30 "
                "pass is absent for this window (measured gap 2022-04-01..16). "
                "Nothing in this lane is a daily maximum."
            ),
        },
        "anomaly_baseline": {
            "construction": "MOD11A2 2013-2021 same-composite-period mean, QC-good only",
            "n_years": len(list(BASELINE_YEARS)),
            "samples_per_tile_period": {f"{k[0]}_{k[1]:03d}": n for k, n in sorted(clim_n.items())},
            "composite_vs_daily_residual_k_2022": composite_residual_k,
        },
        "daily_bbox_mean_anomaly_k": day_means,
        "window_mean_bbox_anomaly_k": round(
            float(np.mean(list(day_means.values()))), 2
        )
        if day_means
        else None,
        "per_granule": daily_stats,
        "l3_product_consistency": l3,
        "source": {
            "products": "MOD11A1/MOD11A2 v061 (NASA), COG mirror: Microsoft Planetary Computer",
            "route_note": (
                "LP DAAC HDF4 verified accessible (Stage A) but unreadable here "
                "(no GDAL HDF4 driver — probed); MPC serves the same v061 product "
                "as COGs. Accessed " + accessed
            ),
        },
    }
    (out_dir / "lst_lane.json").write_text(json.dumps(lst_lane, indent=2))

    # window-mean anomaly map (largest-coverage tile mosaic, equal grids per tile)
    fig, axes = plt.subplots(1, 1, figsize=(8, 6))
    tile_means = {
        t: np.nanmean(np.stack(arrs), axis=0) for t, arrs in window_anom_tiles.items()
    }
    biggest = max(tile_means, key=lambda t: np.isfinite(tile_means[t]).sum())
    im = axes.imshow(tile_means[biggest], cmap="inferno", vmin=-2, vmax=10)
    fig.colorbar(im, ax=axes, label="window-mean LST anomaly (K) — Terra ~10:30 local")
    axes.set_title(
        f"{EVENT_ID} — MOD11A1 LST anomaly, tile {biggest}\n"
        f"Terra ~{view_time_h:.1f}h local snapshot (NOT a daily max); "
        "baseline: A2 2013-2021"
    )
    fig.savefig(out_dir / "anomaly_lst_window_mean.png", dpi=150, bbox_inches="tight")

    print(json.dumps({k: v for k, v in lst_lane.items() if k != "per_granule"}, indent=1)[:2000])
    print(f"wrote {out_dir}/lst_lane.json")


if __name__ == "__main__":
    main()
