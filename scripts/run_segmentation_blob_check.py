"""Run Varon segmentation on the restored Stage A ortho enhancement and
report whether the two saturated round blobs are INSIDE or OUTSIDE the
plume's connected component(s).

This is a Stage A diagnostic, NOT Stage B. It produces:
  - stage_a_outputs/.../plume_mask_overlay.png — overlay PNG
  - stage_a_outputs/.../segmentation_report.json — numerical findings

Inputs are read-only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from aether_detection.plume_segmentation import (
    component_label_at_point,
    largest_component_in_region,
    segment_plume_varon,
)

OUTPUT_DIR = Path("stage_a_outputs/turkmenistan_goturdepe_2022_08_15")
ORTHO_NPZ = OUTPUT_DIR / "our_enhancement_ortho.npz"

# Plume bbox per the benchmark YAML (the region we expect plume(s) to lie in).
PLUME_BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}

# The two round saturated blobs visible in side_by_side.png. These bboxes
# are from scripts/diagnose_blob_mass_change.py — chosen to enclose each
# bright disk, NOT chosen by trial and error after seeing the segmentation
# result. They are the same bboxes used in the earlier blob-mass integral.
BLOB_A_BBOX = {"min_lon": 53.45, "max_lon": 53.58, "min_lat": 39.50, "max_lat": 39.60}
BLOB_B_BBOX = {"min_lon": 53.55, "max_lon": 53.68, "min_lat": 39.42, "max_lat": 39.52}


@dataclass
class SegReport:
    n_components: int = 0
    background_n: int = 0
    background_mean_ppmm: float = 0.0
    background_std_ppmm: float = 0.0
    plume_component_label: int = 0
    plume_component_pixel_count: int = 0
    blob_a_center: tuple[float, float] | None = None
    blob_a_component_label: int = 0
    blob_a_component_pixel_count: int = 0
    blob_a_inside_plume: bool = False
    blob_b_center: tuple[float, float] | None = None
    blob_b_component_label: int = 0
    blob_b_component_pixel_count: int = 0
    blob_b_inside_plume: bool = False
    top10_component_pixel_counts: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def find_blob_peak(
    enh: np.ndarray, lon_centers: np.ndarray, lat_centers: np.ndarray,
    bbox: dict,
) -> tuple[float, float, int, int]:
    """Locate the brightest pixel inside a blob bbox; return (lon, lat, row, col)."""
    in_lon = (lon_centers >= bbox["min_lon"]) & (lon_centers <= bbox["max_lon"])
    in_lat = (lat_centers >= bbox["min_lat"]) & (lat_centers <= bbox["max_lat"])
    col_idx = np.where(in_lon)[0]
    row_idx = np.where(in_lat)[0]
    sub = enh[np.ix_(row_idx, col_idx)]
    sub_finite = np.where(np.isfinite(sub), sub, -np.inf)
    flat = int(np.argmax(sub_finite))
    sub_r, sub_c = np.unravel_index(flat, sub.shape)
    row = int(row_idx[sub_r])
    col = int(col_idx[sub_c])
    return float(lon_centers[col]), float(lat_centers[row]), row, col


def main() -> None:
    print(f"Loading {ORTHO_NPZ}...")
    npz = np.load(ORTHO_NPZ)
    enh = npz["enhancement_ppm_m"]
    lon_c = npz["ortho_lon_centers"]
    lat_c = npz["ortho_lat_centers"]
    print(f"  shape={enh.shape}  lon range=[{lon_c.min():.3f}, {lon_c.max():.3f}]")

    # Build background mask: every pixel that is finite AND outside the
    # plume bbox. The bbox covers ~25% of the scene, so we still have
    # roughly 1.5M background pixels for the t-test reference.
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    in_bbox = (
        (lon_grid >= PLUME_BBOX["min_lon"]) & (lon_grid <= PLUME_BBOX["max_lon"])
        & (lat_grid >= PLUME_BBOX["min_lat"]) & (lat_grid <= PLUME_BBOX["max_lat"])
    )
    finite = np.isfinite(enh)
    bg_mask = finite & (~in_bbox)
    print(f"  background pixels (outside bbox, finite): {int(bg_mask.sum())}")

    print("Running Varon segmentation (5×5 t-test, 3×3 median, σ=2 gaussian, >0.5 threshold)...")
    result = segment_plume_varon(enh, bg_mask)
    print(f"  n components: {result.n_components}")
    print(f"  background μ={result.background_mean:+.2f} ppm·m  "
          f"σ={result.background_variance ** 0.5:.2f} ppm·m  n={result.background_n}")

    rep = SegReport()
    rep.n_components = result.n_components
    rep.background_n = result.background_n
    rep.background_mean_ppmm = float(result.background_mean)
    rep.background_std_ppmm = float(np.sqrt(result.background_variance))

    counts = result.component_pixel_counts
    if counts.size > 1:
        nonzero = counts[1:]
        top_idx = np.argsort(-nonzero)[:10]
        rep.top10_component_pixel_counts = [int(nonzero[i]) for i in top_idx]
        print(f"  top-10 component pixel counts: {rep.top10_component_pixel_counts}")

    # The "plume": the largest connected component inside the plume bbox.
    plume_label = largest_component_in_region(
        result.labels, lon_c, lat_c,
        PLUME_BBOX["min_lon"], PLUME_BBOX["max_lon"],
        PLUME_BBOX["min_lat"], PLUME_BBOX["max_lat"],
    )
    rep.plume_component_label = int(plume_label)
    if plume_label > 0:
        rep.plume_component_pixel_count = int(counts[plume_label])
        print(f"  plume CC label = {plume_label}  pixel count = {counts[plume_label]}")
    else:
        rep.notes.append("No plume CC found in bbox — segmentation found nothing inside the bbox.")
        print("  WARNING: no plume CC found in bbox")

    # The two blob centres — defined as the brightest pixel inside each
    # blob bbox in the enhancement raster (not hand-picked coordinates).
    for name, bbox, set_label, set_count, set_center, set_inside in [
        ("A", BLOB_A_BBOX, "blob_a_component_label", "blob_a_component_pixel_count",
         "blob_a_center", "blob_a_inside_plume"),
        ("B", BLOB_B_BBOX, "blob_b_component_label", "blob_b_component_pixel_count",
         "blob_b_center", "blob_b_inside_plume"),
    ]:
        lon, lat, row, col = find_blob_peak(enh, lon_c, lat_c, bbox)
        setattr(rep, set_center, (lon, lat))
        label = component_label_at_point(result.labels, lon_c, lat_c, lon, lat)
        setattr(rep, set_label, int(label))
        if label > 0:
            setattr(rep, set_count, int(counts[label]))
        inside = bool(label == plume_label and plume_label > 0)
        setattr(rep, set_inside, inside)
        print(
            f"  Blob {name}: brightest at lon={lon:.4f} lat={lat:.4f} "
            f"(value={enh[row, col]:+.1f} ppm·m)  → CC label = {label}  "
            f"{'inside plume CC' if inside else 'OUTSIDE plume CC'}"
        )

    # ---------- Render overlay ----------
    print("Rendering plume_mask_overlay.png...")
    fig, axes = plt.subplots(1, 2, figsize=(16, 8), dpi=120)
    extent = [float(lon_c[0]), float(lon_c[-1]), float(lat_c[-1]), float(lat_c[0])]
    joint = enh[np.isfinite(enh)][:200_000]
    vmax = float(np.nanpercentile(joint, 99)) if joint.size > 0 else 1.0

    im0 = axes[0].imshow(
        enh, extent=extent, origin="upper", cmap="inferno", vmin=0.0, vmax=vmax,
        aspect="equal", interpolation="nearest",
    )
    axes[0].set_title("Our enhancement (ppm·m)")
    axes[0].set_xlabel("Longitude")
    axes[0].set_ylabel("Latitude")
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)

    # Right panel: plume mask outline overlaid on the enhancement.
    im1 = axes[1].imshow(
        enh, extent=extent, origin="upper", cmap="inferno", vmin=0.0, vmax=vmax,
        aspect="equal", interpolation="nearest",
    )
    # Plume CC: shown as a cyan filled mask at low alpha plus a hard outline.
    plume_mask = (result.labels == plume_label) if plume_label > 0 else np.zeros_like(result.labels, bool)
    cyan_overlay = np.zeros((*plume_mask.shape, 4))
    cyan_overlay[plume_mask] = [0.0, 1.0, 1.0, 0.35]
    axes[1].imshow(cyan_overlay, extent=extent, origin="upper", aspect="equal")
    axes[1].contour(
        plume_mask.astype(float), levels=[0.5],
        extent=extent, origin="upper", colors="cyan", linewidths=1.4,
    )

    # Mark blob centres
    blob_pts = [
        (rep.blob_a_center, "Blob A", rep.blob_a_inside_plume),
        (rep.blob_b_center, "Blob B", rep.blob_b_inside_plume),
    ]
    for center, label, inside in blob_pts:
        if center is None:
            continue
        edge = "lime" if not inside else "red"
        for ax in axes:
            ax.plot(center[0], center[1], marker="o", markersize=12, markeredgewidth=2.2,
                    markeredgecolor=edge, markerfacecolor="none")
            ax.annotate(label, center, color=edge, fontsize=10, fontweight="bold",
                        xytext=(8, 8), textcoords="offset points")

    # Outline the plume bbox for context
    for ax in axes:
        ax.add_patch(patches.Rectangle(
            (PLUME_BBOX["min_lon"], PLUME_BBOX["min_lat"]),
            PLUME_BBOX["max_lon"] - PLUME_BBOX["min_lon"],
            PLUME_BBOX["max_lat"] - PLUME_BBOX["min_lat"],
            fill=False, edgecolor="white", lw=0.8, alpha=0.6, ls="--",
        ))

    axes[1].set_title(
        f"Plume CC (cyan) + blob centres\n"
        f"Blob A: {'INSIDE plume CC' if rep.blob_a_inside_plume else 'OUTSIDE plume CC'} | "
        f"Blob B: {'INSIDE plume CC' if rep.blob_b_inside_plume else 'OUTSIDE plume CC'}"
    )
    axes[1].set_xlabel("Longitude")
    axes[1].set_ylabel("Latitude")

    fig.tight_layout()
    out_png = OUTPUT_DIR / "plume_mask_overlay.png"
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_png}")

    # Second render: zoomed into the plume bbox so the plume CC and blob
    # locations are clearly visible at full pixel resolution.
    fig2, ax = plt.subplots(figsize=(12, 8), dpi=150)
    ax.imshow(
        enh, extent=extent, origin="upper", cmap="inferno", vmin=0.0, vmax=vmax,
        aspect="equal", interpolation="nearest",
    )
    ax.imshow(cyan_overlay, extent=extent, origin="upper", aspect="equal")
    ax.contour(
        plume_mask.astype(float), levels=[0.5],
        extent=extent, origin="upper", colors="cyan", linewidths=1.8,
    )
    for center, label, inside in blob_pts:
        if center is None:
            continue
        edge = "lime" if not inside else "red"
        ax.plot(center[0], center[1], marker="o", markersize=18, markeredgewidth=2.5,
                markeredgecolor=edge, markerfacecolor="none")
        ax.annotate(label, center, color=edge, fontsize=12, fontweight="bold",
                    xytext=(12, 12), textcoords="offset points")
    ax.add_patch(patches.Rectangle(
        (PLUME_BBOX["min_lon"], PLUME_BBOX["min_lat"]),
        PLUME_BBOX["max_lon"] - PLUME_BBOX["min_lon"],
        PLUME_BBOX["max_lat"] - PLUME_BBOX["min_lat"],
        fill=False, edgecolor="white", lw=1.0, alpha=0.7, ls="--",
    ))
    # Zoom to the plume bbox with a small margin.
    margin = 0.05
    ax.set_xlim(PLUME_BBOX["min_lon"] - margin, PLUME_BBOX["max_lon"] + margin)
    ax.set_ylim(PLUME_BBOX["min_lat"] - margin, PLUME_BBOX["max_lat"] + margin)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(
        f"Plume bbox zoom — cyan = plume CC (label {plume_label}, {counts[plume_label]} px)\n"
        f"Blob A CC={rep.blob_a_component_label} ({'INSIDE' if rep.blob_a_inside_plume else 'OUTSIDE'} plume CC), "
        f"Blob B CC={rep.blob_b_component_label} ({'INSIDE' if rep.blob_b_inside_plume else 'OUTSIDE'} plume CC)"
    )
    out_png_zoom = OUTPUT_DIR / "plume_mask_overlay_zoom.png"
    fig2.tight_layout()
    fig2.savefig(out_png_zoom, dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"  wrote {out_png_zoom}")

    # Save JSON
    out_json = OUTPUT_DIR / "segmentation_report.json"
    with out_json.open("w") as f:
        json.dump(asdict(rep), f, indent=2)
    print(f"  wrote {out_json}")

    print()
    print("=" * 64)
    print("HEADLINE:")
    print(f"  Plume CC label: {rep.plume_component_label}  "
          f"({rep.plume_component_pixel_count} pixels)")
    print(f"  Blob A: label={rep.blob_a_component_label}  "
          f"inside plume CC = {rep.blob_a_inside_plume}")
    print(f"  Blob B: label={rep.blob_b_component_label}  "
          f"inside plume CC = {rep.blob_b_inside_plume}")
    print("=" * 64)


if __name__ == "__main__":
    main()
