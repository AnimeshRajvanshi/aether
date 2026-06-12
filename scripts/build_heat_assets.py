"""Sprint 9 Stage D — build the heat event's dashboard render assets.

Produces, for one registered heat event (HEAT_EVENTS in run_heat_stage_b):
  apps/api/aether_api/assets/<event_id>/
    air_anomaly.png    ERA5 window-mean daily-Tmax anomaly (K), inferno
    air_baseline.png   the 1991-2020 climatology the anomaly is measured
                       against (degC), magma — the "baseline toggle" layer
    lst_anomaly.png    MOD11A1 Terra window-mean LST anomaly (K), mosaicked
                       from the native sinusoidal tiles and warped to EPSG:4326
                       (10:41 local-solar mean view time — never a daily max)
    bounds.json        EPSG:4326 bounds + per-layer colormap windows + lane
                       labels (the source of HeatRasterMeta)

Same honesty rules as build_dashboard_assets.py: real pixels only; transparent
where data is absent (ocean, QC-failed LST); every styling choice recorded in
bounds.json. Air layers are masked to ERA5 land cells — the AIR-lane analysis
domain — so the render shows exactly the analyzed field.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.merge import merge as rio_merge
from rasterio.warp import Resampling, calculate_default_transform, reproject

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_heat_stage_b import HEAT_EVENTS, season_dates  # noqa: E402

CACHE_B = Path.home() / ".aether_cache" / "sprint9_heat_stage_b"
MODIS_DIR = CACHE_B / "modis"
ASSETS_ROOT = REPO_ROOT / "apps" / "api" / "aether_api" / "assets"

LST_SCALE = 0.02
AIR_VMIN, AIR_VMAX = 0.0, 8.0  # K anomaly window (matches the committed PNG style)
BASE_VMIN, BASE_VMAX = 20.0, 45.0  # degC climatology window
LST_VMIN, LST_VMAX = -2.0, 10.0  # K anomaly window


def colorize(arr: np.ndarray, cmap_name: str, vmin: float, vmax: float) -> np.ndarray:
    """(H, W) float -> (H, W, 4) uint8 RGBA; NaN -> fully transparent."""
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    rgba = cm.get_cmap(cmap_name)(norm(arr))
    rgba[..., 3] = np.where(np.isnan(arr), 0.0, 0.92)
    return (rgba * 255).astype(np.uint8)


def save_png(path: Path, rgba: np.ndarray) -> None:
    import matplotlib.image as mimg

    mimg.imsave(path, rgba)


def air_layers(event_id: str, out_dir: Path) -> dict[str, object]:
    """ERA5 window-mean anomaly + climatology layers from the Stage B cache."""
    ev = HEAT_EVENTS[event_id]
    grid = np.load(CACHE_B / f"era5_grid_{event_id}.npz")
    land = grid["land"]
    years = range(ev.baseline_years[0], ev.baseline_years[1] + 1)
    base = np.stack(
        [np.asarray(np.load(CACHE_B / f"era5_tmax_{y}.npz")["tmax"]) for y in years]
    )
    event_arr = np.asarray(
        np.load(CACHE_B / f"era5_tmax_{ev.window_start.year}.npz")["tmax"]
    )
    dates = season_dates(ev, ev.window_start.year)
    widx = [i for i, d in enumerate(dates) if ev.window_start <= d <= ev.window_end]

    # Same ±10d day-window climatology as the Stage B lane (per window day).
    clim_days = []
    for di in widx:
        lo, hi = max(di - 10, 0), min(di + 11, len(dates))
        clim_days.append(base[:, lo:hi].reshape(-1, *base.shape[2:]).mean(axis=0))
    clim_mean = np.mean(np.stack(clim_days), axis=0)
    anom = np.mean(np.stack([event_arr[i] for i in widx]), axis=0) - clim_mean

    anom_masked = np.where(land, anom, np.nan)
    clim_masked = np.where(land, clim_mean - 273.15, np.nan)
    save_png(out_dir / "air_anomaly.png", colorize(anom_masked, "inferno", AIR_VMIN, AIR_VMAX))
    save_png(out_dir / "air_baseline.png", colorize(clim_masked, "magma", BASE_VMIN, BASE_VMAX))
    return {
        "air_anomaly": {
            "colormap": "inferno",
            "vmin_k": AIR_VMIN,
            "vmax_k": AIR_VMAX,
            "label": "2 m air Tmax anomaly (K) vs 1991-2020 ±10d climatology",
            "lane": "AIR",
        },
        "air_baseline": {
            "colormap": "magma",
            "vmin_c": BASE_VMIN,
            "vmax_c": BASE_VMAX,
            "label": "1991-2020 climatological daily Tmax (degC) — the anomaly baseline",
            "lane": "AIR",
        },
    }


def lst_layer(
    event_id: str, out_dir: Path, bbox: tuple[float, float, float, float]
) -> dict[str, object]:
    """MOD11A1 window-mean anomaly: per-tile native arrays -> mosaic -> EPSG:4326."""
    from collections import defaultdict

    from run_heat_lst_uhi import collect, composite_start, read_masked_lst

    a1 = collect("modis-11A1-061")
    a2 = collect("modis-11A2-061")
    window = [date(2022, 4, d) for d in range(2, 12)]

    clim_stack: dict[tuple[str, int], list[np.ndarray]] = defaultdict(list)
    profile_by_tile: dict[str, dict[str, object]] = {}
    for item_id, assets in a2.items():
        year = int(item_id.split(".")[1][1:5])
        start = int(item_id.split(".")[1][5:8])
        if year not in range(2013, 2022) or "LST_Day_1km" not in assets:
            continue
        tile = item_id.split(".")[2]
        clim_stack[(tile, start)].append(read_masked_lst(assets["LST_Day_1km"], assets["QC_Day"]))
        if tile not in profile_by_tile:
            with rasterio.open(assets["LST_Day_1km"]) as src:
                profile_by_tile[tile] = {"transform": src.transform, "crs": src.crs}
    clim = {k: np.nanmean(np.stack(v), axis=0) for k, v in clim_stack.items()}

    tile_anoms: dict[str, list[np.ndarray]] = defaultdict(list)
    for item_id, assets in a1.items():
        ydoy = item_id.split(".")[1]
        year, dd = int(ydoy[1:5]), int(ydoy[5:8])
        day = date(year, 1, 1).fromordinal(date(year, 1, 1).toordinal() + dd - 1)
        if day not in window or "LST_Day_1km" not in assets:
            continue
        tile = item_id.split(".")[2]
        key = (tile, composite_start(day))
        if key not in clim:
            continue
        anom = read_masked_lst(assets["LST_Day_1km"], assets["QC_Day"]) - clim[key]
        tile_anoms[tile].append(anom)

    datasets = []
    for tile, arrs in tile_anoms.items():
        mean_anom = np.nanmean(np.stack(arrs), axis=0).astype(np.float32)
        prof = profile_by_tile[tile]
        mem = MemoryFile()
        with mem.open(
            driver="GTiff",
            height=mean_anom.shape[0],
            width=mean_anom.shape[1],
            count=1,
            dtype="float32",
            crs=prof["crs"],
            transform=prof["transform"],
            nodata=np.nan,
        ) as ds:
            ds.write(mean_anom, 1)
        datasets.append(mem.open())

    mosaic, mosaic_transform = rio_merge(datasets, nodata=np.nan)
    src_crs = datasets[0].crs
    for ds in datasets:
        ds.close()

    west, south, east, north = bbox
    dst_transform, _w, _h = calculate_default_transform(
        src_crs, "EPSG:4326", mosaic.shape[2], mosaic.shape[1],
        *rasterio.transform.array_bounds(mosaic.shape[1], mosaic.shape[2], mosaic_transform),
        dst_width=int((east - west) / 0.01),
        dst_height=int((north - south) / 0.01),
    )
    # Force the destination grid to the event bbox exactly so the PNG drapes
    # with the same bounds as the air layers.
    dst_transform = rasterio.transform.from_bounds(
        west, south, east, north, int((east - west) / 0.01), int((north - south) / 0.01)
    )
    dst = np.full((int((north - south) / 0.01), int((east - west) / 0.01)), np.nan, np.float32)
    reproject(
        source=mosaic[0],
        destination=dst,
        src_transform=mosaic_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs="EPSG:4326",
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=Resampling.nearest,
    )
    save_png(out_dir / "lst_anomaly.png", colorize(dst, "inferno", LST_VMIN, LST_VMAX))
    return {
        "lst_anomaly": {
            "colormap": "inferno",
            "vmin_k": LST_VMIN,
            "vmax_k": LST_VMAX,
            "label": (
                "MODIS Terra LST anomaly (K) vs 2013-2021 same-period composites — "
                "~10:41 local-solar snapshot, NOT a daily maximum"
            ),
            "lane": "LST",
        }
    }


def main() -> None:
    event_id = sys.argv[1] if len(sys.argv) > 1 else "india_nw_heatwave_2022_04"
    ev = HEAT_EVENTS[event_id]
    out_dir = ASSETS_ROOT / event_id
    out_dir.mkdir(parents=True, exist_ok=True)
    bbox = (ev.lon_min, ev.lat_min, ev.lon_max, ev.lat_max)

    layers: dict[str, object] = {}
    layers.update(air_layers(event_id, out_dir))
    layers.update(lst_layer(event_id, out_dir, bbox))

    # The measured mean Terra view time, read from the committed LST artifact so
    # the label cannot drift from the science.
    lst_lane = json.loads(
        (REPO_ROOT / "stage_b_outputs" / event_id / "lst_lane.json").read_text()
    )
    view_time = lst_lane["observation_time_caveat"]["measured_mean_day_view_time_local_h"]

    bounds = {
        "event_id": event_id,
        "crs": "EPSG:4326",
        "bounds": {
            "west": ev.lon_min,
            "south": ev.lat_min,
            "east": ev.lon_max,
            "north": ev.lat_max,
        },
        "phenomenon": "heat_wave",
        "layers": ["air_anomaly", "air_baseline", "lst_anomaly"],
        "layer_meta": layers,
        "lst_view_time_local_h": view_time,
        "rendering": (
            "AIR layers: ERA5 0.25-deg bbox land cells (the Stage B analysis "
            "domain), window-mean over 2022-04-02..11; transparent off-land. "
            "LST layer: MOD11A1 Terra-only window-mean anomaly, QC mandatory-good "
            "pixels, native-sinusoidal mosaic warped to EPSG:4326; transparent "
            "where QC-failed/absent. Real pixels throughout; no interpolation "
            "beyond the warp."
        ),
        "source": {
            "air": "~/.aether_cache/sprint9_heat_stage_b/era5_tmax_*.npz (ERA5 v3)",
            "lst": "~/.aether_cache/sprint9_heat_stage_b/modis (MOD11A1/A2 v061 COGs)",
            "view_time": f"stage_b_outputs/{event_id}/lst_lane.json",
        },
    }
    (out_dir / "bounds.json").write_text(json.dumps(bounds, indent=2))
    print(f"wrote {out_dir}/{{air_anomaly,air_baseline,lst_anomaly}}.png + bounds.json")


if __name__ == "__main__":
    main()
