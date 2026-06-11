"""Map committed Stage A/B outputs + benchmark YAML -> API response models.

This module is the single place numbers enter the system. Every value is read
from one of:
  - stage_b_outputs/<id>/q_estimate.json        (quantification, uncertainty, geometry, wind)
  - stage_a_outputs/<id>/stage_a_report.json    (Pearson validation, granules, bands)
  - eval/benchmark/<id>.yaml                     (reference total, sources, citations, location)
  - assets/<id>/bounds.json                      (raster bounds + colormap window)

Derived quantities (clearly commented) are computed here from those real fields
— never invented. Display-only labels (country, chip text, short name) are noted
as such; they carry no scientific value. If a file is missing, the event is
treated as PENDING rather than fabricated.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aether_causal.schema import HypothesisSet
from aether_eval.loader import load_event_file
from aether_eval.schema import BenchmarkEvent, Measurement

from . import config
from .models import (
    Atmosphere,
    CalibratedRate,
    EventDetail,
    EventStatus,
    EventSummary,
    Geometry,
    Provenance,
    Quantification,
    RasterBounds,
    RasterMeta,
    Reference,
    ScopeCaveat,
    UncertaintyTerm,
    Validation,
)

# Events surfaced on the globe, in display order. Goturdepe is the quantified
# wedge; Permian is an honest "pending" — its benchmark exists but Sprint 2 could
# not quantify it (no granule-matched target spectrum). See its YAML.
EVENT_IDS = ["turkmenistan_goturdepe_2022_08_15", "permian_basin_2022"]

# Display-only labels (NOT scientific values). Coordinates, rates and citations
# all come from files; these are just human-facing names/regions for the HUD.
_DISPLAY: dict[str, dict[str, str]] = {
    "turkmenistan_goturdepe_2022_08_15": {
        "short_name": "GOTURDEPE–BARSAGELMEZ",
        "region": "Turkmenistan",
    },
    "permian_basin_2022": {
        "short_name": "PERMIAN BASIN",
        "region": "Carlsbad, NM · USA",
    },
}

_SENSOR_CHIP = {
    "hyperspectral": "Hyperspectral",
    "thermal_ir": "Thermal",
    "multispectral": "Multispectral",
}


def _read_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def _is_active(event_id: str) -> bool:
    """An event is ACTIVE (rendered live) only when BOTH its quantification and its
    UI render assets are committed.

    Sprint 7 generality fix: activation was previously gated on q_estimate.json
    alone — a Goturdepe-shaped assumption. Permian's Stage B quantification can
    land in stage_b_outputs/ while the event is still gated behind Stage D (UI
    integration), which is what produces the assets/<id>/bounds.json render set.
    Until those assets exist the event stays an honest PENDING.
    """
    q_path = config.stage_b_dir(event_id) / "q_estimate.json"
    bounds_path = config.assets_dir(event_id) / "bounds.json"
    return q_path.exists() and bounds_path.exists()


def _emission_measurement(event: BenchmarkEvent) -> Measurement | None:
    """The reference emission-rate measurement (cluster total) from the YAML."""
    return event.known_measurements.get("emission_rate_metric_tonnes_per_hr")


def _scope_caveat(
    event: BenchmarkEvent, meas: Measurement, ours_central: float, nasa_central: float
) -> ScopeCaveat:
    """Build the event-specific 'Read Before Citing' block.

    Sprint 7 generality: the block is CONTENT keyed to what the reference IS, not
    a Thorpe template with swapped numbers. A peer-reviewed multi-source cluster
    total (uncertainty + n_sources present) yields a single-plume-vs-cluster
    FRACTION; a press-release figure with no method/uncertainty yields a
    CONTEXT-ONLY block that refuses the comparison.
    """
    ref_total = meas.value
    if meas.uncertainty is not None and meas.n_sources:
        # Cluster-fraction (e.g. Goturdepe / Thorpe 2023). Text + numerics unchanged.
        n_sources = meas.n_sources
        frac_low = nasa_central / ref_total * 100.0
        frac_high = ours_central / ref_total * 100.0
        return ScopeCaveat(
            kind="cluster_fraction",
            reference_total_t_hr=ref_total,
            reference_uncertainty_t_hr=meas.uncertainty,
            n_sources=n_sources,
            fraction_low_pct=frac_low,
            fraction_high_pct=frac_high,
            text=(
                f"This is one source-connected plume. Thorpe et al. 2023 report "
                f"{ref_total:g} ± {meas.uncertainty:g} t/hr for the full {n_sources}-source "
                f"cluster. A single-plume estimate is not comparable to the cluster total — "
                f"expected ≈{round(frac_low)}–{round(frac_high)}% of it."
            ),
        )
    # Context-only (e.g. Permian / 18.3 t/hr press release). No cluster, no fraction.
    return ScopeCaveat(
        kind="context_only",
        reference_total_t_hr=ref_total,
        text=(
            f"The only published figure for this event is {ref_total:g} t/hr — a "
            f"press-release value with no observation date, method, or uncertainty. It "
            f"names no overpass, so its correspondence to THIS scene is inferred, not "
            f"established, and super-emitter intermittency makes a same-site / "
            f"different-day comparison meaningless. It is CONTEXT for the site, not a "
            f"validation target for this retrieval. Our estimate ≈{ours_central:.1f} t/hr "
            f"is cross-checked against NASA's L2B over the same footprint (see "
            f"validation), not against this figure."
        ),
    )


def _primary_sensor(event: BenchmarkEvent) -> tuple[str, str]:
    """(sensor display name, sensor-type chip) from observed_by[0]."""
    if not event.observed_by:
        return ("EMIT", "Hyperspectral")
    obs = event.observed_by[0]
    name = obs.sensor.split(" (")[0]  # "EMIT (Earth Surface...)" -> "EMIT"
    chip = _SENSOR_CHIP.get(str(obs.sensor_type.value), obs.sensor_type.value.title())
    return (name, chip)


# --------------------------------------------------------------------------- #
# Summaries (globe markers)
# --------------------------------------------------------------------------- #
def list_events() -> list[EventSummary]:
    return [_summary(eid) for eid in EVENT_IDS]


def _summary(event_id: str) -> EventSummary:
    event = load_event_file(config.benchmark_yaml(event_id))
    disp = _DISPLAY[event_id]
    sensor_name, _ = _primary_sensor(event)

    if _is_active(event_id):
        q = _read_json(config.stage_b_dir(event_id) / "q_estimate.json")
        stage_a = _read_json(config.stage_a_dir(event_id) / "stage_a_report.json")
        # Marker sits on the real plume centroid; headline is the OURS-CAL rate.
        return EventSummary(
            event_id=event_id,
            name=event.name,
            short_name=disp["short_name"],
            planetary_body=event.planetary_body,
            phenomenon_type=event.phenomenon_type,
            lat=q["plume_centroid_lat"],
            lon=q["plume_centroid_lon"],
            status=EventStatus.ACTIVE,
            sensor=sensor_name,
            headline=f"CH₄ · {q['q_central_t_hr']:.1f} t/hr",
            acquisition_utc=stage_a.get("acquisition_utc"),
        )

    # No Stage B result -> pending marker at the benchmark location (honest gap).
    return EventSummary(
        event_id=event_id,
        name=event.name,
        short_name=disp["short_name"],
        planetary_body=event.planetary_body,
        phenomenon_type=event.phenomenon_type,
        lat=event.location.lat,
        lon=event.location.lon,
        status=EventStatus.PENDING,
        sensor=sensor_name,
        headline="pending",
    )


# --------------------------------------------------------------------------- #
# Source attribution (Sprint 4 artifact)
# --------------------------------------------------------------------------- #
def get_hypotheses(event_id: str) -> HypothesisSet | None:
    """Load + validate the committed attribution artifact, or None if absent.

    Validated through aether_causal's own HypothesisSet (extra="forbid"), so the
    API can neither add nor drop a field relative to the committed JSON.
    """
    path = config.hypotheses_json(event_id)
    if not path.exists():
        return None
    return HypothesisSet.model_validate_json(path.read_text())


# --------------------------------------------------------------------------- #
# Detail (inspector)
# --------------------------------------------------------------------------- #
def get_event_detail(event_id: str) -> EventDetail | None:
    if event_id not in EVENT_IDS:
        return None
    event = load_event_file(config.benchmark_yaml(event_id))
    if _is_active(event_id):
        return _active_detail(event_id, event)
    return _pending_detail(event_id, event)


def _references(event: BenchmarkEvent) -> list[Reference]:
    return [Reference(citation=r.citation, doi=r.doi, url=r.url) for r in event.references]


def _chips(event: BenchmarkEvent) -> list[str]:
    _, sensor_chip = _primary_sensor(event)
    pheno = (
        "Emission Event"
        if event.phenomenon_type.value == "emission_event"
        else (event.phenomenon_type.value.replace("_", " ").title())
    )
    return [pheno, event.planetary_body.value.title(), sensor_chip]


def _active_detail(event_id: str, event: BenchmarkEvent) -> EventDetail:
    q = _read_json(config.stage_b_dir(event_id) / "q_estimate.json")
    a = _read_json(config.stage_a_dir(event_id) / "stage_a_report.json")
    bounds = _read_json(config.assets_dir(event_id) / "bounds.json")
    disp = _DISPLAY[event_id]
    meas = _emission_measurement(event)
    assert meas is not None, f"{event_id} is active but has no reference emission measurement"
    # NOTE: a reference WITHOUT an uncertainty (e.g. Permian's press-release 18.3 t/hr)
    # is valid — it yields a context_only scope block, not a cluster fraction. The
    # earlier `assert meas.uncertainty is not None` was a Goturdepe-shaped assumption.

    bias = q["enhancement_bias_factor"]
    sigma = q["q_total_fractional_sigma"]
    ours_central = q["q_central_t_hr"]
    nasa_central = q["q_central_nasa_calibrated_t_hr"]
    ours_low, ours_high = q["q_low_t_hr"], q["q_high_t_hr"]
    # NASA-cal range = ours range / bias (both calibrations share one fractional
    # window; dividing the IME by the MF amplitude bias shifts the whole interval).
    nasa_low, nasa_high = ours_low / bias, ours_high / bias

    quantification = Quantification(
        ours_cal=CalibratedRate(
            label="OURS-CAL",
            value_t_hr=ours_central,
            range_low_t_hr=ours_low,
            range_high_t_hr=ours_high,
            sigma_fractional=sigma,
            note=(
                "Central estimate from our INDEPENDENT retrieval — matched filter on a "
                "methane absorption spectrum generated from HITRAN2020 via HAPI (NASA's "
                f"per-granule target is not used). The +{bias:.2f}× MF over-amplitude vs NASA "
                "L2B is now reproduced independently — a real MF systematic, not a "
                "NASA-convention artifact — and carried one-sided."
            ),
        ),
        nasa_cal=CalibratedRate(
            label="NASA-CAL",
            value_t_hr=nasa_central,
            range_low_t_hr=nasa_low,
            range_high_t_hr=nasa_high,
            sigma_fractional=sigma,
            note=(
                f"Our IME divided by the independently-measured {bias:.2f}× MF amplitude ratio "
                "vs NASA L2B (ours/NASA over the plume CC), anchoring the rate to NASA's "
                "enhancement amplitude for direct comparison to NASA-derived rates."
            ),
        ),
        enhancement_bias_factor=bias,
        central_p_value=q["central_p_value"],
    )

    # Uncertainty budget. value_pct are the real 1σ fractional terms; bar_fraction
    # expresses each as a share of the combined 1σ (q_total_fractional_sigma).
    total_pct = sigma * 100.0
    alpha1_pct = q["wind_fractional_alpha1"] * 100.0
    u10_pct = q["wind_fractional_u10"] * 100.0
    # Mask sensitivity as a ± is half the peak-to-peak Q spread over p∈{0.01,0.05,0.1}.
    mask_pct = q["seg_sensitivity_q_spread_fractional"] / 2.0 * 100.0
    budget = [
        UncertaintyTerm(
            key="alpha1",
            label="α₁ wind parameterization",
            kind="symmetric",
            value_pct=alpha1_pct,
            display=f"±{alpha1_pct:.1f}%",
            bar_fraction=min(1.0, alpha1_pct / total_pct),
        ),
        UncertaintyTerm(
            key="era5_u10",
            label="ERA5 wind representativeness",
            kind="symmetric",
            value_pct=u10_pct,
            display=f"±{u10_pct:.1f}%",
            bar_fraction=min(1.0, u10_pct / total_pct),
        ),
        UncertaintyTerm(
            key="mask",
            label="Plume-mask sensitivity",
            kind="symmetric",
            value_pct=mask_pct,
            display=f"±{mask_pct:.1f}%",
            bar_fraction=min(1.0, mask_pct / total_pct),
        ),
        UncertaintyTerm(
            key="mf_amplitude",
            label="MF amplitude (systematic)",
            kind="systematic",
            factor=bias,
            display=f"+{bias:.2f}×",
            bar_fraction=1.0,
        ),
    ]

    geometry = Geometry(
        ime_t=q["ime_central_kg"] / 1000.0,
        area_km2=q["plume_cc_area_km2"],
        length_km=q["plume_length_m"] / 1000.0,
        centroid_lat=q["plume_centroid_lat"],
        centroid_lon=q["plume_centroid_lon"],
    )

    atmosphere = Atmosphere(
        u10_speed_ms=q["era5_u10_speed_ms"],
        u_eff_ms=q["u_eff_ms"],
        era5_grid_lat=q["era5_grid_lat"],
        era5_grid_lon=q["era5_grid_lon"],
        era5_nearest_hour_utc=q["era5_nearest_hour_utc"],
    )

    validation = Validation(
        pearson_in_bbox=a["pearson_in_bbox"],
        pearson_full_scene=a["pearson_full_scene"],
        n_pixels_bbox=a["n_pixels_compared_bbox"],
        reference_product="NASA L2B CH4ENH",
        note=(
            "Spatial agreement of our enhancement with NASA L2B CH4ENH, "
            "orthorectified, unsmoothed, over the plume bbox."
        ),
    )

    scope = _scope_caveat(event, meas, ours_central, nasa_central)
    ref_total = meas.value
    n_sources = meas.n_sources or 0

    provenance = Provenance(
        acquisition_utc=a["acquisition_utc"],
        l1b_granule_ur=a.get("l1b_granule_ur"),
        l2a_mask_granule_ur=a.get("l2a_mask_granule_ur"),
        l2b_ch4_granule_ur=a.get("l2b_ch4_granule_ur"),
        target_spectrum_source=a.get("target_spectrum_source"),
        bands_used=a.get("bands_used"),
    )

    cmap = bounds["colormap"]
    raster = RasterMeta(
        bounds=RasterBounds(**bounds["bounds"]),
        colormap=cmap["name"],
        vmin_ppm_m=cmap["vmin_ppm_m"],
        vmax_ppm_m=cmap["vmax_ppm_m"],
        layers=["enhancement", "nasa", "diff"],
    )

    # Deterministic brief assembled entirely from the real values above.
    acq_date = a["acquisition_utc"][:10]
    brief = (
        f"EMIT imaged a coherent methane plume over the {disp['short_name'].split('–')[0].title()} "
        f"gas field on {acq_date}. Our independent retrieval — a matched filter on a methane "
        f"absorption spectrum generated from HITRAN2020 via HAPI, with no NASA per-granule "
        f"target — reproduces NASA's L2B enhancement at r = {validation.pearson_in_bbox:.2f} and "
        f"yields {geometry.ime_t:.1f} t integrated mass over a {geometry.area_km2:.1f} km² mask. "
        f"With a {atmosphere.u10_speed_ms:.1f} m/s wind this implies ≈{ours_central:.0f} t CH₄/hr "
        f"from this single source — one of {n_sources} Thorpe et al. quantify at "
        f"{ref_total:g} ± {meas.uncertainty:g} t/hr."
    )

    return EventDetail(
        event_id=event_id,
        name=event.name,
        short_name=disp["short_name"],
        planetary_body=event.planetary_body,
        phenomenon_type=event.phenomenon_type,
        lat=q["plume_centroid_lat"],
        lon=q["plume_centroid_lon"],
        status=EventStatus.ACTIVE,
        location_label=(
            f"{disp['region']} · {geometry.centroid_lat:.2f}°N {geometry.centroid_lon:.2f}°E"
        ),
        chips=_chips(event),
        quantification=quantification,
        uncertainty_budget=budget,
        geometry=geometry,
        atmosphere=atmosphere,
        validation=validation,
        scope_caveat=scope,
        brief=brief,
        raster=raster,
        provenance=provenance,
        references=_references(event),
    )


def _pending_detail(event_id: str, event: BenchmarkEvent) -> EventDetail:
    """Honest pending payload: location + references + the published (non-citable)
    figure, but NO quantification/geometry/validation — we have not run Stage B."""
    disp = _DISPLAY[event_id]
    meas = _emission_measurement(event)
    ca = event.canonical_acquisition

    reason = "No Stage B quantification has been run for this event. " + (
        meas.note.strip().split("  ")[0] if meas else ""
    )

    provenance = None
    if ca is not None:
        provenance = Provenance(
            acquisition_utc=ca.utc.isoformat().replace("+00:00", "Z"),
            l1b_granule_ur=ca.l1b_granule_ur,
            l2a_mask_granule_ur=ca.l2a_mask_granule_ur,
            l2b_ch4_granule_ur=ca.l2b_ch4_granule_ur,
        )

    return EventDetail(
        event_id=event_id,
        name=event.name,
        short_name=disp["short_name"],
        planetary_body=event.planetary_body,
        phenomenon_type=event.phenomenon_type,
        lat=event.location.lat,
        lon=event.location.lon,
        status=EventStatus.PENDING,
        location_label=f"{disp['region']} · {event.location.lat:.2f}°N {event.location.lon:.2f}°W",
        chips=_chips(event),
        provenance=provenance,
        references=_references(event),
        pending_reason=reason,
    )
