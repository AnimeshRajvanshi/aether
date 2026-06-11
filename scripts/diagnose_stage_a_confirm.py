"""Confirm the three suspected bugs by re-running the MF with each one toggled.

NOT production code. Runs the per-column matched filter five times against the
real radiance + NASA target on the SAME inputs, with progressively NASA-faithful
choices:

  M0  current implementation              — our 3-window mask, fixed alpha=1e-9, no ppm_scaling
  M1  + apply ppm_scaling=100000          — H1 fix only (final multiply)
  M2  + use NASA's CH4 window [2137,2493] — H1 + H5 (band selection)
  M3  + LOOCV-fit shrinkage per column    — H1 + H5 + H2 (covariance method)
  M4  + EMIT 1275-1321 nm always-exclude  — full NASA replication

If H1+H2+H5 explain the failure, each step's Pearson should monotonically rise
toward NASA's L2B over the plume bbox. Tests no production code; modifies no
files in packages/.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import rioxarray
import scipy.linalg
import xarray as xr
from aether_detection import target_signature

# --------------------------------------------------------------------------- #
# Inputs (all cached locally from the failed Stage A run)
# --------------------------------------------------------------------------- #
RAD_PATH = Path(
    "/Users/animeshrajvanshi/.aether_cache/emit_l1b/downloads/"
    "19131fbb269a9cf4/EMIT_L1B_RAD_001_20220815T042838_2222703_003.nc"
)
L2B_PATH = Path(
    "/Users/animeshrajvanshi/.aether_cache/emit_l2b_ch4/"
    "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003/"
    "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003.tif"
)
TARGET_PATH = Path(
    "/Users/animeshrajvanshi/.aether_cache/emit_targets/emit20220815t042838_ch4_target"
)
OUR_NPZ = Path(
    "/Users/animeshrajvanshi/Documents/aether/stage_a_outputs/"
    "turkmenistan_goturdepe_2022_08_15/our_enhancement_raw.npz"
)

PPM_SCALING_NASA_DEFAULT = 100000.0
NASA_CH4_WINDOW = (2137.0, 2493.0)
NASA_EMIT_ALWAYS_EXCLUDE = (1275.0, 1321.0)

# Bounding box of plume region for the headline correlation statistic.
BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def select_indices(wl: np.ndarray, windows: list[tuple[float, float]]) -> np.ndarray:
    keep = np.zeros_like(wl, dtype=bool)
    for lo, hi in windows:
        keep |= (wl >= lo) & (wl <= hi)
    return np.nonzero(keep)[0]


def exclude_indices(idx: np.ndarray, wl: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Drop band indices whose wavelength falls in (lo, hi)."""
    keep = ~((wl[idx] > lo) & (wl[idx] < hi))
    return idx[keep]


def fit_looshrinkage_alpha(data: np.ndarray) -> float:
    """Theiler LOOCV shrinkage alpha — verbatim adaptation of NASA emit-sds/emit-ghg
    `fit_looshrinkage_alpha` (Apache-2.0 licensed); used here only for diagnostic
    comparison. Returns the alpha minimizing leave-one-out negative log-likelihood.
    """
    stability_scaling = 100.0
    nchan = data.shape[1]
    n = data.shape[0]
    X = data * stability_scaling
    S = np.cov(X.T, ddof=1)
    T = np.diag(np.diag(S))
    alphas = 10.0 ** np.arange(-10, 0 + 0.05, 0.05)
    nchanlog2pi = nchan * np.log(2.0 * np.pi)
    nll = np.full(len(alphas), np.inf)
    for i, alpha in enumerate(alphas):
        try:
            beta = (1.0 - alpha) / (n - 1.0)
            G = n * (beta * S) + (alpha * T)
            G_det = scipy.linalg.det(G, check_finite=False)
            if G_det == 0:
                continue
            r_k = (X.dot(scipy.linalg.inv(G, check_finite=False)) * X).sum(axis=1)
            q = 1.0 - beta * r_k
            nll[i] = (
                0.5 * (nchanlog2pi + np.log(G_det))
                + 1.0 / (2.0 * n) * (np.log(q) + r_k / q).sum()
            )
        except (np.linalg.LinAlgError, FloatingPointError):
            pass
    mindex = int(np.argmin(nll))
    return float(alphas[mindex]) if nll[mindex] != np.inf else 0.0


