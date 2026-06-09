"""Sprint 6 v2: saturation-aware HITRAN k — Stage A shape + Stage B end-to-end.

Regenerates k with the finite-enhancement log-radiance regression (the fix for the
Stage B fidelity loss caused by the omitted line-core saturation), then re-runs
Goturdepe detection + quantification with it, algorithm unchanged. Same forward
scaling as before (ppm_scaling_factor = 1.0 — our k is in 1/(ppm·m); NOT reverse-fit
to 27.1 t/hr). NASA's file is a shape cross-check only, never an input.

Run from the repo root:  uv run python scripts/run_hitran_k_v2.py
"""

from __future__ import annotations

# Imports follow warnings.filterwarnings() / matplotlib.use(); exempt E402.
# ruff: noqa: E402
import json
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rioxarray
from aether_data_spine import emit_l1b, emit_l2a_mask
from aether_detection import hitran_k, matched_filter, quantification, target_signature
from aether_detection.constants import MF_SPECTRAL_WINDOWS_NM
from aether_detection.constants import (
    TURKMENISTAN_GOTURDEPE_2022_08_15_TARGET_FILENAME as TARGET_FILE,
)
from aether_detection.plume_segmentation import largest_component_in_region, segment_plume_varon
from aether_detection.target_signature import select_band_indices
from scipy.stats import spearmanr

EVENT_ID = "turkmenistan_goturdepe_2022_08_15"
REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("~/.aether_cache").expanduser()
OUT = REPO_ROOT / "stage_a_outputs" / EVENT_ID / "hitran_k"
L2B_TIF = (
    CACHE
    / "emit_l2b_ch4"
    / "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003"
    / "EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003.tif"
)
PLUME_BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}
PIXEL_SIZE_DEG = 5.422325e-4
C_MAX_PPM_M = 10000.0  # super-emitter enhancement range; documented, not NASA-tuned


def log(m: str) -> None:
    print(m, flush=True)


