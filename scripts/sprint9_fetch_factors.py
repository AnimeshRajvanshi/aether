"""Sprint 9 Stage C — fetch the factor-diagnostic inputs (heat attribution).

Every factor hypothesis must bind to a computed diagnostic (the
no-fabrication-for-factors rule); this fetches the reanalysis inputs those
diagnostics are computed from, into the gitignored cache.

Variables and stores (cost-driven, documented):
- z500 CLIMATOLOGY (1991-2020, window days): the 6-hourly 240x121 (~1.5 deg)
  ARCO store — synoptic ridges are 1000-km features, so 1.5 deg is the right
  scale, and the 0.25-deg store's all-37-level chunks make a multi-decade z500
  climatology unaffordable (measured chunk economics, Stage A/B).
- z500 2022 window: the 0.25-deg v3 store (10 hour-chunks), coarsened to a
  regional mean at compute time. Cross-store caveat: the climatology grid is
  conservatively regridded; regional MEANS are preserved well by conservative
  regridding, and only regional means are compared (stated in the artifact).
- swvl1 (soil moisture), d2m (dewpoint), u10/v10 (winds): v3 store for both
  climatology and 2022 (absent from the coarse store) — single-level chunks,
  affordable. Daily 06:00 UTC (11:30 IST) sample.

Cache: ~/.aether_cache/sprint9_heat_stage_c/
Priming: `--prime <var> <year>...` fetches one variable's years and exits.
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import xarray as xr

V3 = "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
COARSE = (
    "gs://gcp-public-data-arco-era5/ar/"
    "1959-2022-6h-240x121_equiangular_with_poles_conservative.zarr"
)
CACHE = Path.home() / ".aether_cache" / "sprint9_heat_stage_c"

LAT_MAX, LAT_MIN = 32.875, 22.375
LON_MIN, LON_MAX = 67.875, 84.375
HOUR_UTC = 6  # 11:30 IST — shared sample hour for every factor variable

CLIM_YEARS = range(1991, 2021)
EVENT_YEAR = 2022

# Day ranges per variable family (calendar days, no Feb 29 issues in Mar/Apr).
SOIL_DAYS = (date(2000, 3, 1), date(2000, 4, 11))  # antecedent March + window
WINDOW_DAYS = (date(2000, 4, 2), date(2000, 4, 11))  # winds/dewpoint/z500


def drange(d0: date, d1: date, year: int) -> list[date]:
    out = []
    d = date(year, d0.month, d0.day)
    end = date(year, d1.month, d1.day)
    while d <= end:
        out.append(d)
        d += timedelta(days=1)
    return out


def fetch_v3_year(ds: xr.Dataset, var: str, year: int, days: tuple[date, date]) -> None:
    """One year's daily-06UTC field for `var` over the bbox -> npz."""
    out = CACHE / f"{var}_{year}.npz"
    if out.exists():
        return
    dates = drange(days[0], days[1], year)
    times = np.array([np.datetime64(f"{d.isoformat()}T{HOUR_UTC:02d}:00") for d in dates])
    sel = ds[var]
    if "level" in sel.dims:
        sel = sel.sel(level=500)
    t0 = time.time()
    block = (
        sel.sel(latitude=slice(LAT_MAX, LAT_MIN), longitude=slice(LON_MIN, LON_MAX))
        .sel(time=times)
        .values.astype(np.float32)
    )
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, field=block)
    print(f"  {var} {year}: {block.shape} in {time.time() - t0:.0f}s", flush=True)


def fetch_z500_climatology() -> None:
    """Regional-mean z500 (m) per (year, window day) from the coarse store."""
    out = CACHE / "z500_clim_regional.npz"
    if out.exists():
        return
    ds = xr.open_zarr(COARSE, consolidated=True, storage_options={"token": "anon"})
    g = ds["geopotential"].sel(level=500)
    # dims (time, longitude, latitude); coords ascending lon 0..358.5, lat -90..90
    lat = ds["latitude"].values
    lon = ds["longitude"].values
    lat_sel = (lat >= LAT_MIN) & (lat <= LAT_MAX)
    lon_sel = (lon >= LON_MIN) & (lon <= LON_MAX)
    w = np.cos(np.deg2rad(lat[lat_sel]))[None, :] * np.ones((int(lon_sel.sum()), 1))
    vals = np.zeros((len(list(CLIM_YEARS)), 10), dtype=np.float32)
    t0 = time.time()
    for yi, year in enumerate(CLIM_YEARS):
        dates = drange(WINDOW_DAYS[0], WINDOW_DAYS[1], year)
        times = np.array(
            [np.datetime64(f"{d.isoformat()}T{HOUR_UTC:02d}:00") for d in dates]
        )
        block = g.sel(time=times).values  # (10, n_lon, n_lat)
        sub = block[:, lon_sel][:, :, lat_sel] / 9.80665  # geopotential -> meters
        vals[yi] = (sub * w).sum(axis=(1, 2)) / w.sum()
        print(f"  z500 clim {year}: done ({time.time() - t0:.0f}s elapsed)", flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, regional_mean_m=vals, years=np.array(list(CLIM_YEARS)))
    print(f"wrote {out}", flush=True)


V3_PLAN: dict[str, tuple[tuple[date, date], list[int]]] = {
    "volumetric_soil_water_layer_1": (SOIL_DAYS, [*CLIM_YEARS, EVENT_YEAR]),
    "2m_dewpoint_temperature": (WINDOW_DAYS, [*CLIM_YEARS, EVENT_YEAR]),
    "10m_u_component_of_wind": (WINDOW_DAYS, [*CLIM_YEARS, EVENT_YEAR]),
    "10m_v_component_of_wind": (WINDOW_DAYS, [*CLIM_YEARS, EVENT_YEAR]),
    "geopotential": (WINDOW_DAYS, [EVENT_YEAR]),  # 2022 only; climatology is coarse-store
}


def main() -> None:
    ds = xr.open_zarr(V3, consolidated=True, storage_options={"token": "anon"})
    if len(sys.argv) > 3 and sys.argv[1] == "--prime":
        var = sys.argv[2]
        days, _years = V3_PLAN[var]
        for year in (int(y) for y in sys.argv[3:]):
            fetch_v3_year(ds, var, year, days)
        print("prime done", flush=True)
        return
    fetch_z500_climatology()
    for var, (days, years) in V3_PLAN.items():
        for year in years:
            fetch_v3_year(ds, var, year, days)
    print("factor fetch complete", flush=True)


if __name__ == "__main__":
    main()
