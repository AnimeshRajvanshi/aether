"""Tests for the Varon 2018 plume segmentation.

The headline test reproduces the structural property the user is relying on
for Stage B: spatially disjoint enhancement features end up in *distinct*
connected components.
"""

from __future__ import annotations

import numpy as np
import pytest
from aether_detection.plume_segmentation import (
    SEGMENTATION_CONNECTIVITY_STRUCTURE,
    component_label_at_point,
    largest_component_in_region,
    segment_plume_varon,
)


def _synthetic_scene_with_plume_and_disjoint_blobs(
    seed: int = 11,
    n_rows: int = 200,
    n_cols: int = 300,
    bg_std: float = 50.0,
    plume_value: float = 800.0,
    blob_value: float = 1500.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(enhancement, lat_centers, lon_centers)`` for a contrived scene.

    The scene has:
      - Gaussian background noise with σ = ``bg_std`` ppm·m.
      - One elongated plume in the lower-left quadrant (rows 130-180,
        cols 50-100) with a Gaussian falloff from its peak — the "real plume".
      - Two compact disjoint disk-shaped blobs in the upper portion:
        BLOB_A near (row=40, col=170) and BLOB_B near (row=60, col=210),
        separated by far more than the Gaussian smoothing scale so they
        do not accidentally merge into one component.

    The background's own statistics dominate everywhere except in the plume
    and blob footprints, so the t-test should pick up exactly those features.
    """
    rng = np.random.default_rng(seed)
    enh = bg_std * rng.standard_normal((n_rows, n_cols))

    rr, cc = np.indices(enh.shape)
    # Elongated plume
    plume = plume_value * np.exp(
        -((rr - 155) ** 2 / (2 * 12 ** 2) + (cc - 75) ** 2 / (2 * 18 ** 2))
    )
    enh += plume
    # Two disjoint blob disks
    blob_a = blob_value * np.exp(
        -((rr - 40) ** 2 / (2 * 6 ** 2) + (cc - 170) ** 2 / (2 * 6 ** 2))
    )
    blob_b = blob_value * np.exp(
        -((rr - 60) ** 2 / (2 * 5 ** 2) + (cc - 210) ** 2 / (2 * 5 ** 2))
    )
    enh += blob_a + blob_b

    lat_centers = np.linspace(40.0, 39.0, n_rows)
    lon_centers = np.linspace(53.0, 54.0, n_cols)
    return enh, lat_centers, lon_centers


def test_disjoint_features_separate_into_distinct_components() -> None:
    """The plume and the two blobs become THREE distinct connected components.

    This is the core property the Stage B IME proposal relies on: if the
    segmentation correctly labels each visually-separate enhancement region
    as its own connected component, an IME computed over the source-anchored
    plume component will not pick up the unrelated blob mass.
    """
    enh, _lat, _lon = _synthetic_scene_with_plume_and_disjoint_blobs()
    # Build a background mask: rows 0-30 and cols 250-299 (corners far from
    # any injected feature). Plenty of pixels for a stable t-test reference.
    bg_mask = np.zeros_like(enh, dtype=bool)
    bg_mask[0:25, :] = True
    bg_mask[:, 250:] = True

    result = segment_plume_varon(enh, bg_mask)

    # We expect at least three plume connected components: plume + blob A +
    # blob B. (Smoothing may also pick up small noise speckles; we just
    # require ≥ 3 components, not exactly 3.)
    assert result.n_components >= 3, (
        f"Expected ≥ 3 connected components after segmentation; "
        f"got {result.n_components}"
    )

    # Pick representative interior pixels of the three injected features.
    # Confirm they sit in three DIFFERENT non-zero labels.
    plume_label = result.labels[155, 75]
    blob_a_label = result.labels[40, 170]
    blob_b_label = result.labels[60, 210]
    assert plume_label > 0, "Plume interior pixel must be in a labelled CC"
    assert blob_a_label > 0, "Blob A interior pixel must be in a labelled CC"
    assert blob_b_label > 0, "Blob B interior pixel must be in a labelled CC"
    assert plume_label != blob_a_label, (
        "Plume and Blob A must be in DIFFERENT connected components"
    )
    assert plume_label != blob_b_label, (
        "Plume and Blob B must be in DIFFERENT connected components"
    )
    assert blob_a_label != blob_b_label, (
        "The two blobs are spatially disjoint and must NOT share a CC"
    )


def test_component_label_at_point() -> None:
    """`component_label_at_point` resolves (lon, lat) to its CC label."""
    enh, lat_centers, lon_centers = _synthetic_scene_with_plume_and_disjoint_blobs()
    bg_mask = np.zeros_like(enh, dtype=bool)
    bg_mask[0:25, :] = True
    bg_mask[:, 250:] = True
    result = segment_plume_varon(enh, bg_mask)

    plume_lat = float(lat_centers[155])
    plume_lon = float(lon_centers[75])
    plume_label = component_label_at_point(
        result.labels, lon_centers, lat_centers, plume_lon, plume_lat
    )
    # Same point looked up directly in the labels array.
    assert plume_label == int(result.labels[155, 75])
    assert plume_label > 0


def test_largest_component_in_region() -> None:
    """`largest_component_in_region` returns the dominant plume CC in a bbox."""
    enh, lat_centers, lon_centers = _synthetic_scene_with_plume_and_disjoint_blobs()
    bg_mask = np.zeros_like(enh, dtype=bool)
    bg_mask[0:25, :] = True
    bg_mask[:, 250:] = True
    result = segment_plume_varon(enh, bg_mask)

    # The plume bbox encloses rows 130-180, cols 50-100, which maps to
    # latitudes around 39.0-39.35 and longitudes around 53.17-53.33.
    plume_min_lat = float(lat_centers[180])
    plume_max_lat = float(lat_centers[130])
    plume_min_lon = float(lon_centers[50])
    plume_max_lon = float(lon_centers[100])
    largest = largest_component_in_region(
        result.labels, lon_centers, lat_centers,
        plume_min_lon, plume_max_lon, plume_min_lat, plume_max_lat,
    )
    assert largest == int(result.labels[155, 75])


def test_rejects_bad_shapes() -> None:
    """Mismatched shapes and non-2-D inputs are rejected."""
    with pytest.raises(ValueError, match="enhancement must be 2-D"):
        segment_plume_varon(np.zeros((4, 5, 6)), np.zeros((4, 5), dtype=bool))
    with pytest.raises(ValueError, match="background_mask shape"):
        segment_plume_varon(np.zeros((10, 20)), np.zeros((10, 21), dtype=bool))
    with pytest.raises(ValueError, match="neighborhood_size must be odd"):
        segment_plume_varon(
            np.zeros((100, 100)), np.ones((100, 100), dtype=bool),
            neighborhood_size=4,
        )


def test_background_too_small_raises() -> None:
    """Refuse to run with fewer background samples than the kernel size requires."""
    enh = np.zeros((100, 100))
    bg = np.zeros_like(enh, dtype=bool)
    bg[0, 0:10] = True  # only 10 pixels, < 25 needed for 5×5
    with pytest.raises(ValueError, match="Background sample too small"):
        segment_plume_varon(enh, bg)


def test_connectivity_structure_is_eight() -> None:
    """The exported connectivity matrix is 3×3 ones (8-connectivity)."""
    np.testing.assert_array_equal(
        SEGMENTATION_CONNECTIVITY_STRUCTURE,
        np.ones((3, 3), dtype=np.intp),
    )
