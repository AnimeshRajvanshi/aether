"""Verify Varon's wind-location requirement: U_eff wants wind at the source,
not at the geometric centroid of the plume mask.

Locked methodology (chosen BEFORE running):
  Source = centroid of the top 5% of plume-CC pixels ranked by upwind
  projection. Upwind direction = -ERA5 wind vector. Projection in metres
  using local cos(lat).

Recompute Q with the wind fetched at this source location and report whether
Q changes materially. NO knob is tuned — the 5% top-rank threshold and the
upwind-projection metric are fixed in this script.

Read-only of cached Stage A artefacts + one new ARCO-ERA5 call.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from aether_data_spine import era5
from aether_detection import quantification
from aether_detection.plume_segmentation import (
    largest_component_in_region,
    segment_plume_varon,
)

# --- inputs -------------------------------------------------------------- #
STAGE_A_NPZ = Path(
    "stage_a_outputs/turkmenistan_goturdepe_2022_08_15/our_enhancement_ortho.npz"
)
STAGE_B_REPORT = Path(
    "stage_b_outputs/turkmenistan_goturdepe_2022_08_15/q_estimate.json"
)
ACQUISITION_UTC = datetime(2022, 8, 15, 4, 28, 38, tzinfo=UTC)
PIXEL_SIZE_DEG = 5.422325e-4
PLUME_BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}
TOP_FRACTION_FOR_SOURCE = 0.05  # locked before run
SURFACE_PRESSURE_PA = 101325.0
SURFACE_TEMPERATURE_K = 295.0


def main() -> None:
    print("Loading Stage A ortho enhancement + Stage B baseline...")
    ortho = np.load(STAGE_A_NPZ)
    enh = ortho["enhancement_ppm_m"]
    lon_c = ortho["ortho_lon_centers"]
    lat_c = ortho["ortho_lat_centers"]

    with STAGE_B_REPORT.open() as f:
        stage_b = json.load(f)
    baseline_centroid_lat = stage_b["plume_centroid_lat"]
    baseline_centroid_lon = stage_b["plume_centroid_lon"]
    baseline_u10 = stage_b["era5_u10_speed_ms"]
    baseline_u = stage_b["era5_u_ms"]
    baseline_v = stage_b["era5_v_ms"]
    baseline_q = stage_b["q_central_t_hr"]
    print(f"  baseline centroid: ({baseline_centroid_lat:.4f} N, "
          f"{baseline_centroid_lon:.4f} E)")
    print(f"  baseline ERA5 wind: u={baseline_u:.2f} m/s  v={baseline_v:.2f} m/s  "
          f"|U10|={baseline_u10:.2f} m/s")
    print(f"  baseline Q (centroid-based)        : {baseline_q:.3f} t/hr")

    # ---------------------------------------------------------------- #
    # 1. Locate plume CC (same segmentation as Stage B).
    # ---------------------------------------------------------------- #
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    in_bbox = (
        (lon_grid >= PLUME_BBOX["min_lon"]) & (lon_grid <= PLUME_BBOX["max_lon"])
        & (lat_grid >= PLUME_BBOX["min_lat"]) & (lat_grid <= PLUME_BBOX["max_lat"])
    )
    finite = np.isfinite(enh)
    bg_mask = finite & (~in_bbox)
    seg = segment_plume_varon(enh, bg_mask, p_value=0.05)
    plume_label = largest_component_in_region(
        seg.labels, lon_c, lat_c,
        PLUME_BBOX["min_lon"], PLUME_BBOX["max_lon"],
        PLUME_BBOX["min_lat"], PLUME_BBOX["max_lat"],
    )
    plume_mask = seg.labels == plume_label
    cc_rows, cc_cols = np.where(plume_mask)
    cc_lats = lat_c[cc_rows]
    cc_lons = lon_c[cc_cols]
    print(f"\n  plume CC: {int(plume_mask.sum())} pixels (same as Stage B)")

    # ---------------------------------------------------------------- #
    # 2. Project CC pixels onto the upwind axis using the baseline wind.
    # ---------------------------------------------------------------- #
    # Upwind = the direction OPPOSITE to ERA5 wind.
    upwind_u = -baseline_u
    upwind_v = -baseline_v
    upwind_mag = np.hypot(upwind_u, upwind_v)
    upwind_unit_u = upwind_u / upwind_mag  # eastward component
    upwind_unit_v = upwind_v / upwind_mag  # northward component
    print(f"  ERA5 wind blows toward (u={baseline_u:.2f}, v={baseline_v:.2f}); "
          f"upwind = (+{upwind_unit_u:.3f}, +{upwind_unit_v:.3f}) — i.e. wind comes "
          "FROM east-northeast")

    # Convert CC pixel lon/lat to local metres for projection. Reference =
    # baseline centroid (this just sets the origin; the relative projection
    # is independent of the reference).
    lat_ref = baseline_centroid_lat
    cc_x_m = (cc_lons - baseline_centroid_lon) * 111319.49 * np.cos(np.radians(lat_ref))
    cc_y_m = (cc_lats - baseline_centroid_lat) * 111319.49
    upwind_projection = cc_x_m * upwind_unit_u + cc_y_m * upwind_unit_v
    print(f"  upwind-projection range across CC: "
          f"[{upwind_projection.min() / 1000:.2f}, {upwind_projection.max() / 1000:.2f}] km "
          f"(plume length along upwind axis ~"
          f"{(upwind_projection.max() - upwind_projection.min()) / 1000:.2f} km)")

    # ---------------------------------------------------------------- #
    # 3. Source = centroid of top 5% upwind-projected pixels.
    # ---------------------------------------------------------------- #
    threshold = np.quantile(upwind_projection, 1.0 - TOP_FRACTION_FOR_SOURCE)
    top_idx = upwind_projection >= threshold
    n_top = int(top_idx.sum())
    source_lat = float(cc_lats[top_idx].mean())
    source_lon = float(cc_lons[top_idx].mean())
    print(f"\n  top {TOP_FRACTION_FOR_SOURCE * 100:.0f}% upwind pixels = "
          f"{n_top} pixels; source = ({source_lat:.4f} N, {source_lon:.4f} E)")
    distance_km = np.hypot(
        (source_lon - baseline_centroid_lon) * 111319.49 * np.cos(np.radians(lat_ref)),
        (source_lat - baseline_centroid_lat) * 111319.49,
    ) / 1000.0
    print(f"  distance source → baseline centroid: {distance_km:.2f} km")

    # ---------------------------------------------------------------- #
    # 4. Re-fetch ERA5 wind at the source.
    # ---------------------------------------------------------------- #
    print("\n  Re-fetching ARCO-ERA5 wind at the source location...")
    src_wind = era5.get_wind_at_point(
        lat=source_lat, lon=source_lon, utc=ACQUISITION_UTC,
    )
    print(f"  ERA5 grid cell at source: "
          f"({src_wind.grid_lat:.3f} N, {src_wind.grid_lon:.3f} E)")
    print(f"  10 m wind at source: u={src_wind.u_ms:.2f}  v={src_wind.v_ms:.2f}  "
          f"|U10|={src_wind.speed_ms:.2f} m/s")
    delta_u10 = src_wind.speed_ms - baseline_u10
    print(f"  ΔU10 (source − centroid): {delta_u10:+.3f} m/s "
          f"({delta_u10 / baseline_u10 * 100:+.2f}%)")

    # ---------------------------------------------------------------- #
    # 5. Recompute Q with the source-located wind.
    # ---------------------------------------------------------------- #
    pixel_areas = quantification.pixel_areas_m2(
        lon_c, lat_c, PIXEL_SIZE_DEG, PIXEL_SIZE_DEG,
    )
    n_air = quantification.n_air_mol_per_m3(SURFACE_PRESSURE_PA, SURFACE_TEMPERATURE_K)
    src_result = quantification.quantify_plume(
        enh_ppm_m=enh,
        plume_mask=plume_mask,
        pixel_areas=pixel_areas,
        n_air_mol_m3=n_air,
        u10_ms=src_wind.speed_ms,
        u10_sigma_ms=min(3.0, 1.6 + 0.4 * src_wind.hour_distance_h),
    )

    print(f"\n  U_eff at source: {src_result.u_eff_ms:.3f} m/s "
          f"(was {stage_b['u_eff_ms']:.3f} at centroid)")
    delta_q = src_result.q_tonnes_per_hr - baseline_q
    print(f"  Q (source-based)    : {src_result.q_tonnes_per_hr:.3f} t/hr")
    print(f"  Q (centroid baseline) : {baseline_q:.3f} t/hr")
    print(f"  ΔQ (source − centroid): {delta_q:+.3f} t/hr "
          f"({delta_q / baseline_q * 100:+.2f}%)")

    # Material change criterion locked: |ΔQ/Q| < 0.10 (smaller than the
    # symmetric uncertainty budget of ±12.9%) → not material.
    rel = abs(delta_q / baseline_q)
    is_material = rel >= 0.10
    print(f"\n  Material-change threshold (|ΔQ/Q| ≥ 0.10): "
          f"{'MATERIAL' if is_material else 'NOT MATERIAL'} ({rel * 100:.1f}%)")

    out_json = Path(
        "stage_b_outputs/turkmenistan_goturdepe_2022_08_15/wind_location_check.json"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w") as f:
        json.dump({
            "centroid_lat": baseline_centroid_lat,
            "centroid_lon": baseline_centroid_lon,
            "source_lat": source_lat,
            "source_lon": source_lon,
            "distance_km": float(distance_km),
            "n_top_pixels": n_top,
            "top_fraction_for_source": TOP_FRACTION_FOR_SOURCE,
            "centroid_u10_ms": baseline_u10,
            "source_u10_ms": float(src_wind.speed_ms),
            "delta_u10_ms": float(delta_u10),
            "centroid_u_eff_ms": stage_b["u_eff_ms"],
            "source_u_eff_ms": float(src_result.u_eff_ms),
            "centroid_q_t_hr": baseline_q,
            "source_q_t_hr": float(src_result.q_tonnes_per_hr),
            "delta_q_t_hr": float(delta_q),
            "relative_delta_q": float(rel),
            "material_change": bool(is_material),
            "material_threshold": 0.10,
            "centroid_era5_grid_lat": stage_b["era5_grid_lat"],
            "centroid_era5_grid_lon": stage_b["era5_grid_lon"],
            "source_era5_grid_lat": float(src_wind.grid_lat),
            "source_era5_grid_lon": float(src_wind.grid_lon),
        }, f, indent=2)
    print(f"\n  wrote {out_json}")


if __name__ == "__main__":
    main()
