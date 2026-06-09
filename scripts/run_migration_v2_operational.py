"""Sprint 6 operational migration: make the v2 saturation-aware HITRAN k the
OPERATIONAL Goturdepe retrieval, end to end, offline and reproducibly.

This re-runs the committed Stage A detection + Stage B quantification with the
independent v2 k (``hitran_k.generate_k_regression``) and writes the operational
artifacts that the API/dashboard/attribution read:

  stage_a_outputs/<id>/our_enhancement_ortho.npz   (v2 ortho enhancement; gitignored)
  stage_a_outputs/<id>/stage_a_report.json         (v2; provenance line FLIPPED to HITRAN)
  stage_b_outputs/<id>/q_estimate.json + .md       (v2 Q + RE-PROPAGATED uncertainty budget)
  stage_b_outputs/<id>/wind_location_check.json    (v2 upwind source S, recomputed offline)

The NASA-k originals are preserved alongside as ``*.nasa_k.*`` (committed) and in
git history — this script never deletes them.

Honesty notes (the things that did and did NOT change):
  * The v2 k is generated from HITRAN2020 via HAPI; NASA's per-granule target file
    is NEVER read here (cross-check only, in run_hitran_k_v2.py). Forward scaling
    is 1.0 — k is in 1/(ppm·m), not reverse-fit to any flux.
  * The MF amplitude systematic is now the INDEPENDENTLY MEASURED ours/NASA ratio
    over the plume CC (≈1.46×), computed here — not the hand-carried 1.66× of the
    NASA-k run.
  * ERA5 wind is UNCHANGED BY CONSTRUCTION: the v2 plume centroid and upwind source
    both fall in the same 0.25° ARCO-ERA5 grid cells as the NASA-k run, so the
    reanalysis returns identical winds. We reuse the committed wind values and
    assert the grid-cell identity rather than issue a redundant network fetch.

Run from the repo root:  uv run python scripts/run_migration_v2_operational.py
"""

from __future__ import annotations

# Imports follow warnings.filterwarnings(); exempt E402.
# ruff: noqa: E402
import json
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import rioxarray
from aether_data_spine import emit_l1b, emit_l2a_mask
from aether_detection import hitran_k, matched_filter, quantification
from aether_detection.plume_segmentation import (
    largest_component_in_region,
    segment_plume_varon,
)

EVENT_ID = "turkmenistan_goturdepe_2022_08_15"
REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("~/.aether_cache").expanduser()
SA_DIR = REPO_ROOT / "stage_a_outputs" / EVENT_ID
SB_DIR = REPO_ROOT / "stage_b_outputs" / EVENT_ID
L2B_TIF = (
    CACHE / "emit_l2b_ch4"
    / "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003"
    / "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003.tif"
)

PLUME_BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}
PIXEL_SIZE_DEG = 5.422325e-4
C_MAX_PPM_M = 10000.0
SEG_P_VALUES = (0.01, 0.05, 0.10)
TOP_FRACTION_FOR_SOURCE = 0.05  # locked (matches diagnose_wind_location.py)

# Provenance descriptor for the FLIPPED target-spectrum line. The independent k is
# generated, not downloaded; this string names the method + the file we wrote.
K_LOCAL = "stage_a_outputs/%s/hitran_k/hitran_k_sat.json" % EVENT_ID
TARGET_SPECTRUM_SOURCE = (
    "Independent HITRAN2020 line-by-line (HAPI) — saturation-aware unit absorption "
    "via finite-enhancement log-radiance regression (Thompson/EMIT-ATBD method). "
    "NASA per-granule target NOT used (shape cross-check only, r=0.993). "
    "See %s and hitran_k/hitran_k_sat_provenance.json." % K_LOCAL
)


def log(m: str) -> None:
    print(m, flush=True)


