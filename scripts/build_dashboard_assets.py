"""Derive the committable dashboard rasters from Stage A/B outputs.

Sprint 3 serves the methane plume as a georeferenced image overlay on the
Cesium globe. The orthorectified enhancement lives in a gitignored ``.npz``
(large, regenerable) and NASA's L2B reference lives in the gitignored
``.aether_cache`` GeoTIFF. This script renders small, *committable* artefacts
from them so ``apps/api`` can serve real pixels from version control and a
fresh clone (after regenerating Stage A/B) still works:

  enhancement.png  — our orthorectified MF retrieval, inferno colormap
  nasa.png         — NASA L2B CH4ENH on the SAME ortho grid (already aligned)
  diff.png         — (ours - nasa), diverging colormap, for the Δ toggle
  bounds.json      — EPSG:4326 [west, south, east, north] of the crop
  mask.geojson     — outline of plume CC 1213 in lon/lat (cyan in the UI)

Nothing here invents data. The plume mask is reconstructed with the *exact*
Stage B segmentation call (``segment_plume_varon`` at p<0.05 +
``largest_component_in_region``); the script asserts the regenerated label and
pixel count equal the committed ``q_estimate.json`` before writing, so the
GeoJSON is provably the same CC that was quantified. The colormap window is a
robust percentile of the data, recorded in ``bounds.json`` for reproducibility.

Run from the repo root:  uv run python scripts/build_dashboard_assets.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.image as mpimg
import numpy as np
import rasterio.features
import rioxarray
from aether_detection.plume_segmentation import (
    largest_component_in_region,
    segment_plume_varon,
)
from affine import Affine
from matplotlib import colormaps

# --- Paths: mirror scripts/run_stage_b_goturdepe.py so we read the same files - #
EVENT_ID = "turkmenistan_goturdepe_2022_08_15"
REPO_ROOT = Path(__file__).resolve().parents[1]
STAGE_A_DIR = REPO_ROOT / "stage_a_outputs" / EVENT_ID
STAGE_B_DIR = REPO_ROOT / "stage_b_outputs" / EVENT_ID
ORTHO_NPZ = STAGE_A_DIR / "our_enhancement_ortho.npz"
Q_ESTIMATE = STAGE_B_DIR / "q_estimate.json"
L2B_TIF = Path(
    "~/.aether_cache/emit_l2b_ch4/"
    "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003/"
    "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003.tif"
).expanduser()

OUT_DIR = REPO_ROOT / "apps" / "api" / "aether_api" / "assets" / EVENT_ID

# Segmentation parameters — identical to run_stage_b_goturdepe.py. Do not drift.
PLUME_BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}
CENTRAL_P_VALUE = 0.05


def _load_ortho() -> tuple[np.ndarray, np.ndarray, np.ndarray, Affine]:
    """Load our ortho enhancement, its lon/lat centers and the L2B affine."""
    npz = np.load(ORTHO_NPZ)
    enh = npz["enhancement_ppm_m"]
    lon_c = npz["ortho_lon_centers"]
    lat_c = npz["ortho_lat_centers"]
    transform = Affine(*npz["l2b_transform"])
    return enh, lon_c, lat_c, transform


def _sample_l2b_on_grid(lon_c: np.ndarray, lat_c: np.ndarray) -> np.ndarray:
    """NASA L2B on our ortho grid — same nearest-pixel sampling as Stage B."""
    l2b = rioxarray.open_rasterio(L2B_TIF, masked=True).squeeze("band", drop=True)
    inv = ~l2b.rio.transform()
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    cols_f, rows_f = inv * (lon_grid.ravel(), lat_grid.ravel())
    cols_i = np.round(cols_f).astype(np.int64)
    rows_i = np.round(rows_f).astype(np.int64)
    h, w = l2b.shape
    valid = (rows_i >= 0) & (rows_i < h) & (cols_i >= 0) & (cols_i < w)
    out = np.full(lon_grid.size, np.nan, dtype=np.float64)
    out[valid] = np.asarray(l2b.values)[rows_i[valid], cols_i[valid]]
    return out.reshape(lon_grid.shape)


def _reconstruct_plume_mask(enh: np.ndarray, lon_c: np.ndarray, lat_c: np.ndarray) -> np.ndarray:
    """Rebuild CC 1213 exactly as Stage B did, and verify against q_estimate.json."""
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    in_bbox = (
        (lon_grid >= PLUME_BBOX["min_lon"])
        & (lon_grid <= PLUME_BBOX["max_lon"])
        & (lat_grid >= PLUME_BBOX["min_lat"])
        & (lat_grid <= PLUME_BBOX["max_lat"])
    )
    bg_mask = np.isfinite(enh) & (~in_bbox)
    seg = segment_plume_varon(enh, bg_mask, p_value=CENTRAL_P_VALUE)
    label = largest_component_in_region(
        seg.labels,
        lon_c,
        lat_c,
        PLUME_BBOX["min_lon"],
        PLUME_BBOX["max_lon"],
        PLUME_BBOX["min_lat"],
        PLUME_BBOX["max_lat"],
    )
    mask = seg.labels == label

    q = json.loads(Q_ESTIMATE.read_text())
    assert label == q["plume_cc_label"], f"label {label} != committed {q['plume_cc_label']}"
    assert int(mask.sum()) == q["plume_cc_pixel_count"], (
        f"pixel count {int(mask.sum())} != committed {q['plume_cc_pixel_count']}"
    )
    print(f"  plume mask verified: CC {label}, {int(mask.sum())} px (matches q_estimate.json)")
    return mask


def _crop_to_mask(
    mask: np.ndarray, *arrays: np.ndarray, lon_c: np.ndarray, lat_c: np.ndarray, margin: float = 0.6
) -> tuple[list[np.ndarray], np.ndarray, np.ndarray]:
    """Crop arrays + axes to the plume mask's bounding box + ``margin`` (frac of span).

    Framing the overlay on the quantified plume (CC 1213) — rather than the whole
    0.7°x0.4° segmentation bbox, which is mostly background speckle — makes the
    plume legible, matching the mockup. Cesium still anchors the image at its true
    lon/lat bounds (recorded in bounds.json), so this is purely a framing choice.
    """
    rows, cols = np.where(mask)
    r0, r1 = rows.min(), rows.max() + 1
    c0, c1 = cols.min(), cols.max() + 1
    mr = int((r1 - r0) * margin)
    mc = int((c1 - c0) * margin)
    r0, r1 = max(0, r0 - mr), min(mask.shape[0], r1 + mr)
    c0, c1 = max(0, c0 - mc), min(mask.shape[1], c1 + mc)
    cropped = [a[r0:r1, c0:c1] for a in arrays]
    return cropped, lon_c[c0:c1], lat_c[r0:r1]


def _bounds_from_centers(lon_c: np.ndarray, lat_c: np.ndarray) -> dict[str, float]:
    """EPSG:4326 pixel-edge bounds from cell centers (half a pixel beyond edges)."""
    dx = float(np.abs(np.mean(np.diff(lon_c))))
    dy = float(np.abs(np.mean(np.diff(lat_c))))
    return {
        "west": float(lon_c.min() - dx / 2),
        "east": float(lon_c.max() + dx / 2),
        "south": float(lat_c.min() - dy / 2),
        "north": float(lat_c.max() + dy / 2),
    }


def _write_colormap_png(
    arr: np.ndarray,
    path: Path,
    cmap: str,
    vmin: float,
    vmax: float,
    *,
    ramp_alpha: bool,
    emphasis: np.ndarray | None = None,
) -> None:
    """RGBA PNG: NaN -> transparent, finite -> colormap. Row 0 = north (origin upper).

    When ``ramp_alpha`` is set (the inferno enhancement/NASA layers), alpha rises
    with the normalized value so the bright field glows and weak background fades
    into the terrain — the mockup's over-terrain look — without discarding pixels.
    When ``emphasis`` (the plume mask) is given, those pixels are floored to high
    opacity so the quantified plume CC reads as the hero against faint context.
    The diff layer uses flat alpha so positive and negative excursions read equally.
    """
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    normalized = norm(np.nan_to_num(arr, nan=vmin))
    rgba = colormaps[cmap](normalized)
    finite = np.isfinite(arr)
    if ramp_alpha:
        alpha = np.where(finite, np.clip(normalized, 0.0, 1.0) ** 0.9, 0.0)
        if emphasis is not None:
            alpha = np.where(emphasis & finite, np.maximum(alpha, 0.92), alpha * 0.55)
        rgba[..., 3] = alpha
    else:
        rgba[..., 3] = np.where(finite, 1.0, 0.0)
    mpimg.imsave(path, (rgba * 255).astype(np.uint8))
    print(f"  wrote {path.relative_to(REPO_ROOT)}  ({arr.shape[1]}x{arr.shape[0]})")


def _write_mask_geojson(mask: np.ndarray, transform: Affine, path: Path) -> None:
    """Vectorize the plume mask to lon/lat polygons (largest first)."""
    shapes = [
        geom
        for geom, val in rasterio.features.shapes(mask.astype(np.uint8), transform=transform)
        if val == 1
    ]
    shapes.sort(key=lambda g: -len(g["coordinates"][0]))
    fc: dict[str, Any] = {
        "type": "FeatureCollection",
        "properties": {"cc_label": 1213, "source": "stage_b segment_plume_varon p<0.05"},
        "features": [
            {"type": "Feature", "properties": {"rank": i}, "geometry": g}
            for i, g in enumerate(shapes)
        ],
    }
    path.write_text(json.dumps(fc))
    print(f"  wrote {path.relative_to(REPO_ROOT)}  ({len(shapes)} polygon(s))")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Building dashboard assets for {EVENT_ID} -> {OUT_DIR.relative_to(REPO_ROOT)}")

    enh, lon_c, lat_c, _transform = _load_ortho()
    print(f"  ortho grid: {enh.shape}")
    nasa = _sample_l2b_on_grid(lon_c, lat_c)
    mask_full = _reconstruct_plume_mask(enh, lon_c, lat_c)

    # Crop everything to the plume's own bounding box + margin (legible framing).
    (enh_c, nasa_c, mask_c), lon_cc, lat_cc = _crop_to_mask(
        mask_full, enh, nasa, mask_full, lon_c=lon_c, lat_c=lat_c
    )
    bounds = _bounds_from_centers(lon_cc, lat_cc)

    # Colormap window: 0 -> 98th percentile of the *in-mask plume* signal. The
    # plume's own dynamic range sets the scale (principled, not eyeballed); the
    # off-plume field (background std ~480 ppm·m) fades via the alpha ramp rather
    # than dominating a symmetric percentile window.
    plume_vals = enh_c[mask_c & np.isfinite(enh_c)]
    vmin = 0.0
    vmax = float(np.percentile(plume_vals, 98))
    print(f"  colormap window (ppm·m): vmin={vmin:.1f} vmax={vmax:.1f} (P98 of in-mask plume)")

    _write_colormap_png(
        enh_c,
        OUT_DIR / "enhancement.png",
        "inferno",
        vmin,
        vmax,
        ramp_alpha=True,
        emphasis=mask_c,
    )
    _write_colormap_png(
        nasa_c,
        OUT_DIR / "nasa.png",
        "inferno",
        vmin,
        vmax,
        ramp_alpha=True,
        emphasis=mask_c,
    )

    diff = enh_c - nasa_c
    dlim = float(np.nanpercentile(np.abs(diff[np.isfinite(diff)]), 98))
    _write_colormap_png(diff, OUT_DIR / "diff.png", "RdBu_r", -dlim, dlim, ramp_alpha=False)

    # Crop affine for vectorizing the cropped mask in lon/lat.
    dx = float(np.mean(np.diff(lon_cc)))
    dy = float(np.mean(np.diff(lat_cc)))
    crop_transform = Affine(dx, 0, bounds["west"], 0, dy, bounds["north"])
    _write_mask_geojson(mask_c, crop_transform, OUT_DIR / "mask.geojson")

    bounds_doc = {
        "event_id": EVENT_ID,
        "crs": "EPSG:4326",
        "bounds": bounds,
        "colormap": {"name": "inferno", "vmin_ppm_m": vmin, "vmax_ppm_m": vmax},
        "diff_colormap": {"name": "RdBu_r", "abs_limit_ppm_m": dlim},
        "rendering": (
            "Cropped to CC-1213 bbox + margin. Alpha ramps with normalized signal; "
            "in-mask (quantified plume) pixels floored to 0.92 opacity, off-mask scaled "
            "to 0.55 as faint context. Real pixels throughout — no thresholding-away."
        ),
        "source": {
            "ours": "stage_a_outputs/.../our_enhancement_ortho.npz (enhancement_ppm_m)",
            "nasa": "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003.tif",
        },
    }
    (OUT_DIR / "bounds.json").write_text(json.dumps(bounds_doc, indent=2))
    print(f"  wrote {(OUT_DIR / 'bounds.json').relative_to(REPO_ROOT)}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
