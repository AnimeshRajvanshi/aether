"""Sprint 6 Stage B: end-to-end Goturdepe re-run with our independent HITRAN k.

Swaps ONLY the source of k (NASA per-granule target -> our HITRAN-derived k) and
runs the Sprint 2 detection + quantification UNCHANGED. The absolute scaling is
resolved FORWARD from the physics of our own k, not reverse-fit to 27.1 t/hr:

  Our k is the Beer-Lambert linear unit absorption in 1/(ppm·m vertical column),
  already carrying the two-way air-mass factor and the ppm·m unit chain
  (k = -AMF * sigma * N_per_ppmm). The matched filter solves (x-μ) = α·(k⊙μ), so
  with k in 1/(ppm·m) the raw α is ALREADY in ppm·m vertical -> ppm_scaling = 1.0
  (NASA's k encodes k·Δc, needing their published 1e5; ours does not). This 1.0 is
  derived from the unit chain, NOT chosen to match any flux.

Reports whatever Pearson and Q fall out, plus the honest 1.66× calibration verdict.
Reuses the committed k-independent inputs (ERA5 wind, surface state) verbatim.

Run from the repo root:  uv run python scripts/run_hitran_k_stage_b.py
"""

from __future__ import annotations

# Imports follow warnings.filterwarnings() below (HAPI/GDAL emit noise); exempt E402.
# ruff: noqa: E402
import json
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import rioxarray
from aether_data_spine import emit_l1b, emit_l2a_mask
from aether_detection import matched_filter, quantification
from aether_detection.plume_segmentation import largest_component_in_region, segment_plume_varon

EVENT_ID = "turkmenistan_goturdepe_2022_08_15"
REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("~/.aether_cache").expanduser()
KDIR = REPO_ROOT / "stage_a_outputs" / EVENT_ID / "hitran_k"
OUT_DIR = KDIR  # Stage B artifacts live alongside the Stage A k
L2B_TIF = (
    CACHE
    / "emit_l2b_ch4"
    / "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003"
    / "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003.tif"
)

# Sprint 2 constants — replicated verbatim (the algorithm is unchanged).
PLUME_BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}
PIXEL_SIZE_DEG = 5.422325e-4
SPRINT2_BIAS_FACTOR = 1.66  # the NASA-k OURS/NASA over-amplitude from Sprint 2


