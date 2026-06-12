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
EVENT_IDS = [
    "turkmenistan_goturdepe_2022_08_15",
    "permian_basin_2022",
    "india_nw_heatwave_2022_04",
]

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
    "india_nw_heatwave_2022_04": {
        "short_name": "NW INDIA HEAT WAVE",
        "region": "NW/Central India",
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
    # Sprint 9 generality fix: the quantification artifact is phenomenon-shaped —
    # q_estimate.json for plume events, air_lane.json for heat events. Either
    # counts; the UI assets gate is shared.
    q_path = config.stage_b_dir(event_id) / "q_estimate.json"
    air_path = config.stage_b_dir(event_id) / "air_lane.json"
    bounds_path = config.assets_dir(event_id) / "bounds.json"
    return (q_path.exists() or air_path.exists()) and bounds_path.exists()


# Validation tier per event — see the rubric in docs/science/validation_tiers.md.
# VALIDATED is the RESERVED top tier (requires independent flux truth: controlled
# release, in-situ, or a peer-reviewed PER-SOURCE flux). NO current event qualifies —
# Goturdepe's only flux reference (Thorpe 163±18 t/hr) is a scope-mismatched CLUSTER
# total, so its agreement/disagreement is not claimable (Sprint 2 validation doc).
# Both current events are therefore CROSS-CHECKED; they differ in cross-check STRENGTH
# (carried in the explainer, not the badge). Read from stage_a_report.validation_tier
# when present; Goturdepe's Sprint-6 report predates the field, so it falls back here.
_TIER_DEFAULT: dict[str, str] = {"turkmenistan_goturdepe_2022_08_15": "CROSS-CHECKED"}


def _validation_tier(event_id: str, stage_a: dict[str, Any]) -> str:
    return str(stage_a.get("validation_tier") or _TIER_DEFAULT.get(event_id, "DEMONSTRATION"))


def _fmt_rate(v: float) -> str:
    """Display a t/hr rate: sub-1 rates get 2 decimals (0.85, not 0.9), else 1."""
    return f"{v:.2f}" if abs(v) < 1.0 else f"{v:.1f}"


def _tier_explainer(
    tier: str, val: Validation, *, is_context: bool, k_shape_r: float | None, ours_central: float
) -> str:
    """First-class explainer: what the tier means for THIS event + its limits, tracing
    to the rubric (docs/science/validation_tiers.md). CROSS-CHECKED is differentiated by
    STRENGTH here — never by the badge. Strength keys on whether the event has a
    cluster-scale reference + self-derived localization (Goturdepe = strong) vs a
    press-release reference + NASA-anchored localization (Permian = weaker)."""
    if tier == "VALIDATED":
        # Reserved top tier — held by no current event (stated for an honest ceiling).
        return (
            "VALIDATED — reserved top tier: requires independent flux truth (a controlled "
            "release, in-situ measurement, or peer-reviewed PER-SOURCE flux). No current "
            "event qualifies."
        )
    if tier == "CROSS-CHECKED":
        if not is_context:
            # Strong: pixel-level spatial agreement + self-derived S + k-shape verified.
            k_clause = (
                f", the methane k-shape verified against NASA's per-granule target "
                f"(r = {k_shape_r:.3f})"
                if k_shape_r is not None
                else ""
            )
            return (
                f"CROSS-CHECKED (strong) — pixel-level spatial agreement with NASA L2B "
                f"(r = {val.pearson_in_bbox:.2f}), fully self-derived localization{k_clause}, "
                f"and a NASA-cal anchor. LIMIT: a single overpass with NO independent flux "
                f"reference — Thorpe et al.'s 163 ± 18 t/hr is a scope-mismatched cluster "
                f"total, so agreement/disagreement is not claimable."
            )
        facts = (
            f"integrated mass over NASA's published footprint agrees to "
            f"{val.integrated_mass_ratio:.2f}× (ours/NASA)"
            if val.integrated_mass_ratio is not None
            else f"spatial Pearson r = {val.pearson_in_bbox:.2f}"
        )
        pixel = (
            f", but pixel-level agreement is weak (r = {val.pixel_pearson:.2f})"
            if val.pixel_pearson is not None
            else ""
        )
        return (
            f"CROSS-CHECKED — a NASA L2B raster exists, so our retrieval is checked against "
            f"it: {facts}{pixel}; localization is NASA-footprint-anchored; no k-shape check "
            f"is available. LIMIT: NO independent flux reference — the published 18.3 t/hr is "
            f"press-release context only, not a comparison target."
        )
    return (
        "DEMONSTRATION — no independent reference raster exists for this granule, so the "
        f"~{ours_central:.2f} t/hr retrieval is internally consistent but UNVALIDATED."
    )


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

    if event.phenomenon_type.value == "heat_wave" and _is_active(event_id):
        return _heat_summary(event_id, event)

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
            validation_tier=_validation_tier(event_id, stage_a),
            headline=f"CH₄ · {_fmt_rate(q['q_central_t_hr'])} t/hr",
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

    Gated on activation: a committed attribution artifact is only SERVED once the
    event is live (Stage D). Permian's Stage C hypotheses.json exists on disk (for
    the no-fabrication guard and for Stage D to consume), but until its UI assets
    land the event is PENDING and the API surfaces no hypotheses — never fabricated,
    and not prematurely exposed ahead of the UI gate.
    """
    if not _is_active(event_id):
        return None
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
    if event.phenomenon_type.value == "heat_wave":
        if _is_active(event_id):
            return _heat_active_detail(event_id, event)
        return _pending_detail(event_id, event)
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

    is_context = meas.uncertainty is None  # press-release reference (Permian) vs cluster
    bias = q["enhancement_bias_factor"]
    sigma = q["q_total_fractional_sigma"]
    ours_central = q["q_central_t_hr"]
    nasa_central = q["q_central_nasa_calibrated_t_hr"]
    ours_low, ours_high = q["q_low_t_hr"], q["q_high_t_hr"]
    # NASA-cal range = ours range / bias (both calibrations share one fractional
    # window; dividing the IME by the MF amplitude bias shifts the whole interval).
    nasa_low, nasa_high = ours_low / bias, ours_high / bias

    # The MF-amplitude phrasing must be honest about direction: Goturdepe is an
    # OVER-amplitude (bias > 1); Permian is BELOW NASA (bias < 1, and the +1.46×
    # Goturdepe systematic does not transfer).
    if bias >= 1.0:
        ours_amp = (
            f"The +{bias:.2f}× MF over-amplitude vs NASA L2B is reproduced independently — "
            "a real MF systematic, not a NASA-convention artifact — and carried one-sided."
        )
        nasa_amp = (
            f"Our IME divided by the independently-measured {bias:.2f}× MF amplitude ratio "
            "vs NASA L2B (ours/NASA over the plume mask), anchoring the rate to NASA's "
            "enhancement amplitude for direct comparison to NASA-derived rates."
        )
    else:
        ours_amp = (
            f"Over the plume footprint our MF amplitude is {bias:.2f}× NASA's L2B (ours BELOW "
            "NASA) — the +1.46× over-amplitude measured on Goturdepe does NOT transfer to "
            "this scene."
        )
        nasa_amp = (
            f"Our IME divided by the measured {bias:.2f}× ours/NASA amplitude ratio over "
            "NASA's published footprint — i.e. anchored to NASA's own L2B enhancement there."
        )

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
                f"per-granule target is not used). {ours_amp}"
            ),
        ),
        nasa_cal=CalibratedRate(
            label="NASA-CAL",
            value_t_hr=nasa_central,
            range_low_t_hr=nasa_low,
            range_high_t_hr=nasa_high,
            sigma_fractional=sigma,
            note=nasa_amp,
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

    # CROSS-CHECKED events carry the dual cross-check facts: the integrated-mass
    # ratio over NASA's published footprint AND the (weak) pixel-level Pearson.
    diag_path = config.stage_b_dir(event_id) / "diagnostics.json"
    diag = _read_json(diag_path) if diag_path.exists() else {}
    pixel_pearson = diag.get("pixelwise_pearson_on_footprint_ours_vs_nasa")
    # k-shape cross-check r vs NASA's per-granule target (committed in the k provenance);
    # present for Goturdepe (≈0.993), absent for Permian (no NASA target). Feeds the
    # strong-CROSS-CHECKED explainer.
    kprov_path = config.stage_a_dir(event_id) / "hitran_k" / "hitran_k_sat_provenance.json"
    k_shape_r = (
        _read_json(kprov_path).get("shape_pearson_r_vs_nasa") if kprov_path.exists() else None
    )
    if is_context:
        pixel_r = pixel_pearson if pixel_pearson is not None else float("nan")
        val_note = (
            "TWO cross-check facts vs NASA L2B over the published plume footprint: the "
            f"integrated mass agrees to {bias:.2f}× (ours/NASA), but the pixel-level "
            f"agreement is weak (r = {pixel_r:.2f}) — the masses match even though pixel "
            f"co-registration does not. Full-scene Pearson r = {a['pearson_full_scene']:.2f}."
        )
        integrated_mass_ratio = bias
    else:
        val_note = (
            "Spatial agreement of our enhancement with NASA L2B CH4ENH, "
            "orthorectified, unsmoothed, over the plume bbox."
        )
        integrated_mass_ratio = None
        pixel_pearson = None

    validation = Validation(
        pearson_in_bbox=a["pearson_in_bbox"],
        pearson_full_scene=a["pearson_full_scene"],
        n_pixels_bbox=a["n_pixels_compared_bbox"],
        reference_product="NASA L2B CH4ENH",
        note=val_note,
        integrated_mass_ratio=integrated_mass_ratio,
        pixel_pearson=pixel_pearson,
    )

    scope = _scope_caveat(event, meas, ours_central, nasa_central)
    ref_total = meas.value
    n_sources = meas.n_sources or 0

    # Source-localization provenance: distinguishes Permian's NASA-footprint-anchored
    # S from Goturdepe's end-to-end self-derived S (Stage D requirement).
    localization = (
        "NASA-footprint-anchored — the source point S derives from NASA's published L2B "
        "plume footprint (CH4PLM complex), not a fully self-derived localization."
        if is_context
        else "End-to-end independent — S is self-derived from our own retrieval (top-5% "
        "upwind plume pixels), no NASA plume product used to locate it."
    )
    provenance = Provenance(
        acquisition_utc=a["acquisition_utc"],
        l1b_granule_ur=a.get("l1b_granule_ur"),
        l2a_mask_granule_ur=a.get("l2a_mask_granule_ur"),
        l2b_ch4_granule_ur=a.get("l2b_ch4_granule_ur"),
        target_spectrum_source=a.get("target_spectrum_source"),
        bands_used=a.get("bands_used"),
        localization=localization,
    )

    cmap = bounds["colormap"]
    raster = RasterMeta(
        bounds=RasterBounds(**bounds["bounds"]),
        colormap=cmap["name"],
        vmin_ppm_m=cmap["vmin_ppm_m"],
        vmax_ppm_m=cmap["vmax_ppm_m"],
        layers=["enhancement", "nasa", "diff"],
    )

    # Deterministic brief assembled entirely from the real values above. Event-aware:
    # a cluster event closes on the Thorpe fraction; a context-only event closes on the
    # NASA-footprint cross-check and frames 18.3 t/hr as press-release context.
    acq_date = a["acquisition_utc"][:10]
    tier = _validation_tier(event_id, a)
    if is_context:
        nasa_fp = q.get("q_nasa_l2b_same_footprint_t_hr")
        nasa_fp_clause = (
            f" — agreeing with NASA's own L2B through the same method ({nasa_fp:.2f} t/hr) "
            f"to {bias:.2f}×"
            if nasa_fp is not None
            else ""
        )
        brief = (
            f"EMIT imaged a methane plume near {disp['region']} on {acq_date}. Our independent "
            f"retrieval — a matched filter on a HITRAN2020/HAPI absorption spectrum, with no "
            f"NASA per-granule target — reproduces NASA's L2B structure at r = "
            f"{validation.pearson_full_scene:.2f} (full scene) and, over NASA's published plume "
            f"footprint, yields {ours_central:.2f} t CH₄/hr{nasa_fp_clause}. This is "
            f"{tier} (NASA-L2B-anchored), not a peer-reviewed flux validation. The only "
            f"published figure, {ref_total:g} t/hr, is a press-release value with no date, "
            f"method, or uncertainty — context for the site, not a comparison target."
        )
    else:
        brief = (
            f"EMIT imaged a coherent methane plume over the "
            f"{disp['short_name'].split('–')[0].title()} "
            f"gas field on {acq_date}. Our independent retrieval — a matched filter on a methane "
            f"absorption spectrum generated from HITRAN2020 via HAPI, with no NASA per-granule "
            f"target — reproduces NASA's L2B enhancement at r = {validation.pearson_in_bbox:.2f} "
            f"and yields {geometry.ime_t:.1f} t integrated mass over a {geometry.area_km2:.1f} "
            f"km² mask. With a {atmosphere.u10_speed_ms:.1f} m/s wind this implies "
            f"≈{ours_central:.0f} t CH₄/hr from this single source — one of {n_sources} Thorpe "
            f"et al. quantify at {ref_total:g} ± {meas.uncertainty:g} t/hr."
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
            f"{disp['region']} · {abs(geometry.centroid_lat):.2f}°"
            f"{'N' if geometry.centroid_lat >= 0 else 'S'} "
            f"{abs(geometry.centroid_lon):.2f}°{'E' if geometry.centroid_lon >= 0 else 'W'}"
        ),
        chips=_chips(event),
        validation_tier=tier,
        tier_explainer=_tier_explainer(
            tier, validation, is_context=is_context, k_shape_r=k_shape_r, ours_central=ours_central
        ),
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


# --------------------------------------------------------------------------- #
# Heat vertical (Sprint 9 Stage D)
# --------------------------------------------------------------------------- #
# Every value below is read from a committed, gate-reviewed artifact:
#   stage_b_outputs/<id>/air_lane.json / validation.json / lst_lane.json / uhi.json
#   attribution_outputs/<id>/factor_hypotheses.json
#   assets/<id>/bounds.json
# Rendering rules from the Stage B/C gates are applied structurally here:
# duration/extent always carry criterion+dataset; episode vs window stays
# distinct; LST rows carry the measured view time; tiers are PER QUANTITY.

from aether_causal.schema import FactorHypothesisSet  # noqa: E402

from .models import (  # noqa: E402
    HeatBlock,
    HeatEpisode,
    HeatLayerMeta,
    HeatLstBlock,
    HeatRasterMeta,
    QuantityTierRow,
)

HEAT_TIER_LABEL = "PER-QUANTITY"


def factor_hypotheses_json(event_id: str) -> Path:
    return config.data_root() / "attribution_outputs" / event_id / "factor_hypotheses.json"


def get_factor_hypotheses(event_id: str) -> FactorHypothesisSet | None:
    """Committed Stage C factor artifact, served verbatim once the event is live."""
    if not _is_active(event_id):
        return None
    path = factor_hypotheses_json(event_id)
    if not path.exists():
        return None
    return FactorHypothesisSet.model_validate_json(path.read_text())


def _heat_summary(event_id: str, event: BenchmarkEvent) -> EventSummary:
    disp = _DISPLAY[event_id]
    air = _read_json(config.stage_b_dir(event_id) / "air_lane.json")
    return EventSummary(
        event_id=event_id,
        name=event.name,
        short_name=disp["short_name"],
        planetary_body=event.planetary_body,
        phenomenon_type=event.phenomenon_type,
        lat=event.location.lat,
        lon=event.location.lon,
        status=EventStatus.ACTIVE,
        sensor="ERA5 + MODIS + ISD",
        validation_tier=HEAT_TIER_LABEL,
        headline=(
            f"T2M +{air['c2_anomaly']['window_mean_regional_mean_anomaly_k']:.1f} K · "
            f"peak {air['c1_peak_tmax']['value_c']:.1f} °C"
        ),
        # The canonical analysis window, not a single overpass — area events have
        # no single acquisition; the window is the honest analogue.
        acquisition_utc=f"{air['window'][0]} → {air['window'][1]} (window)",
    )


def _heat_quantity_tiers(
    air: dict[str, Any], val: dict[str, Any], lst: dict[str, Any], uhi: dict[str, Any]
) -> list[QuantityTierRow]:
    v1 = val["v1_station_peak_bracket"]
    v2 = val["v2_era5_station_consistency"]
    v3 = val["v3_imd_anomaly_agreement"]
    v4 = val["v4_duration_extent"]
    c3 = air["c3_duration"]
    view_t = lst["observation_time_caveat"]["measured_mean_day_view_time_local_h"]
    rows = [
        QuantityTierRow(
            quantity="C1",
            label="Peak 2 m air temperature",
            value_display=(
                f"{air['c1_peak_tmax']['value_c']:.2f} °C ({air['c1_peak_tmax']['date']})"
            ),
            tier="VALIDATED" if v1["pass_v1"] else "NOT VALIDATED",
            explainer=(
                "Pre-registered V1 (criteria committed before any station data was "
                f"read): max station-day Tmax across {v2['n_stations']} qualifying ISD "
                f"stations = {v1['max_station_window_tmax_c']:.1f} °C brackets the "
                f"gridded peak within ±{v1['bracket_k']} K — the event's peak "
                "temperature is instrument-validated. Stations are the truth anchor "
                "(ERA5 assimilates them; this is ground-truth agreement, not "
                "independent methodology confirmation)."
            ),
            lane="AIR",
        ),
        QuantityTierRow(
            quantity="C2",
            label="Window-mean regional Tmax anomaly",
            value_display=(
                f"+{air['c2_anomaly']['window_mean_regional_mean_anomaly_k']:.2f} K "
                "(vs own 1991-2020 ±10d climatology)"
            ),
            tier="VALIDATED" if (v3["pass_v3a"] and v3["pass_v3b"]) else "NOT VALIDATED",
            explainer=(
                "Pre-registered V3: agrees with IMD's station-only gridded product "
                f"(ERA5-independent) to {v3['abs_difference_k']:.2f} K on the common "
                f"1° grid with pattern r {v3['pattern_pearson_r']:.3f}. Two products "
                "with different error modes agreeing about the same upstream station "
                "truth."
            ),
            lane="AIR",
        ),
        QuantityTierRow(
            quantity="C3",
            label="Duration (episode)",
            value_display=(
                f"{c3['n_days']} days (ERA5, {c3['criterion']}) vs "
                f"{v4['duration_imd_days']} days (IMD gridded, same criterion)"
            ),
            tier="NOT VALIDATED",
            explainer=(
                "Pre-registered V4a FAILED: the two station-true datasets disagree "
                "(Δ19 days) because a ~0.3-0.5 K systematic moves many cell-days "
                "across the fixed 40 °C/+4.5 K criterion edge. Duration at this "
                "criterion is dataset-fragile — that finding is the result. Always "
                "read duration with its criterion and dataset attached."
            ),
            criterion_dataset=(
                "area ≥5% of bbox land, IMD-style cells (≥40 °C & ≥+4.5 K) · "
                "ERA5 vs IMD gridded"
            ),
            lane="AIR",
        ),
        QuantityTierRow(
            quantity="C4",
            label="Peak-day extent",
            value_display=(
                f"{air['c4_extent']['extent_km2']:,.0f} km² (ERA5 native) vs "
                f"{v4['extent_common_grid_imd_km2']:,.0f} km² (IMD, common 1° grid)"
            ),
            tier="NOT VALIDATED",
            explainer=(
                "Pre-registered V4b FAILED (Δ46% > 30%): same criterion-edge "
                "mechanism as duration. Extent is a criterion-semantics quantity; "
                "it is never quoted without its criterion."
            ),
            criterion_dataset="IMD-style qualifying cells on 2022-04-08 · ERA5 vs IMD gridded",
            lane="AIR",
        ),
        QuantityTierRow(
            quantity="V2",
            label="ERA5↔station consistency",
            value_display=(
                f"bias {v2['median_bias_k']:+.2f} K · RMSD {v2['rmsd_k']:.2f} K · "
                f"r {v2['pearson_r']:.3f} ({v2['n_stations']} stations)"
            ),
            tier="CONSISTENCY NOT CLAIMED",
            explainer=(
                "Pre-registered V2 FAILED its pooled-r criterion (0.728 < 0.85) and "
                "is permanently not-claimed for this event (gate ruling). Bias and "
                "RMSD passed comfortably; the exploratory ≥3-obs diagnosis (r 0.946 "
                "at 36 stations) is labeled exploratory and never upgrades the "
                "verdict."
            ),
            lane="AIR",
        ),
        QuantityTierRow(
            quantity="LST",
            label="Window-mean LST anomaly",
            value_display=(
                f"+{lst['window_mean_bbox_anomaly_k']:.2f} K (Terra ~{view_t:.2f} h local)"
            ),
            tier="CROSS-CHECKED (ceiling)",
            explainer=(
                "Skin temperature, NOT air temperature, and a ~"
                f"{view_t:.2f} h local-solar snapshot BEFORE the diurnal LST peak — "
                "never a daily maximum (the Aqua 13:30 pass is absent for this "
                "window, a measured gap). No in-situ skin-temperature truth exists "
                "in this stack, so LST quantities cap at CROSS-CHECKED."
            ),
            lane="LST",
        ),
        QuantityTierRow(
            quantity="UHI",
            label="Delhi daytime surface urban-rural delta",
            value_display=(
                f"{uhi['window_mean_uhi_k']:+.2f} ± {uhi['window_std_uhi_k']:.2f} K "
                f"({uhi['n_valid_days']} days)"
            ),
            tier="CROSS-CHECKED (ceiling)",
            explainer=(
                "NEGATIVE at the only observed daytime LST time — the urban core "
                "read COOLER than its dry rural ring (sign robust to all "
                "pre-registered sensitivities; Landsat sign-agrees 2 of 3 scenes). "
                "Says nothing about the nighttime or 2 m-air urban roles, which are "
                "explicitly unassessed."
            ),
            lane="LST",
        ),
    ]
    return rows


def _heat_active_detail(event_id: str, event: BenchmarkEvent) -> EventDetail:
    air = _read_json(config.stage_b_dir(event_id) / "air_lane.json")
    val = _read_json(config.stage_b_dir(event_id) / "validation.json")
    lst = _read_json(config.stage_b_dir(event_id) / "lst_lane.json")
    uhi = _read_json(config.stage_b_dir(event_id) / "uhi.json")
    bounds = _read_json(config.assets_dir(event_id) / "bounds.json")
    disp = _DISPLAY[event_id]

    c3 = air["c3_duration"]
    budgets = air["budgets"]["window_mean_regional_anomaly_k"]
    central = budgets["central"]
    # Budget bars: real half-widths in K, scaled against the largest term for
    # bar width only (a visual scaling of the real number, not new data).
    terms_k = {
        "baseline_halves": (
            "Baseline halves (1991-2005 vs 2006-2020)",
            budgets["baseline_halves_half_spread_k"],
            "symmetric",
        ),
        "day_window": (
            "Day-window ±10 → ±15",
            budgets["day_window_pm15_shift_k"],
            "symmetric",
        ),
        "hour_set": (
            "Hour set 06-13 UTC vs 24 h (measured)",
            budgets["hour_set_residual_k"],
            "symmetric",
        ),
        "station_bias": (
            "ERA5 vs station median bias (systematic)",
            budgets["era5_vs_station_median_bias_k"],
            "systematic",
        ),
    }
    max_term = max(abs(v) for _, v, _ in terms_k.values()) or 1.0
    budget_terms = [
        UncertaintyTerm(
            key=key,
            label=label,
            kind=kind,
            value_pct=None,
            factor=None,
            display=f"{value:+.3f} K" if kind == "systematic" else f"±{value:.3f} K",
            bar_fraction=min(abs(value) / max_term, 1.0),
        )
        for key, (label, value, kind) in terms_k.items()
    ]

    layer_meta = [
        HeatLayerMeta(
            key=k,
            label=str(m["label"]),
            colormap=str(m["colormap"]),
            vmin=float(m.get("vmin_k", m.get("vmin_c", 0.0))),
            vmax=float(m.get("vmax_k", m.get("vmax_c", 1.0))),
            unit="K" if "vmin_k" in m else "°C",
            lane=str(m["lane"]),
        )
        for k, m in bounds["layer_meta"].items()
    ]

    heat = HeatBlock(
        peak_tmax_c=air["c1_peak_tmax"]["value_c"],
        peak_date=air["c1_peak_tmax"]["date"],
        window_mean_regional_anomaly_k=central,
        peak_day_extent_km2=air["c4_extent"]["extent_km2"],
        episode=HeatEpisode(
            window_start=air["window"][0],
            window_end=air["window"][1],
            episode_start=c3["start"],
            episode_end=c3["end"],
            episode_days=c3["n_days"],
            criterion=c3["criterion"],
            note=(
                "The canonical 10-day window is the ANALYSIS window (probe-selected, "
                "gate-approved); the episode is the consecutive criterion run "
                "containing it — the upgraded daily-Tmax definition merges the "
                "documented late-March wave into one episode. The two are never "
                "conflated."
            ),
        ),
        quantity_tiers=_heat_quantity_tiers(air, val, lst, uhi),
        lst=HeatLstBlock(
            window_mean_anomaly_k=lst["window_mean_bbox_anomaly_k"],
            view_time_local_h=lst["observation_time_caveat"]["measured_mean_day_view_time_local_h"],
            observation_time_statement=lst["observation_time_caveat"]["statement"],
            composite_baseline_residual_k=lst["anomaly_baseline"]["composite_vs_daily_residual_k_2022"],
            uhi_window_mean_k=uhi["window_mean_uhi_k"],
            uhi_window_std_k=uhi["window_std_uhi_k"],
            uhi_finding=(
                "Daytime SURFACE urban-rural delta is NEGATIVE — the factor engine "
                "carries urban fabric as counter-evidence at the observed time; "
                "nighttime/2 m-air urban roles are explicitly unassessed."
            ),
        ),
        lst_vs_air=(
            "TWO LANES, NEVER CONFLATED: 2 m AIR temperature (ERA5, ISD stations, "
            "IMD gridded — what people experience; VALIDATED claims live here) vs "
            "satellite SKIN temperature (MODIS/Landsat LST — what the surface "
            "radiates; capped at CROSS-CHECKED, observed only at the Terra "
            "morning snapshot). No comparison crosses lanes; ERA5 skin temperature "
            "is used only inside LST product-consistency checks."
        ),
        budget_terms=budget_terms,
        heat_raster=HeatRasterMeta(
            bounds=RasterBounds(**bounds["bounds"]),
            layers=list(bounds["layers"]),
            layer_meta=layer_meta,
            lst_view_time_local_h=float(bounds["lst_view_time_local_h"]),
            rendering=str(bounds["rendering"]),
        ),
    )

    return EventDetail(
        event_id=event_id,
        name=event.name,
        short_name=disp["short_name"],
        planetary_body=event.planetary_body,
        phenomenon_type=event.phenomenon_type,
        lat=event.location.lat,
        lon=event.location.lon,
        status=EventStatus.ACTIVE,
        location_label=disp["region"],
        chips=_chips(event),
        validation_tier=HEAT_TIER_LABEL,
        tier_explainer=(
            "Tiers are PER QUANTITY for this area event (the heat extension of the "
            "tier rubric): the peak temperature (C1) and regional anomaly (C2) are "
            "VALIDATED under pre-registered criteria committed BEFORE any station "
            "data was read; duration (C3) and extent (C4) honestly FAILED their "
            "cross-dataset checks (criterion-edge fragility — the finding); every "
            "LST quantity is capped at CROSS-CHECKED (no in-situ skin truth; Terra "
            "morning snapshot only). No event-level VALIDATED badge exists — that "
            "would overstate C3/C4."
        ),
        references=_references(event),
        heat=heat,
    )
