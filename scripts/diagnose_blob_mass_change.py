"""Compare integrated enhancement over the blob regions before vs after LOOCV.

Reads the saved ortho-grid NPZ from the pre-LOOCV run (preserved in _pre_loocv/)
and the current run, and quantifies the integrated mass over two bounding boxes
covering the two saturated round blobs visible in the upper part of the plume
bbox in the side_by_side.png.

Output: ppm·m·pixel² integrated over each blob region; ratio of after/before
shows whether LOOCV actually removed the bogus mass.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

PRE_PATH = Path(
    "stage_a_outputs/turkmenistan_goturdepe_2022_08_15/_pre_loocv/our_enhancement_ortho.npz"
)
POST_PATH = Path("stage_a_outputs/turkmenistan_goturdepe_2022_08_15/our_enhancement_ortho.npz")

# Two blob regions identified in the side_by_side.png — both visible inside
# the plume bbox in the upper portion (around lat 39.5–39.6 N).
# The bbox bounds are approximate; tight enough to enclose each blob and
# loose enough to not depend on sub-pixel localisation.
BLOB_A_BBOX = {"min_lon": 53.45, "max_lon": 53.58, "min_lat": 39.50, "max_lat": 39.60}
BLOB_B_BBOX = {"min_lon": 53.55, "max_lon": 53.68, "min_lat": 39.42, "max_lat": 39.52}


def integrate_region(arr: np.ndarray, lon_centers: np.ndarray, lat_centers: np.ndarray,
                     bbox: dict) -> tuple[float, float, int]:
    """Return (sum_ppm_m_pixel, sum_abs_ppm_m_pixel, n_pixels) over bbox.

    Each pixel ~60×60 m. Integrated mass (ppm·m·m²) is the sum × pixel area —
    we report the dimensional version (ppm·m × pixel count) for simplicity.
    """
    lon_grid, lat_grid = np.meshgrid(lon_centers, lat_centers)
    in_bbox = (
        (lon_grid >= bbox["min_lon"]) & (lon_grid <= bbox["max_lon"])
        & (lat_grid >= bbox["min_lat"]) & (lat_grid <= bbox["max_lat"])
    )
    values = arr[in_bbox]
    finite = np.isfinite(values)
    vals = values[finite]
    return float(vals.sum()), float(np.abs(vals).sum()), int(vals.size)


def load(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z = np.load(path)
    return z["enhancement_ppm_m"], z["ortho_lon_centers"], z["ortho_lat_centers"]


def main() -> None:
    pre_arr, lon_c, lat_c = load(PRE_PATH)
    post_arr, _, _ = load(POST_PATH)
    assert pre_arr.shape == post_arr.shape, (pre_arr.shape, post_arr.shape)

    print(f"Loaded ortho rasters: shape={pre_arr.shape}")
    print(f"  lon range: {lon_c.min():.4f} to {lon_c.max():.4f}")
    print(f"  lat range: {lat_c.min():.4f} to {lat_c.max():.4f}")

    for name, bbox in [("BLOB A (upper)", BLOB_A_BBOX), ("BLOB B (lower)", BLOB_B_BBOX)]:
        pre_sum, pre_abs, n_pix = integrate_region(pre_arr, lon_c, lat_c, bbox)
        post_sum, post_abs, _ = integrate_region(post_arr, lon_c, lat_c, bbox)
        print(f"\n{name}  bbox={bbox}  n_ortho_pixels={n_pix}")
        print(f"  PRE-LOOCV  signed sum: {pre_sum:+.3e} ppm·m·px  |  |sum|: {pre_abs:.3e}")
        print(f"  POST-LOOCV signed sum: {post_sum:+.3e} ppm·m·px  |  |sum|: {post_abs:.3e}")
        if pre_abs > 0:
            print(f"  reduction in |sum|: {(1 - post_abs / pre_abs) * 100:+.1f}%")

    # Background (bulk-of-scene) check — how did LOOCV affect ordinary pixels?
    print("\n--- Background / bulk comparison ---")
    finite_both = np.isfinite(pre_arr) & np.isfinite(post_arr)
    print(f"  n pixels finite in both: {int(finite_both.sum())}")
    print(f"  PRE  full-scene p1/p50/p99: "
          f"{np.percentile(pre_arr[finite_both], 1):+.1f}  "
          f"{np.percentile(pre_arr[finite_both], 50):+.1f}  "
          f"{np.percentile(pre_arr[finite_both], 99):+.1f}")
    print(f"  POST full-scene p1/p50/p99: "
          f"{np.percentile(post_arr[finite_both], 1):+.1f}  "
          f"{np.percentile(post_arr[finite_both], 50):+.1f}  "
          f"{np.percentile(post_arr[finite_both], 99):+.1f}")


if __name__ == "__main__":
    main()
