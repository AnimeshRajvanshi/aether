"""Sprint 9 Stage B — heat-event AIR-lane runner (event-parameterized).

Computes, for one registered heat event, the pre-registered quantification
analogues (C1-C4), sensitivities (S1-S4), the V1-V4 validation comparisons,
and the uncertainty budgets — exactly as fixed in advance by
docs/science/sprint9_heat_validation.md (committed before any station data was
read; deviations would be reported, not silently absorbed).

Same registry discipline as scripts/run_event_quantification.py: one shared
code path, parameterized by HEAT_EVENTS — no per-event fork.

Inputs (gitignored cache, fetched by the sprint9_fetch_* scripts):
  era5_tmax_<year>.npz, era5_t2m_24h_2022_window.npz,
  imd_maxtemp/maxtemp_<year>.grd, isd_2022/<station>.csv (+ isd-history.csv).
Outputs (committed; ISD/IMD content is DERIVED STATISTICS ONLY, with
provenance + verbatim license note per the interim review ruling):
  stage_b_outputs/<event_id>/air_lane.json
  stage_b_outputs/<event_id>/validation.json
  stage_b_outputs/<event_id>/anomaly_air_window_mean.png

Run: uv run python scripts/run_heat_stage_b.py india_nw_heatwave_2022_04
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from aether_data_spine.isd import daily_tmax
from aether_detection.heat_anomaly import (
    cell_areas_km2,
    coarsen_to_grid,
    day_window_climatology,
    qualifying_mask,
    read_imd_maxtemp_grd,
    run_containing,
    window_dates,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".aether_cache" / "sprint9_heat_stage_b"
ISD_HISTORY = Path.home() / ".aether_cache" / "sprint9_heat_scan" / "isd-history.csv"
ARCO_V3 = "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"

ISD_LICENSE_VERBATIM = (
    "The non-U.S. data in ISD are subject to WMO Resolution 40 restrictions, "
    "and cannot be redistributed to other users or customers."
)


@dataclass(frozen=True)
class HeatEvent:
    event_id: str
    lat_max: float
    lat_min: float
    lon_min: float
    lon_max: float
    window_start: date
    window_end: date
    anchor: date  # peak-area day from the Stage A scan
    baseline_years: tuple[int, int]
    season_start: tuple[int, int]  # cache layout (must match the fetch script)
    season_end: tuple[int, int]
    area_frac_threshold: float


HEAT_EVENTS: dict[str, HeatEvent] = {
    "india_nw_heatwave_2022_04": HeatEvent(
        event_id="india_nw_heatwave_2022_04",
        lat_max=32.875,
        lat_min=22.375,
        lon_min=67.875,
        lon_max=84.375,
        window_start=date(2022, 4, 2),
        window_end=date(2022, 4, 11),
        anchor=date(2022, 4, 8),
        baseline_years=(1991, 2020),
        season_start=(3, 13),
        season_end=(5, 1),
        area_frac_threshold=0.05,
    ),
}

HALF_WINDOW = 10  # pre-registered ±10-day climatology window


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #


def season_dates(ev: HeatEvent, year: int) -> list[date]:
    return window_dates(date(year, *ev.season_start), date(year, *ev.season_end))


def load_era5(ev: HeatEvent) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(base (30,50,ny,nx) K, event (50,ny,nx) K, lats, lons)."""
    years = range(ev.baseline_years[0], ev.baseline_years[1] + 1)
    arrs = []
    for year in years:
        path = CACHE / f"era5_tmax_{year}.npz"
        if not path.exists():
            raise FileNotFoundError(f"missing ERA5 cache year {year} — run the fetch first")
        arrs.append(np.asarray(np.load(path)["tmax"]))
    base = np.stack(arrs, axis=0)
    event = np.asarray(np.load(CACHE / f"era5_tmax_{ev.window_start.year}.npz")["tmax"])
    ds = xr.open_zarr(ARCO_V3, consolidated=True, storage_options={"token": "anon"})
    sub = ds["2m_temperature"].sel(
        latitude=slice(ev.lat_max, ev.lat_min), longitude=slice(ev.lon_min, ev.lon_max)
    )
    lats, lons = sub.latitude.values, sub.longitude.values
    return base, event, lats, lons


