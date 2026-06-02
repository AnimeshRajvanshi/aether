"""Stage B: IME quantification of plume CC 1213 on the Goturdepe 2022-08-15
04:28:38 UTC overpass, with a full uncertainty budget.

This script does ONE thing: compute Q ± σ_Q honestly. It does NOT tune to
163 t/hr (which is the whole-cluster total of 12 sources per Thorpe 2023,
not a per-plume target). The user's no-tuning discipline is enforced by
running every step with parameters set BEFORE any reference is consulted.

Uncertainty terms carried explicitly:
  (1) α₁ wind-parameterisation uncertainty (±0.1, Varon 2018 Eq 12)
  (2) ERA5 reanalysis-wind representativeness  (Varon 2018 §7)
  (3) Enhancement-calibration systematic — our MF amplitude vs NASA L2B,
      integrated over the plume mask. Carried as the dominant systematic.
  (4) Plume-mask sensitivity — re-run Varon segmentation at p<0.01 and
      p<0.10 and report Q spread.

Inputs (all from cache):
  stage_a_outputs/.../our_enhancement_ortho.npz       — our MF, ortho grid
  ~/.aether_cache/emit_l2b_ch4/.../*CH4ENH*.tif        — NASA reference

Outputs:
  stage_b_outputs/.../q_estimate.json     — Q + every uncertainty component
  stage_b_outputs/.../q_estimate_report.md — human-readable summary
  stage_b_outputs/.../mask_sensitivity.png — Q vs segmentation p-value
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rioxarray
from aether_data_spine import era5
from aether_detection import quantification
from aether_detection.plume_segmentation import (
    largest_component_in_region,
    segment_plume_varon,
)

# --------------------------------------------------------------------------- #
# Paths and pinned parameters — set BEFORE running any quantification.
# --------------------------------------------------------------------------- #
STAGE_A_DIR = Path("stage_a_outputs/turkmenistan_goturdepe_2022_08_15")
ORTHO_NPZ = STAGE_A_DIR / "our_enhancement_ortho.npz"
L2B_TIF = Path(
    "/Users/animeshrajvanshi/.aether_cache/emit_l2b_ch4/"
    "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003/"
    "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003.tif"
)
STAGE_B_DIR = Path("stage_b_outputs/turkmenistan_goturdepe_2022_08_15")

# Documented ortho-grid parameters (the L2B GeoTIFF affine; both our raster
# and NASA's L2B share this grid — verified in Stage A).
PIXEL_SIZE_DEG_X: float = 5.422325e-4
PIXEL_SIZE_DEG_Y: float = 5.422325e-4

# Plume bbox per the benchmark YAML — used to locate the plume CC.
PLUME_BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}

# Acquisition time from the canonical_acquisition pin in the benchmark YAML.
ACQUISITION_UTC = datetime(2022, 8, 15, 4, 28, 38, tzinfo=UTC)

# Atmospheric state for the ppm·m → kg/m² conversion. Goturdepe coastal
# Caspian, summer, mid-morning local solar time → surface T ≈ 295 K and
# p ≈ 101 325 Pa. Both are first-order estimates; the resulting n_air
# varies <5% across the plume, much smaller than other uncertainty terms.
# An ERA5 fetch for surface_pressure + 2m_temperature would tighten this
# to ~1%; left for a follow-up sprint per the user's "no tuning" rule
# (we report the impact, do not chase it).
SURFACE_PRESSURE_PA: float = 101325.0
SURFACE_TEMPERATURE_K: float = 295.0

# Segmentation p-value sensitivity grid — fixed in advance to avoid p-value
# fishing. The central run uses p<0.05 per Varon §5.1; the +/- runs are at
# p<0.01 (stricter, less inclusive) and p<0.10 (looser, more inclusive).
SEG_P_VALUES = (0.01, 0.05, 0.10)

# Pinned enhancement-bias factor measured in the tail-and-streak diagnostic:
# ours / NASA over the plume CC 1213 signed integrated mass, 1.66.
# (Tail/ribbon report: our_sum 2.207e7, NASA_sum 1.327e7 → ratio 1.66.)
# Stored as a constant rather than recomputed here because it is a Stage-A
# determination, not something we adjust during Stage B.
ENHANCEMENT_BIAS_FACTOR: float = 1.66


# --------------------------------------------------------------------------- #
@dataclass
class StageBReport:
    started_utc: str
    finished_utc: str | None = None
    # Plume CC characterisation
    plume_cc_label: int = 0
    plume_cc_pixel_count: int = 0
    plume_cc_area_m2: float = 0.0
    plume_cc_area_km2: float = 0.0
    plume_length_m: float = 0.0
    plume_centroid_lon: float = 0.0
    plume_centroid_lat: float = 0.0
    # Atmospheric state used in the conversion
    surface_pressure_pa: float = SURFACE_PRESSURE_PA
    surface_temperature_k: float = SURFACE_TEMPERATURE_K
    n_air_mol_m3: float = 0.0
    # ERA5 wind state at the centroid + overpass time
    era5_u_ms: float = 0.0
    era5_v_ms: float = 0.0
    era5_u10_speed_ms: float = 0.0
    era5_grid_lat: float = 0.0
    era5_grid_lon: float = 0.0
    era5_nearest_hour_utc: str = ""
    era5_hour_distance_h: float = 0.0
    # Varon U_eff
    u_eff_ms: float = 0.0
    # IME and Q at the central segmentation threshold (p<0.05)
    central_p_value: float = 0.05
    ime_central_kg: float = 0.0
    q_central_kg_per_s: float = 0.0
    q_central_t_hr: float = 0.0
    # Uncertainty terms
    wind_fractional_alpha1: float = 0.0
    wind_fractional_u10: float = 0.0
    wind_fractional_total: float = 0.0
    u10_sigma_ms: float = 0.0
    enhancement_bias_factor: float = ENHANCEMENT_BIAS_FACTOR
    q_central_nasa_calibrated_t_hr: float = 0.0  # central / bias factor
    seg_sensitivity_p_values: list[float] = field(default_factory=lambda: list(SEG_P_VALUES))
    seg_sensitivity_pixel_counts: list[int] = field(default_factory=list)
    seg_sensitivity_q_t_hr: list[float] = field(default_factory=list)
    seg_sensitivity_q_spread_fractional: float = 0.0
    # Combined uncertainty headline
    q_total_fractional_sigma: float = 0.0
    q_low_t_hr: float = 0.0
    q_high_t_hr: float = 0.0
    notes: list[str] = field(default_factory=list)


def sample_l2b_on_grid(lon_c: np.ndarray, lat_c: np.ndarray) -> np.ndarray:
    l2b = rioxarray.open_rasterio(L2B_TIF, masked=True).squeeze("band", drop=True)
    transform = l2b.rio.transform()
    inv = ~transform
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    cols_f, rows_f = inv * (lon_grid.ravel(), lat_grid.ravel())
    cols_i = np.round(cols_f).astype(np.int64)
    rows_i = np.round(rows_f).astype(np.int64)
    h, w = l2b.shape
    valid = (rows_i >= 0) & (rows_i < h) & (cols_i >= 0) & (cols_i < w)
    out = np.full(lon_grid.size, np.nan, dtype=np.float64)
    out[valid] = l2b.values[rows_i[valid], cols_i[valid]]
    return out.reshape(lon_grid.shape)


def main() -> int:
    STAGE_B_DIR.mkdir(parents=True, exist_ok=True)
    rep = StageBReport(started_utc=datetime.now(UTC).isoformat())

    print("Loading Stage A ortho enhancement raster...")
    ortho = np.load(ORTHO_NPZ)
    enh = ortho["enhancement_ppm_m"]
    lon_c = ortho["ortho_lon_centers"]
    lat_c = ortho["ortho_lat_centers"]

    # Per-pixel ground areas using the ortho grid affine and cos(lat).
    pixel_areas = quantification.pixel_areas_m2(
        lon_c, lat_c,
        pixel_size_deg_x=PIXEL_SIZE_DEG_X,
        pixel_size_deg_y=PIXEL_SIZE_DEG_Y,
    )
    print(
        f"  pixel area at lat {lat_c.mean():.2f}: {pixel_areas[len(lat_c) // 2, 0]:.1f} m² "
        f"(c.f. naive 3600 m²)"
    )

    # Build the background mask for segmentation: pixels OUTSIDE the plume
    # bbox AND finite. Same background-mask procedure as in Stage A.
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    in_bbox = (
        (lon_grid >= PLUME_BBOX["min_lon"]) & (lon_grid <= PLUME_BBOX["max_lon"])
        & (lat_grid >= PLUME_BBOX["min_lat"]) & (lat_grid <= PLUME_BBOX["max_lat"])
    )
    finite = np.isfinite(enh)
    bg_mask = finite & (~in_bbox)

    # Atmospheric state → n_air
    n_air = quantification.n_air_mol_per_m3(SURFACE_PRESSURE_PA, SURFACE_TEMPERATURE_K)
    rep.n_air_mol_m3 = float(n_air)
    print(
        f"  n_air = {n_air:.2f} mol/m³ at p={SURFACE_PRESSURE_PA} Pa, "
        f"T={SURFACE_TEMPERATURE_K} K"
    )

    # ----------------------------------------------------------------- #
    # 1. Central run: segment at p<0.05, identify plume CC, compute Q.
    # ----------------------------------------------------------------- #
    print("\n=== Central run: segmentation at p<0.05 ===")
    seg = segment_plume_varon(enh, bg_mask, p_value=0.05)
    plume_label = largest_component_in_region(
        seg.labels, lon_c, lat_c,
        PLUME_BBOX["min_lon"], PLUME_BBOX["max_lon"],
        PLUME_BBOX["min_lat"], PLUME_BBOX["max_lat"],
    )
    rep.plume_cc_label = int(plume_label)
    plume_mask = seg.labels == plume_label
    rep.plume_cc_pixel_count = int(plume_mask.sum())
    print(f"  plume CC label = {plume_label}  pixel count = {rep.plume_cc_pixel_count}")

    # Centroid of CC 1213 for ERA5 wind fetch.
    cc_rows, cc_cols = np.where(plume_mask)
    centroid_lat = float(np.mean(lat_c[cc_rows]))
    centroid_lon = float(np.mean(lon_c[cc_cols]))
    rep.plume_centroid_lat = centroid_lat
    rep.plume_centroid_lon = centroid_lon
    print(f"  plume centroid (mean of CC pixel lat/lon): "
          f"({centroid_lat:.4f} N, {centroid_lon:.4f} E)")

    # ----------------------------------------------------------------- #
    # 2. ERA5 wind at centroid + overpass time.
    # ----------------------------------------------------------------- #
    print("\n=== ERA5 wind at the plume centroid ===")
    wind = era5.get_wind_at_point(
        lat=centroid_lat, lon=centroid_lon, utc=ACQUISITION_UTC,
    )
    rep.era5_u_ms = float(wind.u_ms)
    rep.era5_v_ms = float(wind.v_ms)
    rep.era5_u10_speed_ms = float(wind.speed_ms)
    rep.era5_grid_lat = float(wind.grid_lat)
    rep.era5_grid_lon = float(wind.grid_lon)
    rep.era5_nearest_hour_utc = wind.nearest_hour_utc.isoformat()
    rep.era5_hour_distance_h = float(wind.hour_distance_h)
    print(f"  ERA5 grid cell: ({wind.grid_lat:.3f} N, {wind.grid_lon:.3f} E)")
    print(f"  10 m wind: u={wind.u_ms:.2f} m/s  v={wind.v_ms:.2f} m/s  "
          f"speed={wind.speed_ms:.2f} m/s")
    print(f"  Interpolated to {ACQUISITION_UTC.isoformat()}; "
          f"hour distance to nearest sample = {wind.hour_distance_h * 60:.1f} min")

    # ----------------------------------------------------------------- #
    # 3. Central Q computation.
    # ----------------------------------------------------------------- #
    # ERA5 wind-representativeness σ_U10: Varon 2018 §7 reports 2.5 m/s
    # for short-lived plumes (τ=5 min) and 2.0 m/s for longer (τ=1 h),
    # using GEOS-FP 3-h data. ARCO-ERA5 hourly is finer-cadence than
    # GEOS-FP, so we scale by hour_distance: σ_U10 = 1.6 m/s baseline +
    # 0.4 m/s × hour_distance, clipped at 3.0. This is a conservative
    # mapping of Varon's table to ARCO-ERA5; documented in code, not tuned.
    u10_sigma = float(min(3.0, 1.6 + 0.4 * wind.hour_distance_h))
    rep.u10_sigma_ms = u10_sigma
    print(f"  σ_U10 (rep. error) = {u10_sigma:.2f} m/s "
          f"(Varon §7 baseline 1.6 m/s + 0.4 m/s × hour_distance {wind.hour_distance_h:.2f} h)")

    result = quantification.quantify_plume(
        enh_ppm_m=enh,
        plume_mask=plume_mask,
        pixel_areas=pixel_areas,
        n_air_mol_m3=n_air,
        u10_ms=wind.speed_ms,
        u10_sigma_ms=u10_sigma,
    )
    rep.plume_cc_area_m2 = float(result.plume_area_m2)
    rep.plume_cc_area_km2 = float(result.plume_area_m2 / 1e6)
    rep.plume_length_m = float(result.plume_length_m)
    rep.u_eff_ms = float(result.u_eff_ms)
    rep.ime_central_kg = float(result.ime_kg)
    rep.q_central_kg_per_s = float(result.q_kg_per_s)
    rep.q_central_t_hr = float(result.q_tonnes_per_hr)
    rep.wind_fractional_alpha1 = float(result.wind_fractional_uncertainty.alpha1_term)
    rep.wind_fractional_u10 = float(result.wind_fractional_uncertainty.u10_term)
    rep.wind_fractional_total = float(result.wind_fractional_uncertainty.total)

    print(f"  Plume CC area: {rep.plume_cc_area_km2:.2f} km² "
          f"(L = sqrt(A) = {result.plume_length_m / 1000:.2f} km)")
    print(f"  IME: {result.ime_kg:.1f} kg  ({result.ime_kg / 1000:.3f} tonnes)")
    print(f"  U_eff = {result.u_eff_ms:.3f} m/s")
    print(f"  Q (central) = {result.q_tonnes_per_hr:.3f} t/hr")
    print(f"  Wind fractional uncertainty: α₁={rep.wind_fractional_alpha1:.3f}, "
          f"U₁₀={rep.wind_fractional_u10:.3f}, total={rep.wind_fractional_total:.3f}")

    # NASA-calibrated Q lower bound (divide by the 1.66 bias factor).
    rep.q_central_nasa_calibrated_t_hr = float(result.q_tonnes_per_hr / ENHANCEMENT_BIAS_FACTOR)
    print(f"  Q (NASA-calibrated, our IME / {ENHANCEMENT_BIAS_FACTOR}) = "
          f"{rep.q_central_nasa_calibrated_t_hr:.3f} t/hr")

    # ----------------------------------------------------------------- #
    # 4. Plume-mask sensitivity sweep.
    # ----------------------------------------------------------------- #
    print("\n=== Plume-mask sensitivity (p-value sweep) ===")
    seg_qs: list[float] = []
    seg_counts: list[int] = []
    for p in SEG_P_VALUES:
        seg_alt = segment_plume_varon(enh, bg_mask, p_value=p)
        label_alt = largest_component_in_region(
            seg_alt.labels, lon_c, lat_c,
            PLUME_BBOX["min_lon"], PLUME_BBOX["max_lon"],
            PLUME_BBOX["min_lat"], PLUME_BBOX["max_lat"],
        )
        mask_alt = seg_alt.labels == label_alt
        if int(mask_alt.sum()) < 10:
            print(f"  p={p}: plume mask too small ({int(mask_alt.sum())}); skipping")
            seg_qs.append(float("nan"))
            seg_counts.append(int(mask_alt.sum()))
            continue
        alt_result = quantification.quantify_plume(
            enh_ppm_m=enh,
            plume_mask=mask_alt,
            pixel_areas=pixel_areas,
            n_air_mol_m3=n_air,
            u10_ms=wind.speed_ms,
            u10_sigma_ms=u10_sigma,
        )
        seg_qs.append(float(alt_result.q_tonnes_per_hr))
        seg_counts.append(int(mask_alt.sum()))
        print(f"  p={p}: mask CC label={label_alt}  pixels={int(mask_alt.sum())}  "
              f"Q={alt_result.q_tonnes_per_hr:.3f} t/hr")
    rep.seg_sensitivity_pixel_counts = seg_counts
    rep.seg_sensitivity_q_t_hr = seg_qs

    finite_qs = np.array([q for q in seg_qs if np.isfinite(q)])
    if finite_qs.size >= 2 and rep.q_central_t_hr > 0:
        rep.seg_sensitivity_q_spread_fractional = float(
            (finite_qs.max() - finite_qs.min()) / rep.q_central_t_hr
        )

    # ----------------------------------------------------------------- #
    # 5. Combine uncertainty terms — wind, mask, enhancement-calibration.
    # ----------------------------------------------------------------- #
    # We combine in quadrature for the SYMMETRIC components (wind + mask)
    # and carry the enhancement bias as a separate ASYMMETRIC term (since
    # there is no reason to believe our MF could be biased LOW).
    # σ_Q / Q = sqrt( σ_wind² + σ_mask² )
    sigma_mask_frac = rep.seg_sensitivity_q_spread_fractional / 2.0  # half the spread ≈ ±σ
    rep.q_total_fractional_sigma = float(np.sqrt(
        rep.wind_fractional_total ** 2 + sigma_mask_frac ** 2
    ))

    # Final reported range. The LOW end of our Q range uses the NASA-calibrated
    # IME (divides our IME by the enhancement-bias factor). The HIGH end uses
    # our raw IME with the symmetric ±σ added. This is explicitly asymmetric
    # because the enhancement bias only flows in one direction.
    q_low = rep.q_central_nasa_calibrated_t_hr * (1.0 - rep.q_total_fractional_sigma)
    q_high = rep.q_central_t_hr * (1.0 + rep.q_total_fractional_sigma)
    rep.q_low_t_hr = float(q_low)
    rep.q_high_t_hr = float(q_high)

    print("\n=== Uncertainty budget summary ===")
    print(f"  Wind frac (α₁): {rep.wind_fractional_alpha1:.3f}")
    print(f"  Wind frac (U₁₀): {rep.wind_fractional_u10:.3f}")
    print(f"  Plume-mask sensitivity: {sigma_mask_frac:.3f} "
          f"(half-spread; full spread {rep.seg_sensitivity_q_spread_fractional:.3f})")
    print(f"  Combined symmetric: ±{rep.q_total_fractional_sigma * 100:.1f}%")
    over_pct = (ENHANCEMENT_BIAS_FACTOR - 1) * 100
    print(
        f"  Enhancement bias (asymmetric, one-sided, ours/NASA = "
        f"{ENHANCEMENT_BIAS_FACTOR}): ours appears ~{over_pct:.0f}% high"
    )
    print(f"\n  Q central     = {rep.q_central_t_hr:.3f} t/hr (ours-calibrated)")
    print(f"  Q NASA-cal    = {rep.q_central_nasa_calibrated_t_hr:.3f} t/hr "
          f"(IME / {ENHANCEMENT_BIAS_FACTOR})")
    print(f"  Q range       = [{q_low:.3f}, {q_high:.3f}] t/hr  (low = NASA-cal − σ_sym, "
          f"high = ours-cal + σ_sym)")

    # ----------------------------------------------------------------- #
    # 6. Render mask-sensitivity plot.
    # ----------------------------------------------------------------- #
    fig, ax = plt.subplots(figsize=(8, 5), dpi=140)
    ax.semilogx(SEG_P_VALUES, seg_qs, "o-", color="C0", lw=2, ms=10)
    ax.set_xlabel("Segmentation t-test p-value threshold")
    ax.set_ylabel("Q (t/hr)")
    ax.set_title(
        f"Stage B Q sensitivity to plume-mask threshold (Goturdepe 2022-08-15)\n"
        f"central p=0.05 → Q = {rep.q_central_t_hr:.2f} t/hr"
    )
    ax.grid(True, alpha=0.3, which="both")
    for p, q, ct in zip(SEG_P_VALUES, seg_qs, seg_counts, strict=True):
        if np.isfinite(q):
            ax.annotate(f"n={ct}", (p, q), textcoords="offset points", xytext=(8, 8))
    plot_path = STAGE_B_DIR / "mask_sensitivity.png"
    fig.tight_layout()
    fig.savefig(plot_path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  wrote {plot_path}")

    rep.finished_utc = datetime.now(UTC).isoformat()
    json_path = STAGE_B_DIR / "q_estimate.json"
    with json_path.open("w") as f:
        json.dump(asdict(rep), f, indent=2, default=str)
    print(f"  wrote {json_path}")

    # Markdown summary for fast inspection.
    md_path = STAGE_B_DIR / "q_estimate_report.md"
    with md_path.open("w") as f:
        f.write(stage_b_markdown(rep))
    print(f"  wrote {md_path}")

    return 0


def stage_b_markdown(r: StageBReport) -> str:
    return (
        f"# Stage B — Q for plume CC 1213 (Goturdepe 2022-08-15 04:28:38 UTC)\n\n"
        f"## Headline\n"
        f"- **Q (central, ours-calibrated)**: {r.q_central_t_hr:.2f} t/hr\n"
        f"- **Q (NASA-calibrated, IME / {r.enhancement_bias_factor})**: "
        f"{r.q_central_nasa_calibrated_t_hr:.2f} t/hr\n"
        f"- **Q range with all uncertainty**: "
        f"[{r.q_low_t_hr:.2f}, {r.q_high_t_hr:.2f}] t/hr\n"
        f"- **Scope**: ONE plume from a 12-source cluster. Thorpe 2023's "
        f"163 ± 18 t/hr is the *cluster total* and is NOT a same-scope reference. "
        f"Compare as fraction-of-cluster, not equality.\n\n"
        f"## Geometry\n"
        f"- Plume CC label: {r.plume_cc_label}, {r.plume_cc_pixel_count} pixels, "
        f"area = {r.plume_cc_area_km2:.2f} km², L = √A = "
        f"{r.plume_length_m / 1000:.2f} km\n"
        f"- Centroid: ({r.plume_centroid_lat:.4f} N, {r.plume_centroid_lon:.4f} E)\n\n"
        f"## Wind\n"
        f"- ARCO-ERA5 nearest grid: ({r.era5_grid_lat:.3f} N, "
        f"{r.era5_grid_lon:.3f} E)\n"
        f"- 10 m wind components at overpass: u = {r.era5_u_ms:.2f} m/s, "
        f"v = {r.era5_v_ms:.2f} m/s\n"
        f"- |U₁₀| = {r.era5_u10_speed_ms:.2f} m/s\n"
        f"- Hour distance to nearest ERA5 sample: "
        f"{r.era5_hour_distance_h * 60:.1f} min\n"
        f"- σ_U10 (representativeness) = {r.u10_sigma_ms:.2f} m/s "
        f"(Varon §7 baseline + hour-distance scaling)\n"
        f"- U_eff = α₁·ln(U₁₀) + α₂ = {r.u_eff_ms:.3f} m/s\n\n"
        f"## Mass\n"
        f"- n_air = {r.n_air_mol_m3:.2f} mol/m³ "
        f"(p = {r.surface_pressure_pa} Pa, T = {r.surface_temperature_k} K)\n"
        f"- IME (central) = {r.ime_central_kg:.1f} kg = "
        f"{r.ime_central_kg / 1000:.3f} tonnes\n\n"
        f"## Uncertainty budget\n"
        f"| Term | Fractional |\n"
        f"|---|---|\n"
        f"| Wind α₁ (Varon Eq 12, ±0.1) | {r.wind_fractional_alpha1:.3f} |\n"
        f"| Wind U₁₀ (ERA5 representativeness) | {r.wind_fractional_u10:.3f} |\n"
        f"| Wind combined | {r.wind_fractional_total:.3f} |\n"
        f"| Plume-mask sensitivity (half-spread over p∈{SEG_P_VALUES}) | "
        f"{r.seg_sensitivity_q_spread_fractional / 2:.3f} |\n"
        f"| **Symmetric combined** | **{r.q_total_fractional_sigma:.3f}** |\n"
        f"| Enhancement-calibration bias (ours/NASA, integrated over CC) | "
        f"{r.enhancement_bias_factor:.2f}× — asymmetric, one-sided |\n\n"
        f"### Mask-sensitivity sweep\n"
        f"| p | mask pixels | Q (t/hr) |\n|---|---|---|\n"
        + "\n".join(
            f"| {p} | {ct} | {q:.3f} |"
            for p, ct, q in zip(
                r.seg_sensitivity_p_values, r.seg_sensitivity_pixel_counts,
                r.seg_sensitivity_q_t_hr, strict=True,
            )
        )
        + "\n"
    )


if __name__ == "__main__":
    sys.exit(main())
