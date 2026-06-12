"""Sprint 9 Stage B — ERA5 daily-Tmax cache for the heat event bbox.

Fetches, per year, hourly 2m temperature at 06-13 UTC (11:30-18:30 IST — the
pre-registered daily-Tmax hour set, docs/science/sprint9_heat_validation.md §2)
for calendar days Mar 13 - May 1 (50 days: the Apr 2-11 window, room for the
duration run to extend to Mar 23 - Apr 21, and the ±10-day climatology window
around all of those; ±15 for the S2 sensitivity is covered for the canonical
window days). Domain: the benchmark bbox (67.875-84.375 E, 22.375-32.875 N).

Also fetches ALL 24 hours for the 10 canonical window days of 2022 (S3: the
measured residual of the 06-13 hour set vs the true 24 h daily max).

Cache: ~/.aether_cache/sprint9_heat_stage_b/era5_tmax_<year>.npz
       (daily Tmax (n_days, ny, nx) float32 + the hour-of-max index)
       era5_t2m_24h_2022_window.npz for the S3 check.
Parallel priming: `--prime <year>...` fetches only those years and exits.
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import xarray as xr

ARCO_V3 = "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
CACHE_DIR = Path.home() / ".aether_cache" / "sprint9_heat_stage_b"

# Benchmark bbox (eval/benchmark/india_nw_heatwave_2022_04.yaml)
LAT_MAX, LAT_MIN = 32.875, 22.375
LON_MIN, LON_MAX = 67.875, 84.375

TMAX_HOURS_UTC = list(range(6, 14))  # 06..13 — pre-registered (§2)
SEASON_START = (3, 13)
SEASON_END = (5, 1)
YEARS = [*range(1991, 2021), 2022]

WINDOW_24H_START = date(2022, 4, 2)
WINDOW_24H_END = date(2022, 4, 11)


def season_dates(year: int) -> list[date]:
    """Mar 13 - May 1, Feb-29-free by construction (uniform 50-day axis)."""
    d0, d1 = date(year, *SEASON_START), date(year, *SEASON_END)
    out = []
    d = d0
    while d <= d1:
        out.append(d)
        d += timedelta(days=1)
    return out


def fetch_year(ds: xr.Dataset, year: int) -> None:
    cache = CACHE_DIR / f"era5_tmax_{year}.npz"
    if cache.exists():
        return
    dates = season_dates(year)
    times = np.array(
        [np.datetime64(f"{d.isoformat()}T{h:02d}:00") for d in dates for h in TMAX_HOURS_UTC]
    )
    t0 = time.time()
    block = (
        ds["2m_temperature"]
        .sel(latitude=slice(LAT_MAX, LAT_MIN), longitude=slice(LON_MIN, LON_MAX))
        .sel(time=times)
        .values.astype(np.float32)
    )
    n_h = len(TMAX_HOURS_UTC)
    cube = block.reshape(len(dates), n_h, *block.shape[1:])
    tmax = cube.max(axis=1)
    hour_of_max = np.array(TMAX_HOURS_UTC, dtype=np.int16)[cube.argmax(axis=1)]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, tmax=tmax, hour_of_max=hour_of_max)
    print(f"  {year}: {block.shape[0]} hours in {time.time() - t0:.0f}s", flush=True)


def fetch_window_24h(ds: xr.Dataset) -> None:
    """All 24 hours for the canonical window days (the S3 hour-set residual)."""
    cache = CACHE_DIR / "era5_t2m_24h_2022_window.npz"
    if cache.exists():
        return
    days = []
    d = WINDOW_24H_START
    while d <= WINDOW_24H_END:
        days.append(d)
        d += timedelta(days=1)
    times = np.array(
        [np.datetime64(f"{d.isoformat()}T{h:02d}:00") for d in days for h in range(24)]
    )
    t0 = time.time()
    block = (
        ds["2m_temperature"]
        .sel(latitude=slice(LAT_MAX, LAT_MIN), longitude=slice(LON_MIN, LON_MAX))
        .sel(time=times)
        .values.astype(np.float32)
    )
    cube = block.reshape(len(days), 24, *block.shape[1:])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, t2m=cube)
    print(f"  24h window: {block.shape[0]} hours in {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    ds = xr.open_zarr(ARCO_V3, consolidated=True, storage_options={"token": "anon"})
    if len(sys.argv) > 2 and sys.argv[1] == "--prime":
        for year in (int(y) for y in sys.argv[2:]):
            fetch_year(ds, year)
        print("prime done", flush=True)
        return
    for year in YEARS:
        fetch_year(ds, year)
    fetch_window_24h(ds)
    print("era5 tmax cache complete", flush=True)


if __name__ == "__main__":
    main()
