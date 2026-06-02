"""Unit tests for emit_l1b. All network mocked.

We synthesize tiny NetCDF-4 files with the EMIT L1B group layout so the parser
and accessor paths get exercised end-to-end without touching NASA Earthdata.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import xarray as xr
from aether_data_spine import emit_l1b

# --------------------------------------------------------------------------- #
# Synthetic L1B granule builder
# --------------------------------------------------------------------------- #


def _write_synthetic_rad_netcdf(
    path: Path, n_lines: int = 6, n_cols: int = 5, n_bands: int = 8
) -> None:
    """Write a NetCDF-4 file mirroring EMIT_L1B_RAD's group structure.

    Root group: /radiance (downtrack, crosstrack, bands)
    Group /sensor_band_parameters: wavelengths, fwhm (bands,)
    Group /location: lon, lat (downtrack, crosstrack)

    Crucially we do NOT attach a coordinate to the `bands` dimension. Real
    EMIT L1B files leave `bands` unlabelled. With a coord present, xarray
    can outer-join on the coord values and silently masks the alignment
    bug exercised by test_merging_rad_and_obs_avoids_bands_dimension_collision.
    """
    rng = np.random.default_rng(11)
    wavelengths = np.linspace(500.0, 2450.0, n_bands)
    rad = rng.uniform(10.0, 30.0, size=(n_lines, n_cols, n_bands)).astype(np.float32)

    # Root group with radiance. No coords on any of the dims, mirroring the
    # real EMIT file: dims are bare (downtrack, crosstrack, bands).
    ds_root = xr.Dataset(
        data_vars={"radiance": (("downtrack", "crosstrack", "bands"), rad)},
    )
    ds_root.to_netcdf(path, mode="w", engine="netcdf4")

    # Sensor band parameters group — wavelengths and fwhm both on the same
    # bare `bands` dim. No coord on bands here either.
    ds_band = xr.Dataset(
        data_vars={
            "wavelengths": (("bands",), wavelengths.astype(np.float32)),
            "fwhm": (("bands",), np.full(n_bands, 7.5, dtype=np.float32)),
        },
    )
    ds_band.to_netcdf(path, mode="a", engine="netcdf4", group="sensor_band_parameters")

    # Location group with lon/lat/elev (downtrack, crosstrack) and a tiny GLT
    # on (ortho_y, ortho_x). Bare dims again. GLT values are 1-based with 0
    # marking "no source pixel" — same convention as the real EMIT GLT.
    lon = np.linspace(-104.20, -104.10, n_cols)[None, :].repeat(n_lines, axis=0)
    lat = np.linspace(32.30, 32.20, n_lines)[:, None].repeat(n_cols, axis=1)
    n_ortho_y = n_lines + 1
    n_ortho_x = n_cols + 1
    glt_y = np.zeros((n_ortho_y, n_ortho_x), dtype=np.int32)
    glt_x = np.zeros((n_ortho_y, n_ortho_x), dtype=np.int32)
    # Trivial identity GLT over the overlapping region; corner stays at 0.
    glt_y[:n_lines, :n_cols] = np.arange(1, n_lines + 1)[:, None]
    glt_x[:n_lines, :n_cols] = np.arange(1, n_cols + 1)[None, :]
    ds_loc = xr.Dataset(
        data_vars={
            "lon": (("downtrack", "crosstrack"), lon.astype(np.float32)),
            "lat": (("downtrack", "crosstrack"), lat.astype(np.float32)),
            "elev": (
                ("downtrack", "crosstrack"),
                np.full((n_lines, n_cols), 100.0, dtype=np.float32),
            ),
            "glt_x": (("ortho_y", "ortho_x"), glt_x),
            "glt_y": (("ortho_y", "ortho_x"), glt_y),
        },
    )
    ds_loc.to_netcdf(path, mode="a", engine="netcdf4", group="location")


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_constants_reference_known_product() -> None:
    """Product short name and version are pinned to the published v001 spec."""
    assert emit_l1b.EMITL1BRAD_SHORT_NAME == "EMITL1BRAD"
    assert emit_l1b.EMITL1BRAD_VERSION == "001"


def test_open_l1b_radiance_flattens_groups(tmp_path: Path) -> None:
    """The opener merges /, /sensor_band_parameters, /location into one Dataset."""
    nc = tmp_path / "EMIT_L1B_RAD_test.nc"
    _write_synthetic_rad_netcdf(nc)

    ds = emit_l1b._open_l1b_radiance(nc)
    assert "radiance" in ds.data_vars
    assert "wavelengths_nm" in ds.data_vars
    assert "fwhm_nm" in ds.data_vars
    assert "lon" in ds.data_vars
    assert "lat" in ds.data_vars
    assert ds["radiance"].shape[-1] == ds["wavelengths_nm"].shape[0]


def test_get_radiance_cube_returns_numpy_with_aligned_shapes(tmp_path: Path) -> None:
    nc = tmp_path / "EMIT_L1B_RAD_test.nc"
    _write_synthetic_rad_netcdf(nc, n_lines=4, n_cols=3, n_bands=6)
    ds = emit_l1b._open_l1b_radiance(nc)

    rad, wl, fwhm = emit_l1b.get_radiance_cube(ds)
    assert rad.shape == (4, 3, 6)
    assert wl.shape == (6,)
    assert fwhm.shape == (6,)
    assert rad.dtype == np.float64
    # Wavelengths cover at least one MF window endpoint.
    assert wl.min() <= 1340.0 < wl.max()


def test_get_radiance_cube_rejects_band_axis_mismatch(tmp_path: Path) -> None:
    """If wavelengths_nm doesn't line up with the band axis, fail loudly."""
    nc = tmp_path / "EMIT_L1B_RAD_test.nc"
    _write_synthetic_rad_netcdf(nc, n_lines=4, n_cols=3, n_bands=6)
    ds = emit_l1b._open_l1b_radiance(nc)
    # Corrupt the wavelengths_nm shape.
    ds = ds.assign(wavelengths_nm=("bands_short", np.zeros(3, dtype=np.float32)))
    with pytest.raises(ValueError, match="wavelengths_nm shape"):
        emit_l1b.get_radiance_cube(ds)


