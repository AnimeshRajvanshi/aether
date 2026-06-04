"""Tests for the back-projection wedge geometry (Stage A)."""

from __future__ import annotations

import math

import pytest
from aether_causal.geometry import build_wedge

# Synthetic inputs: wind blowing due WEST (u=-10, v=0) => source is due EAST.
_Q = {
    "era5_u_ms": -10.0,
    "era5_v_ms": 0.0,
    "era5_u10_speed_ms": 10.0,
    "u10_sigma_ms": 1.0,
    "u_eff_ms": 2.0,
    "plume_length_m": 8000.0,
}
_WIND = {"source_lat": 39.0, "source_lon": 54.0}


def test_azimuths_due_west_wind() -> None:
    w = build_wedge(_Q, _WIND)
    assert w.downwind_azimuth_deg == pytest.approx(270.0)  # blows toward west
    assert w.upwind_azimuth_deg == pytest.approx(90.0)  # source toward east


def test_half_angle_from_sigma() -> None:
    w = build_wedge(_Q, _WIND)
    assert w.half_angle_1sigma_deg == pytest.approx(math.degrees(math.atan2(1.0, 10.0)))
    assert w.half_angle_2sigma_deg == pytest.approx(math.degrees(math.atan2(2.0, 10.0)))
    assert w.half_angle_2sigma_deg > w.half_angle_1sigma_deg


def test_transit_time() -> None:
    w = build_wedge(_Q, _WIND)
    assert w.transit_time_s == pytest.approx(8000.0 / 2.0)


def test_relate_upwind_point_in_wedge_downwind_out() -> None:
    w = build_wedge(_Q, _WIND)
    # a point ~5 km due EAST of the apex is upwind -> inside the wedge
    east = w.relate(39.0, 54.0 + 0.05)
    assert east.angular_dev_from_upwind_deg < 1.0
    assert east.within_wedge_2sigma and east.within_radius
    # a point due WEST (downwind) is opposite the source -> excluded
    west = w.relate(39.0, 54.0 - 0.05)
    assert west.angular_dev_from_upwind_deg == pytest.approx(180.0, abs=1.0)
    assert not west.within_wedge_2sigma


def test_relate_radius_excludes_far_points() -> None:
    w = build_wedge(_Q, _WIND, search_radius_km=25.0)
    far = w.relate(39.0, 54.0 + 1.0)  # ~86 km east
    assert far.distance_km > 25.0
    assert not far.within_radius
    assert not far.within_wedge_1sigma  # radius gate also fails the wedge test
