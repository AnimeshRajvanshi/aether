"""Unit tests for era5.get_wind_at_point. Network mocked via in-memory xarray."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest
import xarray as xr
from aether_data_spine import era5


def _make_synthetic_era5(
    u_field: float = 3.0,
    v_field: float = 4.0,
    lat_grid=(31.5, 32.0, 32.5, 33.0),
    lon_grid=(-105.0, -104.5, -104.0, -103.5),  # -180..180 convention
) -> xr.Dataset:
    """Build a tiny synthetic ERA5 dataset with constant 10 m winds.

    Times bracket 2022-08-15T04:28:38Z so the interpolation path can land on
    a real value.
    """
    times = np.array(
        ["2022-08-15T04:00:00", "2022-08-15T05:00:00", "2022-08-15T06:00:00"],
        dtype="datetime64[ns]",
    )
    shape = (times.size, len(lat_grid), len(lon_grid))
    u = np.full(shape, u_field, dtype=np.float32)
    v = np.full(shape, v_field, dtype=np.float32)
    ds = xr.Dataset(
        data_vars={
            era5.ARCO_ERA5_VAR_U10: (("time", "latitude", "longitude"), u),
            era5.ARCO_ERA5_VAR_V10: (("time", "latitude", "longitude"), v),
        },
        coords={
            "time": times,
            "latitude": np.array(lat_grid),
            "longitude": np.array(lon_grid),
        },
    )
    return ds


def test_get_wind_at_point_uniform_field_returns_field_value() -> None:
    ds = _make_synthetic_era5(u_field=3.0, v_field=4.0)
    out = era5.get_wind_at_point(
        lat=32.25,
        lon=-104.15,
        utc=datetime(2022, 8, 15, 4, 28, 38),
        dataset=ds,
    )
    # Uniform u=3, v=4 → speed = 5.
    assert out.u_ms == pytest.approx(3.0, abs=1e-6)
    assert out.v_ms == pytest.approx(4.0, abs=1e-6)
    assert out.speed_ms == pytest.approx(5.0, abs=1e-6)
    # The nearest grid cell should be at lat 32.0 or 32.5 — never further than 0.5°.
    assert abs(out.grid_lat - 32.25) <= 0.5
    assert abs(out.grid_lon - (-104.15)) <= 0.5
    # Hour distance reports distance to nearest sampled hour. 04:28 is 28 min
    # from 04:00 and 32 min from 05:00 — nearest is 04:00, distance ~28 min.
    assert 0.4 < out.hour_distance_h < 0.5


def test_get_wind_at_point_linear_in_time() -> None:
    """If u differs between consecutive hourly samples, output linear-interps."""
    ds = _make_synthetic_era5(u_field=0.0, v_field=0.0)
    # Replace u with a linear ramp in time: 0 at t0=04, 6 at t1=05, 12 at t2=06.
    times = ds.time.values
    n_t = times.size
    n_lat = ds.latitude.size
    n_lon = ds.longitude.size
    ramp = np.linspace(0.0, 12.0, n_t).reshape(n_t, 1, 1)
    ramp_full = np.tile(ramp, (1, n_lat, n_lon)).astype(np.float32)
    ds[era5.ARCO_ERA5_VAR_U10].values[:] = ramp_full

    # 04:30 is the midpoint between 04:00 (u=0) and 05:00 (u=6); expect u≈3.
    out = era5.get_wind_at_point(
        lat=32.0, lon=-104.5, utc=datetime(2022, 8, 15, 4, 30, 0), dataset=ds
    )
    assert out.u_ms == pytest.approx(3.0, abs=1e-3)


def test_normalize_longitude_for_0_360_grid() -> None:
    """When the dataset uses 0..360 longitudes, a negative input is translated."""
    ds = _make_synthetic_era5(
        lon_grid=(255.0, 255.5, 256.0, 256.5),  # 0..360 convention
    )
    # -104.5 in 0..360 is 255.5.
    out = era5.get_wind_at_point(
        lat=32.0, lon=-104.5, utc=datetime(2022, 8, 15, 4, 28, 38), dataset=ds
    )
    # We pick the nearest grid cell; for input -104.5 the matching cell is at
    # longitude 255.5, which our WindAtOverpass exposes back as -104.5
    # (we wrap >180 to negative before reporting).
    assert out.grid_lon == pytest.approx(-104.5, abs=0.01)


def _make_synthetic_surface(
    sp_field: float = 90000.0,
    t2m_field: float = 305.0,
    lat_grid=(31.5, 32.0, 32.5, 33.0),
    lon_grid=(-105.0, -104.5, -104.0, -103.5),
) -> xr.Dataset:
    """Tiny synthetic ERA5 dataset with constant surface pressure + 2 m temperature."""
    times = np.array(
        ["2022-08-26T17:00:00", "2022-08-26T18:00:00", "2022-08-26T19:00:00"],
        dtype="datetime64[ns]",
    )
    shape = (times.size, len(lat_grid), len(lon_grid))
    return xr.Dataset(
        data_vars={
            era5.ARCO_ERA5_VAR_SP: (
                ("time", "latitude", "longitude"),
                np.full(shape, sp_field, dtype=np.float32),
            ),
            era5.ARCO_ERA5_VAR_T2M: (
                ("time", "latitude", "longitude"),
                np.full(shape, t2m_field, dtype=np.float32),
            ),
        },
        coords={"time": times, "latitude": np.array(lat_grid), "longitude": np.array(lon_grid)},
    )


def test_get_surface_state_uniform_field_returns_field_value() -> None:
    ds = _make_synthetic_surface(sp_field=89500.0, t2m_field=306.0)
    out = era5.get_surface_state_at_point(
        lat=32.25, lon=-104.15, utc=datetime(2022, 8, 26, 17, 46, 42), dataset=ds
    )
    assert out.surface_pressure_pa == pytest.approx(89500.0, abs=1e-3)
    assert out.temperature_2m_k == pytest.approx(306.0, abs=1e-3)
    assert abs(out.grid_lat - 32.25) <= 0.5
    assert abs(out.grid_lon - (-104.15)) <= 0.5
    # 17:46 is 14 min from 18:00 (nearest) → ~0.23 h.
    assert 0.2 < out.hour_distance_h < 0.3


def test_constants_are_public_arco_uri() -> None:
    """The dataset URI points at the anonymous ARCO-ERA5 GCS bucket."""
    assert era5.ARCO_ERA5_GCS_URI.startswith("gs://gcp-public-data-arco-era5/")
    assert era5.ARCO_ERA5_VAR_U10 == "10m_u_component_of_wind"
    assert era5.ARCO_ERA5_VAR_V10 == "10m_v_component_of_wind"


@pytest.mark.integration
class TestArcoEra5Integration:
    """Real-network tests for ARCO-ERA5. Skipped by default."""

    def test_fetch_real_wind_at_carlsbad_overpass(self) -> None:
        pytest.skip("Manual: hits gs://gcp-public-data-arco-era5 directly")
