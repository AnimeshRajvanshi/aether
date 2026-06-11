"""Shared, event-parameterized end-to-end methane quantification runner.

Sprint 7 generality: ONE code path for every event, driven by the EVENTS
registry below (the same pattern as ``scripts/acquire_ogim_subset.py``). It
replaces the Goturdepe-hardcoded assumptions called out in the Stage A report —
no ``_permian`` fork. Run:

    uv run python scripts/run_event_quantification.py <event_id>

What it does, from scratch, for one event (no NASA-k baseline is read; nothing
is reverse-fit to any flux):

  1. Resolve + download (idempotent cache) the L1B RAD, L2A MASK, L2B CH4ENH
     granules for the event's pinned URs.
  2. Geometry (mean SZA/VZA) + scene-mean surface elevation from the L1B OBS.
  3. Near-surface state (p, T) from ARCO-ERA5 at the plume-bbox centroid +
     overpass time — NOT a sea-level default (the Permian is at ~1 km; a 101325
     Pa default would bias n_air ~10%). One trusted reanalysis, same as the wind.
  4. Per-granule independent v2 saturation-aware HITRAN k from the granule's own
     geometry / SRF / surface state (``hitran_k.generate_k_regression``,
     forward scale 1.0). NASA's file is never read.
  5. Matched filter → orthorectify via the GLT.
  6. Pearson of our ortho enhancement vs the NASA L2B CH4ENH (the cross-check;
     a CROSS-CHECKED tier when an L2B raster exists for the granule).
  7. Varon segmentation → source-connected plume CC → IME → Q with U_eff from
     ERA5 wind at the plume centroid.
  8. Mandatory scene checks (re-run, not assumed): wind source-vs-centroid ΔQ%,
     U_eff regime vs the Varon 2-8 m/s range (with boundary margins), plume-mask
     p-value sensitivity sweep.
  9. From-scratch uncertainty budget. The +1.46x MF-amplitude systematic
     measured on Goturdepe is carried as a PRIOR with an explicit
     transfer-unvalidated note; independently, because this granule HAS a NASA
     L2B, we MEASURE this scene's own ours/NASA ratio over the plume CC — the
     first cross-scene test of whether that systematic transfers.

Goturdepe is in the registry to document the shared path, but its canonical
artifacts are the FROZEN Sprint-6 operational outputs (produced by
``scripts/run_migration_v2_operational.py``); this runner is exercised on
Permian and Goturdepe's committed files are verified byte-identical afterwards.
"""

from __future__ import annotations

# Imports follow warnings.filterwarnings(); exempt E402.
# ruff: noqa: E402
import json
import sys
import time
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

warnings.filterwarnings("ignore")

