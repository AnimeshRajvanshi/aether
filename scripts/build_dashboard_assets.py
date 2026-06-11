"""Derive the committable dashboard rasters from Stage A/B outputs.

Sprint 3 serves the methane plume as a georeferenced image overlay on the
Cesium globe. The orthorectified enhancement lives in a gitignored ``.npz``
(large, regenerable) and NASA's L2B reference lives in the gitignored
``.aether_cache`` GeoTIFF. This script renders small, *committable* artefacts
from them so ``apps/api`` can serve real pixels from version control:

  enhancement.png  — our orthorectified MF retrieval, inferno colormap
  nasa.png         — NASA L2B CH4ENH on the SAME ortho grid (already aligned)
  diff.png         — (ours - nasa), diverging colormap, for the Δ toggle
  bounds.json      — EPSG:4326 [west, south, east, north] of the crop
  mask.geojson     — outline of the quantified plume in lon/lat (cyan in the UI)

Event-parameterized (Sprint 7 generality):

    uv run python scripts/build_dashboard_assets.py [<event_id>]

defaulting to Goturdepe. Two plume-mask strategies, selected by the event's
quantification method (NOT a fork):
  * ``self_seg``       — Goturdepe: reconstruct the Varon CC exactly as Stage B
    did and assert label + pixel-count == q_estimate.json.
  * ``nasa_footprint`` — Permian (CROSS-CHECKED): the mask is NASA's published
    plume footprint (L2B > threshold inside the complex bbox); assert pixel-count
    == q_estimate.json. (Permian's self-segmentation could not isolate the weak
    plume — see Stage C; the served overlay uses the same footprint the flux was
    integrated over.)

Nothing here invents data. Goturdepe's committed assets are produced by the
``self_seg`` path and are left byte-identical (this script is re-run only for the
new event).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
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

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("~/.aether_cache").expanduser()
CENTRAL_P_VALUE = 0.05


@dataclass(frozen=True)
class AssetEvent:
    """Per-event config for the dashboard-asset build."""

    event_id: str
    l2b_tif: Path
    plume_bbox: dict[str, float]
    mask_strategy: str  # "self_seg" | "nasa_footprint"
    nasa_footprint_threshold: float  # used only for nasa_footprint
    rendering_note: str


EVENTS: dict[str, AssetEvent] = {
    "turkmenistan_goturdepe_2022_08_15": AssetEvent(
        event_id="turkmenistan_goturdepe_2022_08_15",
        l2b_tif=CACHE / "emit_l2b_ch4"
        / "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003"
        / "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003.tif",
        plume_bbox={"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7},
        mask_strategy="self_seg",
        nasa_footprint_threshold=0.0,
        rendering_note=(
            "Cropped to the quantified CC bbox + margin. Alpha ramps with normalized signal; "
            "in-mask (quantified plume) pixels floored to 0.92 opacity, off-mask scaled to 0.55 "
            "as faint context. Real pixels throughout — no thresholding-away."
        ),
    ),
    "permian_basin_2022": AssetEvent(
        event_id="permian_basin_2022",
        l2b_tif=CACHE / "emit_l2b_ch4"
        / "EMIT_L2B_CH4ENH_002_20220826T174642_2223812_024"
        / "EMIT_L2B_CH4ENH_002_20220826T174642_2223812_024.tif",
        plume_bbox={"min_lon": -104.104, "min_lat": 32.346, "max_lon": -104.070, "max_lat": 32.396},
        mask_strategy="nasa_footprint",
        nasa_footprint_threshold=200.0,
        rendering_note=(
            "Mask = NASA's published plume footprint (L2B > 200 ppm·m inside complex 000524's "
            "bbox), the same footprint the flux was integrated over (CROSS-CHECKED; our own "
            "self-segmentation could not isolate this weak plume — see Stage C). In-mask pixels "
            "floored to 0.92 opacity, off-mask scaled to 0.55. Real pixels throughout."
        ),
    ),
}


def _load_ortho(stage_a_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, Affine]:
    npz = np.load(stage_a_dir / "our_enhancement_ortho.npz")
    return (
        npz["enhancement_ppm_m"],
        npz["ortho_lon_centers"],
        npz["ortho_lat_centers"],
        Affine(*npz["l2b_transform"]),
    )


def _sample_l2b_on_grid(l2b_tif: Path, lon_c: np.ndarray, lat_c: np.ndarray) -> np.ndarray:
    l2b = rioxarray.open_rasterio(l2b_tif, masked=True).squeeze("band", drop=True)
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


def _l2b_direct(l2b_tif: Path, shape: tuple[int, int]) -> np.ndarray:
    """The L2B array on its native ortho grid — which IS the ortho npz grid (the
    enhancement was orthorectified onto the L2B grid in the runner). Used for the
    nasa_footprint mask so it reproduces the runner's exact nasa array (resampling
    would shift edge pixels and the mask count would not match q_estimate.json)."""
    arr = np.asarray(
        rioxarray.open_rasterio(l2b_tif, masked=True).squeeze("band", drop=True).values,
        dtype=np.float64,
    )
    if arr.shape != shape:
        raise SystemExit(f"L2B shape {arr.shape} != ortho grid {shape}; grids must match")
    return arr


def _in_bbox(lon_c: np.ndarray, lat_c: np.ndarray, b: dict[str, float]) -> np.ndarray:
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    return (
        (lon_grid >= b["min_lon"]) & (lon_grid <= b["max_lon"])
        & (lat_grid >= b["min_lat"]) & (lat_grid <= b["max_lat"])
    )


def _reconstruct_mask(
    ev: AssetEvent, enh: np.ndarray, nasa: np.ndarray, lon_c: np.ndarray, lat_c: np.ndarray, q: dict
) -> np.ndarray:
    """Rebuild the quantified plume mask and verify it against q_estimate.json."""
    in_bbox = _in_bbox(lon_c, lat_c, ev.plume_bbox)
    if ev.mask_strategy == "self_seg":
        bg_mask = np.isfinite(enh) & (~in_bbox)
        seg = segment_plume_varon(enh, bg_mask, p_value=CENTRAL_P_VALUE)
        label = largest_component_in_region(
            seg.labels, lon_c, lat_c,
            ev.plume_bbox["min_lon"], ev.plume_bbox["max_lon"],
            ev.plume_bbox["min_lat"], ev.plume_bbox["max_lat"],
        )
        mask = seg.labels == label
        assert label == q["plume_cc_label"], f"label {label} != committed {q['plume_cc_label']}"
    else:  # nasa_footprint
        mask = in_bbox & np.isfinite(nasa) & np.isfinite(enh) & (nasa > ev.nasa_footprint_threshold)
    assert int(mask.sum()) == q["plume_cc_pixel_count"], (
        f"mask px {int(mask.sum())} != committed {q['plume_cc_pixel_count']}"
    )
    print(f"  plume mask verified: {int(mask.sum())} px (matches q_estimate.json; {ev.mask_strategy})")  # noqa: E501
    return mask


def _crop_to_mask(
    mask: np.ndarray, *arrays: np.ndarray, lon_c: np.ndarray, lat_c: np.ndarray, margin: float = 0.6
) -> tuple[list[np.ndarray], np.ndarray, np.ndarray]:
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
    dx = float(np.abs(np.mean(np.diff(lon_c))))
    dy = float(np.abs(np.mean(np.diff(lat_c))))
    return {
        "west": float(lon_c.min() - dx / 2),
        "east": float(lon_c.max() + dx / 2),
        "south": float(lat_c.min() - dy / 2),
        "north": float(lat_c.max() + dy / 2),
    }


def _write_colormap_png(
    arr: np.ndarray, path: Path, cmap: str, vmin: float, vmax: float, *,
    ramp_alpha: bool, emphasis: np.ndarray | None = None,
) -> None:
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


def _write_mask_geojson(
    mask: np.ndarray, transform: Affine, path: Path, cc_label: int, src: str
) -> None:
    shapes = [
        geom
        for geom, val in rasterio.features.shapes(mask.astype(np.uint8), transform=transform)
        if val == 1
    ]
    shapes.sort(key=lambda g: -len(g["coordinates"][0]))
    fc: dict[str, Any] = {
        "type": "FeatureCollection",
        "properties": {"cc_label": cc_label, "source": src},
        "features": [
            {"type": "Feature", "properties": {"rank": i}, "geometry": g}
            for i, g in enumerate(shapes)
        ],
    }
    path.write_text(json.dumps(fc))
    print(f"  wrote {path.relative_to(REPO_ROOT)}  ({len(shapes)} polygon(s))")


def main() -> int:
    event_id = sys.argv[1] if len(sys.argv) > 1 else "turkmenistan_goturdepe_2022_08_15"
    if event_id not in EVENTS:
        raise SystemExit(f"unknown event_id {event_id!r}; known: {sorted(EVENTS)}")
    ev = EVENTS[event_id]
    stage_a_dir = REPO_ROOT / "stage_a_outputs" / event_id
    stage_b_dir = REPO_ROOT / "stage_b_outputs" / event_id
    out_dir = REPO_ROOT / "apps" / "api" / "aether_api" / "assets" / event_id
    out_dir.mkdir(parents=True, exist_ok=True)
    q = json.loads((stage_b_dir / "q_estimate.json").read_text())
    print(f"Building dashboard assets for {event_id} -> {out_dir.relative_to(REPO_ROOT)}")

    enh, lon_c, lat_c, _transform = _load_ortho(stage_a_dir)
    print(f"  ortho grid: {enh.shape}")
    # nasa_footprint events define the mask from NASA's L2B, so read it DIRECTLY on
    # the shared ortho grid (matches the runner exactly); self_seg events only use
    # nasa for the diff layer, so the resampled read is fine (and preserves the
    # original Goturdepe behavior byte-for-byte).
    nasa = (
        _l2b_direct(ev.l2b_tif, enh.shape) if ev.mask_strategy == "nasa_footprint"
        else _sample_l2b_on_grid(ev.l2b_tif, lon_c, lat_c)
    )
    mask_full = _reconstruct_mask(ev, enh, nasa, lon_c, lat_c, q)

    (enh_c, nasa_c, mask_c), lon_cc, lat_cc = _crop_to_mask(
        mask_full, enh, nasa, mask_full, lon_c=lon_c, lat_c=lat_c
    )
    bounds = _bounds_from_centers(lon_cc, lat_cc)

    plume_vals = enh_c[mask_c & np.isfinite(enh_c)]
    vmin = 0.0
    vmax = float(np.percentile(plume_vals, 98))
    print(f"  colormap window (ppm·m): vmin={vmin:.1f} vmax={vmax:.1f} (P98 of in-mask plume)")

    _write_colormap_png(enh_c, out_dir / "enhancement.png", "inferno", vmin, vmax,
                        ramp_alpha=True, emphasis=mask_c)
    _write_colormap_png(nasa_c, out_dir / "nasa.png", "inferno", vmin, vmax,
                        ramp_alpha=True, emphasis=mask_c)
    diff = enh_c - nasa_c
    dlim = float(np.nanpercentile(np.abs(diff[np.isfinite(diff)]), 98))
    _write_colormap_png(diff, out_dir / "diff.png", "RdBu_r", -dlim, dlim, ramp_alpha=False)

    dx = float(np.mean(np.diff(lon_cc)))
    dy = float(np.mean(np.diff(lat_cc)))
    crop_transform = Affine(dx, 0, bounds["west"], 0, dy, bounds["north"])
    mask_src = (
        f"stage_b segment_plume_varon p<{CENTRAL_P_VALUE}" if ev.mask_strategy == "self_seg"
        else f"NASA L2B footprint > {ev.nasa_footprint_threshold:.0f} ppm·m (complex bbox)"
    )
    _write_mask_geojson(mask_c, crop_transform, out_dir / "mask.geojson",
                        int(q["plume_cc_label"]), mask_src)

    bounds_doc = {
        "event_id": event_id,
        "crs": "EPSG:4326",
        "bounds": bounds,
        "colormap": {"name": "inferno", "vmin_ppm_m": vmin, "vmax_ppm_m": vmax},
        "diff_colormap": {"name": "RdBu_r", "abs_limit_ppm_m": dlim},
        "rendering": ev.rendering_note,
        "source": {
            "ours": f"stage_a_outputs/{event_id}/our_enhancement_ortho.npz (enhancement_ppm_m)",
            "nasa": ev.l2b_tif.name,
        },
    }
    (out_dir / "bounds.json").write_text(json.dumps(bounds_doc, indent=2))
    print(f"  wrote {(out_dir / 'bounds.json').relative_to(REPO_ROOT)}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
