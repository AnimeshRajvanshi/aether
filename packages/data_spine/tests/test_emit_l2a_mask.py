"""Unit tests for emit_l2a_mask. Network mocked."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest
import xarray as xr
from aether_data_spine import emit_l2a_mask


def _make_synthetic_mask_ds(n_lines: int = 4, n_cols: int = 5, n_bands: int = 7) -> xr.Dataset:
    """Mock an L2A mask dataset. Fill the aggregate band (idx 4) with a known pattern."""
    cube = np.zeros((n_lines, n_cols, n_bands), dtype=np.float32)
    # Mark some pixels bad on the cloud band (0) and water band (2).
    cube[0, 0, emit_l2a_mask.MASK_BAND_CLOUD] = 1.0
    cube[2, 3, emit_l2a_mask.MASK_BAND_WATER] = 1.0
    cube[3, 4, emit_l2a_mask.MASK_BAND_SPACECRAFT] = 1.0
    # Aggregate band reflects an OR over the individual flags.
    cube[..., emit_l2a_mask.MASK_BAND_AGGREGATE] = (
        cube[..., emit_l2a_mask.MASK_BAND_CLOUD]
        + cube[..., emit_l2a_mask.MASK_BAND_CIRRUS]
        + cube[..., emit_l2a_mask.MASK_BAND_WATER]
        + cube[..., emit_l2a_mask.MASK_BAND_SPACECRAFT]
    )
    return xr.Dataset(
        data_vars={"mask": (("downtrack", "crosstrack", "mask_band"), cube)},
    )


def test_build_bad_pixel_mask_uses_aggregate() -> None:
    ds = _make_synthetic_mask_ds()
    bad = emit_l2a_mask.build_bad_pixel_mask(ds, use_aggregate=True)
    assert bad.shape == (4, 5)
    assert bad[0, 0]  # cloud → bad
    assert bad[2, 3]  # water → bad
    assert bad[3, 4]  # spacecraft → bad
    assert not bad[1, 2]  # untouched pixel


def test_build_bad_pixel_mask_or_combines_when_aggregate_false() -> None:
    ds = _make_synthetic_mask_ds()
    # Zero out the aggregate band; the OR-combined mask should still flag the
    # same pixels via the individual flag bands.
    ds["mask"][..., emit_l2a_mask.MASK_BAND_AGGREGATE] = 0.0
    bad = emit_l2a_mask.build_bad_pixel_mask(ds, use_aggregate=False)
    assert bad[0, 0]
    assert bad[2, 3]
    assert bad[3, 4]


def test_build_bad_pixel_mask_rejects_2d_input() -> None:
    """A 2-D 'mask' variable is not the expected per-band cube."""
    ds = xr.Dataset(data_vars={"mask": (("y", "x"), np.zeros((3, 3)))})
    with pytest.raises(ValueError, match="3-D mask cube"):
        emit_l2a_mask.build_bad_pixel_mask(ds)


def test_search_uses_correct_concept_id() -> None:
    with patch("earthaccess.search_data") as mock_search:
        mock_search.return_value = []
        emit_l2a_mask.search_l2a_mask_granules(32.25, -104.15, "2022-08-15", "2022-08-16")
        kwargs = mock_search.call_args.kwargs
        assert kwargs["concept_id"] == emit_l2a_mask.EMITL2AMASK_CONCEPT_ID
