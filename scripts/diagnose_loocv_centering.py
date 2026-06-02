"""Compare LOOCV α selection: NASA-faithful (uncentered) vs Theiler-clean
(centered). Verbatim NASA port from emit-sds/emit-ghg/parallel_mf.py used as
the gold reference. Read-only — no production changes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import scipy.linalg
import xarray as xr
from aether_detection.matched_filter import (
    _default_alpha_grid,
    fit_looshrinkage_alpha,
)
from aether_detection.target_signature import select_band_indices

RAD_PATH = Path(
    "/Users/animeshrajvanshi/.aether_cache/emit_l1b/downloads/"
    "19131fbb269a9cf4/EMIT_L1B_RAD_001_20220815T042838_2222703_003.nc"
)


def nasa_verbatim_fit(data: np.ndarray, alphas: np.ndarray) -> float:
    """Verbatim port of NASA's fit_looshrinkage_alpha for cross-check."""
    stability_scaling = 100.0
    nchan = data.shape[1]
    nll = np.zeros(len(alphas))
    n = data.shape[0]
    x = data * stability_scaling
    s = np.cov(x.T, ddof=1)
    t = np.diag(np.diag(s))
    nchanlog2pi = nchan * np.log(2.0 * np.pi)
    nll[:] = np.inf
    for i, alpha in enumerate(alphas):
        try:
            beta = (1.0 - alpha) / (n - 1.0)
            g = n * (beta * s) + (alpha * t)
            g_det = scipy.linalg.det(g, check_finite=False)
            if g_det == 0:
                continue
            r_k = (x.dot(scipy.linalg.inv(g, check_finite=False)) * x).sum(axis=1)
            q = 1.0 - beta * r_k
            nll[i] = 0.5 * (nchanlog2pi + np.log(g_det)) + 1.0 / (2.0 * n) * (
                np.log(q) + (r_k / q)
            ).sum()
        except np.linalg.LinAlgError:
            pass
    mindex = int(np.argmin(nll))
    return float(alphas[mindex]) if nll[mindex] != np.inf else 0.0


def main() -> None:
    print("Loading L1B radiance...")
    ds_root = xr.open_dataset(RAD_PATH, engine="netcdf4")
    ds_sb = xr.open_dataset(RAD_PATH, engine="netcdf4", group="sensor_band_parameters")
    radiance = ds_root["radiance"].values
    wl = ds_sb["wavelengths"].values

    band_indices = select_band_indices(wl, ((2137.0, 2493.0),))
    rad_kept = radiance[:, :, band_indices].astype(np.float64)
    print(f"  radiance.shape={radiance.shape}  bands_kept={band_indices.size}")
    alpha_grid = _default_alpha_grid()
    grid_np = np.asarray(alpha_grid)

    # Probe a representative set of columns, including the blob columns
    # identified earlier (1241, 1149, 1109) and a few bulk columns.
    probe_columns = [600, 700, 800, 1095, 1109, 1149, 1241]

    print(f"\nProbing {len(probe_columns)} columns with three LOOCV variants:")
    print(f"{'col':>5} {'OUR_port':>11} {'NASA_verbatim':>14} {'CENTERED':>11}")
    for c in probe_columns:
        col = rad_kept[:, c, :]  # (lines, B) uncentered radiance
        mu = col.mean(axis=0)
        centered = col - mu
        our_alpha = fit_looshrinkage_alpha(col)
        nasa_alpha = nasa_verbatim_fit(col, grid_np)
        centered_alpha = fit_looshrinkage_alpha(centered)
        print(f"{c:>5} {our_alpha:>11.3e} {nasa_alpha:>14.3e} {centered_alpha:>11.3e}")

    # Aggregate α distributions over a 50-column sample.
    print("\nα distribution over 50 columns (uniformly sampled), uncentered vs centered:")
    n_cols = rad_kept.shape[1]
    sampled_cols = np.linspace(0, n_cols - 1, 50).astype(int)
    uncentered_alphas = []
    centered_alphas = []
    for c in sampled_cols:
        col = rad_kept[:, c, :]
        mu = col.mean(axis=0)
        uncentered_alphas.append(fit_looshrinkage_alpha(col))
        centered_alphas.append(fit_looshrinkage_alpha(col - mu))
    uncentered_alphas = np.array(uncentered_alphas)
    centered_alphas = np.array(centered_alphas)
    for name, arr in [("UNCENTERED (NASA-faithful)", uncentered_alphas),
                       ("CENTERED (Theiler-clean)", centered_alphas)]:
        print(
            f"  {name}: "
            f"min={arr.min():.3e}  median={np.median(arr):.3e}  "
            f"p95={np.percentile(arr, 95):.3e}  max={arr.max():.3e}"
        )


if __name__ == "__main__":
    main()