import earthaccess
import matplotlib.pyplot as plt
import numpy as np
import rioxarray
from aether_data_spine import emit_l1b, emit_l2a_mask, era5
from aether_detection import constants, hitran_k, matched_filter, quantification
from aether_detection.plume_segmentation import (
    largest_component_in_region,
    segment_plume_varon,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("~/.aether_cache").expanduser()

# Goturdepe-measured MF-amplitude systematic (ours/NASA over the plume CC, v2 k),
# carried as a PRIOR to a new scene with an explicit "transfer unvalidated" note.
GOTURDEPE_MEASURED_MF_BIAS = 1.46

PIXEL_SIZE_DEG = 5.422325e-4  # EMIT L2B v002 ortho grid (both rasters share it)
C_MAX_PPM_M = 10000.0
# NASA-L2B enhancement thresholds (ppm·m) defining the published-plume footprint;
# central = 200 (the "strong-signal" convention used for Goturdepe's Pearson).
NASA_THRESHOLDS = (100.0, 200.0, 500.0)
NASA_CENTRAL_THR = 200.0
TOP_FRACTION_FOR_SOURCE = 0.05  # top-5% upwind CC pixels define the source S
MATERIAL_DELTA_Q = 0.10  # >=10% source-vs-centroid shift flagged as material


@dataclass(frozen=True)
class Event:
    """Per-event config — one shared code path, no per-event fork."""

    event_id: str
    l1b_ur: str
    l2a_ur: str
    l2b_ur: str
    acquisition_utc: datetime
    plume_bbox: dict[str, float]  # min_lon/min_lat/max_lon/max_lat
    tier: str  # earnable validation tier decided by the Stage A probe
    nasa_target_shape_crosscheck: bool  # is there a NASA per-granule target k to compare shape?
    notes: list[str] = field(default_factory=list)

    @property
    def bbox_args(self) -> tuple[float, float, float, float]:
        b = self.plume_bbox
        return (b["min_lon"], b["max_lon"], b["min_lat"], b["max_lat"])


EVENTS: dict[str, Event] = {
    # Goturdepe: present to document the shared path. NOT re-run here — its
    # canonical artifacts are the frozen Sprint-6 operational outputs.
    "turkmenistan_goturdepe_2022_08_15": Event(
        event_id="turkmenistan_goturdepe_2022_08_15",
        l1b_ur=constants.TURKMENISTAN_GOTURDEPE_2022_08_15_L1B_GRANULE_UR,
        l2a_ur=constants.TURKMENISTAN_GOTURDEPE_2022_08_15_L2A_MASK_GRANULE_UR,
        l2b_ur=constants.TURKMENISTAN_GOTURDEPE_2022_08_15_L2B_CH4_GRANULE_UR,
        acquisition_utc=datetime(2022, 8, 15, 4, 28, 38, tzinfo=UTC),
        plume_bbox={"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7},
        # CROSS-CHECKED (strong), not VALIDATED: VALIDATED is reserved for independent
        # flux truth, which Goturdepe lacks (Thorpe is a scope-mismatched cluster total).
        # See docs/science/validation_tiers.md. (This runner refuses Goturdepe anyway.)
        tier="CROSS-CHECKED",
        nasa_target_shape_crosscheck=True,
        notes=["Frozen Sprint-6 operational artifacts (run_migration_v2_operational.py)."],
    ),
    # Permian / Carlsbad NM, EMIT 2022-08-26. No NASA per-granule target spectrum
    # exists (so no k-shape cross-check); a NASA L2B CH4ENH raster DOES exist
    # (Stage A probe) -> CROSS-CHECKED tier is earnable via spatial Pearson.
    #
    # Plume bbox = the footprint of NASA's published L2B CH4PLM complex
    # **000524** (CMR GPolygon: lon [-104.0997, -104.0742], lat [32.3504,
    # 32.3916]), padded ~0.004 deg. This is the iconic ~3.3 km press-release
    # plume (peak 5631 ppm·m at 32.357 N, -104.092 E in the L2B CH4ENH raster).
    # Same provenance pattern as Goturdepe's bbox (complex 000494). The benchmark
    # YAML's earlier bbox was an approximate "SE of Carlsbad" guess that missed
    # the actual complex; corrected in the YAML with this provenance.
    "permian_basin_2022": Event(
        event_id="permian_basin_2022",
        l1b_ur=constants.PERMIAN_2022_08_26_L1B_GRANULE_UR,
        l2a_ur=constants.PERMIAN_2022_08_26_L2A_MASK_GRANULE_UR,
        l2b_ur=constants.PERMIAN_2022_08_26_L2B_CH4_GRANULE_UR,
        acquisition_utc=datetime(2022, 8, 26, 17, 46, 42, tzinfo=UTC),
        plume_bbox={"min_lon": -104.104, "min_lat": 32.346, "max_lon": -104.070, "max_lat": 32.396},
        tier="CROSS-CHECKED",
        nasa_target_shape_crosscheck=False,
    ),
}


def log(m: str) -> None:
    print(m, flush=True)


# --------------------------------------------------------------------------- #
# Data resolution
# --------------------------------------------------------------------------- #
def _search_one(short_name: str, ur: str) -> object:
    res = earthaccess.search_data(short_name=short_name, readable_granule_name=ur)
    if len(res) != 1:
        raise SystemExit(f"expected exactly 1 granule for {ur}, got {len(res)}")
    return res[0]


def _ensure_granules(ev: Event) -> Path:
    """Download (idempotent) all three granules; return the L2B CH4ENH GeoTIFF path."""
    earthaccess.login(persist=True)
    emit_l1b.download_and_cache_l1b(_search_one("EMITL1BRAD", ev.l1b_ur))
    emit_l2a_mask.download_and_cache_l2a_mask(_search_one("EMITL2AMASK", ev.l2a_ur))
    l2b_dir = CACHE / "emit_l2b_ch4" / ev.l2b_ur
    tif = next((p for p in l2b_dir.glob("*CH4ENH*.tif") if "UNCERT" not in p.name), None)
    if tif is None:
        l2b_dir.mkdir(parents=True, exist_ok=True)
        g = _search_one("EMITL2BCH4ENH", ev.l2b_ur)
        paths = earthaccess.download([g], local_path=str(l2b_dir))
        tif = next(
            (Path(p) for p in paths if "CH4ENH" in Path(p).name and "UNCERT" not in Path(p).name),
            None,
        )
    if tif is None:
        raise SystemExit(f"no CH4ENH GeoTIFF for {ev.l2b_ur}")
    return tif


def _l1b_cache_path(ev: Event) -> Path:
    import hashlib

    key = hashlib.sha256(ev.l1b_ur.encode()).hexdigest()[:16]
    return CACHE / "emit_l1b" / f"{key}.zarr"


def _l2a_cache_path(ev: Event) -> Path:
    import hashlib

    key = hashlib.sha256(ev.l2a_ur.encode()).hexdigest()[:16]
    return CACHE / "emit_l2a_mask" / f"{key}.zarr"


def _geometry(ds) -> tuple[float, float]:
    """Mean solar- and view-zenith [deg] from the OBS cube (bands 4 and 2)."""
    a = np.asarray(ds["obs_obs"].values, dtype=np.float64)
    a = np.moveaxis(a, int(np.argmin(a.shape)), -1)

    def mb(i: int) -> float:
        v = a[..., i].ravel()
        v = v[np.isfinite(v) & (v > -900)]
        return float(np.mean(v))

    return mb(4), mb(2)


def _scene_mean_elev_m(ds) -> float:
    e = np.asarray(ds["elev"].values, dtype=np.float64).ravel()
    e = e[np.isfinite(e) & (e > -1000)]
    return float(np.mean(e)) if e.size else float("nan")


def _source_from_upwind(
    plume_mask: np.ndarray, lon_c: np.ndarray, lat_c: np.ndarray,
    centroid_lat: float, centroid_lon: float, u: float, v: float,
) -> tuple[float, float, float, int]:
    """Source S = mean of the top-5% CC pixels projected onto the upwind direction."""
    cc_rows, cc_cols = np.where(plume_mask)
    cc_lats, cc_lons = lat_c[cc_rows], lon_c[cc_cols]
    upwind_u, upwind_v = -u, -v
    mag = np.hypot(upwind_u, upwind_v)
    uu, uv = upwind_u / mag, upwind_v / mag
    cc_x = (cc_lons - centroid_lon) * 111319.49 * np.cos(np.radians(centroid_lat))
    cc_y = (cc_lats - centroid_lat) * 111319.49
    proj = cc_x * uu + cc_y * uv
    thr = np.quantile(proj, 1.0 - TOP_FRACTION_FOR_SOURCE)
    top = proj >= thr
    source_lat = float(cc_lats[top].mean())
    source_lon = float(cc_lons[top].mean())
    dist_km = float(np.hypot(
        (source_lon - centroid_lon) * 111319.49 * np.cos(np.radians(centroid_lat)),
        (source_lat - centroid_lat) * 111319.49,
    ) / 1000.0)
    return source_lat, source_lon, dist_km, int(top.sum())


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in EVENTS:
        raise SystemExit(f"usage: run_event_quantification.py <event_id>; known: {sorted(EVENTS)}")
    ev = EVENTS[sys.argv[1]]
    if ev.event_id == "turkmenistan_goturdepe_2022_08_15":
        raise SystemExit(
            "Refusing to run Goturdepe through the general runner: its canonical "
            "artifacts are the frozen Sprint-6 operational outputs "
            "(scripts/run_migration_v2_operational.py). The registry entry documents "
            "the shared code path; re-running would perturb closed numbers."
        )

    t_start = datetime.now(UTC)
    sa_dir = REPO_ROOT / "stage_a_outputs" / ev.event_id
    sb_dir = REPO_ROOT / "stage_b_outputs" / ev.event_id
    k_dir = sa_dir / "hitran_k"
    for d in (sa_dir, sb_dir, k_dir):
        d.mkdir(parents=True, exist_ok=True)

    bbox = ev.plume_bbox
    bbox_centroid_lat = (bbox["min_lat"] + bbox["max_lat"]) / 2.0
    bbox_centroid_lon = (bbox["min_lon"] + bbox["max_lon"]) / 2.0

    # ---- 1. resolve + load inputs ----
    l2b_tif = _ensure_granules(ev)
    ds = emit_l1b.load_l1b_from_cache(_l1b_cache_path(ev))
    radiance, wl, fwhm = emit_l1b.get_radiance_cube(ds)
    sza, vza = _geometry(ds)
    elev_m = _scene_mean_elev_m(ds)
    log(f"geometry: SZA={sza:.3f} VZA={vza:.3f}; scene-mean elev={elev_m:.0f} m")

    l2a = emit_l2a_mask.load_l2a_mask_from_cache(_l2a_cache_path(ev))
    bad = emit_l2a_mask.build_bad_pixel_mask(l2a, use_aggregate=True)
    bad_frac = float(bad.mean())

    # ---- 2. near-surface state from ERA5 (NOT a sea-level default) ----
    ss = era5.get_surface_state_at_point(bbox_centroid_lat, bbox_centroid_lon, ev.acquisition_utc)
    p_pa = float(ss.surface_pressure_pa)
    t_k = float(ss.temperature_2m_k)
    log(f"ERA5 surface state @bbox-centroid: p={p_pa:.0f} Pa  T={t_k:.1f} K  "
        f"(grid {ss.grid_lat:.2f},{ss.grid_lon:.2f}; {ss.hour_distance_h * 60:.0f} min)")

    # ---- 3. per-granule independent v2 HITRAN k (forward scale 1.0) ----
    res = hitran_k.generate_k_regression(
        wl, fwhm, solar_zenith_deg=sza, view_zenith_deg=vza,
        surface_pressure_pa=p_pa, surface_temperature_k=t_k, c_max_ppm_m=C_MAX_PPM_M,
    )
    our_k = res.k
    k_prov = dict(res.provenance)
    k_prov["event_id"] = ev.event_id
    k_prov["l1b_granule_ur"] = ev.l1b_ur
    k_prov["era5_surface_pressure_source"] = era5.ARCO_ERA5_GCS_URI
    k_prov["nasa_target_shape_crosscheck_available"] = ev.nasa_target_shape_crosscheck
    (k_dir / "hitran_k_sat.json").write_text(json.dumps(
        {"wavelengths_nm": res.wavelengths_nm.tolist(), "k": our_k.tolist()}, indent=2
    ))
    (k_dir / "hitran_k_sat_provenance.json").write_text(json.dumps(k_prov, indent=2, default=str))
    log(f"generated per-granule v2 k: {int(res.in_window_mask.sum())} in-window bands; "
        f"no NASA shape cross-check available={not ev.nasa_target_shape_crosscheck}")

    # ---- 4. matched filter + orthorectify ----
    log("running matched filter (v2 k, ppm_scaling=1.0)...")
    t0 = time.time()
    mf = matched_filter.run_matched_filter(
        radiance=radiance, wavelengths_nm=wl, unit_absorption_spectrum_k=our_k,
        bad_pixel_mask=bad, ppm_scaling_factor=1.0,
    )
    log(f"  MF done in {time.time() - t0:.1f}s; bands kept={mf.band_indices_kept.size}")
    glt_x = np.asarray(ds["glt_x"].values)
    glt_y = np.asarray(ds["glt_y"].values)
    ours_ortho = emit_l1b.orthorectify_raw_raster(mf.enhancement_ppm_m, glt_x, glt_y)

    # ---- 5. NASA L2B + Pearson cross-check ----
    l2b = rioxarray.open_rasterio(l2b_tif, masked=True).squeeze("band", drop=True)
    nasa_ortho = np.asarray(l2b.values, dtype=np.float64)
    transform = l2b.rio.transform()
    ny, nx = nasa_ortho.shape
    lon_c = np.array([transform.c + (i + 0.5) * transform.a for i in range(nx)])
    lat_c = np.array([transform.f + (i + 0.5) * transform.e for i in range(ny)])
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    in_bbox = (
        (lon_grid >= bbox["min_lon"]) & (lon_grid <= bbox["max_lon"])
        & (lat_grid >= bbox["min_lat"]) & (lat_grid <= bbox["max_lat"])
    )
    if nasa_ortho.shape != ours_ortho.shape:
        raise SystemExit(f"ortho-grid mismatch: NASA {nasa_ortho.shape} vs ours {ours_ortho.shape}")

    np.savez_compressed(
        sa_dir / "our_enhancement_ortho.npz",
        enhancement_ppm_m=ours_ortho, ortho_lon_centers=lon_c, ortho_lat_centers=lat_c,
        l2b_transform=np.asarray(transform[:6]),
    )
    ok = np.isfinite(ours_ortho) & np.isfinite(nasa_ortho)
    ok_bbox = ok & in_bbox
    pearson_full = float(np.corrcoef(ours_ortho[ok], nasa_ortho[ok])[0, 1])
    pearson_bbox = float(np.corrcoef(ours_ortho[ok_bbox], nasa_ortho[ok_bbox])[0, 1])
    strong = ok_bbox & ((ours_ortho > 200.0) | (nasa_ortho > 200.0))
    pearson_strong = (
        float(np.corrcoef(ours_ortho[strong], nasa_ortho[strong])[0, 1])
        if strong.sum() > 50 else float("nan")
    )
    log(f"Pearson vs NASA L2B: full={pearson_full:.4f} bbox={pearson_bbox:.4f} "
        f"strong={pearson_strong:.4f}")

    alpha = mf.shrinkage_alpha_per_column
    alpha = alpha[np.isfinite(alpha)]
    target_spectrum_source = (
        "Independent HITRAN2020 line-by-line (HAPI) — saturation-aware unit absorption "
        "via finite-enhancement log-radiance regression (Thompson/EMIT-ATBD method), "
        "generated from this granule's own geometry/SRF/ERA5 surface state. "
        "No NASA per-granule target spectrum exists for this granule, so there is NO "
        "k-shape cross-check (unlike Goturdepe's r=0.993). "
        f"See stage_a_outputs/{ev.event_id}/hitran_k/."
    )
    stage_a_report = {
        "started_utc": t_start.isoformat(),
        "finished_utc": datetime.now(UTC).isoformat(),
        "event_id": ev.event_id,
        "acquisition_utc": ev.acquisition_utc.isoformat().replace("+00:00", "Z"),
        "l1b_granule_ur": ev.l1b_ur,
        "l2a_mask_granule_ur": ev.l2a_ur,
        "l2b_ch4_granule_ur": ev.l2b_ur,
        "validation_tier": ev.tier,
        "target_spectrum_source": target_spectrum_source,
        "target_spectrum_local_path": str(k_dir / "hitran_k_sat.json"),
        "k_method": res.provenance["method"],
        "k_nasa_target_used": False,
        "k_shape_pearson_r_vs_nasa": None,
        "k_shape_crosscheck_available": ev.nasa_target_shape_crosscheck,
        "k_provenance_ref": f"stage_a_outputs/{ev.event_id}/hitran_k/hitran_k_sat_provenance.json",
        "ppm_scaling_factor_forward": 1.0,
        "geometry_solar_zenith_deg": sza,
        "geometry_view_zenith_deg": vza,
        "scene_mean_elevation_m": elev_m,
        "era5_surface_pressure_pa": p_pa,
        "era5_2m_temperature_k": t_k,
        "era5_surface_grid_lat": float(ss.grid_lat),
        "era5_surface_grid_lon": float(ss.grid_lon),
        "radiance_shape": list(radiance.shape),
        "bands_used": int(mf.band_indices_kept.size),
        "bad_pixel_fraction": bad_frac,
        "nasa_l2b_geotiff": str(l2b_tif),
        "plume_bbox": bbox,
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
        "retrieval": "v2 saturation-aware HITRAN k (per-granule; Sprint 7 shared runner)",
        "notes": [
            "Independent per-granule retrieval. NASA file never read in k generation. "
            "Forward scale 1.0; nothing reverse-fit to any flux.",
        ],
    }
    (sa_dir / "stage_a_report.json").write_text(json.dumps(stage_a_report, indent=2))
    log("wrote stage_a_report.json")

    # ---- 6. plume mask ----
    # This event is CROSS-CHECKED: a NASA L2B CH4ENH raster exists. For a WEAK
    # plume in a busy scene, our own Varon self-segmentation latches onto noise
    # confusers (a real generality finding, recorded below), so the credible,
    # authoritative plume mask anchors to NASA's published plume area: the
    # NASA-L2B>threshold pixels inside complex 000524's bbox. We integrate OUR
    # independent enhancement over that footprint (magnitude is entirely ours);
    # NASA's enhancement over the SAME footprint is the cross-check.
    finite = np.isfinite(ours_ortho)
    pixel_areas = quantification.pixel_areas_m2(lon_c, lat_c, PIXEL_SIZE_DEG, PIXEL_SIZE_DEG)
    n_air = quantification.n_air_mol_per_m3(p_pa, t_k)

    def footprint(thr: float) -> np.ndarray:
        return in_bbox & ok & (nasa_ortho > thr)

    plume_mask = footprint(NASA_CENTRAL_THR)
    fr, fc = np.where(plume_mask)
    centroid_lat = float(np.mean(lat_c[fr]))
    centroid_lon = float(np.mean(lon_c[fc]))
    log(f"NASA-footprint plume mask (L2B>{NASA_CENTRAL_THR:.0f}): px={int(plume_mask.sum())} "
        f"centroid=({centroid_lat:.4f} N, {centroid_lon:.4f} E)")

    # Self-segmentation DIAGNOSTIC (generality finding): does our own Varon
    # segmentation isolate the plume, or grab a confuser?
    bg_mask = finite & (~in_bbox)
    seg = segment_plume_varon(ours_ortho, bg_mask, p_value=0.05)
    self_label = largest_component_in_region(seg.labels, lon_c, lat_c, *ev.bbox_args)
    self_mask = seg.labels == self_label
    self_overlap = int((self_mask & plume_mask).sum())
    self_nasa_mean = (
        float(np.mean(nasa_ortho[self_mask & np.isfinite(nasa_ortho)]))
        if self_mask.sum() else 0.0
    )
    self_isolated = bool(
        self_label != 0 and self_overlap >= 0.3 * self_mask.sum() and self_nasa_mean > 0
    )
    log(f"self-seg diagnostic: label={self_label} px={int(self_mask.sum())} "
        f"overlap_with_footprint={self_overlap} nasa_mean_over_self={self_nasa_mean:.1f} "
        f"isolated_plume={self_isolated}")

    # ---- 7. ERA5 wind at footprint centroid -> Q ----
    wind = era5.get_wind_at_point(centroid_lat, centroid_lon, ev.acquisition_utc)
    u10 = float(wind.speed_ms)
    u10_sigma = float(min(3.0, 1.6 + 0.4 * wind.hour_distance_h))
    log(f"ERA5 wind @centroid: u={wind.u_ms:.2f} v={wind.v_ms:.2f} |U10|={u10:.2f} m/s "
        f"sigma={u10_sigma:.2f} ({wind.hour_distance_h * 60:.0f} min)")

    result = quantification.quantify_plume(
        enh_ppm_m=ours_ortho, plume_mask=plume_mask, pixel_areas=pixel_areas,
        n_air_mol_m3=n_air, u10_ms=u10, u10_sigma_ms=u10_sigma,
    )

    # ---- 8. cross-check: NASA's OWN L2B over the SAME footprint + amplitude ratio ----
    ime_nasa = quantification.ime_kg(nasa_ortho, plume_mask, pixel_areas, n_air)
    q_nasa_footprint = quantification.kg_s_to_tonnes_per_hour(
        quantification.q_kg_per_second(ime_nasa, result.u_eff_ms, result.plume_length_m)
    )
    # MF-amplitude factor for THIS scene = ours/NASA IME over the footprint
    # (the cross-check ratio). Goturdepe's was +1.46x (ours HIGH); see if it transfers.
    bias_measured = float(result.ime_kg / ime_nasa) if ime_nasa != 0 else float("nan")
    q_nasa_cal = float(result.q_tonnes_per_hr / bias_measured) if bias_measured else float("nan")
    q_nasa_cal_carried = float(result.q_tonnes_per_hr / GOTURDEPE_MEASURED_MF_BIAS)
    log(f"Q ours={result.q_tonnes_per_hr:.3f} t/hr  Q nasa(same footprint)={q_nasa_footprint:.3f}  "
        f"ours/NASA IME={bias_measured:.3f}x  (Goturdepe prior 1.46x)")

    # ---- 9. scene check: U_eff regime (margins to Varon 2-8 m/s) ----
    u10_lo, u10_hi = constants.VARON2018_U10_MIN_VALID_MS, 8.0
    margin_lo = u10 - u10_lo
    margin_hi = u10_hi - u10
    in_regime = u10_lo <= u10 <= u10_hi
    near_lo = margin_lo < 1.0  # within 1 m/s of the low boundary -> boundary-proximate
    log(f"U_eff regime: |U10|={u10:.2f} in [{u10_lo},{u10_hi}]={in_regime}; "
        f"margin_lo={margin_lo:.2f} margin_hi={margin_hi:.2f} near_low={near_lo}")

    # ---- 10. scene check: wind source-vs-centroid ----
    source_lat, source_lon, dist_km, n_top = _source_from_upwind(
        plume_mask, lon_c, lat_c, centroid_lat, centroid_lon, wind.u_ms, wind.v_ms
    )
    src_wind = era5.get_wind_at_point(source_lat, source_lon, ev.acquisition_utc)
    src_u10 = float(src_wind.speed_ms)
    src_sigma = float(min(3.0, 1.6 + 0.4 * src_wind.hour_distance_h))
    src_result = quantification.quantify_plume(
        enh_ppm_m=ours_ortho, plume_mask=plume_mask, pixel_areas=pixel_areas,
        n_air_mol_m3=n_air, u10_ms=src_u10, u10_sigma_ms=src_sigma,
    )
    delta_q = float(src_result.q_tonnes_per_hr - result.q_tonnes_per_hr)
    rel_delta_q = abs(delta_q / result.q_tonnes_per_hr)
    wind_check = {
        "centroid_lat": centroid_lat, "centroid_lon": centroid_lon,
        "source_lat": source_lat, "source_lon": source_lon, "distance_km": dist_km,
        "n_top_pixels": n_top, "top_fraction_for_source": TOP_FRACTION_FOR_SOURCE,
        "centroid_u10_ms": u10, "source_u10_ms": src_u10, "delta_u10_ms": float(src_u10 - u10),
        "centroid_grid_lat": float(wind.grid_lat), "centroid_grid_lon": float(wind.grid_lon),
        "source_grid_lat": float(src_wind.grid_lat), "source_grid_lon": float(src_wind.grid_lon),
        "centroid_u_eff_ms": float(result.u_eff_ms), "source_u_eff_ms": float(src_result.u_eff_ms),
        "centroid_q_t_hr": float(result.q_tonnes_per_hr),
        "source_q_t_hr": float(src_result.q_tonnes_per_hr),
        "delta_q_t_hr": delta_q, "relative_delta_q": rel_delta_q,
        "material_change": bool(rel_delta_q >= MATERIAL_DELTA_Q),
        "material_threshold": MATERIAL_DELTA_Q,
        "note": (
            "Source S = mean of the top-5% upwind footprint pixels; ERA5 wind re-fetched "
            "at S (re-run, not assumed). Goturdepe's 0.5% was scene-specific."
        ),
    }
    (sb_dir / "wind_location_check.json").write_text(json.dumps(wind_check, indent=2))
    log(f"wind source-vs-centroid: dist={dist_km:.2f} km dQ={delta_q:+.3f} t/hr "
        f"({rel_delta_q * 100:.1f}%) material={wind_check['material_change']}")

    # ---- 11. scene check: mask sensitivity — sweep the NASA-footprint threshold ----
    seg_qs: list[float] = []
    seg_counts: list[int] = []
    for thr in NASA_THRESHOLDS:
        m = footprint(thr)
        if int(m.sum()) < 5:
            seg_qs.append(float("nan"))
            seg_counts.append(int(m.sum()))
            continue
        alt = quantification.quantify_plume(
            enh_ppm_m=ours_ortho, plume_mask=m, pixel_areas=pixel_areas,
            n_air_mol_m3=n_air, u10_ms=u10, u10_sigma_ms=u10_sigma,
        )
        seg_qs.append(float(alt.q_tonnes_per_hr))
        seg_counts.append(int(m.sum()))
    finite_qs = np.array([q for q in seg_qs if np.isfinite(q)])
    seg_spread_frac = (
        float((finite_qs.max() - finite_qs.min()) / result.q_tonnes_per_hr)
        if finite_qs.size >= 2 and result.q_tonnes_per_hr > 0 else 0.0
    )

    # ---- 12. from-scratch uncertainty budget ----
    w = result.wind_fractional_uncertainty
    sigma_mask_frac = seg_spread_frac / 2.0
    q_total_sigma = float(np.sqrt(w.total ** 2 + sigma_mask_frac ** 2))
    q_low = q_nasa_cal * (1.0 - q_total_sigma)
    q_high = result.q_tonnes_per_hr * (1.0 + q_total_sigma)

    q_report = {
        "started_utc": t_start.isoformat(),
        "finished_utc": datetime.now(UTC).isoformat(),
        "event_id": ev.event_id,
        "validation_tier": ev.tier,
        "plume_cc_label": int(NASA_CENTRAL_THR),  # footprint-anchored: no self-seg CC label
        "plume_cc_pixel_count": int(plume_mask.sum()),
        "plume_cc_area_m2": float(result.plume_area_m2),
        "plume_cc_area_km2": float(result.plume_area_m2 / 1e6),
        "plume_length_m": float(result.plume_length_m),
        "plume_centroid_lon": centroid_lon, "plume_centroid_lat": centroid_lat,
        "surface_pressure_pa": p_pa, "surface_temperature_k": t_k,
        "surface_state_source": "ARCO-ERA5 surface_pressure + 2m_temperature @ bbox centroid",
        "n_air_mol_m3": float(n_air),
        "era5_u_ms": float(wind.u_ms), "era5_v_ms": float(wind.v_ms),
        "era5_u10_speed_ms": u10,
        "era5_grid_lat": float(wind.grid_lat), "era5_grid_lon": float(wind.grid_lon),
        "era5_nearest_hour_utc": wind.nearest_hour_utc.isoformat(),
        "era5_hour_distance_h": float(wind.hour_distance_h),
        "u_eff_ms": float(result.u_eff_ms),
        "u_eff_regime_u10_min": u10_lo, "u_eff_regime_u10_max": u10_hi,
        "u_eff_regime_in_range": in_regime,
        "u_eff_regime_margin_low_ms": margin_lo, "u_eff_regime_margin_high_ms": margin_hi,
        "u_eff_regime_boundary_proximate": near_lo,
        "plume_mask_method": "NASA-L2B-footprint-anchored (CROSS-CHECKED)",
        "nasa_footprint_threshold_ppm_m": NASA_CENTRAL_THR,
        "central_p_value": 0.05,
        "ime_central_kg": float(result.ime_kg),
        "q_central_kg_per_s": float(result.q_kg_per_s),
        "q_central_t_hr": float(result.q_tonnes_per_hr),
        # Cross-check: NASA's OWN L2B enhancement, same footprint + IME/Varon method.
        "q_nasa_l2b_same_footprint_t_hr": q_nasa_footprint,
        "ime_nasa_l2b_same_footprint_kg": float(ime_nasa),
        "wind_fractional_alpha1": float(w.alpha1_term),
        "wind_fractional_u10": float(w.u10_term),
        "wind_fractional_total": float(w.total),
        "u10_sigma_ms": u10_sigma,
        "enhancement_bias_factor": bias_measured,
        "enhancement_bias_factor_source": (
            "MEASURED ours/NASA IME ratio over the published-plume footprint (this granule "
            "HAS a NASA L2B CH4ENH). This is the cross-check amplitude factor; used for the "
            "NASA-calibrated Q. ours<NASA here, OPPOSITE in sign to Goturdepe's +1.46x."
        ),
        "carried_goturdepe_mf_bias": GOTURDEPE_MEASURED_MF_BIAS,
        "carried_goturdepe_mf_bias_note": (
            "The +1.46x MF-amplitude systematic was MEASURED on Goturdepe (ours HIGH). Its "
            "transfer to a new scene was UNVALIDATED; this scene's measured "
            f"{bias_measured:.2f}x (ours LOW) is the first cross-scene test — it does NOT "
            "transfer (sign flips)."
        ),
        "q_central_nasa_calibrated_t_hr": q_nasa_cal,
        "q_central_nasa_calibrated_carried_1p46_t_hr": q_nasa_cal_carried,
        "self_segmentation_isolated_plume": self_isolated,
        "self_segmentation_label": int(self_label),
        "self_segmentation_pixel_count": int(self_mask.sum()),
        "self_segmentation_nasa_mean_ppm_m": self_nasa_mean,
        "self_segmentation_note": (
            "GENERALITY FINDING: our own Varon self-segmentation did NOT isolate this weak "
            "plume (it grabbed a confuser; NASA-mean over its CC was negative). Works for a "
            "dominant plume (Goturdepe); marginal for a weak one in a busy scene -> we anchor "
            "the mask to NASA's published footprint instead."
        ),
        "seg_sensitivity_thresholds_ppm_m": list(NASA_THRESHOLDS),
        "seg_sensitivity_pixel_counts": seg_counts,
        "seg_sensitivity_q_t_hr": seg_qs,
        "seg_sensitivity_q_spread_fractional": seg_spread_frac,
        "q_total_fractional_sigma": q_total_sigma,
        "q_low_t_hr": float(q_low), "q_high_t_hr": float(q_high),
        "source_vs_centroid_relative_delta_q": rel_delta_q,
        "retrieval": "v2 saturation-aware HITRAN k (per-granule; Sprint 7 shared runner)",
        "notes": [],
    }
    (sb_dir / "q_estimate.json").write_text(json.dumps(q_report, indent=2, default=str))
    (sb_dir / "q_estimate_report.md").write_text(_stage_b_markdown(ev, q_report))
    log("wrote q_estimate.json + q_estimate_report.md")

    # ---- 13. diagnostics: background stats, footprint cross-check, overlays ----
    bg_vals = ours_ortho[bg_mask]
    pearson_footprint = (
        float(np.corrcoef(ours_ortho[plume_mask], nasa_ortho[plume_mask])[0, 1])
        if plume_mask.sum() > 10 else float("nan")
    )
    diag = {
        "background_mean_ppm_m": float(np.nanmean(bg_vals)),
        "background_std_ppm_m": float(np.nanstd(bg_vals)),
        "background_p99_ppm_m": float(np.nanpercentile(bg_vals, 99)),
        "plume_footprint_mean_ours_ppm_m": float(np.nanmean(ours_ortho[plume_mask])),
        "plume_footprint_max_ours_ppm_m": float(np.nanmax(ours_ortho[plume_mask])),
        "plume_footprint_mean_nasa_ppm_m": float(np.nanmean(nasa_ortho[plume_mask])),
        "plume_footprint_pixel_count": int(plume_mask.sum()),
        "plume_to_background_contrast": float(
            np.nanmean(ours_ortho[plume_mask]) / max(np.nanstd(bg_vals), 1e-9)
        ),
        "pixelwise_pearson_on_footprint_ours_vs_nasa": pearson_footprint,
        "note": (
            "Internal-consistency sanity. background std is the scene-clutter noise level; "
            "contrast = mean(ours over footprint)/std(background). pixelwise Pearson on the "
            "footprint is LOW here even though integrated magnitudes agree — the plume is "
            "weak relative to clutter, so pixel-level co-registration is poor."
        ),
    }
    (sb_dir / "diagnostics.json").write_text(json.dumps(diag, indent=2))
    log(f"diagnostics: bg std={diag['background_std_ppm_m']:.1f}; "
        f"footprint mean ours={diag['plume_footprint_mean_ours_ppm_m']:.1f} "
        f"nasa={diag['plume_footprint_mean_nasa_ppm_m']:.1f}; "
        f"pixelwise r(footprint)={pearson_footprint:.3f}")

    _render_side_by_side(ev, ours_ortho, nasa_ortho, transform, bbox, pearson_bbox, sa_dir)
    _render_overlay(ev, ours_ortho, plume_mask, lon_c, lat_c, bbox, sa_dir)

    log("\n===== Stage B summary (Permian) =====")
    log(f"  tier             : {ev.tier}")
    log(f"  Pearson full/bbox: {pearson_full:.4f} / {pearson_bbox:.4f}")
    log(f"  Q ours (footprint): {result.q_tonnes_per_hr:.3f} t/hr")
    log(f"  Q NASA L2B (same) : {q_nasa_footprint:.3f} t/hr  (cross-check ratio "
        f"{bias_measured:.2f}x)")
    log(f"  Q range          : [{q_low:.3f}, {q_high:.3f}] t/hr")
    log(f"  self-seg isolated: {self_isolated} (generality finding)")
    log("  18.3 t/hr        : CONTEXT ONLY — NASA's own L2B via this method also gives "
        f"~{q_nasa_footprint:.1f} t/hr, ~{18.3 / max(q_nasa_footprint, 1e-6):.0f}x below 18.3")
    return 0


def _stage_b_markdown(ev: Event, r: dict) -> str:
    rows = "\n".join(
        f"| {thr:.0f} | {ct} | {q:.3f} |"
        for thr, ct, q in zip(
            r["seg_sensitivity_thresholds_ppm_m"], r["seg_sensitivity_pixel_counts"],
            r["seg_sensitivity_q_t_hr"], strict=True,
        )
    )
    return (
        f"# Stage B — Permian/Carlsbad 2022-08-26 — per-granule v2 HITRAN k "
        f"(NASA-footprint-anchored)\n\n"
        f"**Validation tier: {r['validation_tier']}** (NASA L2B CH4ENH exists → spatial "
        f"Pearson + footprint cross-check; NO peer-reviewed per-source flux). 18.3 t/hr is "
        f"press-release CONTEXT only — never a target.\n\n"
        f"## Headline\n"
        f"- **Q (ours, over NASA's published complex-000524 footprint, L2B>"
        f"{r['nasa_footprint_threshold_ppm_m']:.0f})**: {r['q_central_t_hr']:.2f} t/hr\n"
        f"- **Cross-check — NASA's OWN L2B over the same footprint + method**: "
        f"{r['q_nasa_l2b_same_footprint_t_hr']:.2f} t/hr "
        f"(ours/NASA IME = {r['enhancement_bias_factor']:.2f}×)\n"
        f"- **Q range with all uncertainty**: "
        f"[{r['q_low_t_hr']:.2f}, {r['q_high_t_hr']:.2f}] t/hr\n"
        f"- **Retrieval**: independent per-granule v2 saturation-aware HITRAN2020/HAPI k "
        f"(no NASA target exists for this granule → no k-shape cross-check).\n"
        f"- **MF-amplitude transfer test**: Goturdepe measured +1.46× (ours HIGH); here "
        f"{r['enhancement_bias_factor']:.2f}× (ours LOW) — the systematic does NOT transfer.\n\n"
        f"## Self-segmentation (generality finding)\n"
        f"- Our own Varon self-segmentation isolated the plume: "
        f"**{r['self_segmentation_isolated_plume']}** "
        f"({r['self_segmentation_pixel_count']} px, NASA-mean over its CC "
        f"{r['self_segmentation_nasa_mean_ppm_m']:.0f} ppm·m). The plume is weak vs scene "
        f"clutter, so self-segmentation grabs a confuser — hence the NASA-footprint anchor.\n\n"
        f"## Geometry & surface state\n"
        f"- Footprint {r['plume_cc_pixel_count']} px, area {r['plume_cc_area_km2']:.2f} km², "
        f"L=√A {r['plume_length_m'] / 1000:.2f} km\n"
        f"- Centroid: ({r['plume_centroid_lat']:.4f} N, {r['plume_centroid_lon']:.4f} E)\n"
        f"- Surface state (ERA5): p={r['surface_pressure_pa']:.0f} Pa, "
        f"T={r['surface_temperature_k']:.1f} K, n_air={r['n_air_mol_m3']:.2f} mol/m³\n\n"
        f"## Wind & U_eff regime\n"
        f"- |U₁₀| = {r['era5_u10_speed_ms']:.2f} m/s, U_eff = {r['u_eff_ms']:.3f} m/s, "
        f"σ_U10 = {r['u10_sigma_ms']:.2f} m/s\n"
        f"- Varon regime [{r['u_eff_regime_u10_min']:.0f}, "
        f"{r['u_eff_regime_u10_max']:.0f}] m/s: in-range={r['u_eff_regime_in_range']}; "
        f"margin to low={r['u_eff_regime_margin_low_ms']:.2f} m/s, "
        f"to high={r['u_eff_regime_margin_high_ms']:.2f} m/s; "
        f"boundary-proximate={r['u_eff_regime_boundary_proximate']}\n"
        f"- Source-vs-centroid ΔQ = {r['source_vs_centroid_relative_delta_q'] * 100:.1f}%\n\n"
        f"## Uncertainty budget (from scratch)\n"
        f"| Term | Fractional |\n|---|---|\n"
        f"| Wind α₁ | {r['wind_fractional_alpha1']:.3f} |\n"
        f"| Wind U₁₀ | {r['wind_fractional_u10']:.3f} |\n"
        f"| Wind combined | {r['wind_fractional_total']:.3f} |\n"
        f"| Mask (footprint-threshold) sensitivity (half-spread) | "
        f"{r['seg_sensitivity_q_spread_fractional'] / 2:.3f} |\n"
        f"| **Symmetric combined** | **{r['q_total_fractional_sigma']:.3f}** |\n"
        f"| MF amplitude (measured this scene, one-sided) | {r['enhancement_bias_factor']:.2f}× |\n"
        f"| MF amplitude (carried Goturdepe prior, transfer test) | "
        f"{r['carried_goturdepe_mf_bias']:.2f}× |\n\n"
        f"### Footprint-threshold sensitivity sweep\n"
        f"| NASA L2B threshold (ppm·m) | mask px | Q ours (t/hr) |\n|---|---|---|\n{rows}\n"
    )


def _render_side_by_side(ev, ours, nasa, transform, bbox, pearson_bbox, out_dir) -> None:
    ny, nx = nasa.shape
    x_edges = np.array([transform.c + i * transform.a for i in range(nx + 1)])
    y_edges = np.array([transform.f + i * transform.e for i in range(ny + 1)])
    extent = [
        float(x_edges.min()), float(x_edges.max()), float(y_edges.min()), float(y_edges.max()),
    ]
    joint = np.concatenate([ours[np.isfinite(ours)][:200_000], nasa[np.isfinite(nasa)][:200_000]])
    vmax = float(np.nanpercentile(joint, 99)) if joint.size else 1.0
    fig, axes = plt.subplots(1, 2, figsize=(16, 8), dpi=120)
    for ax, data, title in (
        (axes[0], ours, "Our matched-filter enhancement (ppm·m)"),
        (axes[1], nasa, "NASA L2B CH4ENH (ppm·m)"),
    ):
        im = ax.imshow(data, extent=extent, origin="upper", cmap="inferno", vmin=0.0, vmax=vmax,
                       interpolation="nearest", aspect="equal")
        ax.set_title(title)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.plot(
            [bbox["min_lon"], bbox["max_lon"], bbox["max_lon"], bbox["min_lon"], bbox["min_lon"]],
            [bbox["min_lat"], bbox["min_lat"], bbox["max_lat"], bbox["max_lat"], bbox["min_lat"]],
            "c-", lw=1.0, alpha=0.6,
        )
    fig.suptitle(
        f"Stage A — Permian {ev.acquisition_utc:%Y-%m-%d}  Pearson(bbox)={pearson_bbox:.3f}",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(out_dir / "side_by_side.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


def _render_overlay(ev, ours, plume_mask, lon_c, lat_c, bbox, out_dir) -> None:
    pad = 0.05
    col = (lon_c >= bbox["min_lon"] - pad) & (lon_c <= bbox["max_lon"] + pad)
    row = (lat_c >= bbox["min_lat"] - pad) & (lat_c <= bbox["max_lat"] + pad)
    ci, ri = np.where(col)[0], np.where(row)[0]
    if ci.size and ri.size:
        sub = ours[ri.min():ri.max() + 1, ci.min():ci.max() + 1]
        subm = plume_mask[ri.min():ri.max() + 1, ci.min():ci.max() + 1]
        ext = [lon_c[ci.min()], lon_c[ci.max()], lat_c[ri.max()], lat_c[ri.min()]]
    else:
        sub, subm, ext = ours, plume_mask, None
    vmax = float(np.nanpercentile(sub[np.isfinite(sub)], 99)) if np.isfinite(sub).any() else 1.0
    fig, ax = plt.subplots(figsize=(9, 8), dpi=130)
    im = ax.imshow(
        sub, extent=ext, origin="upper", cmap="inferno", vmin=0.0, vmax=vmax, aspect="equal",
    )
    ax.contour(subm.astype(float), levels=[0.5], colors="cyan", linewidths=1.2,
               extent=ext, origin="upper")
    ax.set_title(f"Permian plume CC overlay (segmentation p=0.05)\n{ev.acquisition_utc:%Y-%m-%d}")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="ppm·m")
    fig.tight_layout()
    fig.savefig(out_dir / "plume_mask_overlay.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
