"""Sprint 9 Stage A — ERA5 percentile scan for flagship heat-event selection.

Cardinal rule 1 of the heat vertical: the flagship event is SELECTED BY THE
PROBE from reanalysis percentiles + documented reporting — never asserted from
training memory. This script is the reanalysis half of that selection.

Design (documented choices, all revisitable in Stage B at full rigor):

- Store: ARCO-ERA5 v3 (0.25 deg, hourly; the same store the methane pipeline
  already uses). Single store + single grid avoids cross-store regrid bias.
  Coverage measured (not assumed): final ERA5 to 2025-12-31, preliminary
  ERA5T to ~2026-06-05 (probe metadata, era5_metadata.json).
- Daily-max proxy: max of T2m at 09:00 and 10:00 UTC (14:30 / 15:30 IST) —
  the climatological afternoon peak over India. A 2-hour proxy slightly
  underestimates the true daily max, but it is applied identically to the
  baseline and the candidates, so percentile exceedance is consistent. Each
  extra hour costs one whole-globe chunk per day (the v3 chunk layout), so
  this is the cost/fidelity compromise; Stage B recomputes the selected
  event's numbers from all 24 hours.
- Season: Feb 19 - Jul 10 fetched (Feb 29 dropped for a uniform day axis) so
  that the Mar 1 - Jun 30 pre-monsoon scan days each have a +/-10-day
  climatology window. Indian heat events outside Mar-Jun would not be found
  by this scan — a stated scope choice, not a claim of nonexistence.
- Climatology: per gridpoint, per scan day, mean and 95th percentile of the
  proxy over 1991-2020 (WMO standard normals period) x (+/-10-day window)
  = 630 samples per cell/day.
- Domain: lat 6.5-37.5 N, lon 68-97.5 E, ERA5 land_sea_mask > 0.5. The bbox
  includes neighbouring countries; candidate geolocation is reconciled
  against documented reporting afterwards (the reporting half of rule 1).
- Daily event index, two families (both reported; selection uses the second):
  (1) PERCENTILE index: cos(lat)-weighted fraction of land cells with
      proxy > p95 ("area_frac"), severity = area-weighted mean of (proxy - p95)
      over exceeding cells, in K. Found defect (kept, documented): raw-K
      exceedances over the Himalaya/Tibetan-plateau cells inside the bbox are
      huge (snow/elevation variance), so this family's top windows centroid in
      the mountains, not where heatwaves affect people.
  (2) IMD-STYLE index: cells qualifying with proxy >= 40 degC (313.15 K) AND
      anomaly vs day-of-year climatological mean >= +4.5 K — IMD's published
      plains heat-wave criterion (Tmax >= 40 degC, departure >= 4.5 K) applied
      to the ERA5 proxy. The absolute threshold removes the plateau without an
      ad-hoc elevation mask. Same run/ranking construction as (1).
- Candidate window: contiguous run (1-day gaps tolerated) of days with
  area_frac >= 0.10 (family 1) or qualifying area_frac >= 0.05 (family 2,
  the 40 degC+4.5 K joint criterion is much stricter); ranked by the run's
  summed area_frac * severity.

Resumable: per-year proxy arrays cached under ~/.aether_cache/sprint9_heat_scan/.
Output: stage_a_outputs/sprint9_heat_probe/era5_scan_results.json
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

ARCO_V3 = "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"

CACHE_DIR = Path.home() / ".aether_cache" / "sprint9_heat_scan"
OUT_DIR = Path(__file__).resolve().parents[1] / "stage_a_outputs" / "sprint9_heat_probe"

LAT_MAX, LAT_MIN = 37.5, 6.5
LON_MIN, LON_MAX = 68.0, 97.5
PROXY_HOURS = (9, 10)  # UTC
BASELINE_YEARS = range(1991, 2021)  # WMO 1991-2020 normals
SCAN_YEARS = range(2013, 2027)  # Landsat 8 era onwards; 2026 is partial (ERA5T)
WINDOW_HALF_DAYS = 10
P_EXCEED = 95.0
AREA_FRAC_THRESHOLD = 0.10
IMD_ABS_THRESHOLD_K = 313.15  # 40 degC — IMD plains heat-wave absolute criterion
IMD_DEPARTURE_K = 4.5  # IMD heat-wave departure-from-normal criterion
IMD_AREA_FRAC_THRESHOLD = 0.05
MAX_GAP_DAYS = 1
MIN_RUN_DAYS = 3

# Fetch Feb 19 .. Jul 10 (no Feb 29): uniform 142-day axis per year.
SEASON_START = (2, 19)
SEASON_END = (7, 10)
SCAN_START = (3, 1)
SCAN_END = (6, 30)


def season_dates(year: int) -> list[date]:
    """All dates Feb 19 - Jul 10 of `year`, Feb 29 excluded (uniform axis)."""
    d0 = date(year, *SEASON_START)
    d1 = date(year, *SEASON_END)
    out: list[date] = []
    d = d0
    while d <= d1:
        if not (d.month == 2 and d.day == 29):
            out.append(d)
        d += timedelta(days=1)
    return out


def fetch_year_proxy(ds: xr.Dataset, year: int) -> np.ndarray | None:
    """Daily-max proxy (max over PROXY_HOURS) for one season-year, cached.

    Returns array (n_days, n_lat, n_lon) float32, or None when the store has
    no data for the requested season (partial final year).
    """
    cache = CACHE_DIR / f"tmax_proxy_{year}.npz"
    if cache.exists():
        return np.asarray(np.load(cache)["tmax"])

    dates = season_dates(year)
    times = np.array(
        [np.datetime64(f"{d.isoformat()}T{h:02d}:00") for d in dates for h in PROXY_HOURS]
    )
    t2m = ds["2m_temperature"].sel(
        latitude=slice(LAT_MAX, LAT_MIN), longitude=slice(LON_MIN, LON_MAX)
    )
    avail = t2m.time.values
    if times[-1] > avail[-1]:
        usable = times[times <= avail[-1]]
        if usable.size < 2 * 30:  # under a month of season data: skip the year
            print(f"  {year}: insufficient coverage in store, skipped", flush=True)
            return None
        times = usable
    t0 = time.time()
    block = t2m.sel(time=times).values.astype(np.float32)  # (n_times, ny, nx)
    n_days = block.shape[0] // len(PROXY_HOURS)
    block = block[: n_days * len(PROXY_HOURS)]
    proxy = block.reshape(n_days, len(PROXY_HOURS), *block.shape[1:]).max(axis=1)
    # Pad a truncated final year with NaN days so every cached year is 142 long.
    full = np.full((len(dates), *proxy.shape[1:]), np.nan, dtype=np.float32)
    full[: proxy.shape[0]] = proxy
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, tmax=full)
    print(f"  {year}: fetched {block.shape[0]} hours in {time.time() - t0:.0f}s", flush=True)
    return full


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ds = xr.open_zarr(ARCO_V3, consolidated=True, storage_options={"token": "anon"})

    # Cache-priming mode: `... --prime 1997 1998 ...` fetches only those years'
    # proxy caches and exits. Lets several processes prime disjoint year ranges
    # concurrently; the final full run then assembles from cache.
    if len(sys.argv) > 2 and sys.argv[1] == "--prime":
        for year in (int(y) for y in sys.argv[2:]):
            fetch_year_proxy(ds, year)
        print("prime done", flush=True)
        return

    t2m0 = ds["2m_temperature"].sel(
        latitude=slice(LAT_MAX, LAT_MIN), longitude=slice(LON_MIN, LON_MAX)
    )
    lats = t2m0.latitude.values
    lons = t2m0.longitude.values

    # The v3 time axis is allocated 1900-2050 but valid data starts 1940
    # (store attrs) — sample the static mask at a date that certainly has data,
    # not at index 0.
    lsm = (
        ds["land_sea_mask"]
        .sel(latitude=slice(LAT_MAX, LAT_MIN), longitude=slice(LON_MIN, LON_MAX))
        .sel(time="2000-01-01T00:00", method="nearest")
        .values
    )
    land = lsm > 0.5
    n_land = int(land.sum())
    print(f"domain {lats.shape[0]}x{lons.shape[0]}, land cells: {n_land}", flush=True)
    if n_land == 0:
        raise RuntimeError("land mask empty — refusing to scan a domain with no land cells")

    all_years = sorted(set(BASELINE_YEARS) | set(SCAN_YEARS))
    proxies: dict[int, np.ndarray] = {}
    for year in all_years:
        arr = fetch_year_proxy(ds, year)
        if arr is not None:
            proxies[year] = arr

    dates_template = season_dates(2013)  # non-leap layout; Feb 29 dropped anyway
    n_days = len(dates_template)
    scan_idx = [
        i
        for i, d in enumerate(dates_template)
        if (d.month, d.day) >= SCAN_START and (d.month, d.day) <= SCAN_END
    ]

    # ---- climatology: mean + p95 per scan day per cell over baseline years ----
    base = np.stack([proxies[y] for y in BASELINE_YEARS], axis=0)  # (30, 142, ny, nx)
    clim_mean = np.empty((len(scan_idx), *base.shape[2:]), dtype=np.float32)
    clim_p95 = np.empty_like(clim_mean)
    t0 = time.time()
    for j, di in enumerate(scan_idx):
        lo, hi = di - WINDOW_HALF_DAYS, di + WINDOW_HALF_DAYS + 1
        lo = max(lo, 0)
        hi = min(hi, n_days)
        window = base[:, lo:hi].reshape(-1, *base.shape[2:])
        clim_mean[j] = window.mean(axis=0)
        clim_p95[j] = np.percentile(window, P_EXCEED, axis=0)
    print(f"climatology computed in {time.time() - t0:.0f}s", flush=True)

    w = np.cos(np.deg2rad(lats))[:, None] * np.ones((1, lons.size))
    w_land = np.where(land, w, 0.0)
    w_land_total = w_land.sum()

    # ---- daily indices for scan years (two families; see module docstring) ----
    def day_record(
        year: int, di: int, j: int, day: np.ndarray, qualify: np.ndarray, ref: np.ndarray
    ) -> dict[str, Any]:
        """One daily record: area fraction, severity vs `ref`, geolocation."""
        anom = day - clim_mean[j]
        w_ex = np.where(qualify, w, 0.0)
        area_frac = float(w_ex.sum() / w_land_total)
        if w_ex.sum() > 0:
            sev = float(((day - ref) * w_ex).sum() / w_ex.sum())
            ci = (np.arange(lats.size)[:, None] * w_ex).sum() / w_ex.sum()
            cj = (np.arange(lons.size)[None, :] * w_ex).sum() / w_ex.sum()
            masked_anom = np.where(qualify, anom, -np.inf)
            pk = np.unravel_index(int(np.argmax(masked_anom)), masked_anom.shape)
            peak_anom = float(anom[pk])
            peak_lat, peak_lon = float(lats[pk[0]]), float(lons[pk[1]])
            cen_lat = float(np.interp(ci, np.arange(lats.size), lats))
            cen_lon = float(np.interp(cj, np.arange(lons.size), lons))
        else:
            sev, peak_anom = 0.0, 0.0
            cen_lat = cen_lon = peak_lat = peak_lon = float("nan")
        d = dates_template[di]
        return {
            "date": date(year, d.month, d.day).isoformat(),
            "year": year,
            "area_frac": round(area_frac, 4),
            "severity_k": round(sev, 3),
            "centroid": [round(cen_lat, 2), round(cen_lon, 2)],
            "peak_anom_k": round(peak_anom, 2),
            "peak_cell": [peak_lat, peak_lon],
        }

    daily_p95: list[dict[str, Any]] = []
    daily_imd: list[dict[str, Any]] = []
    for year in SCAN_YEARS:
        if year not in proxies:
            continue
        arr = proxies[year]
        for j, di in enumerate(scan_idx):
            day = arr[di]
            if np.isnan(day).all():
                continue
            valid = land & ~np.isnan(day)
            exceed_p95 = (day > clim_p95[j]) & valid
            daily_p95.append(day_record(year, di, j, day, exceed_p95, clim_p95[j]))
            qualify_imd = (
                (day >= IMD_ABS_THRESHOLD_K)
                & (day - clim_mean[j] >= IMD_DEPARTURE_K)
                & valid
            )
            daily_imd.append(day_record(year, di, j, day, qualify_imd, clim_mean[j]))

    def find_runs(daily: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
        """Contiguous high-area runs (1-day gaps tolerated), ranked by score."""
        candidates: list[dict[str, Any]] = []
        run: list[dict[str, Any]] = []
        gap = 0
        for rec in daily:
            if rec["area_frac"] >= threshold:
                run.append(rec)
                gap = 0
            elif run and gap < MAX_GAP_DAYS:
                gap += 1
            else:
                if len(run) >= MIN_RUN_DAYS:
                    candidates.append(_summarize_run(run))
                run, gap = [], 0
        if len(run) >= MIN_RUN_DAYS:
            candidates.append(_summarize_run(run))
        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates

    candidates_p95 = find_runs(daily_p95, AREA_FRAC_THRESHOLD)
    candidates = find_runs(daily_imd, IMD_AREA_FRAC_THRESHOLD)
    out = {
        "design": {
            "store": ARCO_V3,
            "proxy_hours_utc": list(PROXY_HOURS),
            "baseline_years": [BASELINE_YEARS.start, BASELINE_YEARS.stop - 1],
            "scan_years": [SCAN_YEARS.start, SCAN_YEARS.stop - 1],
            "percentile": P_EXCEED,
            "window_half_days": WINDOW_HALF_DAYS,
            "area_frac_threshold_p95": AREA_FRAC_THRESHOLD,
            "imd_style": {
                "abs_threshold_k": IMD_ABS_THRESHOLD_K,
                "departure_k": IMD_DEPARTURE_K,
                "area_frac_threshold": IMD_AREA_FRAC_THRESHOLD,
            },
            "domain": {"lat": [LAT_MIN, LAT_MAX], "lon": [LON_MIN, LON_MAX], "mask": "lsm>0.5"},
        },
        "candidates_imd_style": candidates,
        "candidates_p95": candidates_p95,
        "daily_imd_top50": sorted(daily_imd, key=lambda r: r["area_frac"], reverse=True)[:50],
    }
    out_path = OUT_DIR / "era5_scan_results.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(
        f"\nIMD-style: {len(candidates)} candidate windows "
        f"(p95 family: {len(candidates_p95)}) -> {out_path}",
        flush=True,
    )
    for c in candidates[:12]:
        print(
            f"  {c['start']}..{c['end']}  score={c['score']:.2f} "
            f"peak_area={c['peak_area_frac']:.2f} peak_anom={c['peak_anom_k']:.1f}K "
            f"centroid~({c['mean_centroid'][0]:.1f},{c['mean_centroid'][1]:.1f})"
        )


def _summarize_run(run: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse a run of daily records into one ranked candidate window."""
    score = sum(r["area_frac"] * r["severity_k"] for r in run)
    peak_day = max(run, key=lambda r: r["area_frac"])
    cen = np.array([r["centroid"] for r in run if not np.isnan(r["centroid"][0])])
    return {
        "start": run[0]["date"],
        "end": run[-1]["date"],
        "n_days": len(run),
        "score": round(float(score), 3),
        "peak_area_frac": peak_day["area_frac"],
        "peak_area_date": peak_day["date"],
        "peak_anom_k": max(r["peak_anom_k"] for r in run),
        "mean_centroid": [round(float(cen[:, 0].mean()), 2), round(float(cen[:, 1].mean()), 2)]
        if cen.size
        else [float("nan"), float("nan")],
        "days": run,
    }


if __name__ == "__main__":
    main()