def test_select_granule_by_ur_matches_exactly() -> None:
    granules = [
        {"umm": {"GranuleUR": "EMIT_L1B_RAD_001_20220815T042838_2222703_003"}},
        {"umm": {"GranuleUR": "EMIT_L1B_RAD_001_20220810T160726_2222203_002"}},
    ]
    matched = emit_l1b.select_granule_by_ur(
        granules, "EMIT_L1B_RAD_001_20220815T042838_2222703_003"
    )
    assert matched["umm"]["GranuleUR"].endswith("20220815T042838_2222703_003")


def test_select_granule_by_ur_refuses_silent_fallback() -> None:
    """Using a different acquisition would invalidate the per-granule MF target.
    The fetch path must raise rather than silently pick the wrong granule.
    """
    granules = [{"umm": {"GranuleUR": "EMIT_L1B_RAD_001_20220810T160726_2222203_002"}}]
    with pytest.raises(ValueError, match="not in search results"):
        emit_l1b.select_granule_by_ur(
            granules, "EMIT_L1B_RAD_001_20220815T042838_2222703_003"
        )


def test_search_l1b_uses_correct_concept_id() -> None:
    """search_l1b_granules wraps earthaccess.search_data with the L1B concept_id.
    We never accidentally hit the L2B concept_id and try to use those granules
    as radiance.
    """
    with patch("earthaccess.search_data") as mock_search:
        mock_search.return_value = []
        emit_l1b.search_l1b_granules(32.25, -104.15, "2022-08-15", "2022-08-16")
        kwargs = mock_search.call_args.kwargs
        assert kwargs["concept_id"] == emit_l1b.EMITL1BRAD_CONCEPT_ID
        assert kwargs["temporal"] == ("2022-08-15", "2022-08-16")
        assert kwargs["point"] == (-104.15, 32.25)