def run_mf(
    radiance: np.ndarray,
    wl: np.ndarray,
    k_full: np.ndarray,
    bad: np.ndarray,
    band_idx: np.ndarray,
    shrinkage_mode: str,          # 'fixed_tiny' (=1e-9) or 'looshrinkage'
    apply_ppm_scaling: bool,
    label: str,
) -> np.ndarray:
    t0 = time.time()
    rad_kept = radiance[:, :, band_idx].astype(np.float64)
    k_kept = k_full[band_idx]
    n_lines, n_cols, n_bands = rad_kept.shape
    out = np.full((n_lines, n_cols), np.nan, dtype=np.float64)

    for c in range(n_cols):
        col = rad_kept[:, c, :]
        good = ~bad[:, c]
        col_good = col[good]
        if col_good.shape[0] < n_bands + 2:
            continue
        mu_c = col_good.mean(axis=0)
        deviations = col_good - mu_c

        if shrinkage_mode == "fixed_tiny":
            alpha = 1e-9
            S = np.cov(deviations, rowvar=False, bias=False)
            T = np.diag(np.diag(S))
            C = (1.0 - alpha) * S + alpha * T
        else:
            alpha = fit_looshrinkage_alpha(deviations)
            S = np.cov(deviations, rowvar=False, bias=False)
            T = np.diag(np.diag(S))
            C = (1.0 - alpha) * S + alpha * T

        s_c = k_kept * mu_c
        try:
            z = np.linalg.solve(C, s_c)
        except np.linalg.LinAlgError:
            continue
        denom = float(s_c @ z)
        if not np.isfinite(denom) or denom == 0.0:
            continue
        col_minus_mu = col - mu_c
        alpha_col = (col_minus_mu @ z) / denom
        out[good, c] = alpha_col[good]

    if apply_ppm_scaling:
        out *= PPM_SCALING_NASA_DEFAULT
    print(f"  [{label}] done in {time.time() - t0:.1f}s  bands_used={band_idx.size}")
    return out


def pearson_in_bbox(ours: np.ndarray, nasa_grid: np.ndarray, lons: np.ndarray,
                    lats: np.ndarray) -> tuple[float, int]:
    in_bbox = (
        (lons >= BBOX["min_lon"])
        & (lons <= BBOX["max_lon"])
        & (lats >= BBOX["min_lat"])
        & (lats <= BBOX["max_lat"])
    )
    ok = in_bbox & np.isfinite(ours) & np.isfinite(nasa_grid)
    if int(ok.sum()) < 100:
        return float("nan"), int(ok.sum())
    return float(np.corrcoef(ours[ok], nasa_grid[ok])[0, 1]), int(ok.sum())


def stats(arr: np.ndarray) -> str:
    a = arr[np.isfinite(arr)]
    if a.size == 0:
        return "(all NaN)"
    return (
        f"p1={np.percentile(a, 1):+.3e}  p50={np.percentile(a, 50):+.3e}  "
        f"p99={np.percentile(a, 99):+.3e}"
    )