def log(m: str) -> None:
    print(m, flush=True)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    q = json.loads((REPO_ROOT / "stage_b_outputs" / EVENT_ID / "q_estimate.json").read_text())
    kj = json.loads((KDIR / "hitran_k.json").read_text())
    our_k = np.asarray(kj["k"], dtype=np.float64)

    # ---- load L1B radiance + our k; run the MF with the FORWARD scale = 1.0 ----
    ds = emit_l1b.load_l1b_from_cache(sorted((CACHE / "emit_l1b").glob("*.zarr"))[0])
    radiance, wl, _ = emit_l1b.get_radiance_cube(ds)
    assert np.allclose(wl, kj["wavelengths_nm"], atol=0.05), "k grid != L1B grid"
    l2a = emit_l2a_mask.load_l2a_mask_from_cache(
        sorted((CACHE / "emit_l2a_mask").glob("*.zarr"))[0]
    )
    bad = emit_l2a_mask.build_bad_pixel_mask(l2a, use_aggregate=True)

    log("Running matched filter with our HITRAN k (ppm_scaling_factor=1.0)...")
    t0 = time.time()
    mf = matched_filter.run_matched_filter(
        radiance=radiance,
        wavelengths_nm=wl,
        unit_absorption_spectrum_k=our_k,
        bad_pixel_mask=bad,
        ppm_scaling_factor=1.0,  # FORWARD-derived: our k is already in 1/(ppm·m)
    )
    log(f"  MF done in {time.time() - t0:.1f}s; bands kept={mf.band_indices_kept.size}")

    # ---- orthorectify onto NASA's grid; Pearson vs NASA L2B (same as Sprint 2) ----
    ours_ortho = emit_l1b.orthorectify_raw_raster(
        mf.enhancement_ppm_m, np.asarray(ds["glt_x"].values), np.asarray(ds["glt_y"].values)
    )
    l2b = rioxarray.open_rasterio(L2B_TIF, masked=True).squeeze("band", drop=True)
    nasa_ortho = np.asarray(l2b.values, dtype=np.float64)
    transform = l2b.rio.transform()
    ny, nx = nasa_ortho.shape
    lon_c = np.array([transform.c + (i + 0.5) * transform.a for i in range(nx)])
    lat_c = np.array([transform.f + (i + 0.5) * transform.e for i in range(ny)])
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    in_bbox = (
        (lon_grid >= PLUME_BBOX["min_lon"])
        & (lon_grid <= PLUME_BBOX["max_lon"])
        & (lat_grid >= PLUME_BBOX["min_lat"])
        & (lat_grid <= PLUME_BBOX["max_lat"])
    )

    ok = np.isfinite(ours_ortho) & np.isfinite(nasa_ortho)
    pearson_full = float(np.corrcoef(ours_ortho[ok], nasa_ortho[ok])[0, 1])
    okb = ok & in_bbox
    pearson_bbox = float(np.corrcoef(ours_ortho[okb], nasa_ortho[okb])[0, 1])
    log(f"  Pearson full={pearson_full:.4f}  bbox={pearson_bbox:.4f}")

    np.savez_compressed(
        OUT_DIR / "ourk_enhancement_ortho.npz",
        enhancement_ppm_m=ours_ortho,
        ortho_lon_centers=lon_c,
        ortho_lat_centers=lat_c,
    )

    # ---- segment our enhancement (p<0.05), same Stage B procedure -> IME -> Q ----
    finite = np.isfinite(ours_ortho)
    bg_mask = finite & (~in_bbox)
    seg = segment_plume_varon(ours_ortho, bg_mask, p_value=0.05)
    label = largest_component_in_region(
        seg.labels,
        lon_c,
        lat_c,
        PLUME_BBOX["min_lon"],
        PLUME_BBOX["max_lon"],
        PLUME_BBOX["min_lat"],
        PLUME_BBOX["max_lat"],
    )
    plume_mask = seg.labels == label
    pixel_areas = quantification.pixel_areas_m2(lon_c, lat_c, PIXEL_SIZE_DEG, PIXEL_SIZE_DEG)
    n_air = quantification.n_air_mol_per_m3(
        float(q["surface_pressure_pa"]), float(q["surface_temperature_k"])
    )
    res = quantification.quantify_plume(
        enh_ppm_m=ours_ortho,
        plume_mask=plume_mask,
        pixel_areas=pixel_areas,
        n_air_mol_m3=n_air,
        u10_ms=float(q["era5_u10_speed_ms"]),
        u10_sigma_ms=float(q["u10_sigma_ms"]),
    )

    # ---- amplitude / 1.66× equivalent: our enhancement vs NASA L2B over the CC ----
    cc = plume_mask & np.isfinite(nasa_ortho)
    mean_ours = float(np.mean(ours_ortho[cc]))
    mean_nasa = float(np.mean(nasa_ortho[cc]))
    bias_vs_nasa = mean_ours / mean_nasa  # our-k OURS/NASA over-amplitude
    q_nasa_cal = float(res.q_tonnes_per_hr / bias_vs_nasa)

    log("\n================  STAGE B — our HITRAN k, forward scale = 1.0  ================")
    log(f"  Pearson vs NASA L2B (bbox):   {pearson_bbox:.4f}   (Sprint 2 NASA-k: 0.7485)")
    log(f"  plume CC pixels:              {int(plume_mask.sum())}   (Sprint 2: 68382)")
    log(f"  IME:                          {res.ime_kg / 1000:.3f} t")
    log(f"  Q (our-k, ours-cal):          {res.q_tonnes_per_hr:.3f} t/hr   (Sprint 2: 27.086)")
    log(f"  amplitude vs NASA L2B (CC):   {bias_vs_nasa:.3f}×   (Sprint 2: {SPRINT2_BIAS_FACTOR})")
    log(f"  Q (NASA-cal, our IME / bias): {q_nasa_cal:.3f} t/hr   (Sprint 2: 16.317)")

    report = {
        "event_id": EVENT_ID,
        "stage": "B — end-to-end with our HITRAN k (forward scale 1.0)",
        "ppm_scaling_factor_forward": 1.0,
        "scaling_chain": (
            "k in 1/(ppm·m vertical) = -AMF*sigma*N_per_ppmm; MF solves (x-μ)=α(k⊙μ) "
            "so raw α is already ppm·m vertical -> ppm_scaling=1.0 (not reverse-fit)."
        ),
        "pearson_full_scene": pearson_full,
        "pearson_in_bbox": pearson_bbox,
        "sprint2_pearson_in_bbox": 0.7485177591221628,
        "plume_cc_pixel_count": int(plume_mask.sum()),
        "ime_t": res.ime_kg / 1000.0,
        "q_ours_cal_t_hr": res.q_tonnes_per_hr,
        "sprint2_q_ours_cal_t_hr": 27.08605196493112,
        "amplitude_vs_nasa_l2b_over_cc": bias_vs_nasa,
        "sprint2_bias_factor": SPRINT2_BIAS_FACTOR,
        "q_nasa_cal_t_hr": q_nasa_cal,
        "sprint2_q_nasa_cal_t_hr": 16.31689877405489,
        "u_eff_ms": res.u_eff_ms,
        "mean_enh_ours_cc_ppm_m": mean_ours,
        "mean_enh_nasa_cc_ppm_m": mean_nasa,
    }
    (OUT_DIR / "hitran_k_stage_b_report.json").write_text(json.dumps(report, indent=2))
    log(f"\nWrote {(OUT_DIR / 'hitran_k_stage_b_report.json').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