def load_era5_land(ev: HeatEvent, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    ds = xr.open_zarr(ARCO_V3, consolidated=True, storage_options={"token": "anon"})
    lsm = (
        ds["land_sea_mask"]
        .sel(latitude=slice(ev.lat_max, ev.lat_min), longitude=slice(ev.lon_min, ev.lon_max))
        .sel(time="2000-01-01T00:00", method="nearest")
        .values
    )
    assert lsm.shape == (lats.size, lons.size)
    return lsm > 0.5


def load_imd(ev: HeatEvent) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(base (30,50,nlat,nlon) degC on the cache day axis, event, lats, lons).

    IMD files are full calendar years; we slice the same Mar 13 - May 1 day
    axis the ERA5 cache uses, and the in-bbox 1-degree cells.
    """
    from aether_detection.heat_anomaly import IMD_GRID_LATS, IMD_GRID_LONS

    lat_sel = (ev.lat_min <= IMD_GRID_LATS) & (ev.lat_max >= IMD_GRID_LATS)
    lon_sel = (ev.lon_min <= IMD_GRID_LONS) & (ev.lon_max >= IMD_GRID_LONS)
    lats = IMD_GRID_LATS[lat_sel]
    lons = IMD_GRID_LONS[lon_sel]

    def year_slice(year: int) -> np.ndarray:
        path = CACHE / "imd_maxtemp" / f"maxtemp_{year}.grd"
        if not path.exists():
            raise FileNotFoundError(f"missing IMD year {year} — refusing a partial baseline")
        cube = read_imd_maxtemp_grd(path, year)
        idx = np.array([(d - date(year, 1, 1)).days for d in season_dates(ev, year)])
        return cube[np.ix_(idx, np.nonzero(lat_sel)[0], np.nonzero(lon_sel)[0])]

    years = range(ev.baseline_years[0], ev.baseline_years[1] + 1)
    base = np.stack([year_slice(y) for y in years], axis=0)
    event = year_slice(ev.window_start.year)
    return base, event, lats, lons


# --------------------------------------------------------------------------- #
# core lane computation (shared by ERA5 [K] and IMD [degC])
# --------------------------------------------------------------------------- #


@dataclass
class LaneResult:
    dates: list[date]
    anomaly: np.ndarray  # (n_days, ny, nx)
    tmax: np.ndarray
    clim: np.ndarray
    area_fracs: list[float]
    qualify: np.ndarray  # (n_days, ny, nx) bool


def compute_lane(
    ev: HeatEvent,
    base: np.ndarray,
    event: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    valid: np.ndarray,
    unit_offset_k: float,
    half_window: int = HALF_WINDOW,
    base_year_slice: slice | None = None,
) -> LaneResult:
    """Anomalies + qualifying area fractions for the computable day range.

    `unit_offset_k`: 0 for arrays already in K; 273.15 for degC arrays (the
    criterion constants are in K).
    """
    if base_year_slice is not None:
        base = base[base_year_slice]
    all_dates = season_dates(ev, ev.window_start.year)
    computable = [
        i
        for i in range(len(all_dates))
        if i - half_window >= 0 and i + half_window < len(all_dates)
    ]
    areas = cell_areas_km2(lats, lons)
    area_total = float((areas * valid).sum())
    out_dates: list[date] = []
    anoms, tmaxs, clims, fracs, quals = [], [], [], [], []
    for i in computable:
        clim = day_window_climatology(base, i, half_window)
        day = event[i]
        qual = qualifying_mask(
            day + unit_offset_k, clim + unit_offset_k, valid,
        )
        out_dates.append(all_dates[i])
        anoms.append(day - clim)
        tmaxs.append(day)
        clims.append(clim)
        quals.append(qual)
        fracs.append(float((areas * qual).sum() / area_total))
    return LaneResult(
        dates=out_dates,
        anomaly=np.stack(anoms),
        tmax=np.stack(tmaxs),
        clim=np.stack(clims),
        area_fracs=fracs,
        qualify=np.stack(quals),
    )


def window_indices(lane: LaneResult, ev: HeatEvent) -> list[int]:
    return [
        i for i, d in enumerate(lane.dates) if ev.window_start <= d <= ev.window_end
    ]


def regional_mean(arr: np.ndarray, valid: np.ndarray, areas: np.ndarray) -> float:
    w = np.where(valid & ~np.isnan(arr), areas, 0.0)
    return float(np.nansum(np.where(valid, arr, np.nan) * w) / w.sum())


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def main() -> None:
    event_id = sys.argv[1] if len(sys.argv) > 1 else "india_nw_heatwave_2022_04"
    ev = HEAT_EVENTS[event_id]
    out_dir = REPO_ROOT / "stage_b_outputs" / ev.event_id
    out_dir.mkdir(parents=True, exist_ok=True)
    accessed = datetime.now(UTC).strftime("%Y-%m-%d")

    # ---------------- ERA5 lane (K) ----------------
    base, event, lats, lons = load_era5(ev)
    land = load_era5_land(ev, lats, lons)
    # Grid + land mask cached so the eval-harness heat recipe re-runs fully
    # offline from the same cache (no zarr open needed for regression).
    np.savez_compressed(
        CACHE / f"era5_grid_{ev.event_id}.npz", lats=lats, lons=lons, land=land
    )
    areas = cell_areas_km2(lats, lons)
    lane = compute_lane(ev, base, event, lats, lons, land, unit_offset_k=0.0)
    widx = window_indices(lane, ev)

    # C1 peak Tmax (window, land cells)
    win_tmax = np.where(land, lane.tmax[widx], np.nan)
    c1_peak_k = float(np.nanmax(win_tmax))
    pk = np.unravel_index(int(np.nanargmax(win_tmax)), win_tmax.shape)
    c1: dict[str, object] = {
        "value_c": round(c1_peak_k - 273.15, 2),
        "date": lane.dates[widx[pk[0]]].isoformat(),
        "lat": float(lats[pk[1]]),
        "lon": float(lons[pk[2]]),
        "definition": "max over window days x bbox land cells of ERA5 daily Tmax (06-13 UTC)",
    }

    # C2 anomalies: peak regional-mean + peak cell + window-mean regional-mean
    reg_anom_by_day = [
        regional_mean(lane.anomaly[i], land, areas) for i in widx
    ]
    win_anom = np.where(land, lane.anomaly[widx], np.nan)
    c2 = {
        "peak_regional_mean_anomaly_k": round(max(reg_anom_by_day), 2),
        "peak_regional_mean_anomaly_date": lane.dates[
            widx[int(np.argmax(reg_anom_by_day))]
        ].isoformat(),
        "window_mean_regional_mean_anomaly_k": round(float(np.mean(reg_anom_by_day)), 3),
        "peak_cell_anomaly_k": round(float(np.nanmax(win_anom)), 2),
        "definition": "anomaly vs own 1991-2020 +/-10d climatology, daily Tmax 06-13 UTC",
    }

    # C3 duration
    run = run_containing(lane.dates, lane.area_fracs, ev.anchor, ev.area_frac_threshold)
    c3 = {
        "n_days": run.n_days,
        "start": run.start.isoformat(),
        "end": run.end.isoformat(),
        "hit_data_boundary": run.hit_data_boundary,
        "criterion": f"area_frac >= {ev.area_frac_threshold} (IMD-style qualifying cells)",
    }

    # C4 peak-day extent
    peak_day_idx = widx[int(np.argmax([lane.area_fracs[i] for i in widx]))]
    c4 = {
        "peak_day": lane.dates[peak_day_idx].isoformat(),
        "extent_km2": round(float((areas * lane.qualify[peak_day_idx]).sum()), -2),
        "area_frac": round(lane.area_fracs[peak_day_idx], 4),
    }

    # ---------------- sensitivities ----------------
    # S1 baseline halves
    s1: dict[str, dict[str, float]] = {}
    for label, sl in [("1991-2005", slice(0, 15)), ("2006-2020", slice(15, 30))]:
        lane_h = compute_lane(
            ev, base, event, lats, lons, land, unit_offset_k=0.0, base_year_slice=sl
        )
        widx_h = window_indices(lane_h, ev)
        peak_h = widx_h[int(np.argmax([lane_h.area_fracs[i] for i in widx_h]))]
        s1[label] = {
            "window_mean_regional_mean_anomaly_k": round(
                float(
                    np.mean(
                        [regional_mean(lane_h.anomaly[i], land, areas) for i in widx_h]
                    )
                ),
                3,
            ),
            "peak_day_extent_km2": round(
                float((areas * lane_h.qualify[peak_h]).sum()), -2
            ),
        }

    # S2 ±15-day window
    lane_15 = compute_lane(ev, base, event, lats, lons, land, unit_offset_k=0.0, half_window=15)
    widx_15 = window_indices(lane_15, ev)
    s2: dict[str, float] = {
        "window_mean_regional_mean_anomaly_k": round(
            float(np.mean([regional_mean(lane_15.anomaly[i], land, areas) for i in widx_15])),
            3,
        )
    }

    # S3 hour-set residual: 06-13 max vs 24h max on window days
    cube24 = np.load(CACHE / "era5_t2m_24h_2022_window.npz")["t2m"]  # (10,24,ny,nx)
    tmax24 = cube24.max(axis=1)
    tmax_sub = cube24[:, 6:14].max(axis=1)
    diff = np.where(land, tmax24 - tmax_sub, np.nan)
    s3 = {
        "mean_residual_k": round(float(np.nanmean(diff)), 4),
        "p99_residual_k": round(float(np.nanpercentile(diff, 99)), 3),
        "max_residual_k": round(float(np.nanmax(diff)), 3),
        "note": "true 24h daily max minus the pre-registered 06-13 UTC max, window days",
    }

    # S4 extent under a p95-percentile criterion instead of IMD-style
    i_peak = peak_day_idx
    all_dates = season_dates(ev, ev.window_start.year)
    di = all_dates.index(lane.dates[i_peak])
    lo, hi = di - HALF_WINDOW, di + HALF_WINDOW + 1
    sample = base[:, lo:hi].reshape(-1, lats.size, lons.size)
    p95 = np.nanpercentile(sample, 95.0, axis=0)
    qual_p95 = (lane.tmax[i_peak] > p95) & land
    s4 = {
        "peak_day_extent_km2_p95_criterion": round(float((areas * qual_p95).sum()), -2),
        "peak_day_extent_km2_imd_criterion": c4["extent_km2"],
    }

    # ---------------- IMD lane (degC) ----------------
    imd_base, imd_event, imd_lats, imd_lons = load_imd(ev)
    imd_valid = ~np.isnan(imd_event).all(axis=0)
    imd_lane = compute_lane(
        ev, imd_base, imd_event, imd_lats, imd_lons, imd_valid, unit_offset_k=273.15
    )
    imd_areas = cell_areas_km2(imd_lats, imd_lons)
    imd_widx = window_indices(imd_lane, ev)
    imd_reg_anom = [
        regional_mean(imd_lane.anomaly[i], imd_valid, imd_areas) for i in imd_widx
    ]

    # ---------------- V3/V4 on the common 1-degree grid ----------------
    # ERA5 window-mean anomaly map coarsened onto the IMD in-bbox cells.
    era5_win_anom_map = np.nanmean(
        np.where(land, lane.anomaly[widx], np.nan), axis=0
    )
    era5_on_1deg = coarsen_to_grid(era5_win_anom_map, lats, lons, imd_lats, imd_lons)
    imd_win_anom_map = np.nanmean(
        np.where(imd_valid, imd_lane.anomaly[imd_widx], np.nan), axis=0
    )
    both = ~np.isnan(era5_on_1deg) & ~np.isnan(imd_win_anom_map)
    common_w = imd_areas * both
    era5_reg_1deg = float(
        np.nansum(np.where(both, era5_on_1deg, 0) * imd_areas) / common_w.sum()
    )
    imd_reg_1deg = float(
        np.nansum(np.where(both, imd_win_anom_map, 0) * imd_areas) / common_w.sum()
    )
    pattern_r = float(
        np.corrcoef(era5_on_1deg[both].ravel(), imd_win_anom_map[both].ravel())[0, 1]
    )
    v3 = {
        "era5_window_mean_regional_anomaly_k_common_grid": round(era5_reg_1deg, 3),
        "imd_window_mean_regional_anomaly_k_common_grid": round(imd_reg_1deg, 3),
        "abs_difference_k": round(abs(era5_reg_1deg - imd_reg_1deg), 3),
        "threshold_k": 1.0,
        "pattern_pearson_r": round(pattern_r, 3),
        "pattern_r_threshold": 0.6,
        "n_common_cells": int(both.sum()),
        "pass_v3a": bool(abs(era5_reg_1deg - imd_reg_1deg) <= 1.0),
        "pass_v3b": bool(pattern_r >= 0.6),
    }

    # V4a duration (IMD lane, same criterion); V4b extent on the common grid.
    try:
        imd_run = run_containing(
            imd_lane.dates, imd_lane.area_fracs, ev.anchor, ev.area_frac_threshold
        )
        imd_duration: int | None = imd_run.n_days
        imd_run_info = {
            "start": imd_run.start.isoformat(),
            "end": imd_run.end.isoformat(),
            "hit_data_boundary": imd_run.hit_data_boundary,
        }
    except ValueError as exc:
        imd_duration = None
        imd_run_info = {"error": str(exc)}
    # extent on common grid: coarsen ERA5 tmax+clim to 1deg, criterion there
    era5_tmax_1deg = coarsen_to_grid(
        np.where(land, lane.tmax[peak_day_idx], np.nan), lats, lons, imd_lats, imd_lons
    )
    era5_clim_1deg = coarsen_to_grid(
        np.where(land, lane.clim[peak_day_idx], np.nan), lats, lons, imd_lats, imd_lons
    )
    q_era5_1deg = qualifying_mask(
        era5_tmax_1deg, era5_clim_1deg, ~np.isnan(era5_tmax_1deg)
    )
    imd_peak_idx = imd_lane.dates.index(lane.dates[peak_day_idx])
    q_imd_1deg = imd_lane.qualify[imd_peak_idx]
    ext_era5 = float((imd_areas * q_era5_1deg).sum())
    ext_imd = float((imd_areas * q_imd_1deg).sum())
    rel = abs(ext_era5 - ext_imd) / max(ext_imd, 1e-9) if ext_imd > 0 else float("inf")
    v4 = {
        "duration_era5_days": run.n_days,
        "duration_imd_days": imd_duration,
        "imd_run": imd_run_info,
        "pass_v4a": bool(imd_duration is not None and abs(run.n_days - imd_duration) <= 2),
        "peak_day": lane.dates[peak_day_idx].isoformat(),
        "extent_common_grid_era5_km2": round(ext_era5, -2),
        "extent_common_grid_imd_km2": round(ext_imd, -2),
        "relative_difference": round(rel, 3),
        "pass_v4b": bool(rel <= 0.30),
    }

    # ---------------- V1/V2 stations (pre-registered; computed LAST) -------
    stations = []
    with ISD_HISTORY.open() as fh:
        for r in csv.DictReader(fh):
            if r["CTRY"] != "IN":
                continue
            try:
                slat, slon = float(r["LAT"]), float(r["LON"])
            except ValueError:
                continue
            if not (ev.lat_min <= slat <= ev.lat_max and ev.lon_min <= slon <= ev.lon_max):
                continue
            sid = f"{r['USAF']}{r['WBAN']}"
            path = CACHE / "isd_2022" / f"{sid}.csv"
            if path.exists():
                stations.append((sid, r["STATION NAME"].strip(), slat, slon, path))

    days = window_dates(ev.window_start, ev.window_end)
    per_station = []
    excluded = 0
    pairs: list[tuple[float, float]] = []
    for sid, name, slat, slon, path in stations:
        recs = daily_tmax(path, sid, days)
        if len(recs) < 7:  # pre-registered: >=7 of 10 window days
            excluded += 1
            continue
        li = int(np.argmin(np.abs(lats - slat)))
        lj = int(np.argmin(np.abs(lons - slon)))
        biases = []
        for rec in recs:
            di2 = lane.dates.index(rec.day)
            era5_c = float(lane.tmax[di2, li, lj]) - 273.15
            pairs.append((era5_c, rec.tmax_c))
            biases.append(era5_c - rec.tmax_c)
        per_station.append(
            {
                "station_id": sid,
                "name": name,
                "lat": slat,
                "lon": slon,
                "n_days": len(recs),
                "station_window_max_c": round(max(r.tmax_c for r in recs), 1),
                "mean_bias_era5_minus_station_k": round(float(np.mean(biases)), 2),
            }
        )

    era5_arr = np.array([p[0] for p in pairs])
    st_arr = np.array([p[1] for p in pairs])
    bias = era5_arr - st_arr
    v2 = {
        "n_stations": len(per_station),
        "n_excluded_lt7days": excluded,
        "n_station_days": len(pairs),
        "median_bias_k": round(float(np.median(bias)), 2),
        "rmsd_k": round(float(np.sqrt(np.mean(bias**2))), 2),
        "pearson_r": round(float(np.corrcoef(era5_arr, st_arr)[0, 1]), 3),
        "thresholds": {"median_bias_k": 1.5, "rmsd_k": 2.5, "pearson_r": 0.85},
        "pass_v2": bool(
            abs(np.median(bias)) <= 1.5
            and float(np.sqrt(np.mean(bias**2))) <= 2.5
            and float(np.corrcoef(era5_arr, st_arr)[0, 1]) >= 0.85
        ),
        "framing": (
            "CONSISTENCY at the truth anchor, NOT independent verification: "
            "ERA5 assimilates synoptic stations, including these."
        ),
    }
    station_max = float(max(s["station_window_max_c"] for s in per_station))
    v1 = {
        "era5_peak_c": float(c1["value_c"]),  # type: ignore[arg-type]
        "max_station_window_tmax_c": station_max,
        "bracket_k": 2.5,
        "pass_v1": bool(abs(float(c1["value_c"]) - station_max) <= 2.5),  # type: ignore[arg-type]
        "framing": "instrument validation of the EVENT's temperatures (stations are truth)",
    }

    # ---------------- budgets ----------------
    s1_anom_spread = abs(
        s1["1991-2005"]["window_mean_regional_mean_anomaly_k"]
        - s1["2006-2020"]["window_mean_regional_mean_anomaly_k"]
    )
    budgets = {
        "window_mean_regional_anomaly_k": {
            "central": c2["window_mean_regional_mean_anomaly_k"],
            "baseline_halves_half_spread_k": round(s1_anom_spread / 2, 3),
            "day_window_pm15_shift_k": round(
                abs(
                    float(s2["window_mean_regional_mean_anomaly_k"])
                    - float(c2["window_mean_regional_mean_anomaly_k"])  # type: ignore[arg-type]
                ),
                3,
            ),
            "hour_set_residual_k": s3["mean_residual_k"],
            "era5_vs_station_median_bias_k": v2["median_bias_k"],
        },
        "peak_day_extent_km2": {
            "central": c4["extent_km2"],
            "baseline_halves": [
                s1["1991-2005"]["peak_day_extent_km2"],
                s1["2006-2020"]["peak_day_extent_km2"],
            ],
            "criterion_p95_vs_imd": s4,
            "grid_1deg_vs_native": [v4["extent_common_grid_era5_km2"], c4["extent_km2"]],
        },
        "duration_days": {
            "central": run.n_days,
            "imd_lane": imd_duration,
        },
    }

    # ---------------- artifacts ----------------
    air = {
        "event_id": ev.event_id,
        "pre_registration": (
            "docs/science/sprint9_heat_validation.md (committed before computation)"
        ),
        "lane": "AIR (2 m air temperature) — never to be conflated with LST",
        "era5_store": ARCO_V3,
        "window": [ev.window_start.isoformat(), ev.window_end.isoformat()],
        "computable_days": [lane.dates[0].isoformat(), lane.dates[-1].isoformat()],
        "c1_peak_tmax": c1,
        "c2_anomaly": c2,
        "c3_duration": c3,
        "c4_extent": c4,
        "daily": [
            {
                "date": d.isoformat(),
                "area_frac": round(f, 4),
                "regional_mean_anomaly_k": round(
                    regional_mean(lane.anomaly[i], land, areas), 3
                ),
            }
            for i, (d, f) in enumerate(zip(lane.dates, lane.area_fracs, strict=True))
        ],
        "sensitivities": {"s1_baseline_halves": s1, "s2_window_pm15": s2,
                          "s3_hour_set": s3, "s4_criterion": s4},
        "budgets": budgets,
        "imd_lane_daily_window": [
            {"date": imd_lane.dates[i].isoformat(), "regional_mean_anomaly_k": round(a, 3)}
            for i, a in zip(imd_widx, imd_reg_anom, strict=True)
        ],
    }
    (out_dir / "air_lane.json").write_text(json.dumps(air, indent=2))

    validation = {
        "event_id": ev.event_id,
        "pre_registration": "docs/science/sprint9_heat_validation.md",
        "computed_after_pre_registration_commit": True,
        "v1_station_peak_bracket": v1,
        "v2_era5_station_consistency": v2,
        "v3_imd_anomaly_agreement": v3,
        "v4_duration_extent": v4,
        "per_station": sorted(per_station, key=lambda s: str(s["station_id"])),
        "provenance": {
            "isd_source": "NOAA NCEI global-hourly (anonymous), accessed " + accessed,
            "isd_license_verbatim": ISD_LICENSE_VERBATIM,
            "isd_handling": (
                "raw station files in gitignored cache only; this artifact carries "
                "derived comparison statistics (per-station bias/window-max summaries), "
                "never a re-hosted observation series (interim review ruling)"
            ),
            "imd_source": "IMD Pune gridded daily Tmax 1.0 deg (maxtemp.php), accessed " + accessed,
            "imd_handling": "raw .grd files in gitignored cache only; derived statistics committed",
        },
    }
    (out_dir / "validation.json").write_text(json.dumps(validation, indent=2))

    # window-mean anomaly map PNG
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(
        era5_win_anom_map,
        extent=(float(lons.min()), float(lons.max()), float(lats.min()), float(lats.max())),
        origin="upper",
        cmap="inferno",
        vmin=0,
        vmax=8,
    )
    fig.colorbar(im, ax=ax, label="window-mean Tmax anomaly (K), AIR lane (ERA5)")
    ax.set_title(
        f"{ev.event_id} — 2m-air Tmax anomaly, {ev.window_start}..{ev.window_end}\n"
        "vs own 1991-2020 ±10d climatology (06-13 UTC daily max)"
    )
    fig.savefig(out_dir / "anomaly_air_window_mean.png", dpi=150, bbox_inches="tight")

    print(json.dumps({"c1": c1, "c2": c2, "c3": c3, "c4": c4}, indent=1))
    print(json.dumps({"v1": v1, "v2": v2, "v3": v3, "v4": v4}, indent=1))
    print(f"wrote {out_dir}/air_lane.json, validation.json")


if __name__ == "__main__":
    main()