def main() -> None:
    print("Loading inputs...")
    ds_root = xr.open_dataset(RAD_PATH, engine="netcdf4")
    ds_sb = xr.open_dataset(RAD_PATH, engine="netcdf4", group="sensor_band_parameters")
    radiance = ds_root["radiance"].values
    wl = ds_sb["wavelengths"].values
    npz = np.load(OUR_NPZ)
    lons = npz["lon"]
    lats = npz["lat"]
    bad = npz["bad_pixel_mask"]
    _target_wl, k = target_signature.load_unit_absorption_spectrum(TARGET_PATH)
    print(f"  radiance.shape={radiance.shape}  bands_total={wl.size}")

    print("Sampling NASA L2B at L1B pixels...")
    l2b = rioxarray.open_rasterio(L2B_PATH, masked=True).squeeze("band", drop=True)
    transform = l2b.rio.transform()
    inv = ~transform
    cols_f, rows_f = inv * (lons.ravel(), lats.ravel())
    cols_i = np.round(cols_f).astype(np.int64)
    rows_i = np.round(rows_f).astype(np.int64)
    h, w = l2b.shape
    valid = (rows_i >= 0) & (rows_i < h) & (cols_i >= 0) & (cols_i < w)
    nasa = np.full(lons.size, np.nan)
    nasa[valid] = l2b.values[rows_i[valid], cols_i[valid]]
    nasa_grid = nasa.reshape(lons.shape)
    nasa_r, _n_nasa = pearson_in_bbox(nasa_grid, nasa_grid, lons, lats)  # 1.0 sanity check
    print(f"  NASA L2B: {stats(nasa_grid)}  (self-correlation should be 1.0, got {nasa_r:.3f})")

    # Band index sets
    three_window = select_indices(wl, [(500, 1340), (1500, 1790), (1950, 2450)])
    nasa_window = select_indices(wl, [NASA_CH4_WINDOW])
    nasa_window_excluded = exclude_indices(nasa_window, wl, *NASA_EMIT_ALWAYS_EXCLUDE)

    print("\nBand selection sizes:")
    print(f"  M0/M1 (three windows)              : {three_window.size} bands")
    print(f"  M2/M3 (NASA CH4 [2137,2493])       : {nasa_window.size} bands")
    print(f"  M4   (NASA + EMIT exclude 1275-1321): {nasa_window_excluded.size} bands")

    runs = []

    print("\nM0  current implementation (3-window, fixed alpha=1e-9, no scaling)")
    m0 = run_mf(radiance, wl, k, bad, three_window, "fixed_tiny", False, "M0")
    print(f"  stats: {stats(m0)}")
    runs.append(("M0", m0))

    print("\nM1  + apply ppm_scaling=100000 (H1 fix only)")
    m1 = m0 * PPM_SCALING_NASA_DEFAULT
    print(f"  stats: {stats(m1)}")
    runs.append(("M1", m1))

    print("\nM2  + NASA's CH4 window [2137,2493] (H1+H5 fixes)")
    m2 = run_mf(radiance, wl, k, bad, nasa_window, "fixed_tiny", True, "M2")
    print(f"  stats: {stats(m2)}")
    runs.append(("M2", m2))

    print("\nM3  + LOOCV-fit shrinkage per column (H1+H2+H5 fixes)")
    m3 = run_mf(radiance, wl, k, bad, nasa_window, "looshrinkage", True, "M3")
    print(f"  stats: {stats(m3)}")
    runs.append(("M3", m3))

    print("\nM4  + EMIT 1275-1321 nm always-exclude (full NASA replication)")
    m4 = run_mf(radiance, wl, k, bad, nasa_window_excluded, "looshrinkage", True, "M4")
    print(f"  stats: {stats(m4)}")
    runs.append(("M4", m4))

    print("\n" + "=" * 64)
    print("PEARSON vs NASA L2B over plume bbox  (NASA self = 1.0)")
    print("=" * 64)
    for name, arr in runs:
        r, n = pearson_in_bbox(arr, nasa_grid, lons, lats)
        print(f"  {name}: pearson = {r:+.4f}  (n={n} pixels compared)")

    # Magnitude check: at NASA-strong-plume pixels, what does each run report?
    print("\nMedian value at NASA-strong-plume pixels (NASA > 1000 ppm m):")
    strong = nasa_grid > 1000.0
    print(f"  NASA median there: {np.nanmedian(nasa_grid[strong]):+.2f} ppm m")
    for name, arr in runs:
        v = arr[strong]
        v = v[np.isfinite(v)]
        print(f"  {name} median there: {np.median(v):+.2f}  (n={v.size})")


if __name__ == "__main__":
    main()