def _geometry(ds) -> tuple[float, float]:
    """Mean solar- and view-zenith from the OBS cube (bands 4 and 2)."""
    a = np.asarray(ds["obs_obs"].values, dtype=np.float64)
    a = np.moveaxis(a, int(np.argmin(a.shape)), -1)

    def mb(i: int) -> float:
        v = a[..., i].ravel()
        v = v[np.isfinite(v) & (v > -900)]
        return float(np.mean(v))

    return mb(4), mb(2)


def main() -> int:
    t_start = datetime.now(UTC)
    nasa_q = json.loads((SB_DIR / "q_estimate.nasa_k.json").read_text())
    nasa_a = json.loads((SA_DIR / "stage_a_report.nasa_k.json").read_text())
    p_pa = float(nasa_q["surface_pressure_pa"])
    t_k = float(nasa_q["surface_temperature_k"])

    # ---- load cached EMIT inputs (offline) ----
    ds = emit_l1b.load_l1b_from_cache(sorted((CACHE / "emit_l1b").glob("*.zarr"))[0])
    radiance, wl, fwhm = emit_l1b.get_radiance_cube(ds)
    sza, vza = _geometry(ds)
    log(f"geometry: SZA={sza:.3f} VZA={vza:.3f}; surface P={p_pa:.0f} T={t_k:.1f}")

    l2a = emit_l2a_mask.load_l2a_mask_from_cache(
        sorted((CACHE / "emit_l2a_mask").glob("*.zarr"))[0]
    )
    bad = emit_l2a_mask.build_bad_pixel_mask(l2a, use_aggregate=True)
    bad_frac = float(bad.mean())

    # ---- Stage A: generate v2 k + run MF (forward scale 1.0) ----
    res = hitran_k.generate_k_regression(
        wl, fwhm, solar_zenith_deg=sza, view_zenith_deg=vza,
        surface_pressure_pa=p_pa, surface_temperature_k=t_k, c_max_ppm_m=C_MAX_PPM_M,
    )
    our_k = res.k
    shape_r = float(res.provenance.get("shape_pearson_r_vs_nasa", 0.0)) or None

    log("Running matched filter with v2 saturation-aware k (ppm_scaling=1.0)...")
    t0 = time.time()
    mf = matched_filter.run_matched_filter(
        radiance=radiance, wavelengths_nm=wl, unit_absorption_spectrum_k=our_k,
        bad_pixel_mask=bad, ppm_scaling_factor=1.0,
    )
    log(f"  MF done in {time.time() - t0:.1f}s; bands kept={mf.band_indices_kept.size}")

    glt_x = np.asarray(ds["glt_x"].values)
    glt_y = np.asarray(ds["glt_y"].values)
    ours_ortho = emit_l1b.orthorectify_raw_raster(mf.enhancement_ppm_m, glt_x, glt_y)

    l2b = rioxarray.open_rasterio(L2B_TIF, masked=True).squeeze("band", drop=True)
    nasa_ortho = np.asarray(l2b.values, dtype=np.float64)
    transform = l2b.rio.transform()
    ny, nx = nasa_ortho.shape
    lon_c = np.array([transform.c + (i + 0.5) * transform.a for i in range(nx)])
    lat_c = np.array([transform.f + (i + 0.5) * transform.e for i in range(ny)])
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    in_bbox = (
        (lon_grid >= PLUME_BBOX["min_lon"]) & (lon_grid <= PLUME_BBOX["max_lon"])
        & (lat_grid >= PLUME_BBOX["min_lat"]) & (lat_grid <= PLUME_BBOX["max_lat"])
    )

    # Operational ortho npz (same format as run_stage_a_goturdepe.py — l2b_transform
    # is required by build_dashboard_assets.py + diagnose_wind_location.py).
    np.savez_compressed(
        SA_DIR / "our_enhancement_ortho.npz",
        enhancement_ppm_m=ours_ortho,
        ortho_lon_centers=lon_c,
        ortho_lat_centers=lat_c,
        l2b_transform=np.asarray(transform[:6]),
    )

    ok = np.isfinite(ours_ortho) & np.isfinite(nasa_ortho)
    ok_bbox = ok & in_bbox
    pearson_full = float(np.corrcoef(ours_ortho[ok], nasa_ortho[ok])[0, 1])
    pearson_bbox = float(np.corrcoef(ours_ortho[ok_bbox], nasa_ortho[ok_bbox])[0, 1])
    strong = ok_bbox & ((ours_ortho > 200.0) | (nasa_ortho > 200.0))
    pearson_strong = float(np.corrcoef(ours_ortho[strong], nasa_ortho[strong])[0, 1])
    log(f"Stage A Pearson vs NASA L2B: full={pearson_full:.4f} bbox={pearson_bbox:.4f} "
        f"strong={pearson_strong:.4f}")

    alpha = mf.shrinkage_alpha_per_column
    alpha = alpha[np.isfinite(alpha)]

    stage_a_report = {
        "started_utc": t_start.isoformat(),
        "finished_utc": datetime.now(UTC).isoformat(),
        "acquisition_utc": nasa_a["acquisition_utc"],
        "l1b_granule_ur": nasa_a["l1b_granule_ur"],
        "l2a_mask_granule_ur": nasa_a["l2a_mask_granule_ur"],
        "l2b_ch4_granule_ur": nasa_a["l2b_ch4_granule_ur"],
        # --- FLIPPED provenance: independent HITRAN, NASA target NOT used ---
        "target_spectrum_source": TARGET_SPECTRUM_SOURCE,
        "target_spectrum_local_path": str((SA_DIR / "hitran_k" / "hitran_k_sat.json")),
        "k_method": res.provenance["method"],
        "k_nasa_target_used": False,
        "k_shape_pearson_r_vs_nasa": shape_r,
        "k_provenance_ref": "stage_a_outputs/%s/hitran_k/hitran_k_sat_provenance.json" % EVENT_ID,
        "ppm_scaling_factor_forward": 1.0,
        "radiance_shape": list(radiance.shape),
        "bands_used": int(mf.band_indices_kept.size),
        "bad_pixel_fraction": bad_frac,
        "enhancement_raw_npy": nasa_a.get("enhancement_raw_npy"),
        "nasa_l2b_geotiff": str(L2B_TIF),
        "side_by_side_png": nasa_a.get("side_by_side_png"),
        "plume_bbox": PLUME_BBOX,
        "pearson_full_scene": pearson_full,
        "pearson_in_bbox": pearson_bbox,
        "pearson_in_bbox_strong_signal": pearson_strong,
        "n_pixels_compared_full": int(ok.sum()),
        "n_pixels_compared_bbox": int(ok_bbox.sum()),
        "shrinkage_alpha_min": float(alpha.min()) if alpha.size else None,
        "shrinkage_alpha_median": float(np.median(alpha)) if alpha.size else None,
        "shrinkage_alpha_p95": float(np.percentile(alpha, 95)) if alpha.size else None,
        "shrinkage_alpha_max": float(alpha.max()) if alpha.size else None,
        "shrinkage_alpha_n_columns": int(alpha.size),
        "retrieval": "v2 saturation-aware HITRAN k (operational migration; Sprint 6)",
        "nasa_k_baseline": "stage_a_outputs/%s/stage_a_report.nasa_k.json" % EVENT_ID,
        "notes": [
            "Operational retrieval migrated from NASA per-granule k to the independent "
            "v2 HITRAN2020/HAPI saturation-aware k. NASA-k baseline preserved alongside.",
        ],
    }
    (SA_DIR / "stage_a_report.json").write_text(json.dumps(stage_a_report, indent=2))
    log("Wrote stage_a_report.json (v2, provenance flipped)")

    # ---- Stage B: segment, quantify, RE-PROPAGATE uncertainty budget ----
    finite = np.isfinite(ours_ortho)
    bg_mask = finite & (~in_bbox)
    pixel_areas = quantification.pixel_areas_m2(lon_c, lat_c, PIXEL_SIZE_DEG, PIXEL_SIZE_DEG)
    n_air = quantification.n_air_mol_per_m3(p_pa, t_k)

    seg = segment_plume_varon(ours_ortho, bg_mask, p_value=0.05)
    plume_label = largest_component_in_region(
        seg.labels, lon_c, lat_c,
        PLUME_BBOX["min_lon"], PLUME_BBOX["max_lon"], PLUME_BBOX["min_lat"], PLUME_BBOX["max_lat"],
    )
    plume_mask = seg.labels == plume_label
    cc_rows, cc_cols = np.where(plume_mask)
    centroid_lat = float(np.mean(lat_c[cc_rows]))
    centroid_lon = float(np.mean(lon_c[cc_cols]))
    log(f"plume CC label={plume_label} px={int(plume_mask.sum())} "
        f"centroid=({centroid_lat:.4f} N, {centroid_lon:.4f} E)")

    # Wind UNCHANGED BY CONSTRUCTION — assert same ERA5 grid cell, then reuse.
    def era5_cell(lat: float, lon: float) -> tuple[float, float]:
        return (round(lat / 0.25) * 0.25, round(lon / 0.25) * 0.25)

    assert era5_cell(centroid_lat, centroid_lon) == (
        nasa_q["era5_grid_lat"], nasa_q["era5_grid_lon"]
    ), "v2 centroid left the NASA-k ERA5 grid cell — wind is NOT unchanged; re-fetch required"
    u10 = float(nasa_q["era5_u10_speed_ms"])
    u10_sigma = float(nasa_q["u10_sigma_ms"])

    result = quantification.quantify_plume(
        enh_ppm_m=ours_ortho, plume_mask=plume_mask, pixel_areas=pixel_areas,
        n_air_mol_m3=n_air, u10_ms=u10, u10_sigma_ms=u10_sigma,
    )

    # MEASURED MF-amplitude systematic: ours/NASA over the plume CC (computed, not 1.66).
    cc = plume_mask & np.isfinite(nasa_ortho)
    bias = float(np.mean(ours_ortho[cc]) / np.mean(nasa_ortho[cc]))
    q_nasa_cal = float(result.q_tonnes_per_hr / bias)
    log(f"Q(ours-cal)={result.q_tonnes_per_hr:.3f} t/hr  measured bias={bias:.4f}×  "
        f"Q(nasa-cal)={q_nasa_cal:.3f} t/hr")

    # Mask-sensitivity sweep on the NEW enhancement map.
    seg_qs: list[float] = []
    seg_counts: list[int] = []
    for p in SEG_P_VALUES:
        seg_alt = segment_plume_varon(ours_ortho, bg_mask, p_value=p)
        label_alt = largest_component_in_region(
            seg_alt.labels, lon_c, lat_c,
            PLUME_BBOX["min_lon"], PLUME_BBOX["max_lon"], PLUME_BBOX["min_lat"], PLUME_BBOX["max_lat"],
        )
        mask_alt = seg_alt.labels == label_alt
        if int(mask_alt.sum()) < 10:
            seg_qs.append(float("nan"))
            seg_counts.append(int(mask_alt.sum()))
            continue
        alt = quantification.quantify_plume(
            enh_ppm_m=ours_ortho, plume_mask=mask_alt, pixel_areas=pixel_areas,
            n_air_mol_m3=n_air, u10_ms=u10, u10_sigma_ms=u10_sigma,
        )
        seg_qs.append(float(alt.q_tonnes_per_hr))
        seg_counts.append(int(mask_alt.sum()))
    finite_qs = np.array([q for q in seg_qs if np.isfinite(q)])
    seg_spread_frac = (
        float((finite_qs.max() - finite_qs.min()) / result.q_tonnes_per_hr)
        if finite_qs.size >= 2 else 0.0
    )

    wind = result.wind_fractional_uncertainty
    sigma_mask_frac = seg_spread_frac / 2.0
    q_total_sigma = float(np.sqrt(wind.total ** 2 + sigma_mask_frac ** 2))
    q_low = q_nasa_cal * (1.0 - q_total_sigma)
    q_high = result.q_tonnes_per_hr * (1.0 + q_total_sigma)

    q_report = {
        "started_utc": t_start.isoformat(),
        "finished_utc": datetime.now(UTC).isoformat(),
        "plume_cc_label": int(plume_label),
        "plume_cc_pixel_count": int(plume_mask.sum()),
        "plume_cc_area_m2": float(result.plume_area_m2),
        "plume_cc_area_km2": float(result.plume_area_m2 / 1e6),
        "plume_length_m": float(result.plume_length_m),
        "plume_centroid_lon": centroid_lon,
        "plume_centroid_lat": centroid_lat,
        "surface_pressure_pa": p_pa,
        "surface_temperature_k": t_k,
        "n_air_mol_m3": float(n_air),
        "era5_u_ms": float(nasa_q["era5_u_ms"]),
        "era5_v_ms": float(nasa_q["era5_v_ms"]),
        "era5_u10_speed_ms": u10,
        "era5_grid_lat": float(nasa_q["era5_grid_lat"]),
        "era5_grid_lon": float(nasa_q["era5_grid_lon"]),
        "era5_nearest_hour_utc": nasa_q["era5_nearest_hour_utc"],
        "era5_hour_distance_h": float(nasa_q["era5_hour_distance_h"]),
        "era5_reuse_note": (
            "ERA5 wind carried from the NASA-k run: the v2 plume centroid falls in the "
            "same 0.25° ARCO-ERA5 grid cell, so the reanalysis wind is identical by "
            "construction (asserted in the runner). Wind terms are unchanged by the k swap."
        ),
        "u_eff_ms": float(result.u_eff_ms),
        "central_p_value": 0.05,
        "ime_central_kg": float(result.ime_kg),
        "q_central_kg_per_s": float(result.q_kg_per_s),
        "q_central_t_hr": float(result.q_tonnes_per_hr),
        "wind_fractional_alpha1": float(wind.alpha1_term),
        "wind_fractional_u10": float(wind.u10_term),
        "wind_fractional_total": float(wind.total),
        "u10_sigma_ms": u10_sigma,
        "enhancement_bias_factor": bias,
        "enhancement_bias_factor_source": (
            "INDEPENDENTLY MEASURED ours/NASA mean ratio over plume CC this run "
            "(v2 HITRAN k); not the NASA-k run's hand-carried 1.66×."
        ),
        "q_central_nasa_calibrated_t_hr": q_nasa_cal,
        "seg_sensitivity_p_values": list(SEG_P_VALUES),
        "seg_sensitivity_pixel_counts": seg_counts,
        "seg_sensitivity_q_t_hr": seg_qs,
        "seg_sensitivity_q_spread_fractional": seg_spread_frac,
        "q_total_fractional_sigma": q_total_sigma,
        "q_low_t_hr": float(q_low),
        "q_high_t_hr": float(q_high),
        "retrieval": "v2 saturation-aware HITRAN k (operational migration; Sprint 6)",
        "nasa_k_baseline": "stage_b_outputs/%s/q_estimate.nasa_k.json" % EVENT_ID,
        "notes": [],
    }
    (SB_DIR / "q_estimate.json").write_text(json.dumps(q_report, indent=2, default=str))
    (SB_DIR / "q_estimate_report.md").write_text(_stage_b_markdown(q_report))
    log("Wrote q_estimate.json + q_estimate_report.md (v2, budget re-propagated)")

    # ---- wind-location source S (recomputed offline from v2 enhancement) ----
    nasa_w = json.loads((SB_DIR / "wind_location_check.nasa_k.json").read_text())
    u = float(nasa_q["era5_u_ms"])
    v = float(nasa_q["era5_v_ms"])
    upwind_u, upwind_v = -u, -v
    mag = np.hypot(upwind_u, upwind_v)
    uu, uv = upwind_u / mag, upwind_v / mag
    cc_lats = lat_c[cc_rows]
    cc_lons = lon_c[cc_cols]
    lat_ref = centroid_lat
    cc_x = (cc_lons - centroid_lon) * 111319.49 * np.cos(np.radians(lat_ref))
    cc_y = (cc_lats - centroid_lat) * 111319.49
    proj = cc_x * uu + cc_y * uv
    thr = np.quantile(proj, 1.0 - TOP_FRACTION_FOR_SOURCE)
    top = proj >= thr
    source_lat = float(cc_lats[top].mean())
    source_lon = float(cc_lons[top].mean())
    dist_km = float(np.hypot(
        (source_lon - centroid_lon) * 111319.49 * np.cos(np.radians(lat_ref)),
        (source_lat - centroid_lat) * 111319.49,
    ) / 1000.0)

    # Source ERA5 wind: same-grid-cell reuse (assert), unchanged by construction.
    assert era5_cell(source_lat, source_lon) == (
        nasa_w["source_era5_grid_lat"], nasa_w["source_era5_grid_lon"]
    ), "v2 source S left the NASA-k source ERA5 grid cell — re-fetch required"
    src_u10 = float(nasa_w["source_u10_ms"])
    src_sigma = u10_sigma  # same hour_distance -> same sigma
    src_result = quantification.quantify_plume(
        enh_ppm_m=ours_ortho, plume_mask=plume_mask, pixel_areas=pixel_areas,
        n_air_mol_m3=n_air, u10_ms=src_u10, u10_sigma_ms=src_sigma,
    )
    delta_q = float(src_result.q_tonnes_per_hr - result.q_tonnes_per_hr)
    rel = abs(delta_q / result.q_tonnes_per_hr)
    wind_check = {
        "centroid_lat": centroid_lat,
        "centroid_lon": centroid_lon,
        "source_lat": source_lat,
        "source_lon": source_lon,
        "distance_km": dist_km,
        "n_top_pixels": int(top.sum()),
        "top_fraction_for_source": TOP_FRACTION_FOR_SOURCE,
        "centroid_u10_ms": u10,
        "source_u10_ms": src_u10,
        "delta_u10_ms": float(src_u10 - u10),
        "centroid_u_eff_ms": float(result.u_eff_ms),
        "source_u_eff_ms": float(src_result.u_eff_ms),
        "centroid_q_t_hr": float(result.q_tonnes_per_hr),
        "source_q_t_hr": float(src_result.q_tonnes_per_hr),
        "delta_q_t_hr": delta_q,
        "relative_delta_q": float(rel),
        "material_change": bool(rel >= 0.10),
        "material_threshold": 0.10,
        "centroid_era5_grid_lat": float(nasa_q["era5_grid_lat"]),
        "centroid_era5_grid_lon": float(nasa_q["era5_grid_lon"]),
        "source_era5_grid_lat": float(nasa_w["source_era5_grid_lat"]),
        "source_era5_grid_lon": float(nasa_w["source_era5_grid_lon"]),
        "era5_reuse_note": (
            "Source S recomputed from the v2 enhancement (offline geometry: top-5% "
            "upwind CC pixels). ERA5 wind at S carried from the NASA-k run — S stays in "
            "the same 0.25° grid cell (asserted), so the wind is identical by construction."
        ),
    }
    (SB_DIR / "wind_location_check.json").write_text(json.dumps(wind_check, indent=2))
    log(f"Wrote wind_location_check.json (v2): source=({source_lat:.5f} N, {source_lon:.5f} E) "
        f"dist={dist_km:.2f} km")

    log("\n===== operational migration summary (v2) =====")
    log(f"  Stage A Pearson bbox : {pearson_bbox:.4f}  (NASA-k {nasa_a['pearson_in_bbox']:.4f})")
    log(f"  Q ours-cal           : {result.q_tonnes_per_hr:.3f} t/hr  (NASA-k {nasa_q['q_central_t_hr']:.3f})")
    log(f"  Q nasa-cal           : {q_nasa_cal:.3f} t/hr  (NASA-k {nasa_q['q_central_nasa_calibrated_t_hr']:.3f})")
    log(f"  MF amplitude bias    : {bias:.4f}×  (NASA-k 1.66×, hand-carried)")
    log(f"  Q range              : [{q_low:.3f}, {q_high:.3f}] t/hr")
    return 0


