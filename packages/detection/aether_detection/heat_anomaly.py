"""Heat-vertical anomaly primitives (Sprint 9 Stage B).

Pure-array building blocks for the AIR lane (ERA5 / IMD gridded daily Tmax)
and the criterion machinery shared with the LST lane. Everything here is
sensor-agnostic and unit-testable offline: arrays in, diagnostics out. Data
acquisition lives in scripts/; this module never touches the network.

Definitions follow the PRE-REGISTERED design (docs/science/
sprint9_heat_validation.md §2): day-of-year climatology with a ±window mean,
anomalies always against the same dataset's own climatology, and the IMD-style
qualifying criterion (Tmax ≥ 40 °C AND anomaly ≥ +4.5 K) from IMD's published
heat-wave definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np

# IMD-style criterion (verbatim thresholds from IMD's plains heat-wave
# definition, quoted in Srivastava et al. 2024 §2 / the Stage A report).
IMD_ABS_THRESHOLD_K = 313.15  # 40 degC
IMD_DEPARTURE_K = 4.5

EARTH_RADIUS_KM = 6371.0088

# IMD gridded daily Tmax product constants (layout verified empirically in the
# Stage A probe: lat-major float32-LE, 99.9 = missing).
IMD_GRID_LATS = np.arange(7.5, 37.5 + 0.5, 1.0)
IMD_GRID_LONS = np.arange(67.5, 97.5 + 0.5, 1.0)
IMD_MISSING = 99.9


def read_imd_maxtemp_grd(path: Path, year: int) -> np.ndarray:
    """Read one IMD gridded daily-Tmax year file -> (n_days, 31 lat, 31 lon) degC.

    Missing values (99.9) become NaN. The file is day-major, then lat-major
    (verified against ISD/ERA5 in the Stage A probe, not assumed from the
    sample readers).
    """
    raw = np.fromfile(path, dtype="<f4")
    n_days = 366 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 365
    expected = n_days * 31 * 31
    if raw.size != expected:
        raise ValueError(f"{path}: {raw.size} floats, expected {expected} for {year}")
    cube = raw.reshape(n_days, 31, 31)
    cube = np.where(np.isclose(cube, IMD_MISSING, atol=0.05), np.nan, cube)
    return cube.astype(np.float32)


def day_window_climatology(
    base: np.ndarray, day_index: int, half_window: int
) -> np.ndarray:
    """Mean over (years × ±half_window days) for one target day.

    `base` is (n_years, n_days, ...); the window is clipped at the array edges
    (the fetch is sized so canonical-window days are never clipped).
    """
    lo = max(day_index - half_window, 0)
    hi = min(day_index + half_window + 1, base.shape[1])
    window = base[:, lo:hi].reshape(-1, *base.shape[2:])
    return np.nanmean(window, axis=0)


def qualifying_mask(
    tmax_k: np.ndarray,
    clim_mean_k: np.ndarray,
    valid: np.ndarray,
    abs_threshold_k: float = IMD_ABS_THRESHOLD_K,
    departure_k: float = IMD_DEPARTURE_K,
) -> np.ndarray:
    """IMD-style qualifying cells: hot in absolute terms AND anomalously hot."""
    with np.errstate(invalid="ignore"):
        return (
            (tmax_k >= abs_threshold_k)
            & (tmax_k - clim_mean_k >= departure_k)
            & valid
            & ~np.isnan(tmax_k)
        )


def cell_areas_km2(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """(ny, nx) areas of regular lat/lon cells, cos(lat)-weighted."""
    dlat = float(abs(lats[1] - lats[0])) if lats.size > 1 else 1.0
    dlon = float(abs(lons[1] - lons[0])) if lons.size > 1 else 1.0
    km_per_deg = EARTH_RADIUS_KM * np.pi / 180.0
    cell_h = dlat * km_per_deg
    cell_w = dlon * km_per_deg * np.cos(np.deg2rad(lats))
    return np.outer(cell_h * cell_w, np.ones(lons.size))


@dataclass(frozen=True)
class DurationRun:
    """A consecutive-day qualifying run containing the anchor day."""

    start: date
    end: date
    n_days: int
    hit_data_boundary: bool  # True => the run may extend beyond the computed days


def run_containing(
    dates: list[date],
    area_fracs: list[float],
    anchor: date,
    threshold: float,
) -> DurationRun:
    """The maximal consecutive run of days with area_frac >= threshold around anchor.

    `hit_data_boundary` is set when the run touches the first/last computed day
    — the duration is then a lower bound, and the caller must say so.
    """
    if anchor not in dates:
        raise ValueError(f"anchor {anchor} not in computed dates")
    i = dates.index(anchor)
    if area_fracs[i] < threshold:
        raise ValueError(
            f"anchor day {anchor} does not qualify (area_frac={area_fracs[i]:.3f} "
            f"< {threshold}) — duration undefined"
        )
    lo = i
    while lo - 1 >= 0 and area_fracs[lo - 1] >= threshold:
        lo -= 1
    hi = i
    while hi + 1 < len(dates) and area_fracs[hi + 1] >= threshold:
        hi += 1
    boundary = lo == 0 or hi == len(dates) - 1
    return DurationRun(
        start=dates[lo], end=dates[hi], n_days=hi - lo + 1, hit_data_boundary=boundary
    )


def coarsen_to_grid(
    fine: np.ndarray,
    fine_lats: np.ndarray,
    fine_lons: np.ndarray,
    coarse_lats: np.ndarray,
    coarse_lons: np.ndarray,
) -> np.ndarray:
    """Cell-mean coarsening of a fine regular grid onto a coarse regular grid.

    Used for the common-1°-grid comparisons (pre-registration V3/V4): each
    coarse cell is the nanmean of the fine cells whose centers fall inside it.
    """
    dlat = abs(coarse_lats[1] - coarse_lats[0]) / 2.0 if coarse_lats.size > 1 else 0.5
    dlon = abs(coarse_lons[1] - coarse_lons[0]) / 2.0 if coarse_lons.size > 1 else 0.5
    out = np.full((coarse_lats.size, coarse_lons.size), np.nan, dtype=np.float32)
    for i, clat in enumerate(coarse_lats):
        lat_sel = (fine_lats >= clat - dlat) & (fine_lats < clat + dlat)
        if not lat_sel.any():
            continue
        for j, clon in enumerate(coarse_lons):
            lon_sel = (fine_lons >= clon - dlon) & (fine_lons < clon + dlon)
            if not lon_sel.any():
                continue
            block = fine[np.ix_(lat_sel, lon_sel)]
            if np.isnan(block).all():
                continue
            out[i, j] = np.nanmean(block)
    return out


def window_dates(start: date, end: date) -> list[date]:
    out = []
    d = start
    while d <= end:
        out.append(d)
        d += timedelta(days=1)
    return out
