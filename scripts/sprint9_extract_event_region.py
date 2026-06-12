"""Sprint 9 Stage A — extract the selected window's event region from the scan.

Reads the cached daily proxies + recomputes the climatology exactly as the scan
does, then for the selected window reports per-day qualifying-cell stats and the
bbox of the largest qualifying cluster on the peak-area day. This bbox is the
benchmark YAML's region candidate — derived from data, not asserted.

Output: stage_a_outputs/sprint9_heat_probe/event_region_<id>.json
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import numpy as np
import xarray as xr
from sprint9_scan_era5_heat import (
    ARCO_V3,
    BASELINE_YEARS,
    IMD_ABS_THRESHOLD_K,
    IMD_DEPARTURE_K,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    OUT_DIR,
    SCAN_END,
    SCAN_START,
    WINDOW_HALF_DAYS,
    fetch_year_proxy,
    season_dates,
)

WINDOW_START = date(2022, 4, 2)
WINDOW_END = date(2022, 4, 11)
EVENT_TAG = "2022_04"


def largest_cluster_bbox(
    mask: np.ndarray, lats: np.ndarray, lons: np.ndarray
) -> tuple[dict[str, float], int]:
    """BBox of the largest 4-connected qualifying cluster (pure numpy BFS)."""
    visited = np.zeros_like(mask, dtype=bool)
    best: list[tuple[int, int]] = []
    for i, j in zip(*np.nonzero(mask), strict=True):
        if visited[i, j]:
            continue
        stack, comp = [(i, j)], []
        visited[i, j] = True
        while stack:
            a, b = stack.pop()
            comp.append((a, b))
            for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                na, nb = a + da, b + db
                if (
                    0 <= na < mask.shape[0]
                    and 0 <= nb < mask.shape[1]
                    and mask[na, nb]
                    and not visited[na, nb]
                ):
                    visited[na, nb] = True
                    stack.append((na, nb))
        if len(comp) > len(best):
            best = comp
    ii = [c[0] for c in best]
    jj = [c[1] for c in best]
    half = 0.125  # half a 0.25 deg cell, so the bbox bounds whole cells
    bbox = {
        "min_lon": float(lons[max(jj)] if lons[0] > lons[-1] else lons[min(jj)]) - half,
        "max_lon": float(lons[min(jj)] if lons[0] > lons[-1] else lons[max(jj)]) + half,
        "min_lat": float(min(lats[min(ii)], lats[max(ii)])) - half,
        "max_lat": float(max(lats[min(ii)], lats[max(ii)])) + half,
    }
    return bbox, len(best)


def main() -> None:
    ds = xr.open_zarr(ARCO_V3, consolidated=True, storage_options={"token": "anon"})
    t2m0 = ds["2m_temperature"].sel(
        latitude=slice(LAT_MAX, LAT_MIN), longitude=slice(LON_MIN, LON_MAX)
    )
    lats, lons = t2m0.latitude.values, t2m0.longitude.values
    lsm = (
        ds["land_sea_mask"]
        .sel(latitude=slice(LAT_MAX, LAT_MIN), longitude=slice(LON_MIN, LON_MAX))
        .sel(time="2000-01-01T00:00", method="nearest")
        .values
    )
    land = lsm > 0.5

    dates_template = season_dates(2013)
    n_days = len(dates_template)
    scan_idx = [
        i
        for i, d in enumerate(dates_template)
        if SCAN_START <= (d.month, d.day) <= SCAN_END
    ]
    base_years = [fetch_year_proxy(ds, y) for y in BASELINE_YEARS]
    assert all(b is not None for b in base_years), "baseline year missing from cache/store"
    base = np.stack([b for b in base_years if b is not None], axis=0)
    arr = fetch_year_proxy(ds, WINDOW_START.year)
    assert arr is not None

    w = np.cos(np.deg2rad(lats))[:, None] * np.ones((1, lons.size))

    days_out: list[dict[str, Any]] = []
    peak: tuple[float, dict[str, float], int, str] | None = None
    for di in scan_idx:
        d = dates_template[di]
        cur = date(WINDOW_START.year, d.month, d.day)
        if not (WINDOW_START <= cur <= WINDOW_END):
            continue
        lo, hi = max(di - WINDOW_HALF_DAYS, 0), min(di + WINDOW_HALF_DAYS + 1, n_days)
        clim_mean = base[:, lo:hi].reshape(-1, *base.shape[2:]).mean(axis=0)
        day = arr[di]
        qualify = (day >= IMD_ABS_THRESHOLD_K) & (day - clim_mean >= IMD_DEPARTURE_K) & land
        bbox, n_cells = largest_cluster_bbox(qualify, lats, lons)
        w_ex = np.where(qualify, w, 0.0)
        anom = day - clim_mean
        rec: dict[str, Any] = {
            "date": cur.isoformat(),
            "qualifying_cells": int(qualify.sum()),
            "largest_cluster_cells": n_cells,
            "cluster_bbox": bbox,
            "mean_anom_over_qualifying_k": round(
                float((anom * w_ex).sum() / w_ex.sum()), 2
            )
            if w_ex.sum() > 0
            else None,
            "max_anom_k": round(float(np.where(qualify, anom, -np.inf).max()), 2),
            "max_proxy_c": round(float(np.where(qualify, day, -np.inf).max()) - 273.15, 2),
        }
        days_out.append(rec)
        if peak is None or qualify.sum() > peak[2]:
            mean_anom = float(rec["mean_anom_over_qualifying_k"] or 0)
            peak = (mean_anom, bbox, int(qualify.sum()), cur.isoformat())

    assert peak is not None
    out = {
        "window": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
        "criterion": {
            "abs_threshold_k": IMD_ABS_THRESHOLD_K,
            "departure_k": IMD_DEPARTURE_K,
        },
        "peak_area_date": peak[3],
        "peak_day_cluster_bbox": peak[1],
        "days": days_out,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"event_region_{EVENT_TAG}.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "days"}, indent=2))
    for rec in days_out:
        print(
            f"  {rec['date']}: cells={rec['qualifying_cells']} "
            f"cluster={rec['largest_cluster_cells']} "
            f"mean_anom={rec['mean_anom_over_qualifying_k']}K max_anom={rec['max_anom_k']}K "
            f"max_T={rec['max_proxy_c']}C"
        )
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
