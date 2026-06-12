"""The real EMIT pipeline as an eval pipeline (ADR 0002).

Re-runs each event's canonical recipe — per-granule HITRAN k → matched filter →
orthorectification → plume mask → IME → Q — **end-to-end from cached inputs,
entirely in memory**. It writes nothing into `stage_a_outputs/`,
`stage_b_outputs/`, or anywhere else in the repo: the committed artifacts are
the comparison target of the REGRESSION family and must stay byte-identical.

Per-event recipes mirror the frozen scripts that produced the committed
artifacts (the scripts remain the historical record; this module is the living
re-verification — if they drift, the regression checks catch it):

* Goturdepe — `scripts/run_migration_v2_operational.py` (Sprint 6 operational):
  fully OFFLINE. Surface p/T and ERA5 winds are carried from the committed
  NASA-k baseline with the same 0.25° grid-cell-identity assertion; Varon
  self-segmentation (p=0.05), largest CC in the plume bbox.
* Permian — `scripts/run_event_quantification.py` (Sprint 7 shared runner):
  cached granules + LIVE ARCO-ERA5 (surface state at the plume-bbox centroid,
  wind at the mask centroid); NASA-footprint-anchored mask (L2B > 200 ppm·m in
  the complex-000524 bbox). This is why the full eval run is network-gated.

Runnability is decided from the benchmark data itself: an event with no pinned
`canonical_acquisition` cannot be observed by an EMIT pipeline and is reported
`not_runnable` with the stated reason (e.g. Aliso Canyon 2015 predates EMIT's
July 2022 launch). Never silently dropped, never faked.

Heavy scientific imports are deferred into the recipe bodies so the harness
(and its CI-safe logic tests) import cleanly without touching the scientific
stack.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aether_ontology import Detection, DetectionType, PhenomenonType, Point, Provenance

from aether_eval.pipelines import _granule_observation_uuid
from aether_eval.runner import EventNotRunnable, PipelineOutput
from aether_eval.schema import BenchmarkEvent

PIPELINE_NAME = "aether-real-emit-pipeline"
PIPELINE_VERSION = "0.1.0"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CACHE = Path("~/.aether_cache").expanduser()

# EMIT launched to the ISS on 2022-07-14 (SpaceX CRS-25); no data exists before.
_EMIT_LAUNCH = datetime(2022, 7, 14, tzinfo=UTC)

# Recipe constants — mirror the frozen scripts (see module docstring).
_PIXEL_SIZE_DEG = 5.422325e-4  # EMIT L2B v002 ortho grid
_C_MAX_PPM_M = 10000.0
_GOTURDEPE_PLUME_BBOX = {"min_lon": 53.5, "min_lat": 39.3, "max_lon": 54.2, "max_lat": 39.7}
_GOTURDEPE_SEG_P_VALUES = (0.01, 0.05, 0.10)
_PERMIAN_NASA_THRESHOLDS = (100.0, 200.0, 500.0)
_PERMIAN_NASA_CENTRAL_THR = 200.0

_GOTURDEPE_ID = "turkmenistan_goturdepe_2022_08_15"
_PERMIAN_ID = "permian_basin_2022"


def _l1b_zarr(ur: str) -> Path:
    return _CACHE / "emit_l1b" / f"{hashlib.sha256(ur.encode()).hexdigest()[:16]}.zarr"


def _l2a_zarr(ur: str) -> Path:
    return _CACHE / "emit_l2a_mask" / f"{hashlib.sha256(ur.encode()).hexdigest()[:16]}.zarr"


def _l2b_tif(ur: str) -> Path:
    d = _CACHE / "emit_l2b_ch4" / ur
    tif = next((p for p in d.glob("*CH4ENH*.tif") if "UNCERT" not in p.name), None)
    if tif is None:
        raise RuntimeError(
            f"NASA L2B CH4ENH GeoTIFF for {ur} not in the local cache ({d}). "
            "Populate it once with the acquisition scripts (see docs/science/"
            "eval_semantics.md); the eval never downloads granules itself."
        )
    return tif


def _require_cache(event: BenchmarkEvent) -> tuple[Path, Path, Path]:
    """Resolve the three cached inputs, with actionable errors if missing."""
    acq = event.canonical_acquisition
    assert acq is not None  # guarded by the runnability check
    if not (acq.l1b_granule_ur and acq.l2a_mask_granule_ur and acq.l2b_ch4_granule_ur):
        raise EventNotRunnable(
            "canonical acquisition does not pin all three granule URs (L1B/L2A/L2B) "
            "— the real pipeline cannot run without them"
        )
    l1b = _l1b_zarr(acq.l1b_granule_ur)
    l2a = _l2a_zarr(acq.l2a_mask_granule_ur)
    for path, what in ((l1b, "L1B radiance"), (l2a, "L2A mask")):
        if not path.exists():
            raise RuntimeError(
                f"cached {what} zarr for {event.event_id} not found at {path}. "
                "Populate the cache once with the acquisition scripts; the eval "
                "never downloads granules itself."
            )
    return l1b, l2a, _l2b_tif(acq.l2b_ch4_granule_ur)


def _ortho_and_pearson(
    ds: Any, our_k: Any, bad: Any, l2b_tif: Path, plume_bbox: dict[str, float]
) -> dict[str, Any]:
    """Matched filter → GLT ortho → Pearson vs NASA L2B. Shared by both recipes."""
    import numpy as np
    import rioxarray
    from aether_data_spine import emit_l1b
    from aether_detection import matched_filter

    radiance, wl, _fwhm = emit_l1b.get_radiance_cube(ds)
    mf = matched_filter.run_matched_filter(
        radiance=radiance, wavelengths_nm=wl, unit_absorption_spectrum_k=our_k,
        bad_pixel_mask=bad, ppm_scaling_factor=1.0,
    )
    glt_x = np.asarray(ds["glt_x"].values)
    glt_y = np.asarray(ds["glt_y"].values)
    ours_ortho = emit_l1b.orthorectify_raw_raster(mf.enhancement_ppm_m, glt_x, glt_y)

    l2b = rioxarray.open_rasterio(l2b_tif, masked=True).squeeze("band", drop=True)
    nasa_ortho = np.asarray(l2b.values, dtype=np.float64)
    transform = l2b.rio.transform()
    ny, nx = nasa_ortho.shape
    lon_c = np.array([transform.c + (i + 0.5) * transform.a for i in range(nx)])
    lat_c = np.array([transform.f + (i + 0.5) * transform.e for i in range(ny)])
    lon_grid, lat_grid = np.meshgrid(lon_c, lat_c)
    in_bbox = (
        (lon_grid >= plume_bbox["min_lon"]) & (lon_grid <= plume_bbox["max_lon"])
        & (lat_grid >= plume_bbox["min_lat"]) & (lat_grid <= plume_bbox["max_lat"])
    )
    if nasa_ortho.shape != ours_ortho.shape:
        raise RuntimeError(
            f"ortho-grid mismatch: NASA {nasa_ortho.shape} vs ours {ours_ortho.shape}"
        )
    ok = np.isfinite(ours_ortho) & np.isfinite(nasa_ortho)
    ok_bbox = ok & in_bbox
    return {
        "ours_ortho": ours_ortho,
        "nasa_ortho": nasa_ortho,
        "lon_c": lon_c,
        "lat_c": lat_c,
        "in_bbox": in_bbox,
        "ok": ok,
        "pearson_full_scene": float(np.corrcoef(ours_ortho[ok], nasa_ortho[ok])[0, 1]),
        "pearson_in_bbox": float(np.corrcoef(ours_ortho[ok_bbox], nasa_ortho[ok_bbox])[0, 1]),
    }


def _geometry(ds: Any) -> tuple[float, float]:
    """Mean solar- and view-zenith [deg] from the OBS cube (bands 4 and 2)."""
    import numpy as np

    a = np.asarray(ds["obs_obs"].values, dtype=np.float64)
    a = np.moveaxis(a, int(np.argmin(a.shape)), -1)

    def mb(i: int) -> float:
        v = a[..., i].ravel()
        v = v[np.isfinite(v) & (v > -900)]
        return float(np.mean(v))

    return mb(4), mb(2)


def _era5_cell(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat / 0.25) * 0.25, round(lon / 0.25) * 0.25)


def _run_goturdepe(event: BenchmarkEvent) -> dict[str, Any]:
    """Mirror of the frozen Sprint-6 operational recipe. Fully offline."""
    import numpy as np
    from aether_data_spine import emit_l1b, emit_l2a_mask
    from aether_detection import hitran_k, quantification
    from aether_detection.plume_segmentation import (
        largest_component_in_region,
        segment_plume_varon,
    )

    l1b_path, l2a_path, l2b_tif = _require_cache(event)
    sb_dir = _REPO_ROOT / "stage_b_outputs" / event.event_id

    # Surface p/T and ERA5 wind come from the committed NASA-k baseline, exactly
    # as the frozen recipe does (wind unchanged by construction, asserted below).
    nasa_q = json.loads((sb_dir / "q_estimate.nasa_k.json").read_text())
    p_pa = float(nasa_q["surface_pressure_pa"])
    t_k = float(nasa_q["surface_temperature_k"])

    ds = emit_l1b.load_l1b_from_cache(l1b_path)
    _radiance, wl, fwhm = emit_l1b.get_radiance_cube(ds)
    sza, vza = _geometry(ds)
    l2a = emit_l2a_mask.load_l2a_mask_from_cache(l2a_path)
    bad = emit_l2a_mask.build_bad_pixel_mask(l2a, use_aggregate=True)

    res = hitran_k.generate_k_regression(
        wl, fwhm, solar_zenith_deg=sza, view_zenith_deg=vza,
        surface_pressure_pa=p_pa, surface_temperature_k=t_k, c_max_ppm_m=_C_MAX_PPM_M,
    )
    bbox = _GOTURDEPE_PLUME_BBOX
    ctx = _ortho_and_pearson(ds, res.k, bad, l2b_tif, bbox)
    ours, nasa = ctx["ours_ortho"], ctx["nasa_ortho"]
    lon_c, lat_c = ctx["lon_c"], ctx["lat_c"]
    bbox_args = (bbox["min_lon"], bbox["max_lon"], bbox["min_lat"], bbox["max_lat"])

    finite = np.isfinite(ours)
    bg_mask = finite & (~ctx["in_bbox"])
    pixel_areas = quantification.pixel_areas_m2(lon_c, lat_c, _PIXEL_SIZE_DEG, _PIXEL_SIZE_DEG)
    n_air = quantification.n_air_mol_per_m3(p_pa, t_k)

    seg = segment_plume_varon(ours, bg_mask, p_value=0.05)
    label = largest_component_in_region(seg.labels, lon_c, lat_c, *bbox_args)
    plume_mask = seg.labels == label
    rr, cc = np.where(plume_mask)
    centroid_lat = float(np.mean(lat_c[rr]))
    centroid_lon = float(np.mean(lon_c[cc]))

    if _era5_cell(centroid_lat, centroid_lon) != (
        nasa_q["era5_grid_lat"], nasa_q["era5_grid_lon"]
    ):
        raise RuntimeError(
            "fresh plume centroid left the committed ERA5 grid cell — the offline "
            "wind-reuse assumption no longer holds; this is a regression in itself"
        )
    u10 = float(nasa_q["era5_u10_speed_ms"])
    u10_sigma = float(nasa_q["u10_sigma_ms"])

    result = quantification.quantify_plume(
        enh_ppm_m=ours, plume_mask=plume_mask, pixel_areas=pixel_areas,
        n_air_mol_m3=n_air, u10_ms=u10, u10_sigma_ms=u10_sigma,
    )
    cc_finite = plume_mask & np.isfinite(nasa)
    bias = float(np.mean(ours[cc_finite]) / np.mean(nasa[cc_finite]))
    q_nasa_cal = float(result.q_tonnes_per_hr / bias)

    # Mask-sensitivity sweep (same p-values as the frozen recipe) for the budget.
    seg_qs: list[float] = []
    for p in _GOTURDEPE_SEG_P_VALUES:
        seg_alt = segment_plume_varon(ours, bg_mask, p_value=p)
        label_alt = largest_component_in_region(seg_alt.labels, lon_c, lat_c, *bbox_args)
        mask_alt = seg_alt.labels == label_alt
        if int(mask_alt.sum()) < 10:
            continue
        alt = quantification.quantify_plume(
            enh_ppm_m=ours, plume_mask=mask_alt, pixel_areas=pixel_areas,
            n_air_mol_m3=n_air, u10_ms=u10, u10_sigma_ms=u10_sigma,
        )
        seg_qs.append(float(alt.q_tonnes_per_hr))
    spread = (max(seg_qs) - min(seg_qs)) / result.q_tonnes_per_hr if len(seg_qs) >= 2 else 0.0
    sigma_total = float(np.sqrt(result.wind_fractional_uncertainty.total ** 2 + (spread / 2) ** 2))

    return {
        "q_central_t_hr": float(result.q_tonnes_per_hr),
        "q_central_nasa_calibrated_t_hr": q_nasa_cal,
        "pearson_full_scene": ctx["pearson_full_scene"],
        "pearson_in_bbox": ctx["pearson_in_bbox"],
        "centroid_lat": centroid_lat,
        "centroid_lon": centroid_lon,
        "ime_kg": float(result.ime_kg),
        "plume_area_km2": float(result.plume_area_m2 / 1e6),
        "q_total_fractional_sigma": sigma_total,
    }


def _run_permian(event: BenchmarkEvent) -> dict[str, Any]:
    """Mirror of the Sprint-7 shared runner recipe. Needs ARCO-ERA5 network."""
    import numpy as np
    from aether_data_spine import emit_l1b, emit_l2a_mask, era5
    from aether_detection import hitran_k, quantification

    acq = event.canonical_acquisition
    assert acq is not None
    l1b_path, l2a_path, l2b_tif = _require_cache(event)
    acq_utc = acq.utc if acq.utc.tzinfo else acq.utc.replace(tzinfo=UTC)

    # Permian's plume bbox IS the benchmark bbox (pinned to NASA complex 000524).
    bbox = {
        "min_lon": event.bbox.min_lon, "min_lat": event.bbox.min_lat,
        "max_lon": event.bbox.max_lon, "max_lat": event.bbox.max_lat,
    }
    ss = era5.get_surface_state_at_point(
        (bbox["min_lat"] + bbox["max_lat"]) / 2.0,
        (bbox["min_lon"] + bbox["max_lon"]) / 2.0,
        acq_utc,
    )
    p_pa = float(ss.surface_pressure_pa)
    t_k = float(ss.temperature_2m_k)

    ds = emit_l1b.load_l1b_from_cache(l1b_path)
    _radiance, wl, fwhm = emit_l1b.get_radiance_cube(ds)
    sza, vza = _geometry(ds)
    l2a = emit_l2a_mask.load_l2a_mask_from_cache(l2a_path)
    bad = emit_l2a_mask.build_bad_pixel_mask(l2a, use_aggregate=True)

    res = hitran_k.generate_k_regression(
        wl, fwhm, solar_zenith_deg=sza, view_zenith_deg=vza,
        surface_pressure_pa=p_pa, surface_temperature_k=t_k, c_max_ppm_m=_C_MAX_PPM_M,
    )
    ctx = _ortho_and_pearson(ds, res.k, bad, l2b_tif, bbox)
    ours, nasa = ctx["ours_ortho"], ctx["nasa_ortho"]
    lon_c, lat_c = ctx["lon_c"], ctx["lat_c"]
    in_bbox, ok = ctx["in_bbox"], ctx["ok"]

    pixel_areas = quantification.pixel_areas_m2(lon_c, lat_c, _PIXEL_SIZE_DEG, _PIXEL_SIZE_DEG)
    n_air = quantification.n_air_mol_per_m3(p_pa, t_k)

    def footprint(thr: float) -> Any:
        return in_bbox & ok & (nasa > thr)

    plume_mask = footprint(_PERMIAN_NASA_CENTRAL_THR)
    rr, cc = np.where(plume_mask)
    centroid_lat = float(np.mean(lat_c[rr]))
    centroid_lon = float(np.mean(lon_c[cc]))

    wind = era5.get_wind_at_point(centroid_lat, centroid_lon, acq_utc)
    u10 = float(wind.speed_ms)
    u10_sigma = float(min(3.0, 1.6 + 0.4 * wind.hour_distance_h))

    result = quantification.quantify_plume(
        enh_ppm_m=ours, plume_mask=plume_mask, pixel_areas=pixel_areas,
        n_air_mol_m3=n_air, u10_ms=u10, u10_sigma_ms=u10_sigma,
    )
    ime_nasa = quantification.ime_kg(nasa, plume_mask, pixel_areas, n_air)
    bias = float(result.ime_kg / ime_nasa)
    q_nasa_cal = float(result.q_tonnes_per_hr / bias)

    seg_qs = []
    for thr in _PERMIAN_NASA_THRESHOLDS:
        m = footprint(thr)
        if int(m.sum()) < 5:
            continue
        alt = quantification.quantify_plume(
            enh_ppm_m=ours, plume_mask=m, pixel_areas=pixel_areas,
            n_air_mol_m3=n_air, u10_ms=u10, u10_sigma_ms=u10_sigma,
        )
        seg_qs.append(float(alt.q_tonnes_per_hr))
    spread = (max(seg_qs) - min(seg_qs)) / result.q_tonnes_per_hr if len(seg_qs) >= 2 else 0.0
    sigma_total = float(np.sqrt(result.wind_fractional_uncertainty.total ** 2 + (spread / 2) ** 2))

    return {
        "q_central_t_hr": float(result.q_tonnes_per_hr),
        "q_central_nasa_calibrated_t_hr": q_nasa_cal,
        "pearson_full_scene": ctx["pearson_full_scene"],
        "pearson_in_bbox": ctx["pearson_in_bbox"],
        "centroid_lat": centroid_lat,
        "centroid_lon": centroid_lon,
        "ime_kg": float(result.ime_kg),
        "plume_area_km2": float(result.plume_area_m2 / 1e6),
        "q_total_fractional_sigma": sigma_total,
    }


_HEAT_INDIA_ID = "india_nw_heatwave_2022_04"
_HEAT_CACHE = _CACHE / "sprint9_heat_stage_b"


def _run_heat_india(event: BenchmarkEvent) -> PipelineOutput:
    """Heat AIR-lane recipe: re-derive C1-C4 from the cached ERA5 daily-Tmax
    set (offline once cached) and compare against the committed air_lane.json.

    Mirrors scripts/run_heat_stage_b.py's lane computation exactly — the
    pre-registered definitions live in aether_detection.heat_anomaly; this
    recipe exists so the ADR-0002 regression family covers the heat vertical.
    """
    from datetime import date

    import numpy as np
    from aether_detection.heat_anomaly import (
        cell_areas_km2,
        day_window_climatology,
        qualifying_mask,
        run_containing,
        window_dates,
    )
    from aether_ontology import BaselineDefinition, GeoJSONGeometry

    years = range(1991, 2021)
    grid_path = _HEAT_CACHE / f"era5_grid_{event.event_id}.npz"
    missing = [
        str(p)
        for p in [grid_path, *(_HEAT_CACHE / f"era5_tmax_{y}.npz" for y in [*years, 2022])]
        if not p.exists()
    ]
    if missing:
        raise EventNotRunnable(
            f"heat ERA5 cache incomplete ({len(missing)} files, first: {missing[0]}); "
            "run scripts/sprint9_fetch_era5_tmax.py first"
        )
    grid = np.load(grid_path)
    lats, lons, land = grid["lats"], grid["lons"], grid["land"]
    base = np.stack(
        [np.asarray(np.load(_HEAT_CACHE / f"era5_tmax_{y}.npz")["tmax"]) for y in years]
    )
    ev_arr = np.asarray(np.load(_HEAT_CACHE / "era5_tmax_2022.npz")["tmax"])

    season = window_dates(date(2022, 3, 13), date(2022, 5, 1))
    half = 10
    areas = cell_areas_km2(lats, lons)
    area_total = float((areas * land).sum())
    dates_out: list[date] = []
    fracs: list[float] = []
    quals = []
    anoms = []
    tmaxs = []
    for i in range(half, len(season) - half):
        clim = day_window_climatology(base, i, half)
        qual = qualifying_mask(ev_arr[i], clim, land)
        dates_out.append(season[i])
        fracs.append(float((areas * qual).sum() / area_total))
        quals.append(qual)
        anoms.append(ev_arr[i] - clim)
        tmaxs.append(ev_arr[i])

    window = [d for d in dates_out if date(2022, 4, 2) <= d <= date(2022, 4, 11)]
    widx = [dates_out.index(d) for d in window]
    win_tmax = np.where(land, np.stack([tmaxs[i] for i in widx]), np.nan)
    c1_peak_c = float(np.nanmax(win_tmax)) - 273.15

    def regional_mean(arr: np.ndarray) -> float:
        w = np.where(land & ~np.isnan(arr), areas, 0.0)
        return float(np.nansum(np.where(land, arr, np.nan) * w) / w.sum())

    reg_anoms = [regional_mean(anoms[i]) for i in widx]
    c2_window_mean = float(np.mean(reg_anoms))
    run = run_containing(dates_out, fracs, date(2022, 4, 8), 0.05)
    peak_i = widx[int(np.argmax([fracs[i] for i in widx]))]
    c4_extent = float((areas * quals[peak_i]).sum())

    # anomaly-weighted centroid + window-union qualifying bbox (the footprint)
    union = np.any(np.stack([quals[i] for i in widx]), axis=0)
    ii, jj = np.nonzero(union)
    wmap = np.where(union, np.nanmean(np.stack([anoms[i] for i in widx]), axis=0), 0.0)
    wsum = float(wmap.sum())
    cen_lat = float((lats[:, None] * wmap).sum() / wsum)
    cen_lon = float((lons[None, :] * wmap).sum() / wsum)
    box = (
        float(lons[jj.max()]) + 0.125,
        float(lons[jj.min()]) - 0.125,
        float(min(lats[ii.min()], lats[ii.max()])) - 0.125,
        float(max(lats[ii.min()], lats[ii.max()])) + 0.125,
    )
    max_lon, min_lon, min_lat, max_lat = box
    detection = Detection(
        detection_type=DetectionType.AIR_TEMPERATURE_ANOMALY,
        observation_ids=[_granule_observation_uuid("era5_" + event.event_id)],
        location=Point(lon=cen_lon, lat=cen_lat),
        footprint=GeoJSONGeometry(
            type="Polygon",
            coordinates=[
                [
                    [min_lon, min_lat],
                    [max_lon, min_lat],
                    [max_lon, max_lat],
                    [min_lon, max_lat],
                    [min_lon, min_lat],
                ]
            ],
        ),
        time_range=event.date_range,
        measurements={
            "peak_tmax_c": round(c1_peak_c, 2),
            "window_mean_regional_anomaly_k": round(c2_window_mean, 3),
            "duration_days": float(run.n_days),
            "peak_day_extent_km2": round(c4_extent, -2),
        },
        measurement_units={
            "peak_tmax_c": "degC",
            "window_mean_regional_anomaly_k": "K",
            "duration_days": "days",
            "peak_day_extent_km2": "km^2",
        },
        algorithm=PIPELINE_NAME,
        algorithm_version=PIPELINE_VERSION,
        baseline=BaselineDefinition(
            dataset="ARCO-ERA5 v3 2m_temperature",
            period_start_year=1991,
            period_end_year=2020,
            day_window_days=10,
            statistic="mean",
            hours_utc=list(range(6, 14)),
        ),
        provenance=Provenance(
            source="aether_detection.heat_anomaly",
            source_id=event.event_id,
            pipeline=PIPELINE_NAME,
            pipeline_version=PIPELINE_VERSION,
            notes="Fresh in-memory AIR-lane re-run for the ADR-0002 regression family.",
        ),
    )
    return PipelineOutput(
        detections=[detection],
        regression_values={
            "c1_peak_c": c1_peak_c,
            "c2_window_mean_anomaly_k": c2_window_mean,
            "c3_duration_days": float(run.n_days),
            "c4_extent_km2": c4_extent,
        },
    )


_RECIPES = {
    _GOTURDEPE_ID: _run_goturdepe,
    _PERMIAN_ID: _run_permian,
    _HEAT_INDIA_ID: _run_heat_india,
}


def check_runnable(event: BenchmarkEvent) -> None:
    """Raise EventNotRunnable with the honest reason if the event can't be run.

    Pure data check (no scientific imports) so it is CI-testable.

    Phenomenon-aware (Sprint 9 Stage B): the EMIT-coverage logic applies only to
    emission events — a heat wave that "predates EMIT" was a true-but-irrelevant
    reason (the Stage A report flagged it). Non-emission phenomena are runnable
    iff a recipe is wired for them.
    """
    if event.phenomenon_type is not PhenomenonType.EMISSION_EVENT:
        if event.event_id not in _RECIPES:
            raise EventNotRunnable(
                f"no eval recipe is wired for phenomenon type "
                f"'{event.phenomenon_type.value}' yet (event '{event.event_id}'); "
                "add one to aether_eval.real_pipeline._RECIPES before scoring it"
            )
        return
    if event.canonical_acquisition is None:
        start = event.date_range.start
        start = start if start.tzinfo else start.replace(tzinfo=UTC)
        end = event.date_range.end or event.date_range.start
        end = end if end.tzinfo else end.replace(tzinfo=UTC)
        if end < _EMIT_LAUNCH:
            raise EventNotRunnable(
                f"no EMIT coverage: the event window ({start.date()}..{end.date()}) "
                "predates EMIT's July 2022 launch; no canonical EMIT acquisition "
                "is pinned"
            )
        raise EventNotRunnable(
            "no canonical EMIT acquisition is pinned for this event; the real "
            "pipeline cannot run without one"
        )
    if event.event_id not in _RECIPES:
        raise EventNotRunnable(
            "no eval recipe is wired for this event's canonical acquisition yet "
            "(add one to aether_eval.real_pipeline before scoring it)"
        )


def real_emit_pipeline(event: BenchmarkEvent) -> PipelineOutput:
    """Run the real EMIT pipeline on one benchmark event (in memory).

    Returns one Detection at the fresh plume centroid plus the regression
    values compared against the committed artifacts by the runner.
    """
    check_runnable(event)
    if event.phenomenon_type is not PhenomenonType.EMISSION_EVENT:
        # Area-phenomenon recipes build their own PipelineOutput (no EMIT
        # acquisition, no plume detection construction).
        return _RECIPES[event.event_id](event)  # type: ignore[return-value]
    values = _RECIPES[event.event_id](event)

    acq = event.canonical_acquisition
    assert acq is not None
    q_central = values["q_central_t_hr"]
    detection = Detection(
        detection_type=DetectionType.METHANE_PLUME,
        observation_ids=[_granule_observation_uuid(acq.l1b_granule_ur or event.event_id)],
        location=Point(lon=values["centroid_lon"], lat=values["centroid_lat"]),
        time_range=event.date_range,
        measurements={
            "emission_rate_metric_tonnes_per_hr": q_central,
            "emission_rate_metric_tonnes_per_hr_nasa_calibrated":
                values["q_central_nasa_calibrated_t_hr"],
            "ime_kg": values["ime_kg"],
            "plume_area_km2": values["plume_area_km2"],
        },
        measurement_units={
            "emission_rate_metric_tonnes_per_hr": "tonnes/hr",
            "emission_rate_metric_tonnes_per_hr_nasa_calibrated": "tonnes/hr",
            "ime_kg": "kg",
            "plume_area_km2": "km^2",
        },
        measurement_uncertainty={
            "emission_rate_metric_tonnes_per_hr":
                q_central * values["q_total_fractional_sigma"],
        },
        algorithm=PIPELINE_NAME,
        algorithm_version=PIPELINE_VERSION,
        provenance=Provenance(
            source="aether_detection",
            source_id=acq.l1b_granule_ur or event.event_id,
            pipeline=PIPELINE_NAME,
            pipeline_version=PIPELINE_VERSION,
            parents=[],
            notes=(
                "Fresh in-memory re-run of the event's canonical recipe for the "
                "ADR-0002 regression family; committed artifacts untouched."
            ),
        ),
    )
    regression_keys = (
        "q_central_t_hr", "q_central_nasa_calibrated_t_hr",
        "pearson_full_scene", "pearson_in_bbox", "centroid_lat", "centroid_lon",
    )
    return PipelineOutput(
        detections=[detection],
        regression_values={k: values[k] for k in regression_keys},
    )