def _stage_b_markdown(r: dict) -> str:
    rows = "\n".join(
        f"| {p} | {ct} | {q:.3f} |"
        for p, ct, q in zip(
            r["seg_sensitivity_p_values"], r["seg_sensitivity_pixel_counts"],
            r["seg_sensitivity_q_t_hr"], strict=True,
        )
    )
    return (
        f"# Stage B — Q for plume CC {r['plume_cc_label']} "
        f"(Goturdepe 2022-08-15 04:28:38 UTC) — v2 HITRAN k (operational)\n\n"
        f"## Headline\n"
        f"- **Q (central, ours-calibrated)**: {r['q_central_t_hr']:.2f} t/hr\n"
        f"- **Q (NASA-calibrated, IME / {r['enhancement_bias_factor']:.2f})**: "
        f"{r['q_central_nasa_calibrated_t_hr']:.2f} t/hr\n"
        f"- **Q range with all uncertainty**: [{r['q_low_t_hr']:.2f}, {r['q_high_t_hr']:.2f}] t/hr\n"
        f"- **Retrieval**: independent v2 saturation-aware HITRAN2020/HAPI k "
        f"(NASA per-granule target not used; shape cross-check r=0.993).\n"
        f"- **MF amplitude systematic**: independently measured {r['enhancement_bias_factor']:.2f}× "
        f"(ours/NASA over the plume CC) — reproduced from physics, not a NASA-convention artifact.\n"
        f"- **Scope**: ONE plume from a 12-source cluster. Thorpe 2023's 163 ± 18 t/hr is the "
        f"*cluster total*, NOT a same-scope reference.\n\n"
        f"## Geometry\n"
        f"- Plume CC label {r['plume_cc_label']}, {r['plume_cc_pixel_count']} px, "
        f"area {r['plume_cc_area_km2']:.2f} km², L=√A {r['plume_length_m'] / 1000:.2f} km\n"
        f"- Centroid: ({r['plume_centroid_lat']:.4f} N, {r['plume_centroid_lon']:.4f} E)\n\n"
        f"## Wind (unchanged by construction — same ERA5 grid cell)\n"
        f"- |U₁₀| = {r['era5_u10_speed_ms']:.2f} m/s, U_eff = {r['u_eff_ms']:.3f} m/s, "
        f"σ_U10 = {r['u10_sigma_ms']:.2f} m/s\n\n"
        f"## Uncertainty budget (RE-PROPAGATED for v2)\n"
        f"| Term | Fractional |\n|---|---|\n"
        f"| Wind α₁ | {r['wind_fractional_alpha1']:.3f} |\n"
        f"| Wind U₁₀ | {r['wind_fractional_u10']:.3f} |\n"
        f"| Wind combined | {r['wind_fractional_total']:.3f} |\n"
        f"| Plume-mask sensitivity (half-spread) | {r['seg_sensitivity_q_spread_fractional'] / 2:.3f} |\n"
        f"| **Symmetric combined** | **{r['q_total_fractional_sigma']:.3f}** |\n"
        f"| MF amplitude (measured, one-sided) | {r['enhancement_bias_factor']:.2f}× |\n\n"
        f"### Mask-sensitivity sweep\n| p | mask px | Q (t/hr) |\n|---|---|---|\n{rows}\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