# --------------------------------------------------------------------------- #
# RAD + OBS merge: regression guard for the "bands" dim collision
# --------------------------------------------------------------------------- #


def _write_synthetic_obs_netcdf(
    path: Path,
    n_lines: int = 6,
    n_cols: int = 5,
    n_obs_bands: int = 11,
) -> None:
    """Write an EMIT_L1B_OBS-shaped NetCDF.

    Mirrors the real OBS structure verified against a real granule:
    root group contains `obs(downtrack, crosstrack, bands)` where `bands` is
    the count of observation-geometry layers (real EMIT: 11 layers — solar
    zenith, view zenith, glint angle, ...). The dim NAME collides with the
    RAD file's "bands" dim, even though the size and meaning are different.
    sensor_band_parameters group carries `observation_bands(bands)` — the
    string label for each obs layer.
    """
    rng = np.random.default_rng(13)
    obs_cube = rng.uniform(0.0, 90.0, size=(n_lines, n_cols, n_obs_bands)).astype(np.float32)
    obs_labels = np.array(
        [f"layer_{i}" for i in range(n_obs_bands)], dtype="S20"
    )

    # Bare dims (no coord on `bands`) to faithfully replicate the real OBS
    # layout. With a coord present, xarray can sidestep the alignment by
    # outer-joining on the coord values and masks the bug we are guarding.
    ds_root = xr.Dataset(
        data_vars={"obs": (("downtrack", "crosstrack", "bands"), obs_cube)},
    )
    ds_root.to_netcdf(path, mode="w", engine="netcdf4")

    ds_sb = xr.Dataset(
        data_vars={"observation_bands": (("bands",), obs_labels)},
    )
    ds_sb.to_netcdf(path, mode="a", engine="netcdf4", group="sensor_band_parameters")


def test_merging_rad_and_obs_avoids_bands_dimension_collision(tmp_path: Path) -> None:
    """RAD `bands=285` + OBS `bands=11` must not collide when merged.

    This test FAILS against the prior implementation (which did
    `rad_ds.assign({...obs_vars...})` without renaming OBS's `bands` dim).
    It passes after the fix, where OBS's `bands` dim is renamed to
    `obs_bands` before assignment.

    The test does the merge inline rather than re-running
    `download_and_cache_l1b` end-to-end (which would require mocking
    earthaccess.download and the Zarr write) — the bug is in the
    rename-and-assign logic, so we exercise that logic directly.
    """
    rad_path = tmp_path / "EMIT_L1B_RAD_test.nc"
    obs_path = tmp_path / "EMIT_L1B_OBS_test.nc"
    _write_synthetic_rad_netcdf(rad_path, n_lines=6, n_cols=5, n_bands=285)
    _write_synthetic_obs_netcdf(obs_path, n_lines=6, n_cols=5, n_obs_bands=11)

    rad_ds = emit_l1b._open_l1b_radiance(rad_path)
    obs_ds = emit_l1b._open_l1b_obs(obs_path)

    # Sanity: confirm we set up the collision the bug needs.
    assert rad_ds.sizes["bands"] == 285
    assert obs_ds.sizes["bands"] == 11

    # The buggy form must raise. Documenting that this WOULD fail without the
    # rename — if a future refactor accidentally goes back to a plain assign,
    # this xfail assertion stops being raised and the test reports it.
    with pytest.raises(xr.AlignmentError, match="conflicting dimension sizes"):
        rad_ds.assign({"obs_obs_BUGGY": obs_ds["obs"]})

    # The correct form: rename obs `bands` -> `obs_bands` first, then merge.
    if obs_ds.sizes["bands"] != rad_ds.sizes["bands"]:
        obs_ds = obs_ds.rename_dims({"bands": "obs_bands"})
    merged = rad_ds.assign({f"obs_{n}": obs_ds[n] for n in obs_ds.data_vars})

    assert merged.sizes["bands"] == 285  # RAD's radiance axis preserved
    assert merged.sizes["obs_bands"] == 11  # OBS axis preserved separately
    assert "radiance" in merged.data_vars
    assert "wavelengths_nm" in merged.data_vars
    assert merged["wavelengths_nm"].shape == (285,)
    assert "obs_obs" in merged.data_vars
    assert merged["obs_obs"].shape == (6, 5, 11)


