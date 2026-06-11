"""Throwaway diagnostic for the Stage A failure on 2022-08-15 Goturdepe.

Walks through the six hypotheses from the user report and prints evidence.
No production code is modified. Read-only.

Run:
    uv run python scripts/diagnose_stage_a.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rioxarray
import xarray as xr
from aether_detection import constants, target_signature

# --------------------------------------------------------------------------- #
# File paths (all cached locally from the failed Stage A run)
# --------------------------------------------------------------------------- #
RAD_PATH = Path(
    "/Users/animeshrajvanshi/.aether_cache/emit_l1b/downloads/"
    "19131fbb269a9cf4/EMIT_L1B_RAD_001_20220815T042838_2222703_003.nc"
)
MASK_PATH = Path(
    "/Users/animeshrajvanshi/.aether_cache/emit_l2a_mask/downloads/"
    "7c647413ff20e696/EMIT_L2A_MASK_002_20220815T042838_2222703_003.nc"
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


def hr(label: str) -> None:
    print("\n" + "=" * 72)
    print(label)
    print("=" * 72)


def sample_l2b_at_l1b_pixels(
    lons: np.ndarray, lats: np.ndarray, l2b_path: Path
) -> tuple[np.ndarray, dict]:
    """Inverse-affine sample the L2B GeoTIFF at every L1B pixel's lon/lat."""
    l2b = rioxarray.open_rasterio(l2b_path, masked=True).squeeze("band", drop=True)
    transform = l2b.rio.transform()
    inv = ~transform
    flat_lons = lons.ravel()
    flat_lats = lats.ravel()
    cols_f, rows_f = inv * (flat_lons, flat_lats)
    cols_i = np.round(cols_f).astype(np.int64)
    rows_i = np.round(rows_f).astype(np.int64)
    h, w = l2b.shape
    valid = (rows_i >= 0) & (rows_i < h) & (cols_i >= 0) & (cols_i < w)
    sampled = np.full(flat_lons.size, np.nan, dtype=np.float64)
    sampled[valid] = l2b.values[rows_i[valid], cols_i[valid]]
    info = {
        "l2b_shape": list(l2b.shape),
        "l2b_crs": str(l2b.rio.crs),
        "l2b_transform": [float(x) for x in transform[:6]],
        "l2b_min": float(np.nanmin(l2b.values)),
        "l2b_max": float(np.nanmax(l2b.values)),
        "l2b_pct_finite": float(np.isfinite(l2b.values).mean()),
    }
    return sampled.reshape(lons.shape), info


