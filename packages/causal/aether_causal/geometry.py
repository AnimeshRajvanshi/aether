"""Back-projection search-wedge geometry for source attribution (Stage A).

Given a quantified plume, the emission source lies UPWIND. We reuse the Sprint 2
ERA5 wind and the data-driven upwind source point (`wind_location_check.json`,
the centroid of the top-5%-upwind CC-1213 pixels) and project upwind along the
ERA5 wind direction, opening an angular uncertainty wedge whose half-angle comes
from the committed ERA5 wind-vector uncertainty over the plume's transit time.

This module computes geometry only — no scoring, no OGIM. All inputs are read
from committed Stage A/B outputs; nothing here is fabricated. Geodesic math uses
pyproj's WGS84 ellipsoid (Geod.inv) so distances/bearings are accurate at 39 N.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from pyproj import Geod

_GEOD = Geod(ellps="WGS84")


def _norm360(deg: float) -> float:
    return deg % 360.0


def _angular_diff(a: float, b: float) -> float:
    """Smallest absolute angle between two bearings, in [0, 180]."""
    d = abs(_norm360(a) - _norm360(b)) % 360.0
    return min(d, 360.0 - d)


@dataclass(frozen=True)
class FeatureRelation:
    """Where a point sits relative to the wedge apex (the upwind source point)."""

    distance_km: float
    bearing_from_apex_deg: float  # geodesic forward azimuth apex -> feature
    angular_dev_from_upwind_deg: float
    within_radius: bool
    within_wedge_1sigma: bool
    within_wedge_2sigma: bool


@dataclass(frozen=True)
class BackProjectionWedge:
    """The Stage A search region: apex at the upwind source, opening upwind."""

    apex_lat: float
    apex_lon: float
    downwind_azimuth_deg: float  # direction the wind blows toward
    upwind_azimuth_deg: float  # wedge centerline (toward the source)
    half_angle_1sigma_deg: float
    half_angle_2sigma_deg: float
    search_radius_km: float
    # provenance / assumptions inputs (all from committed files)
    wind_u_ms: float
    wind_v_ms: float
    wind_speed_ms: float
    u10_sigma_ms: float
    u_eff_ms: float
    plume_length_m: float
    transit_time_s: float

    def relate(self, lat: float, lon: float) -> FeatureRelation:
        """Geometric relationship of a feature point to this wedge."""
        fwd_az, _back_az, dist_m = _GEOD.inv(self.apex_lon, self.apex_lat, lon, lat)
        dist_km = dist_m / 1000.0
        bearing = _norm360(fwd_az)
        dev = _angular_diff(bearing, self.upwind_azimuth_deg)
        return FeatureRelation(
            distance_km=dist_km,
            bearing_from_apex_deg=bearing,
            angular_dev_from_upwind_deg=dev,
            within_radius=dist_km <= self.search_radius_km,
            within_wedge_1sigma=dist_km <= self.search_radius_km
            and dev <= self.half_angle_1sigma_deg,
            within_wedge_2sigma=dist_km <= self.search_radius_km
            and dev <= self.half_angle_2sigma_deg,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_wedge(
    q_estimate: dict[str, Any],
    wind_check: dict[str, Any],
    *,
    search_radius_km: float = 25.0,
) -> BackProjectionWedge:
    """Construct the back-projection wedge from committed Stage A/B outputs.

    Args:
        q_estimate: parsed stage_b_outputs/.../q_estimate.json
        wind_check: parsed stage_b_outputs/.../wind_location_check.json
        search_radius_km: documented radial extent around the source point.

    Geometry:
      - apex = the Sprint 2 upwind source point (top-5%-upwind CC-1213 centroid).
      - centerline = upwind azimuth = (downwind + 180) mod 360, where the
        downwind azimuth is the bearing of the ERA5 wind vector (u east, v north).
      - half-angle = atan(k * sigma_U10 / |U10|), the direction spread induced by
        treating the committed ERA5 wind-speed 1-sigma as an isotropic wind-vector
        uncertainty (k = 1 and 2). This is a documented heuristic uncertainty
        model, NOT a measured directional variance — stated as an assumption.
    """
    u = float(q_estimate["era5_u_ms"])
    v = float(q_estimate["era5_v_ms"])
    speed = float(q_estimate["era5_u10_speed_ms"])
    sigma = float(q_estimate["u10_sigma_ms"])
    u_eff = float(q_estimate["u_eff_ms"])
    plume_len = float(q_estimate["plume_length_m"])

    downwind_az = _norm360(math.degrees(math.atan2(u, v)))  # bearing wind blows TO
    upwind_az = _norm360(downwind_az + 180.0)

    half_1s = math.degrees(math.atan2(sigma, speed))
    half_2s = math.degrees(math.atan2(2.0 * sigma, speed))
    transit_s = plume_len / u_eff

    return BackProjectionWedge(
        apex_lat=float(wind_check["source_lat"]),
        apex_lon=float(wind_check["source_lon"]),
        downwind_azimuth_deg=downwind_az,
        upwind_azimuth_deg=upwind_az,
        half_angle_1sigma_deg=half_1s,
        half_angle_2sigma_deg=half_2s,
        search_radius_km=search_radius_km,
        wind_u_ms=u,
        wind_v_ms=v,
        wind_speed_ms=speed,
        u10_sigma_ms=sigma,
        u_eff_ms=u_eff,
        plume_length_m=plume_len,
        transit_time_s=transit_s,
    )
