"""Pre-Stage-B diagnostic: characterise the plume CC's downwind tail and the
bright diagonal streak north of the plume.

Inputs:
- stage_a_outputs/.../our_enhancement_ortho.npz  (our MF, ortho grid)
- stage_a_outputs/.../our_enhancement_raw.npz    (our MF, raw geometry)
- ~/.aether_cache/emit_l2b_ch4/.../EMIT_L2B_CH4ENH*.tif (NASA L2B reference)

Outputs:
- tail_vs_ribbon_overlay.png   — CC 1213 split at 53.88E, ours vs NASA
- streak_character.png         — streak bbox: ours, NASA, raw-geometry footprint
- crosstrack_histogram.png     — distribution of streak-pixel crosstrack indices
- tail_and_streak_report.json  — every number

No production code is touched. No flux is computed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rioxarray
from aether_detection.plume_segmentation import (
    largest_component_in_region,
    segment_plume_varon,
)

# --------------------------------------------------------------------------- #
OUTPUT_DIR = Path("stage_a_outputs/turkmenistan_goturdepe_2022_08_15")
ORTHO_NPZ = OUTPUT_DIR / "our_enhancement_ortho.npz"
RAW_NPZ = OUTPUT_DIR / "our_enhancement_raw.npz"
L2B_TIF = Path(
    "/Users/animeshrajvanshi/.aether_cache/emit_l2b_ch4/"
    "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003/"
    "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003.tif"
)

PLUME_BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}

# Investigation 1: tail/ribbon split longitude.
TAIL_RIBBON_SPLIT_LON = 53.88

# Investigation 2: streak bounding box. Built from the two blob centres
# (Blob A at 53.4527, 39.5092; Blob B at 53.6295, 39.4707) and the visual
# extent of the linear feature in the overlay PNG, NOT chosen after seeing
# the diagnostic numbers.
STREAK_BBOX = {"min_lon": 53.40, "max_lon": 53.75, "min_lat": 39.46, "max_lat": 39.53}

PIXEL_AREA_M2 = 60.0 * 60.0  # EMIT nominal pixel size for IME book-keeping.


# --------------------------------------------------------------------------- #
@dataclass
class Report:
    # Tail vs ribbon
    plume_cc_label: int = 0
    plume_cc_total_pixels: int = 0
    ribbon_lon_max: float = TAIL_RIBBON_SPLIT_LON
    ribbon_n_pixels: int = 0
    ribbon_our_sum_ppmm: float = 0.0
    ribbon_our_mean_ppmm: float = 0.0
    ribbon_our_median_ppmm: float = 0.0
    ribbon_our_p95_ppmm: float = 0.0
    ribbon_nasa_mean_ppmm: float = 0.0
    ribbon_nasa_median_ppmm: float = 0.0
    ribbon_nasa_p95_ppmm: float = 0.0
    ribbon_our_nasa_pearson: float = 0.0

    tail_lon_min: float = TAIL_RIBBON_SPLIT_LON
    tail_n_pixels: int = 0
    tail_our_sum_ppmm: float = 0.0
    tail_our_mean_ppmm: float = 0.0
    tail_our_median_ppmm: float = 0.0
    tail_our_p95_ppmm: float = 0.0
    tail_nasa_mean_ppmm: float = 0.0
    tail_nasa_median_ppmm: float = 0.0
    tail_nasa_p95_ppmm: float = 0.0
    tail_our_nasa_pearson: float = 0.0

    plume_total_ppmm_pixel: float = 0.0  # signed sum over the whole CC
    tail_mass_fraction_of_plume: float = 0.0

    # Streak character
    streak_bbox: dict = field(default_factory=lambda: STREAK_BBOX)
    streak_n_pixels_in_bbox: int = 0
    streak_our_mean_ppmm: float = 0.0
    streak_our_median_ppmm: float = 0.0
    streak_our_p95_ppmm: float = 0.0
    streak_our_p99_ppmm: float = 0.0
    streak_nasa_mean_ppmm: float = 0.0
    streak_nasa_median_ppmm: float = 0.0
    streak_nasa_p95_ppmm: float = 0.0
    streak_nasa_p99_ppmm: float = 0.0
    streak_our_nasa_pearson: float = 0.0
    streak_our_nasa_ratio_p95: float = 0.0

    # Cross-track analysis (raw geometry)
    raw_streak_n_pixels: int = 0
    raw_streak_high_n_pixels: int = 0
    raw_streak_high_crosstrack_p5: int = 0
    raw_streak_high_crosstrack_p50: int = 0
    raw_streak_high_crosstrack_p95: int = 0
    raw_streak_high_crosstrack_iqr_fraction: float = 0.0
    raw_streak_high_crosstrack_top5_columns: list[int] = field(default_factory=list)
    raw_streak_high_crosstrack_top5_pct: list[float] = field(default_factory=list)
    raw_streak_high_crosstrack_distinct_cols: int = 0


# --------------------------------------------------------------------------- #
def sample_l2b_on_grid(lon_c: np.ndarray, lat_c: np.ndarray) -> np.ndarray:
    """Read the NASA L2B GeoTIFF and resample onto a target lon/lat grid.

    The L2B and our ortho npz already share the same EMIT GLT grid (we
    verified shape (1876, 2507) matches), so this is effectively a direct
    read — but we go through inverse-affine sampling to defend against any
    future grid drift.
    """
    l2b = rioxarray.open_rasterio(L2B_TIF, masked=True).squeeze("band", drop=True)
    transform = l2b.rio.transform()
    inv = ~transform
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    cols_f, rows_f = inv * (lon_grid.ravel(), lat_grid.ravel())
    cols_i = np.round(cols_f).astype(np.int64)
    rows_i = np.round(rows_f).astype(np.int64)
    h, w = l2b.shape
    valid = (rows_i >= 0) & (rows_i < h) & (cols_i >= 0) & (cols_i < w)
    out = np.full(lon_grid.size, np.nan, dtype=np.float64)
    out[valid] = l2b.values[rows_i[valid], cols_i[valid]]
    return out.reshape(lon_grid.shape)


def stats(arr: np.ndarray) -> tuple[float, float, float, float]:
    """Return (mean, median, p95, p99) over finite values."""
    a = arr[np.isfinite(arr)]
    if a.size == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    return (
        float(a.mean()),
        float(np.median(a)),
        float(np.percentile(a, 95)),
        float(np.percentile(a, 99)),
    )


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if int(ok.sum()) < 100:
        return float("nan")
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


# --------------------------------------------------------------------------- #
def main() -> None:
    print("Loading orthorectified rasters...")
    ortho = np.load(ORTHO_NPZ)
    ours = ortho["enhancement_ppm_m"]
    lon_c = ortho["ortho_lon_centers"]
    lat_c = ortho["ortho_lat_centers"]

    nasa = sample_l2b_on_grid(lon_c, lat_c)
    print(f"  ours shape={ours.shape}  nasa shape={nasa.shape}")

    print("Re-running segmentation (same params as Stage A run)...")
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    in_plume_bbox = (
        (lon_grid >= PLUME_BBOX["min_lon"]) & (lon_grid <= PLUME_BBOX["max_lon"])
        & (lat_grid >= PLUME_BBOX["min_lat"]) & (lat_grid <= PLUME_BBOX["max_lat"])
    )
    finite = np.isfinite(ours)
    bg_mask = finite & (~in_plume_bbox)
    seg = segment_plume_varon(ours, bg_mask)
    plume_label = largest_component_in_region(
        seg.labels, lon_c, lat_c,
        PLUME_BBOX["min_lon"], PLUME_BBOX["max_lon"],
        PLUME_BBOX["min_lat"], PLUME_BBOX["max_lat"],
    )
    print(f"  plume CC label = {plume_label}  pixel count = "
          f"{int((seg.labels == plume_label).sum())}")

    rep = Report()
    rep.plume_cc_label = int(plume_label)
    rep.plume_cc_total_pixels = int((seg.labels == plume_label).sum())

    # ===================================================================== #
    # Investigation 1: tail vs ribbon split at 53.88E
    # ===================================================================== #
    print(f"\n=== Investigation 1: tail/ribbon split at lon={TAIL_RIBBON_SPLIT_LON} ===")
    cc_mask = seg.labels == plume_label
    cc_lon = lon_grid[cc_mask]
    cc_ours = ours[cc_mask]
    cc_nasa = nasa[cc_mask]

    ribbon_mask = cc_lon <= TAIL_RIBBON_SPLIT_LON
    tail_mask = cc_lon > TAIL_RIBBON_SPLIT_LON

    ribbon_ours = cc_ours[ribbon_mask]
    ribbon_nasa = cc_nasa[ribbon_mask]
    tail_ours = cc_ours[tail_mask]
    tail_nasa = cc_nasa[tail_mask]

    rep.ribbon_n_pixels = int(ribbon_mask.sum())
    rep.tail_n_pixels = int(tail_mask.sum())

    rep.ribbon_our_sum_ppmm = float(np.nansum(ribbon_ours))
    m, med, p95, _ = stats(ribbon_ours)
    rep.ribbon_our_mean_ppmm, rep.ribbon_our_median_ppmm, rep.ribbon_our_p95_ppmm = m, med, p95
    m, med, p95, _ = stats(ribbon_nasa)
    rep.ribbon_nasa_mean_ppmm, rep.ribbon_nasa_median_ppmm, rep.ribbon_nasa_p95_ppmm = m, med, p95
    rep.ribbon_our_nasa_pearson = pearson(ribbon_ours, ribbon_nasa)

    rep.tail_our_sum_ppmm = float(np.nansum(tail_ours))
    m, med, p95, _ = stats(tail_ours)
    rep.tail_our_mean_ppmm, rep.tail_our_median_ppmm, rep.tail_our_p95_ppmm = m, med, p95
    m, med, p95, _ = stats(tail_nasa)
    rep.tail_nasa_mean_ppmm, rep.tail_nasa_median_ppmm, rep.tail_nasa_p95_ppmm = m, med, p95
    rep.tail_our_nasa_pearson = pearson(tail_ours, tail_nasa)

    total = float(np.nansum(cc_ours))
    rep.plume_total_ppmm_pixel = total
    rep.tail_mass_fraction_of_plume = rep.tail_our_sum_ppmm / total if total else float("nan")

    print(f"  Ribbon (lon ≤ {TAIL_RIBBON_SPLIT_LON}):  n={rep.ribbon_n_pixels}  "
          f"sum={rep.ribbon_our_sum_ppmm:+.3e}  "
          f"ours mean={rep.ribbon_our_mean_ppmm:+.1f}  median={rep.ribbon_our_median_ppmm:+.1f}  "
          f"p95={rep.ribbon_our_p95_ppmm:+.1f}")
    print(f"      NASA at same pixels: mean={rep.ribbon_nasa_mean_ppmm:+.1f}  "
          f"median={rep.ribbon_nasa_median_ppmm:+.1f}  p95={rep.ribbon_nasa_p95_ppmm:+.1f}  "
          f"Pearson(ours, NASA) over ribbon = {rep.ribbon_our_nasa_pearson:+.3f}")
    print(f"  Tail   (lon > {TAIL_RIBBON_SPLIT_LON}):  n={rep.tail_n_pixels}  "
          f"sum={rep.tail_our_sum_ppmm:+.3e}  "
          f"ours mean={rep.tail_our_mean_ppmm:+.1f}  median={rep.tail_our_median_ppmm:+.1f}  "
          f"p95={rep.tail_our_p95_ppmm:+.1f}")
    print(f"      NASA at same pixels: mean={rep.tail_nasa_mean_ppmm:+.1f}  "
          f"median={rep.tail_nasa_median_ppmm:+.1f}  p95={rep.tail_nasa_p95_ppmm:+.1f}  "
          f"Pearson(ours, NASA) over tail = {rep.tail_our_nasa_pearson:+.3f}")
    print(f"  Tail mass fraction of plume CC: {rep.tail_mass_fraction_of_plume * 100:+.1f}%")

    # ===================================================================== #
    # Investigation 2: streak character
    # ===================================================================== #
    print("\n=== Investigation 2: streak character ===")
    streak_mask = (
        (lon_grid >= STREAK_BBOX["min_lon"]) & (lon_grid <= STREAK_BBOX["max_lon"])
        & (lat_grid >= STREAK_BBOX["min_lat"]) & (lat_grid <= STREAK_BBOX["max_lat"])
    )
    streak_ours = ours[streak_mask & finite]
    streak_nasa = nasa[streak_mask & finite]
    rep.streak_n_pixels_in_bbox = int(streak_mask.sum())
    m, med, p95, p99 = stats(streak_ours)
    rep.streak_our_mean_ppmm, rep.streak_our_median_ppmm = m, med
    rep.streak_our_p95_ppmm, rep.streak_our_p99_ppmm = p95, p99
    m, med, p95, p99 = stats(streak_nasa)
    rep.streak_nasa_mean_ppmm, rep.streak_nasa_median_ppmm = m, med
    rep.streak_nasa_p95_ppmm, rep.streak_nasa_p99_ppmm = p95, p99
    rep.streak_our_nasa_pearson = pearson(ours[streak_mask], nasa[streak_mask])
    if rep.streak_nasa_p95_ppmm > 0:
        rep.streak_our_nasa_ratio_p95 = rep.streak_our_p95_ppmm / rep.streak_nasa_p95_ppmm

    print(f"  Streak bbox n_pixels: {rep.streak_n_pixels_in_bbox}")
    print(f"  OURS:  mean={rep.streak_our_mean_ppmm:+.1f}  "
          f"median={rep.streak_our_median_ppmm:+.1f}  "
          f"p95={rep.streak_our_p95_ppmm:+.1f}  p99={rep.streak_our_p99_ppmm:+.1f}")
    print(f"  NASA:  mean={rep.streak_nasa_mean_ppmm:+.1f}  "
          f"median={rep.streak_nasa_median_ppmm:+.1f}  "
          f"p95={rep.streak_nasa_p95_ppmm:+.1f}  p99={rep.streak_nasa_p99_ppmm:+.1f}")
    print(f"  Pearson(ours, NASA) over streak bbox: {rep.streak_our_nasa_pearson:+.3f}")
    print(f"  p95 ratio (ours / NASA): {rep.streak_our_nasa_ratio_p95:+.2f}")

    # ===================================================================== #
    # Cross-track raw analysis: does the streak concentrate on a few cols?
    # ===================================================================== #
    print("\n=== Cross-track raw-geometry analysis ===")
    raw = np.load(RAW_NPZ)
    raw_enh = raw["enhancement_ppm_m"]
    raw_lon = raw["lon"]
    raw_lat = raw["lat"]

    raw_in_streak = (
        (raw_lon >= STREAK_BBOX["min_lon"]) & (raw_lon <= STREAK_BBOX["max_lon"])
        & (raw_lat >= STREAK_BBOX["min_lat"]) & (raw_lat <= STREAK_BBOX["max_lat"])
    )
    raw_finite = np.isfinite(raw_enh)
    rep.raw_streak_n_pixels = int((raw_in_streak & raw_finite).sum())
    # "High" pixels — those that drive the streak. Threshold at 200 ppm·m
    # to match the strong-signal definition used in the Stage A report.
    high_thresh = 200.0
    raw_high = raw_in_streak & raw_finite & (raw_enh > high_thresh)
    rep.raw_streak_high_n_pixels = int(raw_high.sum())
    _rows, raw_cols = np.where(raw_high)
    if raw_cols.size > 0:
        rep.raw_streak_high_crosstrack_p5 = int(np.percentile(raw_cols, 5))
        rep.raw_streak_high_crosstrack_p50 = int(np.percentile(raw_cols, 50))
        rep.raw_streak_high_crosstrack_p95 = int(np.percentile(raw_cols, 95))
        n_distinct = int(np.unique(raw_cols).size)
        rep.raw_streak_high_crosstrack_distinct_cols = n_distinct
        rep.raw_streak_high_crosstrack_iqr_fraction = (
            float(rep.raw_streak_high_crosstrack_p95 - rep.raw_streak_high_crosstrack_p5)
            / raw_enh.shape[1]
        )
        unique, counts = np.unique(raw_cols, return_counts=True)
        top5_order = np.argsort(-counts)[:5]
        rep.raw_streak_high_crosstrack_top5_columns = [int(unique[i]) for i in top5_order]
        rep.raw_streak_high_crosstrack_top5_pct = [
            float(counts[i] / raw_cols.size * 100.0) for i in top5_order
        ]

    print(f"  Raw pixels with (lon,lat) in streak bbox: {rep.raw_streak_n_pixels}")
    print(f"  Of those, raw pixels with enh > {high_thresh} ppm·m: {rep.raw_streak_high_n_pixels}")
    print(f"  Their crosstrack-column distribution: p5={rep.raw_streak_high_crosstrack_p5}  "
          f"p50={rep.raw_streak_high_crosstrack_p50}  p95={rep.raw_streak_high_crosstrack_p95}  "
          f"(out of 1242 columns total)")
    print(f"  IQR-fraction of swath width: "
          f"{rep.raw_streak_high_crosstrack_iqr_fraction * 100:.1f}%")
    print("  N distinct crosstrack columns spanned: "
          f"{rep.raw_streak_high_crosstrack_distinct_cols}")
    top5 = list(zip(
        rep.raw_streak_high_crosstrack_top5_columns,
        [f"{p:.1f}%" for p in rep.raw_streak_high_crosstrack_top5_pct],
        strict=True,
    ))
    print(f"  Top-5 crosstrack columns (col idx, % of high pixels): {top5}")

    # ===================================================================== #
    # Render diagnostics
    # ===================================================================== #
    print("\nRendering diagnostic PNGs...")
    extent = [float(lon_c[0]), float(lon_c[-1]), float(lat_c[-1]), float(lat_c[0])]
    joint = ours[np.isfinite(ours)][:200_000]
    vmax = float(np.nanpercentile(joint, 99)) if joint.size > 0 else 1.0

    # ---- Tail vs ribbon overlay ----
    fig, axes = plt.subplots(1, 2, figsize=(16, 8), dpi=150)
    plot_extent_pad = 0.05
    # Compute the bbox that tightly encloses CC 1213
    cc_rows, cc_cols = np.where(seg.labels == plume_label)
    cc_lon_min = float(lon_c[cc_cols.min()]) - plot_extent_pad
    cc_lon_max = float(lon_c[cc_cols.max()]) + plot_extent_pad
    cc_lat_min = float(lat_c[cc_rows.max()]) - plot_extent_pad
    cc_lat_max = float(lat_c[cc_rows.min()]) + plot_extent_pad

    for ax, panel, title in [
        (axes[0], ours, "Our MF enhancement (ppm·m) with CC 1213 outlined"),
        (axes[1], nasa, "NASA L2B CH4ENH on same grid (ppm·m)"),
    ]:
        ax.imshow(panel, extent=extent, origin="upper", cmap="inferno",
                  vmin=0.0, vmax=vmax, aspect="equal", interpolation="nearest")
        # Plume CC outline (cyan)
        ax.contour(
            (seg.labels == plume_label).astype(float), levels=[0.5],
            extent=extent, origin="upper", colors="cyan", linewidths=1.5,
        )
        # Vertical line at the tail/ribbon split
        ax.axvline(TAIL_RIBBON_SPLIT_LON, color="white", linestyle=":", linewidth=1.2,
                   alpha=0.85)
        ax.text(TAIL_RIBBON_SPLIT_LON + 0.01, cc_lat_min + 0.01,
                f"split lon={TAIL_RIBBON_SPLIT_LON}", color="white", fontsize=10)
        ax.set_xlim(cc_lon_min, cc_lon_max)
        ax.set_ylim(cc_lat_min, cc_lat_max)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title(title)
    fig.suptitle(
        f"Plume CC {plume_label}: ribbon (n={rep.ribbon_n_pixels}, "
        f"our mean={rep.ribbon_our_mean_ppmm:+.0f} ppm·m, "
        f"NASA mean={rep.ribbon_nasa_mean_ppmm:+.0f}) | "
        f"tail (n={rep.tail_n_pixels}, our mean={rep.tail_our_mean_ppmm:+.0f}, "
        f"NASA mean={rep.tail_nasa_mean_ppmm:+.0f}); "
        f"tail mass = {rep.tail_mass_fraction_of_plume * 100:+.1f}% of CC's signed mass"
    )
    fig.tight_layout()
    out1 = OUTPUT_DIR / "tail_vs_ribbon_overlay.png"
    fig.savefig(out1, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out1}")

    # ---- Streak character ----
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), dpi=150)
    for ax, panel, title in [
        (axes[0], ours, "Our MF enhancement (ppm·m), streak bbox"),
        (axes[1], nasa, "NASA L2B CH4ENH (ppm·m), same bbox"),
    ]:
        ax.imshow(panel, extent=extent, origin="upper", cmap="inferno",
                  vmin=0.0, vmax=vmax, aspect="equal", interpolation="nearest")
        ax.set_xlim(STREAK_BBOX["min_lon"] - 0.02, STREAK_BBOX["max_lon"] + 0.02)
        ax.set_ylim(STREAK_BBOX["min_lat"] - 0.02, STREAK_BBOX["max_lat"] + 0.02)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title(title)
    fig.suptitle(
        f"Streak bbox: ours p95={rep.streak_our_p95_ppmm:+.0f}  "
        f"NASA p95={rep.streak_nasa_p95_ppmm:+.0f}  "
        f"Pearson(ours, NASA)={rep.streak_our_nasa_pearson:+.3f}  "
        f"p95 ratio = {rep.streak_our_nasa_ratio_p95:+.2f}"
    )
    fig.tight_layout()
    out2 = OUTPUT_DIR / "streak_character.png"
    fig.savefig(out2, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out2}")

    # ---- Crosstrack histogram ----
    if rep.raw_streak_high_n_pixels > 0:
        fig, ax = plt.subplots(figsize=(12, 4.5), dpi=140)
        ax.hist(raw_cols, bins=80, range=(0, raw_enh.shape[1]), color="orange", edgecolor="black")
        ax.set_xlabel("Cross-track column index (0 = swath edge, 1241 = other edge)")
        ax.set_ylabel(f"High-enhancement raw pixels (enh > {high_thresh} ppm·m)")
        ax.set_title(
            f"Cross-track distribution of high streak pixels (raw geometry, n={raw_cols.size}) — "
            f"covers {rep.raw_streak_high_crosstrack_iqr_fraction * 100:.1f}% of swath width "
            f"(p5={rep.raw_streak_high_crosstrack_p5} to p95={rep.raw_streak_high_crosstrack_p95})"
        )
        ax.grid(True, alpha=0.3)
        out3 = OUTPUT_DIR / "crosstrack_histogram.png"
        fig.tight_layout()
        fig.savefig(out3, dpi=140, bbox_inches="tight")
        plt.close(fig)
        print(f"  wrote {out3}")

    # ---- JSON report ----
    out_json = OUTPUT_DIR / "tail_and_streak_report.json"
    with out_json.open("w") as f:
        json.dump(asdict(rep), f, indent=2)
    print(f"  wrote {out_json}")


if __name__ == "__main__":
    main()