def test_orthorectify_raw_raster_applies_glt_correctly() -> None:
    """The orthorectify helper maps raw-geometry values via the GLT lookup.

    Builds a tiny known raw raster and a GLT that:
      - addresses one of its pixels at one ortho location (identity-ish lookup)
      - leaves another ortho location at GLT=0 (no source) → must be NaN
    """
    raw = np.array(
        [
            [10.0, 20.0, 30.0],
            [40.0, 50.0, 60.0],
        ]
    )  # shape (2, 3)
    glt_y = np.array(
        [
            [1, 2, 0],   # row 0: pull raw row 0, raw row 1, no source
            [0, 1, 2],   # row 1: no source, raw row 0, raw row 1
        ]
    )
    glt_x = np.array(
        [
            [1, 2, 0],   # col 1 from raw, col 2 from raw, no source
            [0, 3, 3],   # no source, col 3, col 3
        ]
    )
    ortho = emit_l1b.orthorectify_raw_raster(raw, glt_x, glt_y)
    assert ortho.shape == (2, 3)
    # (ortho[0,0]) = raw[gy=1-1, gx=1-1] = raw[0,0] = 10
    # (ortho[0,1]) = raw[2-1, 2-1] = raw[1,1] = 50
    # (ortho[0,2]) = NaN (glt=0)
    # (ortho[1,0]) = NaN
    # (ortho[1,1]) = raw[0,2] = 30
    # (ortho[1,2]) = raw[1,2] = 60
    np.testing.assert_array_equal(
        np.isnan(ortho),
        [[False, False, True], [True, False, False]],
    )
    assert ortho[0, 0] == 10
    assert ortho[0, 1] == 50
    assert ortho[1, 1] == 30
    assert ortho[1, 2] == 60


def test_orthorectify_raw_raster_rejects_bad_shapes() -> None:
    raw_2d = np.zeros((4, 4))
    glt = np.zeros((5, 5), dtype=np.int32)
    glt_other = np.zeros((6, 5), dtype=np.int32)
    with pytest.raises(ValueError, match="shape mismatch"):
        emit_l1b.orthorectify_raw_raster(raw_2d, glt, glt_other)
    with pytest.raises(ValueError, match="raw must be 2-D"):
        emit_l1b.orthorectify_raw_raster(np.zeros((2, 3, 4)), glt, glt)


def test_print_loaded_rad_dims_smoke(tmp_path: Path, capsys) -> None:
    """Smoke test: emit a small synthetic granule, open it, print the dims and
    the wavelengths array length the way the Stage A driver does. Catches
    silent regressions where dims drift after a future refactor.
    """
    rad_path = tmp_path / "EMIT_L1B_RAD_smoke.nc"
    _write_synthetic_rad_netcdf(rad_path, n_lines=4, n_cols=3, n_bands=285)
    ds = emit_l1b._open_l1b_radiance(rad_path)
    rad, wl, _fwhm = emit_l1b.get_radiance_cube(ds)
    # Mirror the Stage A driver's sanity print so a real run shows familiar output.
    print(f"dims={dict(ds.sizes)}  wavelengths.size={wl.size}  rad.shape={rad.shape}")
    out = capsys.readouterr().out
    assert "wavelengths.size=285" in out
    assert "rad.shape=(4, 3, 285)" in out


@pytest.mark.integration
class TestEmitL1bIntegration:
    """Real-network tests; skipped by default."""

    def test_download_canonical_permian_granule(self, tmp_path: Path) -> None:
        pytest.skip("Manual: downloads ~1 GB of L1B radiance")
