"""Test residual geolocation hypothesis: is the 0.26 correlation floor caused
by sub-pixel jitter between L1B raw geometry and NASA's L2B orthorectified grid?

Approach: rerun the spatial-agreement check three ways:
  A. nearest-neighbor sampling (what the original driver did) — the baseline
  B. local-max sampling in a 3x3 neighborhood of NASA L2B around each lat/lon
  C. our M4 output ALSO local-max'd in a 3x3 raw-geometry neighborhood, paired
     with NASA at corresponding lon/lat

If (B) and (C) jump correlation significantly above (A), geolocation alignment
is the remaining culprit and the fix lives in the Stage A driver (orthorectify
via GLT before comparing) — NOT in the matched filter math.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import rioxarray
import scipy.linalg
import scipy.ndimage
import xarray as xr
from aether_detection import target_signature

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

BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}


def fit_looshrinkage_alpha(data: np.ndarray) -> float:
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

    print("Re-running MF with NASA-faithful settings (M4) ...")
    nasa_window = np.where((wl >= 2137.0) & (wl <= 2493.0))[0]
    rad_kept = radiance[:, :, nasa_window].astype(np.float64)
    k_kept = k[nasa_window]
    n_lines, n_cols, n_bands = rad_kept.shape
    ours = np.full((n_lines, n_cols), np.nan, dtype=np.float64)
    t0 = time.time()
    for c in range(n_cols):
        col = rad_kept[:, c, :]
        good = ~bad[:, c]
        col_good = col[good]
        if col_good.shape[0] < n_bands + 2:
            continue
        mu_c = col_good.mean(axis=0)
        deviations = col_good - mu_c
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
        out = (col_minus_mu @ z) / denom * 100000.0
        ours[good, c] = out[good]
    print(f"  MF done in {time.time() - t0:.1f}s")

    print("Loading NASA L2B...")
    l2b = rioxarray.open_rasterio(L2B_PATH, masked=True).squeeze("band", drop=True)
    transform = l2b.rio.transform()
    inv = ~transform
    l2b_arr = np.array(l2b.values)
    h, w = l2b.shape

    # ============================================================ A ===
    print("\n[A] Nearest-neighbor sampling (the original driver behavior)")
    cols_f, rows_f = inv * (lons.ravel(), lats.ravel())
    cols_i = np.round(cols_f).astype(np.int64)
    rows_i = np.round(rows_f).astype(np.int64)
    valid = (rows_i >= 0) & (rows_i < h) & (cols_i >= 0) & (cols_i < w)
    nasa_nn = np.full(lons.size, np.nan)
    nasa_nn[valid] = l2b_arr[rows_i[valid], cols_i[valid]]
    nasa_nn = nasa_nn.reshape(lons.shape)
    in_bbox = (
        (lons >= BBOX["min_lon"]) & (lons <= BBOX["max_lon"])
        & (lats >= BBOX["min_lat"]) & (lats <= BBOX["max_lat"])
    )
    ok = in_bbox & np.isfinite(ours) & np.isfinite(nasa_nn)
    print(f"  pearson = {float(np.corrcoef(ours[ok], nasa_nn[ok])[0, 1]):+.4f}  n={int(ok.sum())}")

    # ============================================================ B ===
    print("\n[B] Smooth NASA L2B in a 3x3 window, then nearest-neighbor sample")
    # A 3x3 mean filter on the L2B grid absorbs sub-pixel offsets without smearing
    # the plume itself (which is many pixels wide).
    l2b_smoothed = scipy.ndimage.uniform_filter(np.nan_to_num(l2b_arr, nan=0.0),
                                                size=3, mode="nearest")
    nasa_smooth = np.full(lons.size, np.nan)
    nasa_smooth[valid] = l2b_smoothed[rows_i[valid], cols_i[valid]]
    nasa_smooth = nasa_smooth.reshape(lons.shape)
    ok = in_bbox & np.isfinite(ours) & np.isfinite(nasa_smooth)
    print(
        f"  pearson = {float(np.corrcoef(ours[ok], nasa_smooth[ok])[0, 1]):+.4f}  "
        f"n={int(ok.sum())}"
    )

    # ============================================================ C ===
    print("\n[C] Smooth BOTH (NASA 3x3 + ours 3x3) before correlating")
    ours_smoothed = scipy.ndimage.uniform_filter(np.nan_to_num(ours, nan=0.0),
                                                 size=3, mode="nearest")
    ok = in_bbox & np.isfinite(ours_smoothed) & np.isfinite(nasa_smooth)
    print(
        f"  pearson = {float(np.corrcoef(ours_smoothed[ok], nasa_smooth[ok])[0, 1]):+.4f}  "
        f"n={int(ok.sum())}"
    )

    # ============================================================ D ===
    print("\n[D] Aggregate to 5x5 super-pixels and correlate")
    ours_block = scipy.ndimage.uniform_filter(np.nan_to_num(ours, nan=0.0),
                                              size=5, mode="nearest")[::5, ::5]
    # Sample NASA at the centers of the super-pixels.
    lons_block = lons[::5, ::5]
    lats_block = lats[::5, ::5]
    cols_b, rows_b = inv * (lons_block.ravel(), lats_block.ravel())
    cols_b_i = np.round(cols_b).astype(np.int64)
    rows_b_i = np.round(rows_b).astype(np.int64)
    valid_b = (rows_b_i >= 0) & (rows_b_i < h) & (cols_b_i >= 0) & (cols_b_i < w)
    nasa_block_flat = np.full(lons_block.size, np.nan)
    nasa_block_flat[valid_b] = l2b_smoothed[rows_b_i[valid_b], cols_b_i[valid_b]]
    nasa_block = nasa_block_flat.reshape(lons_block.shape)
    in_bbox_block = (
        (lons_block >= BBOX["min_lon"]) & (lons_block <= BBOX["max_lon"])
        & (lats_block >= BBOX["min_lat"]) & (lats_block <= BBOX["max_lat"])
    )
    ok_b = in_bbox_block & np.isfinite(ours_block) & np.isfinite(nasa_block)
    print(
        f"  pearson = {float(np.corrcoef(ours_block[ok_b], nasa_block[ok_b])[0, 1]):+.4f}  "
        f"n={int(ok_b.sum())}"
    )

    # =========================================================== bbox stats
    print("\nDiagnostic stats over bbox (signed percentiles):")
    for name, arr in [("ours (M4)", ours), ("nasa_nn", nasa_nn), ("nasa_smooth", nasa_smooth)]:
        v = arr[in_bbox & np.isfinite(arr)]
        print(
            f"  {name:14s}: p1={np.percentile(v, 1):+.2f}  "
            f"p50={np.percentile(v, 50):+.2f}  p99={np.percentile(v, 99):+.2f}"
        )


if __name__ == "__main__":
    main()
