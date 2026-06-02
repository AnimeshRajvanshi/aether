"""End-to-end Stage A driver for the Goturdepe 2022-08-15 04:28:38 UTC overpass.

This script does five things in order, with provenance recorded for each:

1. **Authenticate** with NASA Earthdata (interactive login on first run,
   cached to ``~/.netrc`` thereafter).
2. **Download** three NASA granules for ``EMIT_*_20220815T042838_2222703_003``:
   the L1B radiance, the L2A mask, and the L2B CH4 enhancement raster. Cached.
3. **Fetch** NASA's per-granule unit absorption spectrum file
   ``emit20220815t042838_ch4_target`` from EMIT-Data-Resources. ~11 KB, cached.
4. **Run our matched filter** against the L1B radiance using NASA's k as the
   unit absorption spectrum and the L2A aggregate flag as the bad-pixel mask.
5. **Compare** our enhancement raster against NASA's L2B raster:
   - sample the NASA L2B at each L1B pixel's lat/lon (raw-geometry comparison;
     orthorectifying our output is deferred — comparison in sensor space is
     valid because both rasters get sampled at the same pixel-center points),
   - compute Pearson correlation over (a) the full granule, (b) the high-
     enhancement subset where either side exceeds 200 ppm·m,
   - render a side-by-side PNG using the L1B location lon/lat as plot axes,
   - write a JSON report capturing every number.

This script does NOT do Stage B (no IME, no Q, no plume segmentation). It
stops at "we have an enhancement raster that lines up with NASA's."

Run:
    uv run python scripts/run_stage_a_goturdepe.py

Outputs go to ``stage_a_outputs/turkmenistan_goturdepe_2022_08_15/``.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import earthaccess
import matplotlib.pyplot as plt
import numpy as np
import rioxarray
from aether_data_spine import emit_l1b, emit_l2a_mask
from aether_detection import constants, matched_filter, target_signature

# --------------------------------------------------------------------------- #
# Paths and event configuration
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "stage_a_outputs" / "turkmenistan_goturdepe_2022_08_15"
CACHE_DIR = Path.home() / ".aether_cache"
TARGET_CACHE_DIR = CACHE_DIR / "emit_targets"

L1B_UR = constants.TURKMENISTAN_GOTURDEPE_2022_08_15_L1B_GRANULE_UR
L2A_MASK_UR = constants.TURKMENISTAN_GOTURDEPE_2022_08_15_L2A_MASK_GRANULE_UR
L2B_CH4_UR = constants.TURKMENISTAN_GOTURDEPE_2022_08_15_L2B_CH4_GRANULE_UR
ACQUISITION_UTC = constants.TURKMENISTAN_GOTURDEPE_2022_08_15_ACQUISITION_UTC
TARGET_URL = constants.TURKMENISTAN_GOTURDEPE_2022_08_15_TARGET_URL
TARGET_FILENAME = constants.TURKMENISTAN_GOTURDEPE_2022_08_15_TARGET_FILENAME

# Bounding box of the NASA-published plume complex on this granule (000494).
# Tight enough to focus the correlation on the plume area rather than the
# scene-wide near-zero background. Pulled from the granule footprint (CMR);
# the per-plume bbox of complex 000494 is read at runtime from NASA's L2B PLM
# COG when available, with this default as the fallback.
DEFAULT_PLUME_BBOX = {  # (min_lon, min_lat, max_lon, max_lat)
    "min_lon": 53.50,
    "min_lat": 39.30,
    "max_lon": 54.20,
    "max_lat": 39.70,
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


@dataclass
class StageAReport:
    """Everything the stage-A run produces, ready to dump as JSON."""

    started_utc: str
    finished_utc: str | None = None
    acquisition_utc: str = ACQUISITION_UTC
    l1b_granule_ur: str = L1B_UR
    l2a_mask_granule_ur: str = L2A_MASK_UR
    l2b_ch4_granule_ur: str = L2B_CH4_UR
    target_spectrum_source: str = TARGET_URL
    target_spectrum_local_path: str | None = None
    radiance_shape: list[int] | None = None
    bands_used: int | None = None
    bad_pixel_fraction: float | None = None
    enhancement_raw_npy: str | None = None
    nasa_l2b_geotiff: str | None = None
    side_by_side_png: str | None = None
    plume_bbox: dict[str, float] | None = None
    pearson_full_scene: float | None = None
    pearson_in_bbox: float | None = None
    pearson_in_bbox_strong_signal: float | None = None
    n_pixels_compared_full: int | None = None
    n_pixels_compared_bbox: int | None = None
    # Per-column LOOCV shrinkage distribution summary.
    shrinkage_alpha_min: float | None = None
    shrinkage_alpha_median: float | None = None
    shrinkage_alpha_p95: float | None = None
    shrinkage_alpha_max: float | None = None
    shrinkage_alpha_n_columns: int | None = None
    notes: list[str] = field(default_factory=list)


def log(msg: str) -> None:
    print(f"[stage-a] {msg}", flush=True)


def ensure_earthaccess_login() -> None:
    log("Authenticating with NASA Earthdata...")
    auth = earthaccess.login(persist=True)
    if not auth.authenticated:
        raise RuntimeError(
            "NASA Earthdata authentication failed. Create an account at "
            "https://urs.earthdata.nasa.gov and re-run."
        )
    log("Earthdata authenticated.")


def search_one_granule(short_name: str, granule_ur: str) -> Any:
    """Find a single granule by its UR. Refuses silent fallback."""
    log(f"CMR search: {short_name} {granule_ur}")
    results = earthaccess.search_data(
        short_name=short_name,
        readable_granule_name=granule_ur,
    )
    if len(results) != 1:
        raise RuntimeError(
            f"Expected exactly 1 granule for {granule_ur}, got {len(results)}"
        )
    return results[0]


def download_target_spectrum() -> Path:
    """Fetch NASA's per-granule k file once; cache locally."""
    TARGET_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local = TARGET_CACHE_DIR / TARGET_FILENAME
    if local.exists() and local.stat().st_size > 0:
        log(f"Target spectrum already cached at {local}")
        return local
    log(f"Downloading target spectrum from {TARGET_URL}")
    urllib.request.urlretrieve(TARGET_URL, local)
    log(f"Cached to {local} ({local.stat().st_size} bytes)")
    return local


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = StageAReport(started_utc=datetime.now(UTC).isoformat())

    # ---- 1. Authenticate ----
    ensure_earthaccess_login()

    # ---- 2. Download granules ----
    # Three independent fetches; each goes to its own cache so re-runs are fast.
    log("Resolving L1B, L2A mask, L2B CH4ENH granules in CMR...")
    g_l1b = search_one_granule("EMITL1BRAD", L1B_UR)
    g_l2a = search_one_granule("EMITL2AMASK", L2A_MASK_UR)
    g_l2b = search_one_granule("EMITL2BCH4ENH", L2B_CH4_UR)

    log("Downloading L1B radiance (largest file — may take a few minutes)...")
    l1b_cache = emit_l1b.download_and_cache_l1b(g_l1b)
    log(f"L1B cached at {l1b_cache}")

    log("Downloading L2A mask...")
    l2a_cache = emit_l2a_mask.download_and_cache_l2a_mask(g_l2a)
    log(f"L2A mask cached at {l2a_cache}")

    log("Downloading NASA L2B CH4 enhancement (reference for spatial agreement)...")
    l2b_download_dir = CACHE_DIR / "emit_l2b_ch4" / L2B_CH4_UR
    l2b_download_dir.mkdir(parents=True, exist_ok=True)
    l2b_paths = earthaccess.download([g_l2b], local_path=str(l2b_download_dir))
    l2b_tif = next(
        (Path(p) for p in l2b_paths if "CH4ENH" in Path(p).name and "UNCERT" not in Path(p).name),
        None,
    )
    if l2b_tif is None:
        raise RuntimeError(f"No CH4ENH GeoTIFF found among downloaded L2B files: {l2b_paths}")
    log(f"NASA L2B CH4ENH at {l2b_tif}")
    report.nasa_l2b_geotiff = str(l2b_tif)

    # ---- 3. Fetch NASA's per-granule target spectrum ----
    target_path = download_target_spectrum()
    report.target_spectrum_local_path = str(target_path)

    # ---- 4. Load everything ----
    log("Loading L1B radiance + wavelengths + lat/lon...")
    l1b_ds = emit_l1b.load_l1b_from_cache(l1b_cache)
    radiance, wavelengths_nm, _fwhm = emit_l1b.get_radiance_cube(l1b_ds)
    lons = np.asarray(l1b_ds["lon"].values, dtype=np.float64)
    lats = np.asarray(l1b_ds["lat"].values, dtype=np.float64)
    report.radiance_shape = list(radiance.shape)
    log(f"radiance shape={radiance.shape}, wavelengths n={wavelengths_nm.size}")

    log("Loading L2A mask + building bad-pixel mask...")
    l2a_ds = emit_l2a_mask.load_l2a_mask_from_cache(l2a_cache)
    bad_pixel_mask = emit_l2a_mask.build_bad_pixel_mask(l2a_ds, use_aggregate=True)
    bad_pixel_frac = float(bad_pixel_mask.mean())
    report.bad_pixel_fraction = bad_pixel_frac
    log(f"bad-pixel fraction: {bad_pixel_frac * 100:.2f}%")

    log("Loading NASA's per-granule unit absorption spectrum k...")
    target_wavelengths_nm, k = target_signature.load_unit_absorption_spectrum(target_path)
    if target_wavelengths_nm.size != wavelengths_nm.size:
        raise RuntimeError(
            f"k band count {target_wavelengths_nm.size} != L1B band count {wavelengths_nm.size}; "
            "this granule's per-granule target file does not match the L1B."
        )
    if not np.allclose(target_wavelengths_nm, wavelengths_nm, atol=0.05):
        report.notes.append(
            "Per-granule target wavelengths differ slightly from L1B wavelengths; "
            "max delta = "
            f"{float(np.abs(target_wavelengths_nm - wavelengths_nm).max()):.4f} nm. "
            "Using k values as-given (assuming common 285-band layout)."
        )

    # ---- 5. Run MF ----
    log("Running per-column matched filter (this is the expensive step)...")
    t0 = time.time()
    mf_result = matched_filter.run_matched_filter(
        radiance=radiance,
        wavelengths_nm=wavelengths_nm,
        unit_absorption_spectrum_k=k,
        bad_pixel_mask=bad_pixel_mask,
    )
    log(f"MF complete in {time.time() - t0:.1f}s; kept {mf_result.band_indices_kept.size} bands")
    report.bands_used = int(mf_result.band_indices_kept.size)

    our_enh = mf_result.enhancement_ppm_m  # (lines, cols) in raw sensor geometry
    alpha_per_col = mf_result.shrinkage_alpha_per_column

    finite_alpha = alpha_per_col[np.isfinite(alpha_per_col)]
    if finite_alpha.size > 0:
        report.shrinkage_alpha_n_columns = int(finite_alpha.size)
        report.shrinkage_alpha_min = float(finite_alpha.min())
        report.shrinkage_alpha_median = float(np.median(finite_alpha))
        report.shrinkage_alpha_p95 = float(np.percentile(finite_alpha, 95))
        report.shrinkage_alpha_max = float(finite_alpha.max())
        log(
            "LOOCV α per-column: "
            f"min={finite_alpha.min():.3e}  median={np.median(finite_alpha):.3e}  "
            f"p95={np.percentile(finite_alpha, 95):.3e}  max={finite_alpha.max():.3e}"
        )

    # Save our raw-geometry raster as npy + lon/lat alongside for plotting/reuse.
    raw_npy_path = OUTPUT_DIR / "our_enhancement_raw.npy"
    np.savez_compressed(
        raw_npy_path.with_suffix(".npz"),
        enhancement_ppm_m=our_enh,
        lon=lons,
        lat=lats,
        bad_pixel_mask=bad_pixel_mask,
        shrinkage_alpha_per_column=alpha_per_col,
    )
    report.enhancement_raw_npy = str(raw_npy_path.with_suffix(".npz"))
    log(f"Saved our enhancement (raw geometry) to {raw_npy_path.with_suffix('.npz')}")

    # ---- 6. Orthorectify our enhancement via GLT onto NASA's EPSG:4326 grid ----
    # Our matched-filter output is in raw sensor geometry. NASA's L2B GeoTIFF is
    # orthorectified to a regular EPSG:4326 grid. Sampling the L2B at raw-pixel
    # lat/lon with nearest-neighbour rounding introduces sub-pixel jitter that
    # collapses pixel-wise correlation on thin plume filaments (we verified this
    # destroys ~0.4 of the achievable Pearson — see scripts/diagnose_stage_a_alignment.py).
    # The clean fix is to project OUR raster onto NASA's exact same ortho grid
    # using the EMIT GLT, then compare pixel-to-pixel without any smoothing.
    log("Orthorectifying our enhancement via the EMIT GLT...")
    glt_x = np.asarray(l1b_ds["glt_x"].values)
    glt_y = np.asarray(l1b_ds["glt_y"].values)
    ours_ortho = emit_l1b.orthorectify_raw_raster(our_enh, glt_x, glt_y)
    log(f"  ortho shape: {ours_ortho.shape}")

    log("Loading NASA L2B CH4ENH on its ortho grid...")
    l2b = rioxarray.open_rasterio(l2b_tif, masked=True).squeeze("band", drop=True)
    nasa_ortho = np.asarray(l2b.values, dtype=np.float64)
    log(f"  NASA L2B shape: {nasa_ortho.shape}")
    if nasa_ortho.shape != ours_ortho.shape:
        raise RuntimeError(
            f"Ortho-grid mismatch: NASA L2B {nasa_ortho.shape} vs ours {ours_ortho.shape}. "
            "Expected identical because both products share the same EMIT GLT ortho grid."
        )

    # Both rasters now live on the same (1876, 2507) EPSG:4326 grid with the same
    # affine transform — pixel (i, j) on the left panel = pixel (i, j) on the right.
    # The L2B's affine transform gives us the lon/lat of each ortho pixel for plotting.
    transform = l2b.rio.transform()
    n_oy, n_ox = nasa_ortho.shape
    ortho_x_edges = np.array([transform.c + i * transform.a for i in range(n_ox + 1)])
    ortho_y_edges = np.array([transform.f + i * transform.e for i in range(n_oy + 1)])
    extent = [
        float(ortho_x_edges.min()),
        float(ortho_x_edges.max()),
        float(ortho_y_edges.min()),
        float(ortho_y_edges.max()),
    ]
    # Per-pixel lon/lat for bbox masking.
    ortho_lon_centers = (ortho_x_edges[:-1] + ortho_x_edges[1:]) / 2.0
    ortho_lat_centers = (ortho_y_edges[:-1] + ortho_y_edges[1:]) / 2.0
    lon_grid, lat_grid = np.meshgrid(ortho_lon_centers, ortho_lat_centers)

    # Save the orthorectified raster alongside the raw output for reuse.
    ortho_npz_path = OUTPUT_DIR / "our_enhancement_ortho.npz"
    np.savez_compressed(
        ortho_npz_path,
        enhancement_ppm_m=ours_ortho,
        ortho_lon_centers=ortho_lon_centers,
        ortho_lat_centers=ortho_lat_centers,
        l2b_transform=np.asarray(transform[:6]),
    )

    # ---- 7. Compute Pearson on the common ortho grid (no smoothing) ----
    log("Computing Pearson correlations on the common ortho grid (no smoothing)...")
    ok_full = np.isfinite(ours_ortho) & np.isfinite(nasa_ortho)
    n_full = int(ok_full.sum())
    pearson_full = (
        float(np.corrcoef(ours_ortho[ok_full], nasa_ortho[ok_full])[0, 1])
        if n_full > 100
        else float("nan")
    )
    report.pearson_full_scene = pearson_full
    report.n_pixels_compared_full = n_full

    bbox = DEFAULT_PLUME_BBOX
    report.plume_bbox = bbox
    in_bbox = (
        (lon_grid >= bbox["min_lon"])
        & (lon_grid <= bbox["max_lon"])
        & (lat_grid >= bbox["min_lat"])
        & (lat_grid <= bbox["max_lat"])
    )
    ok_bbox = in_bbox & ok_full
    n_bbox = int(ok_bbox.sum())
    pearson_bbox = (
        float(np.corrcoef(ours_ortho[ok_bbox], nasa_ortho[ok_bbox])[0, 1])
        if n_bbox > 100
        else float("nan")
    )
    report.pearson_in_bbox = pearson_bbox
    report.n_pixels_compared_bbox = n_bbox

    # Strong-signal subset — where either side exceeds 200 ppm·m. Focuses the
    # statistic on actual plume pixels rather than the near-zero background.
    strong = ok_bbox & ((ours_ortho > 200.0) | (nasa_ortho > 200.0))
    n_strong = int(strong.sum())
    pearson_strong = (
        float(np.corrcoef(ours_ortho[strong], nasa_ortho[strong])[0, 1])
        if n_strong > 50
        else float("nan")
    )
    report.pearson_in_bbox_strong_signal = pearson_strong

    log(
        f"Pearson (UNSMOOTHED, common ortho grid) — full: {pearson_full:.3f}  "
        f"bbox: {pearson_bbox:.3f}  bbox-strong: {pearson_strong:.3f}"
    )

    # ---- 8. Render side-by-side PNG on the common ortho grid ----
    log("Rendering side-by-side PNG on the common ortho grid...")
    joint = np.concatenate(
        [
            ours_ortho[np.isfinite(ours_ortho)][:200_000],
            nasa_ortho[np.isfinite(nasa_ortho)][:200_000],
        ]
    )
    vmax = float(np.nanpercentile(joint, 99)) if joint.size > 0 else 1.0
    vmin = 0.0

    fig, axes = plt.subplots(1, 2, figsize=(16, 8), dpi=120)
    im0 = axes[0].imshow(
        ours_ortho, extent=extent, origin="upper", cmap="inferno", vmin=vmin, vmax=vmax,
        interpolation="nearest", aspect="equal",
    )
    axes[0].set_title("Our matched-filter enhancement (ppm·m)")
    axes[0].set_xlabel("Longitude")
    axes[0].set_ylabel("Latitude")
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

    im1 = axes[1].imshow(
        nasa_ortho, extent=extent, origin="upper", cmap="inferno", vmin=vmin, vmax=vmax,
        interpolation="nearest", aspect="equal",
    )
    axes[1].set_title("NASA L2B CH4ENH (same ortho grid, ppm·m)")
    axes[1].set_xlabel("Longitude")
    axes[1].set_ylabel("Latitude")
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)

    for ax in axes:
        ax.plot(
            [bbox["min_lon"], bbox["max_lon"], bbox["max_lon"], bbox["min_lon"], bbox["min_lon"]],
            [bbox["min_lat"], bbox["min_lat"], bbox["max_lat"], bbox["max_lat"], bbox["min_lat"]],
            "c-",
            lw=1.0,
            alpha=0.6,
        )

    fig.suptitle(
        f"Stage A — Goturdepe {ACQUISITION_UTC}  (common ortho grid, no smoothing)\n"
        f"Pearson over plume bbox: {pearson_bbox:.3f} "
        f"(strong-signal subset: {pearson_strong:.3f}, n={n_strong} px)",
        fontsize=12,
    )
    png_path = OUTPUT_DIR / "side_by_side.png"
    fig.tight_layout()
    fig.savefig(png_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    report.side_by_side_png = str(png_path)
    log(f"Side-by-side PNG: {png_path}")

    # ---- 9. Write JSON report ----
    report.finished_utc = datetime.now(UTC).isoformat()
    json_path = OUTPUT_DIR / "stage_a_report.json"
    with json_path.open("w") as f:
        json.dump(asdict(report), f, indent=2)
    log(f"Report: {json_path}")

    log("Stage A complete. Summary:")
    log(f"  Acquisition: {ACQUISITION_UTC}")
    log(f"  L1B granule: {L1B_UR}")
    log(f"  Pixels compared (full scene):    {n_full}")
    log(f"  Pixels compared (plume bbox):    {n_bbox}")
    log(f"  Pearson — full scene:            {pearson_full:.3f}")
    log(f"  Pearson — plume bbox:            {pearson_bbox:.3f}")
    log(f"  Pearson — plume bbox, strong:    {pearson_strong:.3f}  (n={n_strong})")
    log("Stage B (IME / Q) is NOT run by this script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