def _geometry(ds) -> tuple[float, float]:
    a = np.asarray(ds["obs_obs"].values, dtype=np.float64)
    a = np.moveaxis(a, int(np.argmin(a.shape)), -1)

    def mb(i: int) -> float:
        v = a[..., i].ravel()
        v = v[np.isfinite(v) & (v > -900)]
        return float(np.mean(v))

    return mb(4), mb(2)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    q = json.loads((REPO_ROOT / "stage_b_outputs" / EVENT_ID / "q_estimate.json").read_text())
    p_pa, t_k = float(q["surface_pressure_pa"]), float(q["surface_temperature_k"])

    ds = emit_l1b.load_l1b_from_cache(sorted((CACHE / "emit_l1b").glob("*.zarr"))[0])
    radiance, wl, fwhm = emit_l1b.get_radiance_cube(ds)
    sza, vza = _geometry(ds)
    log(f"geometry: SZA={sza:.2f} VZA={vza:.2f}; surface P={p_pa:.0f} T={t_k:.1f}")

    # ---- generate saturation-aware k ----
    res = hitran_k.generate_k_regression(
        wl, fwhm, solar_zenith_deg=sza, view_zenith_deg=vza,
        surface_pressure_pa=p_pa, surface_temperature_k=t_k, c_max_ppm_m=C_MAX_PPM_M,
    )
    our_k = res.k
    np.savetxt(
        OUT / "hitran_ch4_target_sat",
        np.column_stack([np.arange(wl.size), wl, our_k]),
        fmt=["%d", "%.6f", "%.8e"],
        header="index  wavelength_nm  k_per_ppm_m  (saturation-aware HITRAN; NASA NOT used)",
    )
    (OUT / "hitran_k_sat.json").write_text(
        json.dumps({"wavelengths_nm": wl.tolist(), "fwhm_nm": fwhm.tolist(), "k": our_k.tolist()})
    )
    np.savez(OUT / "hitran_k_sat.npz", wavelengths_nm=wl, fwhm_nm=fwhm, k=our_k)

    # ---- (a) Stage A: spectral SHAPE vs NASA target (cross-check only) ----
    _nasa_wl, nasa_k = target_signature.load_unit_absorption_spectrum(
        CACHE / "emit_targets" / TARGET_FILE
    )
    mf_bands = select_band_indices(wl, MF_SPECTRAL_WINDOWS_NM)
    r_shape = float(np.corrcoef(our_k[mf_bands], nasa_k[mf_bands])[0, 1])
    rho_shape = float(spearmanr(our_k[mf_bands], nasa_k[mf_bands]).statistic)
    log(f"\n(a) SHAPE vs NASA over {mf_bands.size} MF bands: Pearson r={r_shape:.4f} "
        f"rho={rho_shape:.4f}  (Stage A linear was 0.928)")

    def nrm(x):
        return x / np.max(np.abs(x))

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(wl[mf_bands], nrm(nasa_k[mf_bands]), "o-", color="#888", lw=1.4, ms=4,
            label="NASA target")
    ax.plot(wl[mf_bands], nrm(our_k[mf_bands]), "o-", color="#35d6c3", lw=1.4, ms=4,
            label="Ours · saturation-aware HITRAN")
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("normalized k")
    ax.set_title(f"v2 saturation-aware k vs NASA — shape r = {r_shape:.3f}")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "hitran_k_sat_vs_nasa.png", dpi=130)

    # ---- (b) Stage B: end-to-end MF with the new k, forward scale = 1.0 ----
    l2a = emit_l2a_mask.load_l2a_mask_from_cache(
        sorted((CACHE / "emit_l2a_mask").glob("*.zarr"))[0]
    )
    bad = emit_l2a_mask.build_bad_pixel_mask(l2a, use_aggregate=True)
    log("\nRunning MF with saturation-aware k (ppm_scaling_factor=1.0)...")
    t0 = time.time()
    mf = matched_filter.run_matched_filter(
        radiance=radiance, wavelengths_nm=wl, unit_absorption_spectrum_k=our_k,
        bad_pixel_mask=bad, ppm_scaling_factor=1.0,
    )
    log(f"  MF done in {time.time() - t0:.1f}s")
    ours_ortho = emit_l1b.orthorectify_raw_raster(
        mf.enhancement_ppm_m, np.asarray(ds["glt_x"].values), np.asarray(ds["glt_y"].values)
    )
    l2b = rioxarray.open_rasterio(L2B_TIF, masked=True).squeeze("band", drop=True)
    nasa_ortho = np.asarray(l2b.values, dtype=np.float64)
    tr = l2b.rio.transform()
    ny, nx = nasa_ortho.shape
    lon_c = np.array([tr.c + (i + 0.5) * tr.a for i in range(nx)])
    lat_c = np.array([tr.f + (i + 0.5) * tr.e for i in range(ny)])
    lg, ag = np.meshgrid(lon_c, lat_c)
    bb = (
        (lg >= PLUME_BBOX["min_lon"]) & (lg <= PLUME_BBOX["max_lon"])
        & (ag >= PLUME_BBOX["min_lat"]) & (ag <= PLUME_BBOX["max_lat"])
    )
    ok = np.isfinite(ours_ortho) & np.isfinite(nasa_ortho)
    pearson_full = float(np.corrcoef(ours_ortho[ok], nasa_ortho[ok])[0, 1])
    pearson_bbox = float(np.corrcoef(ours_ortho[ok & bb], nasa_ortho[ok & bb])[0, 1])
    log(f"(b) Pearson vs NASA L2B: full={pearson_full:.4f} bbox={pearson_bbox:.4f}  "
        f"(linear-k v1 was 0.5323; Sprint 2 NASA-k 0.7485)")
    np.savez_compressed(
        OUT / "ourk_sat_enhancement_ortho.npz",
        enhancement_ppm_m=ours_ortho, ortho_lon_centers=lon_c, ortho_lat_centers=lat_c,
    )

    # segment -> IME -> Q
    bg_mask = np.isfinite(ours_ortho) & (~bb)
    seg = segment_plume_varon(ours_ortho, bg_mask, p_value=0.05)
    label = largest_component_in_region(
        seg.labels, lon_c, lat_c,
        PLUME_BBOX["min_lon"], PLUME_BBOX["max_lon"], PLUME_BBOX["min_lat"], PLUME_BBOX["max_lat"],
    )
    pm = seg.labels == label
    areas = quantification.pixel_areas_m2(lon_c, lat_c, PIXEL_SIZE_DEG, PIXEL_SIZE_DEG)
    n_air = quantification.n_air_mol_per_m3(p_pa, t_k)
    qr = quantification.quantify_plume(
        enh_ppm_m=ours_ortho, plume_mask=pm, pixel_areas=areas, n_air_mol_m3=n_air,
        u10_ms=float(q["era5_u10_speed_ms"]), u10_sigma_ms=float(q["u10_sigma_ms"]),
    )
    cc = pm & np.isfinite(nasa_ortho)
    bias = float(np.mean(ours_ortho[cc]) / np.mean(nasa_ortho[cc]))
    q_nasa_cal = float(qr.q_tonnes_per_hr / bias)

    log("\n========  v2 saturation-aware k — Stage B  ========")
    log(f"  Pearson vs NASA L2B (bbox):  {pearson_bbox:.4f}  (v1 linear 0.5323; Sprint 2 0.7485)")
    log(f"  Q (ours-cal):                {qr.q_tonnes_per_hr:.3f} t/hr  (v1 11.87; Sprint 2 27.09)")
    log(f"  amplitude vs NASA L2B (CC):  {bias:.3f}×  (v1 0.79×; Sprint 2 1.66×)")
    log(f"  Q (NASA-cal):                {q_nasa_cal:.3f} t/hr  (Sprint 2 16.32)")

    report = {
        "event_id": EVENT_ID,
        "stage": "v2 saturation-aware k (finite-enhancement log-radiance regression)",
        "method": "single-point c=0 Jacobian -> multi-c regression; rest identical",
        "ppm_scaling_factor_forward": 1.0,
        "c_max_ppm_m": C_MAX_PPM_M,
        "shape_pearson_r_vs_nasa": r_shape,
        "shape_spearman_rho_vs_nasa": rho_shape,
        "stageA_linear_shape_r": 0.9282,
        "pearson_full_scene": pearson_full,
        "pearson_in_bbox": pearson_bbox,
        "v1_linear_pearson_in_bbox": 0.5322565294514309,
        "sprint2_pearson_in_bbox": 0.7485177591221628,
        "ime_t": qr.ime_kg / 1000.0,
        "q_ours_cal_t_hr": qr.q_tonnes_per_hr,
        "v1_linear_q_ours_cal_t_hr": 11.871919395525573,
        "sprint2_q_ours_cal_t_hr": 27.08605196493112,
        "amplitude_vs_nasa_l2b_over_cc": bias,
        "v1_linear_bias": 0.7891727516032657,
        "sprint2_bias_factor": 1.66,
        "q_nasa_cal_t_hr": q_nasa_cal,
        "sprint2_q_nasa_cal_t_hr": 16.31689877405489,
        "plume_cc_pixel_count": int(pm.sum()),
        **{f"prov_{k}": v for k, v in res.provenance.items()},
    }
    (OUT / "hitran_k_v2_report.json").write_text(json.dumps(report, indent=2))
    (OUT / "hitran_k_sat_provenance.json").write_text(
        json.dumps({**res.provenance, "shape_pearson_r_vs_nasa": r_shape}, indent=2)
    )

    # map comparison
    ci = np.where((lon_c >= 53.5) & (lon_c <= 54.2))[0]
    ri = np.where((lat_c >= 39.3) & (lat_c <= 39.7))[0]
    sl = (slice(ri.min(), ri.max() + 1), slice(ci.min(), ci.max() + 1))
    ext = [lon_c[ci.min()], lon_c[ci.max()], lat_c[ri.max()], lat_c[ri.min()]]
    vmax = float(np.nanpercentile(nasa_ortho[sl], 99))
    fig2, ax2 = plt.subplots(1, 2, figsize=(10, 4.0))
    for a, (d, t) in zip(
        ax2,
        [(nasa_ortho, "NASA L2B (reference)"),
         (ours_ortho, f"Ours · saturation-aware k (Pearson {pearson_bbox:.2f})")],
        strict=True,
    ):
        im = a.imshow(d[sl], extent=ext, origin="upper", cmap="inferno", vmin=0, vmax=vmax)
        a.set_title(t, fontsize=10)
    fig2.colorbar(im, ax=ax2, shrink=0.8, label="ppm·m")
    fig2.suptitle("Sprint 6 v2 — enhancement map vs NASA L2B (same scale)")
    fig2.savefig(OUT / "stage_b_map_comparison_v2.png", dpi=120, bbox_inches="tight")

    log(f"\nWrote {(OUT / 'hitran_k_v2_report.json').relative_to(REPO_ROOT)} + sat k artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