def main() -> None:
    # ---- Load everything once ----
    print("Loading our enhancement npz...")
    npz = np.load(OUR_NPZ)
    ours = npz["enhancement_ppm_m"]
    lons = npz["lon"]
    lats = npz["lat"]
    bad = npz["bad_pixel_mask"]
    print(f"  ours.shape={ours.shape}  lons.shape={lons.shape}")

    print("Loading L1B radiance (root) + sensor_band_parameters...")
    ds_root = xr.open_dataset(RAD_PATH, engine="netcdf4")
    ds_sb = xr.open_dataset(RAD_PATH, engine="netcdf4", group="sensor_band_parameters")
    radiance = ds_root["radiance"].values  # (1280, 1242, 285) float32
    wavelengths_nm = ds_sb["wavelengths"].values
    print(f"  radiance.shape={radiance.shape}  dtype={radiance.dtype}")
    print(f"  radiance attrs: {dict(ds_root['radiance'].attrs)}")
    print(f"  wavelengths attrs: {dict(ds_sb['wavelengths'].attrs)}")
    print(f"  band axis: nm range = [{wavelengths_nm.min():.2f}, {wavelengths_nm.max():.2f}]")

    print("Loading NASA target spectrum (k)...")
    target_wl, k = target_signature.load_unit_absorption_spectrum(TARGET_PATH)
    print(f"  k.shape={k.shape}  target_wl.shape={target_wl.shape}")
    print(f"  k stats: min={k.min():.4e}  max={k.max():.4e}  mean={k.mean():.4e}")
    print(f"  fraction k<0: {(k < 0).mean():.3f}  fraction k>0: {(k > 0).mean():.3f}")
    print(
        f"  wavelength match (max |target_wl - L1B_wl|): "
        f"{np.abs(target_wl - wavelengths_nm).max():.4f} nm"
    )

    print("Sampling NASA L2B at L1B pixel positions...")
    nasa_grid, l2b_info = sample_l2b_at_l1b_pixels(lons, lats, L2B_PATH)
    print(f"  L2B info: {l2b_info}")

    # =================================================================== #
    # Hypothesis 1: UNITS / SCALE — is our field actually ~0 or just very small?
    # =================================================================== #
    hr("H1  UNITS / SCALE — our enhancement vs NASA L2B over the same pixels")

    pct_list = [0.1, 1, 5, 50, 95, 99, 99.9]
    print("OUR enhancement (ppm m, allegedly):")
    print(f"  count finite           : {np.isfinite(ours).sum()} / {ours.size}")
    print(f"  min / max              : {np.nanmin(ours):+.4e}  {np.nanmax(ours):+.4e}")
    print(f"  mean / median          : {np.nanmean(ours):+.4e}  {np.nanmedian(ours):+.4e}")
    print(
        "  abs-percentile  ",
        {f"p{p}": f"{np.nanpercentile(np.abs(ours), p):+.4e}" for p in pct_list},
    )
    print("  signed-percentile", {f"p{p}": f"{np.nanpercentile(ours, p):+.4e}" for p in pct_list})

    print("\nNASA L2B CH4ENH sampled at L1B pixels (ppm m, per LP DAAC):")
    print(f"  count finite           : {np.isfinite(nasa_grid).sum()} / {nasa_grid.size}")
    print(f"  min / max              : {np.nanmin(nasa_grid):+.4e}  {np.nanmax(nasa_grid):+.4e}")
    print(
        f"  mean / median          : {np.nanmean(nasa_grid):+.4e}  "
        f"{np.nanmedian(nasa_grid):+.4e}"
    )
    print(
        "  signed-percentile",
        {f"p{p}": f"{np.nanpercentile(nasa_grid, p):+.4e}" for p in pct_list},
    )

    print("\nScale comparison: max |ours| / max |nasa|, mean |ours|/mean |nasa|:")
    print(
        f"  ratio (max)            : "
        f"{np.nanmax(np.abs(ours)) / max(np.nanmax(np.abs(nasa_grid)), 1e-12):.3e}"
    )
    print(
        f"  ratio (mean)           : "
        f"{np.nanmean(np.abs(ours)) / max(np.nanmean(np.abs(nasa_grid)), 1e-12):.3e}"
    )

    # =================================================================== #
    # Hypothesis 2: SINGULAR COVARIANCE / BLOB ARTIFACT
    # =================================================================== #
    hr("H2  SINGULAR COVARIANCE / BLOB ARTIFACT — locate bright blobs and probe their columns")

    # Find the bright-blob pixels: anything with |ours| above the 99.9th percentile.
    blob_threshold = float(np.nanpercentile(np.abs(ours), 99.9))
    blob_mask = np.abs(ours) > blob_threshold
    print(f"  |ours| > p99.9 threshold = {blob_threshold:+.4e}")
    print(f"  pixels above threshold   : {int(blob_mask.sum())}")
    rows_blob, cols_blob = np.where(blob_mask)
    if rows_blob.size > 0:
        unique_cols, col_counts = np.unique(cols_blob, return_counts=True)
        order = np.argsort(-col_counts)
        print("  top-10 cross-track columns containing blob pixels (col_index : pixel_count):")
        for c, ct in zip(unique_cols[order][:10], col_counts[order][:10], strict=True):
            sample_vals = ours[rows_blob[cols_blob == c][:5], c]
            print(
                f"    col={int(c):4d}  n={int(ct):5d}  "
                f"sample values: {[f'{v:+.3e}' for v in sample_vals]}"
            )
        suspect_cols = list(unique_cols[order][:3])
    else:
        suspect_cols = [0]

    # Reimplement the inner MF on a probe column to inspect C condition.
    band_indices_kept = target_signature.select_band_indices(
        wavelengths_nm, constants.MF_SPECTRAL_WINDOWS_NM
    )
    rad_kept = radiance[:, :, band_indices_kept].astype(np.float64)
    k_kept = k[band_indices_kept]
    shrinkage_alpha = constants.MF_SHRINKAGE_ALPHA

    print(
        f"\n  Probing C, sᵀC⁻¹s, conditioning per column. shrinkage_alpha={shrinkage_alpha:g}"
    )
    print(
        "  Showing 3 suspect columns first, then 3 well-behaved columns "
        "(picked from the middle of the cross-track)."
    )

    def probe_column(c: int) -> dict:
        col = rad_kept[:, c, :]
        good = ~bad[:, c]
        col_good = col[good]
        mu_c = col_good.mean(axis=0)
        deviations = col_good - mu_c
        c_emp = np.cov(deviations, rowvar=False, bias=False)
        c_shrunk = (1 - shrinkage_alpha) * c_emp + shrinkage_alpha * np.diag(np.diag(c_emp))
        s_c = k_kept * mu_c
        try:
            z = np.linalg.solve(c_shrunk, s_c)
            denom = float(s_c @ z)
        except np.linalg.LinAlgError:
            z = None
            denom = float("nan")
        eigvals = np.linalg.eigvalsh(c_shrunk)
        cond = float(eigvals.max() / max(eigvals.min(), 1e-300))
        return {
            "n_good": int(good.sum()),
            "mu_range": (float(mu_c.min()), float(mu_c.max())),
            "C_diag_range": (float(np.diag(c_emp).min()), float(np.diag(c_emp).max())),
            "C_cond_number": cond,
            "C_min_eig": float(eigvals.min()),
            "C_max_eig": float(eigvals.max()),
            "s_norm": float(np.linalg.norm(s_c)),
            "sT_Cinv_s": denom,
        }

    well_behaved_cols = [600, 700, 800]
    all_probe_cols = list(suspect_cols) + well_behaved_cols
    for c in all_probe_cols:
        if c >= radiance.shape[1]:
            continue
        info = probe_column(int(c))
        label = "SUSPECT" if c in suspect_cols else "well-behaved"
        print(f"\n  col {int(c):4d} ({label}):")
        for k_, v in info.items():
            print(f"    {k_:18s} = {v}")

    # =================================================================== #
    # Hypothesis 3: TARGET / RADIANCE UNIT CONSISTENCY
    # =================================================================== #
    hr("H3  TARGET / RADIANCE UNIT CONSISTENCY — k vs radiance scale")

    print("L1B radiance numerical magnitude (raw, as loaded by xarray, no manual scale):")
    print(
        f"  full-cube percentiles  : "
        f"p1={np.percentile(radiance, 1):.4e}  p50={np.percentile(radiance, 50):.4e}  "
        f"p99={np.percentile(radiance, 99):.4e}"
    )
    # Pick the central pixel of a clearly-illuminated column for a clean look
    mid_line, mid_col = radiance.shape[0] // 2, radiance.shape[1] // 2
    print(
        f"  example pixel L1B[{mid_line},{mid_col}] radiance @ 5 SWIR bands "
        f"(2100, 2200, 2300, 2350, 2400 nm):"
    )
    for w in [2100, 2200, 2300, 2350, 2400]:
        bi = int(np.argmin(np.abs(wavelengths_nm - w)))
        print(
            f"    wl={wavelengths_nm[bi]:7.2f} nm  rad={radiance[mid_line, mid_col, bi]:.4e}  "
            f"k={k[bi]:+.4e}  s=k*rad={k[bi] * radiance[mid_line, mid_col, bi]:+.4e}"
        )

    print("\nL1B published units (from L1B User Guide, JPL D-107862): W m-2 sr-1 um-1")
    print(
        "Expected magnitude for SWIR over sunlit ground: ~1e-1 to ~10 W m-2 sr-1 um-1.\n"
        "Observed magnitude tells us whether the file is in W/m²/sr/μm or µW/cm²/sr/nm."
    )

    print("\nTarget file k values (first few SWIR bands, signed):")
    swir = (wavelengths_nm >= 2100) & (wavelengths_nm <= 2500)
    swir_idx = np.where(swir)[0]
    for bi in swir_idx[::4]:
        print(f"    wl={wavelengths_nm[bi]:7.2f} nm  k={k[bi]:+.4e}")
    print(f"  Number of k values that are exactly 0.0: {int((k == 0.0).sum())}")

    # =================================================================== #
    # Hypothesis 4: SIGN at NASA-strong-plume pixels
    # =================================================================== #
    hr("H4  SIGN — at NASA-strong-plume pixels, what does our pipeline report?")

    nasa_strong_mask = nasa_grid > 500.0  # NASA reports strong enhancement
    n_strong = int(nasa_strong_mask.sum())
    print(f"  pixels where NASA > 500 ppm·m       : {n_strong}")
    if n_strong > 0:
        ours_strong = ours[nasa_strong_mask]
        nasa_strong = nasa_grid[nasa_strong_mask]
        finite = np.isfinite(ours_strong)
        ours_strong_f = ours_strong[finite]
        nasa_strong_f = nasa_strong[finite]
        if ours_strong_f.size > 0:
            print(f"  ours at those pixels — mean       : {ours_strong_f.mean():+.4e}")
            print(f"  ours at those pixels — median     : {np.median(ours_strong_f):+.4e}")
            print(f"  ours at those pixels — min        : {ours_strong_f.min():+.4e}")
            print(f"  ours at those pixels — max        : {ours_strong_f.max():+.4e}")
            print(f"  fraction positive                 : {(ours_strong_f > 0).mean():.3f}")
            rel = np.abs(ours_strong_f - nasa_strong_f) / np.maximum(np.abs(nasa_strong_f), 1e-9)
            print(f"  fraction within 50% of NASA       : {(rel < 0.5).mean():.3f}")

    # Symmetric check: where NASA is strongly NEGATIVE (some sensors report negative
    # enhancements as noise floor), what do we say?
    nasa_neg_mask = nasa_grid < -500.0
    if int(nasa_neg_mask.sum()) > 100:
        print(f"\n  pixels where NASA < -500 ppm·m      : {int(nasa_neg_mask.sum())}")
        on = ours[nasa_neg_mask]
        on = on[np.isfinite(on)]
        print(f"  ours at those pixels — median     : {np.median(on):+.4e}")

    # =================================================================== #
    # Hypothesis 5: BAND SELECTION — exactly which 219 of 285 bands?
    # =================================================================== #
    hr("H5  BAND SELECTION — exactly which bands are kept")

    band_indices = target_signature.select_band_indices(
        wavelengths_nm, constants.MF_SPECTRAL_WINDOWS_NM
    )
    print(f"  total bands in file        : {wavelengths_nm.size}")
    print(f"  bands kept by 3-window mask: {band_indices.size}  (Stage A report said: 219)")
    print(f"  windows                    : {list(constants.MF_SPECTRAL_WINDOWS_NM)}")
    in_win = np.isin(np.arange(wavelengths_nm.size), band_indices)
    # Break by window
    for lo, hi in constants.MF_SPECTRAL_WINDOWS_NM:
        in_this = (wavelengths_nm >= lo) & (wavelengths_nm <= hi)
        kept_here = int((in_this & in_win).sum())
        all_here = int(in_this.sum())
        print(f"    window {lo:.0f}-{hi:.0f} nm  bands {kept_here}/{all_here}")
    # Specifically check the methane absorption complex around 2.3 µm
    ch4_band_mask = (wavelengths_nm >= 2150) & (wavelengths_nm <= 2400)
    kept_in_ch4 = int((ch4_band_mask & in_win).sum())
    all_in_ch4 = int(ch4_band_mask.sum())
    print(f"\n  bands in CH4-sensitive 2150-2400 nm region: {all_in_ch4} total, {kept_in_ch4} kept")
    # List the actual nm of the dropped bands (the ones outside the three windows)
    dropped = np.where(~in_win)[0]
    print(
        "\n  dropped band wavelengths (first 25): "
        f"{[float(round(w, 2)) for w in wavelengths_nm[dropped][:25]]}"
    )
    print(
        "  dropped band wavelengths (last 15) : "
        f"{[float(round(w, 2)) for w in wavelengths_nm[dropped][-15:]]}"
    )

    # =================================================================== #
    # Hypothesis 6: ALIGNMENT — do we and NASA see the same (lon, lat) for the same pixel?
    # =================================================================== #
    hr("H6  ALIGNMENT — pixel-to-pixel geolocation sanity")

    # Take a few pixels where NASA reports strong enhancement (>1000 ppm·m).
    if int((nasa_grid > 1000.0).sum()) >= 5:
        ys, xs = np.where(nasa_grid > 1000.0)
        idxs = np.linspace(0, len(ys) - 1, num=5).astype(int)
        print("  Showing 5 high-NASA pixels with our value at the same (lon, lat):")
        print(
            f"    {'row':>5} {'col':>5} {'lon':>10} {'lat':>10} "
            f"{'NASA':>12} {'OURS':>12} {'bad?':>5}"
        )
        for i in idxs:
            r, c = int(ys[i]), int(xs[i])
            print(
                f"    {r:5d} {c:5d} {lons[r,c]:10.5f} {lats[r,c]:10.5f} "
                f"{nasa_grid[r,c]:12.2f} {ours[r,c]:12.4e} {bool(bad[r,c])!s:>5}"
            )
    # Also show what NASA reports at our blob pixels (we expect ~0 if the blobs are bogus)
    if rows_blob.size >= 3:
        print("\n  Showing 5 of our blob pixels with the NASA value at same (lon, lat):")
        print(
            f"    {'row':>5} {'col':>5} {'lon':>10} {'lat':>10} "
            f"{'NASA':>12} {'OURS':>12} {'bad?':>5}"
        )
        for i in np.linspace(0, rows_blob.size - 1, num=5).astype(int):
            r, c = int(rows_blob[i]), int(cols_blob[i])
            print(
                f"    {r:5d} {c:5d} {lons[r,c]:10.5f} {lats[r,c]:10.5f} "
                f"{nasa_grid[r,c]:12.2f} {ours[r,c]:12.4e} {bool(bad[r,c])!s:>5}"
            )

    print("\nDone.")


if __name__ == "__main__":
    main()
