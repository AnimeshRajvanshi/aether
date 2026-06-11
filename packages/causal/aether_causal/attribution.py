"""Stage B: deterministic field/sector-level source-attribution engine.

Given the Stage A probe (no OGIM point infrastructure anywhere in Turkmenistan),
attribution is capped at field/sector level. This module builds exactly three
ranked hypotheses for the Goturdepe plume from committed data joins only — no
LLM, no randomness, no fabricated entities. Every component value is a documented
heuristic with a rationale; the score is explicitly NOT a calibrated probability.

Inputs (all committed):
  - stage_b_outputs/.../q_estimate.json        (emission rate, wind, plume length)
  - stage_b_outputs/.../wind_location_check.json (upwind source S, centroid C)
  - stage_a_outputs/.../stage_a_report.json     (acquisition date)
  - eval/benchmark/turkmenistan_goturdepe_2022_08_15.yaml (Thorpe cluster reference)
  - packages/causal/.../resources/ogim/ogim_v2.7_goturdepe_region.geojson (OGIM subset)
"""

from __future__ import annotations

# This module is intentionally prose-dense: the per-hypothesis claims, evidence
# statements, assumptions and rationales ARE the honest product, and wrapping them
# mid-sentence harms legibility and editability. We keep them as single readable
# literals and exempt only line-length (E501) here; all other lints still apply.
# ruff: noqa: E501
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aether_eval.loader import load_event_file
from pyproj import Geod
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

from .geometry import BackProjectionWedge, build_wedge
from .schema import (
    Candidate,
    CandidateKind,
    ConfidenceTier,
    EvidenceItem,
    HypothesisSet,
    ScoreComponent,
    SourceHypothesis,
    SourceRef,
)

_GEOD = Geod(ellps="WGS84")
EVENT_ID = "turkmenistan_goturdepe_2022_08_15"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SUBSET_REL = "packages/causal/aether_causal/resources/ogim/ogim_v2.7_goturdepe_region.geojson"
_Q_REL = f"stage_b_outputs/{EVENT_ID}/q_estimate.json"
_WIND_REL = f"stage_b_outputs/{EVENT_ID}/wind_location_check.json"
_STAGE_A_REL = f"stage_a_outputs/{EVENT_ID}/stage_a_report.json"
_BENCH_REL = f"eval/benchmark/{EVENT_ID}.yaml"

GENERATION_METHOD = "rule_based_deterministic_v1"

# --- Documented heuristic scoring design (shown to the user; NOT a probability) ---
# Weights: for attributing a spatially-located plume, the back-projection spatial
# consistency is the primary discriminator; sector type prior and magnitude
# plausibility are supporting priors.
WEIGHTS = {"spatial_consistency": 0.60, "type_prior": 0.25, "magnitude_consistency": 0.15}

# Type-prior basis: Thorpe et al. 2023 attribute THIS cluster to O&G super-emitters;
# an isolated super-emitter-magnitude point source spatially inside an active gas
# field is characteristically O&G (compressor venting, well/processing fugitives,
# flaring). The exact rate is templated from q_central_t_hr at render time.
TYPE_PRIOR_OG = 0.90
TYPE_PRIOR_NON_OG = 0.15
# Magnitude basis: the retrieved rate is well within documented O&G super-emitter
# range and a small multiple of the per-source mean of the Thorpe 163 t/hr /
# 12-source cluster (the rate itself is templated, never hardcoded).
MAGNITUDE_OG = 0.90
MAGNITUDE_NON_OG = 0.40
# Spatial basis: H1 = S sits well inside a LARGE field polygon, so although S's
# position is uncertain (the same uncertainty that justifies H2), that wobble is
# very unlikely to move S across the field boundary — high but NOT 1.0 (S is not a
# fixed point). H2 = an alternative requires displacing the source from S (permitted
# by the localization uncertainty, not favored). H3 = location does not discriminate
# sector (neutral).
SPATIAL_CONTAINED = 0.85
SPATIAL_DISPLACED = 0.30
SPATIAL_SECTOR_NEUTRAL = 0.50

# Confidence ceiling: with NO facility-level OGIM data here, no hypothesis may
# exceed MODERATE (field/sector-level attribution only).
CEILING = ConfidenceTier.MODERATE
_TIER_ORDER = [
    ConfidenceTier.INSUFFICIENT,
    ConfidenceTier.LOW,
    ConfidenceTier.MODERATE,
    ConfidenceTier.HIGH,
]


def _band(score: float) -> ConfidenceTier:
    if score >= 0.80:
        return ConfidenceTier.HIGH
    if score >= 0.55:
        return ConfidenceTier.MODERATE
    if score >= 0.30:
        return ConfidenceTier.LOW
    return ConfidenceTier.INSUFFICIENT


def _capped_tier(score: float) -> tuple[ConfidenceTier, bool]:
    band = _band(score)
    capped = _TIER_ORDER.index(band) > _TIER_ORDER.index(CEILING)
    tier = CEILING if capped else band
    return tier, capped


@dataclass
class _Inputs:
    q: dict[str, Any]
    wind: dict[str, Any]
    stage_a: dict[str, Any]
    wedge: BackProjectionWedge
    subset: list[dict[str, Any]]
    ref_value: float
    ref_unc: float
    ref_sources: int


def _load_inputs(root: Path) -> _Inputs:
    q = json.loads((root / _Q_REL).read_text())
    wind = json.loads((root / _WIND_REL).read_text())
    stage_a = json.loads((root / _STAGE_A_REL).read_text())
    subset = json.loads((root / _SUBSET_REL).read_text())["features"]
    event = load_event_file(root / _BENCH_REL)
    meas = event.known_measurements["emission_rate_metric_tonnes_per_hr"]
    return _Inputs(
        q=q,
        wind=wind,
        stage_a=stage_a,
        wedge=build_wedge(q, wind),
        subset=subset,
        ref_value=float(meas.value),
        ref_unc=float(meas.uncertainty or 0.0),
        ref_sources=int(meas.n_sources or 0),
    )


def _features(subset: list[dict[str, Any]], layer: str) -> list[dict[str, Any]]:
    return [f for f in subset if f["properties"]["ogim_layer"] == layer]


def _field_by_name(subset: list[dict[str, Any]], name: str) -> tuple[dict[str, Any], BaseGeometry]:
    for f in _features(subset, "Oil_and_Natural_Gas_Fields"):
        if f["properties"].get("NAME") == name:
            return f, shape(f["geometry"])
    raise KeyError(f"OGIM field {name!r} not found in committed subset")


def _months_between(iso_a: str, iso_b: str) -> int:
    """Whole months between two ISO date strings (b - a), for the temporal caveat."""
    ya, ma = int(iso_a[:4]), int(iso_a[5:7])
    yb, mb = int(iso_b[:4]), int(iso_b[5:7])
    return (yb - ya) * 12 + (mb - ma)


def build_hypothesis_set(root: Path | None = None) -> HypothesisSet:
    """Construct the three ranked hypotheses deterministically from committed data."""
    root = root or _REPO_ROOT
    inp = _load_inputs(root)
    wedge = inp.wedge
    s_pt = Point(wedge.apex_lon, wedge.apex_lat)
    q_t_hr = float(inp.q["q_central_t_hr"])
    acq_date = inp.stage_a["acquisition_utc"][:10]

    bars_feat, bars_geom = _field_by_name(inp.subset, "BARSAGELMEZ")
    got_feat, got_geom = _field_by_name(inp.subset, "GOTURDEPE")
    bars_id = int(bars_feat["properties"]["OGIM_ID"])
    got_id = int(got_feat["properties"]["OGIM_ID"])
    s_in_bars = bool(bars_geom.contains(s_pt))
    # distance from S to the Goturdepe polygon interior point (geod on rep pt)
    got_rep = got_geom.representative_point()
    _, _, got_rep_m = _GEOD.inv(wedge.apex_lon, wedge.apex_lat, got_rep.x, got_rep.y)

    # nearest VIIRS flaring detection inside the 2-sigma wedge (corroboration only)
    flares = []
    for f in _features(inp.subset, "Natural_Gas_Flaring_Detections"):
        c = shape(f["geometry"]).representative_point()
        rel = wedge.relate(c.y, c.x)
        if rel.within_wedge_2sigma:
            flares.append((rel.distance_km, f, rel))
    flares.sort(key=lambda x: x[0])
    flare_dist, flare_feat, _flare_rel = flares[0]
    flare_id = int(flare_feat["properties"]["OGIM_ID"])
    flare_date = str(flare_feat["properties"]["SRC_DATE"])
    flare_months = _months_between(acq_date, flare_date)
    flare_caveat = (
        f"This VIIRS flaring detection is dated {flare_date}, ~{flare_months} months AFTER "
        f"the {acq_date} plume overpass. It is evidence of PERSISTENT O&G activity in the "
        f"area, NOT evidence about this specific plume, and is NOT the located source."
    )

    # bearing disagreement: centroid C -> S vs the wind upwind azimuth
    c_lon, c_lat = float(inp.wind["centroid_lon"]), float(inp.wind["centroid_lat"])
    cs_bearing, _, _ = _GEOD.inv(c_lon, c_lat, wedge.apex_lon, wedge.apex_lat)
    cs_bearing %= 360.0
    bearing_gap = abs(((cs_bearing - wedge.upwind_azimuth_deg + 180) % 360) - 180)

    ogim_ref = SourceRef(
        dataset=_SUBSET_REL,
        locator=f"ogim_id={bars_id} BARSAGELMEZ",
        ogim_id=bars_id,
        ogim_layer="Oil_and_Natural_Gas_Fields",
    )
    q_ref = SourceRef(dataset=_Q_REL, locator=f"q_central_t_hr={q_t_hr:.3f}")
    wind_ref = SourceRef(dataset=_WIND_REL, locator="source_lat,source_lon (upwind source S)")

    # ---- shared assumptions (first-class) ----
    half_angle_assumption = (
        f"WEAKEST LINK: the wedge half-angle ({wedge.half_angle_1sigma_deg:.1f} deg at 1-sigma, "
        f"{wedge.half_angle_2sigma_deg:.1f} deg at 2-sigma) is approximated from the ERA5 wind "
        f"SPEED 1-sigma ({wedge.u10_sigma_ms:.2f} m/s) treated as an isotropic wind-vector "
        f"uncertainty — NOT a measured wind-direction variance. Sub-field localization rests on "
        f"this approximation."
    )
    bearing_assumption = (
        f"The bearing from the plume centroid to the back-projected source S ({cs_bearing:.0f} deg) "
        f"disagrees with the ERA5 upwind azimuth ({wedge.upwind_azimuth_deg:.0f} deg) by "
        f"~{bearing_gap:.0f} deg. This is within the 2-sigma wedge but widens source-localization "
        f"uncertainty; sub-field placement should not be over-trusted."
    )
    global_assumptions = [
        f"Steady ERA5 wind over the ~{wedge.transit_time_s / 3600:.2f} h plume transit "
        f"(transit = plume length {wedge.plume_length_m:.0f} m / U_eff {wedge.u_eff_ms:.2f} m/s).",
        half_angle_assumption,
        bearing_assumption,
        "OGIM field boundaries are accepted as drawn (Barsagelmez SRC_DATE 2014-01-01); field "
        "extent/accuracy is not independently verified here.",
        "Sector prior favoring O&G rests on Thorpe et al. 2023 attributing this cluster to O&G "
        "super-emitters and on the active-gas-field context.",
        "HEADLINE: OGIM v2.7 contains NO well, compressor, processing, tank-battery or equipment "
        "records anywhere in Turkmenistan, so facility-level attribution is impossible; all "
        "hypotheses are field/sector-level and capped at MODERATE confidence.",
    ]

    def comp(name: str, value: float, rationale: str) -> ScoreComponent:
        return ScoreComponent(name=name, value=value, weight=WEIGHTS[name], rationale=rationale)

    hyps: list[SourceHypothesis] = []

    # ---------------- H1: O&G within BARSAGELMEZ field ----------------
    h1_components = [
        comp(
            "spatial_consistency",
            SPATIAL_CONTAINED if s_in_bars else 0.5,
            f"The back-projected upwind source S sits well inside the BARSAGELMEZ field polygon "
            f"(point-in-polygon = {s_in_bars}; field area {bars_feat['properties'].get('AREA_KM2')} "
            f"km^2). S's exact position IS uncertain (the ~{bearing_gap:.0f} deg centroid/upwind "
            f"bearing gap and the speed-derived wedge — the same uncertainty H2 rests on), but "
            f"because S lies well "
            f"within such a large field, that wobble is very unlikely to move it across the field "
            f"boundary. High, not 1.0.",
        ),
        comp(
            "type_prior",
            TYPE_PRIOR_OG,
            f"Active oil & gas field; ~{q_t_hr:.0f} t/hr point sources here are characteristically "
            f"O&G (Thorpe 2023 attributes this cluster to O&G).",
        ),
        comp(
            "magnitude_consistency",
            MAGNITUDE_OG,
            f"~{q_t_hr:.0f} t/hr is within documented O&G super-emitter range and "
            f"~{q_t_hr / (inp.ref_value / inp.ref_sources):.0f}x the per-source mean of the "
            f"Thorpe {inp.ref_value:.0f} t/hr / {inp.ref_sources}-source cluster.",
        ),
    ]
    h1_score = round(sum(c.value * c.weight for c in h1_components), 4)
    h1_tier, h1_capped = _capped_tier(h1_score)
    hyps.append(
        SourceHypothesis(
            id="H1",
            rank=1,
            candidate=Candidate(
                kind=CandidateKind.OGIM_FIELD,
                descriptor="O&G operations within the BARSAGELMEZ oil & gas field",
                ogim_layer="Oil_and_Natural_Gas_Fields",
                ogim_id=bars_id,
                ogim_name="BARSAGELMEZ",
                operator=bars_feat["properties"].get("OPERATOR"),
            ),
            claim=(
                f"The ~{q_t_hr:.0f} t/hr methane plume most plausibly originates from oil & gas "
                f"operations within the BARSAGELMEZ field, inside which the back-projected upwind "
                f"source falls. Field/sector-level only: no specific facility can be named because "
                f"OGIM has no point infrastructure in this region."
            ),
            confidence_tier=h1_tier,
            confidence_rationale=(
                f"Heuristic score {h1_score:.2f} (band {_band(h1_score).value}) CAPPED to "
                f"{h1_tier.value}: facility-level attribution is impossible (no OGIM point data), so "
                f"MODERATE field/sector-level is the highest defensible tier — NOT high-confidence "
                f"facility attribution."
            )
            if h1_capped
            else f"Heuristic score {h1_score:.2f}, band {_band(h1_score).value}.",
            score=h1_score,
            score_components=h1_components,
            evidence=[
                EvidenceItem(
                    kind="spatial_containment",
                    statement=(
                        f"The back-projected upwind source S ({wedge.apex_lat:.4f} N, "
                        f"{wedge.apex_lon:.4f} E) lies inside the BARSAGELMEZ field polygon "
                        f"(OGIM_ID {bars_id}, {bars_feat['properties'].get('AREA_KM2')} km^2)."
                    ),
                    source=ogim_ref,
                ),
                EvidenceItem(
                    kind="field_context",
                    statement=(
                        f"BARSAGELMEZ is an active OIL & GAS field (OGIM RESERVOIR_TYPE "
                        f"'{bars_feat['properties'].get('RESERVOIR_TYPE')}', SRC_DATE "
                        f"{bars_feat['properties'].get('SRC_DATE')})."
                    ),
                    source=ogim_ref,
                ),
                EvidenceItem(
                    kind="magnitude_range",
                    statement=(
                        f"Emission rate {q_t_hr:.1f} t/hr (OURS-CAL) is a plausible single-source "
                        f"super-emitter magnitude within the Thorpe {inp.ref_value:.0f} +/- "
                        f"{inp.ref_unc:.0f} t/hr, {inp.ref_sources}-source cluster."
                    ),
                    source=q_ref,
                ),
                EvidenceItem(
                    kind="flaring_corroboration",
                    statement=(
                        f"A VIIRS flaring detection (OGIM_ID {flare_id}, 'UPSTREAM OIL') lies "
                        f"{flare_dist:.1f} km from S within the 2-sigma wedge, corroborating ONGOING "
                        f"upstream O&G activity in the area."
                    ),
                    source=SourceRef(
                        dataset=_SUBSET_REL,
                        locator=f"ogim_id={flare_id} flaring",
                        ogim_id=flare_id,
                        ogim_layer="Natural_Gas_Flaring_Detections",
                    ),
                    temporal_caveat=flare_caveat,
                ),
            ],
            assumptions=[
                "Wind back-projection places the source upwind; S (top-5%-upwind plume pixels) is the "
                "best source estimate.",
                half_angle_assumption,
                bearing_assumption,
            ],
            counter_considerations=[
                "No specific facility can be identified — OGIM has zero wells/compressors/processing "
                "in Turkmenistan; this is field-level attribution only.",
                f"Sub-field placement is weakly constrained (see the {bearing_gap:.0f} deg bearing gap "
                f"and the speed-derived wedge); H2 cannot be excluded.",
            ],
            falsification=(
                "A facility-resolved inventory (or higher-resolution back-projection) placing the "
                "source outside BARSAGELMEZ, or evidence the plume originates from a non-O&G process, "
                "would falsify this."
            ),
            generation_method=GENERATION_METHOD,
        )
    )

    # ---------------- H2: alternative location under localization uncertainty -------
    h2_components = [
        comp(
            "spatial_consistency",
            SPATIAL_DISPLACED,
            f"Requires displacing the true source from S (which is inside BARSAGELMEZ). The "
            f"localization uncertainty — speed-derived wedge + ~{bearing_gap:.0f} deg bearing gap — "
            f"permits an alternative location elsewhere in BARSAGELMEZ or in adjacent GOTURDEPE "
            f"(S not contained in GOTURDEPE; ~{got_rep_m / 1000:.0f} km to its interior), but does "
            f"not favor it.",
        ),
        comp("type_prior", TYPE_PRIOR_OG, "Still O&G (same sector prior as H1)."),
        comp("magnitude_consistency", MAGNITUDE_OG, "Same magnitude plausibility as H1."),
    ]
    h2_score = round(sum(c.value * c.weight for c in h2_components), 4)
    h2_tier, _ = _capped_tier(h2_score)
    hyps.append(
        SourceHypothesis(
            id="H2",
            rank=2,
            candidate=Candidate(
                kind=CandidateKind.OGIM_FIELD,
                descriptor="A different O&G source within BARSAGELMEZ or the adjacent GOTURDEPE field",
                ogim_layer="Oil_and_Natural_Gas_Fields",
                ogim_id=got_id,
                ogim_name="GOTURDEPE",
                operator=got_feat["properties"].get("OPERATOR"),
            ),
            claim=(
                "The source may instead be elsewhere within BARSAGELMEZ or in the adjacent GOTURDEPE "
                "field — an alternative the source-localization uncertainty cannot exclude. Still O&G, "
                "lower confidence than H1."
            ),
            confidence_tier=h2_tier,
            confidence_rationale=(
                f"Heuristic score {h2_score:.2f}, band {_band(h2_score).value}: a residual-uncertainty "
                f"alternative, below H1 by spatial consistency."
            ),
            score=h2_score,
            score_components=h2_components,
            evidence=[
                EvidenceItem(
                    kind="localization_uncertainty",
                    statement=(
                        f"The bearing from the plume centroid to S ({cs_bearing:.0f} deg) disagrees with "
                        f"the ERA5 upwind azimuth ({wedge.upwind_azimuth_deg:.0f} deg) by "
                        f"~{bearing_gap:.0f} deg, and the wedge half-angle is speed-approximated — so an "
                        f"alternative in-field/adjacent location is within uncertainty."
                    ),
                    source=wind_ref,
                ),
                EvidenceItem(
                    kind="adjacent_field",
                    statement=(
                        f"GOTURDEPE (OGIM_ID {got_id}) is an adjacent OIL & GAS field; S is NOT inside it "
                        f"(~{got_rep_m / 1000:.0f} km to its interior point), so it is a weaker but "
                        f"non-excludable alternative."
                    ),
                    source=SourceRef(
                        dataset=_SUBSET_REL,
                        locator=f"ogim_id={got_id} GOTURDEPE",
                        ogim_id=got_id,
                        ogim_layer="Oil_and_Natural_Gas_Fields",
                    ),
                ),
            ],
            assumptions=[
                "Same back-projection assumptions as H1; this hypothesis specifically leans on their "
                "uncertainty being non-negligible.",
                half_angle_assumption,
            ],
            counter_considerations=[
                "S is contained in BARSAGELMEZ, not GOTURDEPE — this alternative is disfavored "
                "spatially and exists only because localization is weak.",
            ],
            falsification=(
                "Tighter localization (measured wind-direction variance or plume-resolved inversion) "
                "confirming S well inside BARSAGELMEZ would further demote this."
            ),
            generation_method=GENERATION_METHOD,
        )
    )

    # ---------------- H3: non-O&G (natural seep / other sector) ----------------
    h3_components = [
        comp(
            "spatial_consistency",
            SPATIAL_SECTOR_NEUTRAL,
            "The back-projected location does not discriminate sector — any source type at that "
            "point is equally consistent spatially — so spatial is set neutral; the discriminator "
            "against a non-O&G source is the type prior.",
        ),
        comp(
            "type_prior",
            TYPE_PRIOR_NON_OG,
            f"Natural geologic methane seeps exist in the South Caspian region, but an isolated "
            f"~{q_t_hr:.0f} t/hr point source spatially coincident with an active gas field is far "
            f"more consistent with O&G; non-O&G is not excluded but is a low prior.",
        ),
        comp(
            "magnitude_consistency",
            MAGNITUDE_NON_OG,
            f"A ~{q_t_hr:.0f} t/hr natural point seep is possible but high; magnitude weakly "
            f"disfavors it.",
        ),
    ]
    h3_score = round(sum(c.value * c.weight for c in h3_components), 4)
    h3_tier, _ = _capped_tier(h3_score)
    hyps.append(
        SourceHypothesis(
            id="H3",
            rank=3,
            candidate=Candidate(
                kind=CandidateKind.SECTOR,
                descriptor="Non-O&G source (natural geologic seep or other sector)",
            ),
            claim=(
                "A non-O&G origin (e.g. a natural geologic methane seep) is possible but unlikely given "
                "the active-gas-field context; ranked down but not dismissed."
            ),
            confidence_tier=h3_tier,
            confidence_rationale=(
                f"Heuristic score {h3_score:.2f}, band {_band(h3_score).value}: stated for completeness; "
                f"the active-field context strongly disfavors it but it is not excluded."
            ),
            score=h3_score,
            score_components=h3_components,
            evidence=[
                EvidenceItem(
                    kind="sector_context",
                    statement=(
                        "The back-projected source lies inside an active O&G field, which argues against "
                        "a non-O&G origin; however no in-situ measurement excludes a natural seep."
                    ),
                    source=ogim_ref,
                ),
            ],
            assumptions=[
                "Sector priors are heuristic, not site-measured; a non-O&G source cannot be excluded "
                "without isotopic or in-situ confirmation.",
            ],
            counter_considerations=[
                "No OGIM or other committed dataset evidences a natural seep at this location; this "
                "hypothesis is included for honesty, not because of positive evidence.",
            ],
            falsification=(
                "Isotopic (delta-13C) or in-situ sampling indicating thermogenic vs biogenic/geologic "
                "origin would resolve sector."
            ),
            generation_method=GENERATION_METHOD,
        )
    )

    return HypothesisSet(
        event_id=EVENT_ID,
        phenomenon="Goturdepe/Barsagelmez methane plume (EMIT 2022-08-15)",
        generated_method=GENERATION_METHOD,
        headline_finding=(
            "OGIM v2.7 contains NO facility-level point infrastructure (wells, compressor stations, "
            "gathering/processing, tank batteries, equipment) anywhere in Turkmenistan. Source "
            "attribution is therefore capped at FIELD/SECTOR level — facility-level attribution is "
            "impossible with available data. This is a first-class finding, not a gap."
        ),
        scoring_disclaimer=(
            "Scores are a documented additive heuristic (weighted components shown), NOT calibrated "
            "probabilities. We have no calibration basis for probabilities; rely on the qualitative "
            "tiers and the visible component rationales."
        ),
        confidence_cap=(
            f"No hypothesis may exceed {CEILING.value.upper()} confidence: with no OGIM point data, "
            f"the best defensible claim is field/sector-level. H1 is field-level MODERATE, not "
            f"facility-level HIGH."
        ),
        plume_summary={
            "emission_rate_ours_cal_t_hr": f"{q_t_hr:.3f}",
            "upwind_source_S": f"{wedge.apex_lat:.5f} N, {wedge.apex_lon:.5f} E",
            "upwind_azimuth_deg": f"{wedge.upwind_azimuth_deg:.1f}",
            "wedge_half_angle_1sigma_deg": f"{wedge.half_angle_1sigma_deg:.1f}",
            "wedge_half_angle_2sigma_deg": f"{wedge.half_angle_2sigma_deg:.1f}",
            "transit_time_h": f"{wedge.transit_time_s / 3600:.2f}",
            "search_radius_km": f"{wedge.search_radius_km:.0f}",
        },
        global_assumptions=global_assumptions,
        hypotheses=hyps,
        provenance={
            "ogim_subset": _SUBSET_REL,
            "ogim_doi": "10.5281/zenodo.15103476",
            "q_estimate": _Q_REL,
            "wind_location": _WIND_REL,
            "benchmark": _BENCH_REL,
            "thorpe_reference": "Thorpe et al. 2023, Sci. Adv. 9 eadh2391, doi:10.1126/sciadv.adh2391",
        },
    )


# =========================================================================== #
# Sprint 7 — facility-level attribution for DENSE-coverage events.
#
# Goturdepe (above) had ZERO OGIM point infrastructure -> field/sector-level only.
# The Permian has dense facility coverage (10,744 wells in the regional subset),
# so the engine can attempt facility-level attribution for the FIRST TIME. This is
# a NEW capability of the SAME engine (shared schema, wedge, scoring primitives,
# render, no-fabrication guard) — selected by what the OGIM data contains, NOT a
# per-event fork. build_hypothesis_set (Goturdepe) is untouched + byte-identical.
#
# The honesty challenge here is the OPPOSITE of Goturdepe's: not "no data" but
# "too much, spatially ambiguous data". Confidence reflects DISCRIMINATION POWER,
# never proximity alone; no facility reaches HIGH unless the evidence isolates it.
# =========================================================================== #


@dataclass(frozen=True)
class FacilityEvent:
    """Per-event config for facility-level attribution — paths + plume-scale radius."""

    event_id: str
    subset_rel: str
    region_label: str
    # Search radius appropriate to the plume scale: the source of a compact plume
    # sits at S +/- the localization error, NOT tens of km upwind. Documented.
    search_radius_km: float
    phenomenon: str
    # localization provenance note (Permian's S is NASA-footprint-anchored).
    localization_note: str


FACILITY_EVENTS: dict[str, FacilityEvent] = {
    "permian_basin_2022": FacilityEvent(
        event_id="permian_basin_2022",
        subset_rel="packages/causal/aether_causal/resources/ogim/ogim_v2.7_permian_basin_region.geojson",
        region_label="Permian Basin / Carlsbad NM",
        # ~3.3 km plume; S localized to ~+/-1 km (centroid->S back-projection was 0.9 km).
        search_radius_km=2.0,
        phenomenon="Permian/Carlsbad methane plume (EMIT 2022-08-26)",
        localization_note=(
            "SEGMENTATION-DEPENDENCE: the source point S is derived from a "
            "NASA-anchored plume footprint (NASA L2B CH4PLM complex 000524), NOT a "
            "fully self-derived localization. Goturdepe's S came end-to-end from our "
            "own retrieval; this attribution inherits NASA's plume location. Treat the "
            "apex accordingly."
        ),
    ),
}

# --- Moderate-source priors (documented; re-derived for the ~0.85 t/hr regime) ---
# Goturdepe's priors were built for a ~27 t/hr SUPER-emitter. The Permian retrieval
# is ~0.85 t/hr [0.57-1.15] — a MODERATE point source. Basis:
#   * Duren et al. 2019, Nature 575, 180-184, doi:10.1038/s41586-019-1720-3 — O&G
#     point-source emission rates are strongly heavy-tailed; the great majority of
#     detected sources sit far below the super-emitter scale.
#   * Cusworth et al. 2021, ES&T Lett 8, 567-573, doi:10.1021/acs.estlett.1c00173 —
#     Permian point sources resolved at facility scale, and strongly intermittent.
# A ~0.85 t/hr (850 kg/hr) source is therefore plausibly a SINGLE well (tank/casing
# venting, an unlit/under-performing flare, a liquids-unloading event), a small
# equipment leak, or a tank battery — it does NOT require a large compressor or
# processing plant. Consequence: facility-TYPE barely discriminates among the well
# candidates, which is itself a discrimination-limiting finding.
FAC_SECTOR_PRIOR_OG = 0.90  # the SECTOR is overwhelmingly O&G (dense active basin)
FAC_TYPE_WELL = 0.85  # a well is a fully plausible moderate-source emitter
FAC_MAGNITUDE_MODERATE = 0.80  # 0.85 t/hr squarely in the moderate point-source regime
FAC_TYPE_NON_OG = 0.08
FAC_MAGNITUDE_NON_OG = 0.30
# Spatial values reflect that even the NEAREST-CENTERLINE candidate is not isolated.
# (Stage C review correction) The nearest-centerline pad is NOT the distance-closest
# candidate, and its only discriminating margin is ANGULAR — which rests on the
# self-declared weakest link (the speed-derived half-angle), with distance margins
# (~0.3-1.6 km) comparable to S's ~1 km NASA-inherited positional uncertainty. So the
# favored ranking is REAL but NOT ESTABLISHED: the spatial value was lowered from the
# original 0.70 (which had been justified by a now-removed, false "closer in both
# distance AND angle" claim) to 0.50, and facility hypotheses are capped at LOW.
FAC_SPATIAL_NEAREST = 0.50  # nearest-CENTERLINE only; margin within the localization noise
FAC_SPATIAL_OTHER = 0.30  # an alternative in-wedge well; cannot be excluded
FAC_SPATIAL_NEUTRAL = 0.50  # location does not discriminate sector (for non-O&G)

# Facility-event confidence ceiling: LOW. When the discriminating margin is within the
# stated localization uncertainty, the data can RANK candidates but cannot ESTABLISH
# one — so no facility hypothesis may exceed LOW (cf. Goturdepe's MODERATE, which rests
# on S sitting inside a 133 km^2 field polygon, robust to the same uncertainty).
FAC_CEILING = ConfidenceTier.LOW

_WELL_LAYER = "Oil_and_Natural_Gas_Wells"
_RENDER_CAP = 8  # cap the rendered ranked candidate list; total is always stated


def _fac_capped_tier(score: float) -> tuple[ConfidenceTier, bool]:
    """Band the score, then cap at FAC_CEILING (LOW) for facility hypotheses."""
    band = _band(score)
    capped = _TIER_ORDER.index(band) > _TIER_ORDER.index(FAC_CEILING)
    return (FAC_CEILING if capped else band), capped


def _facility_candidates(
    subset: list[dict[str, Any]], wedge: BackProjectionWedge
) -> tuple[list[dict[str, Any]], int, int]:
    """Wells within the 2-sigma wedge, ranked by (angular dev, distance).

    Returns (ranked_candidates, n_within_2sigma, n_within_1sigma). Each ranked
    entry carries its real OGIM properties + the geometric relation — nothing
    invented.
    """
    ranked: list[dict[str, Any]] = []
    n1 = 0
    for f in _features(subset, _WELL_LAYER):
        pt = shape(f["geometry"]).representative_point()
        rel = wedge.relate(pt.y, pt.x)
        if not rel.within_wedge_2sigma:
            continue
        if rel.within_wedge_1sigma:
            n1 += 1
        ranked.append({
            "props": f["properties"],
            "dev": rel.angular_dev_from_upwind_deg,
            "dist_km": rel.distance_km,
        })
    ranked.sort(key=lambda c: (c["dev"], c["dist_km"]))
    return ranked, len(ranked), n1


def build_facility_hypothesis_set(event_id: str, root: Path | None = None) -> HypothesisSet:
    """Facility-level, discrimination-honest attribution for a dense-coverage event.

    Deterministic; reads only committed inputs; names only real OGIM records.
    """
    if event_id not in FACILITY_EVENTS:
        raise KeyError(f"no facility-attribution config for {event_id!r}")
    cfg = FACILITY_EVENTS[event_id]
    root = root or _REPO_ROOT

    q = json.loads((root / f"stage_b_outputs/{event_id}/q_estimate.json").read_text())
    wind = json.loads((root / f"stage_b_outputs/{event_id}/wind_location_check.json").read_text())
    stage_a = json.loads((root / f"stage_a_outputs/{event_id}/stage_a_report.json").read_text())
    subset = json.loads((root / cfg.subset_rel).read_text())["features"]
    acq_date = stage_a["acquisition_utc"][:10]
    q_t_hr = float(q["q_central_t_hr"])
    q_lo, q_hi = float(q["q_low_t_hr"]), float(q["q_high_t_hr"])

    wedge = build_wedge(q, wind, search_radius_km=cfg.search_radius_km)
    ranked, n_2sigma, n_1sigma = _facility_candidates(subset, wedge)
    if not ranked:
        raise RuntimeError(f"{event_id}: no facility candidates in the wedge — unexpected")

    top = ranked[0]
    top_props = top["props"]
    top_id = int(top_props["OGIM_ID"])
    top_name = str(top_props.get("FAC_NAME"))  # exact OGIM record name (verifiable)
    top_operator = str(top_props.get("OPERATOR"))

    # The pad/lease is the FAC_NAME prefix before the well-number suffix (" #..."):
    # OGIM lists each completion as its own record ("LEASE NAME #224H", "... #1"),
    # so wells on one lease/pad share this prefix. Group by lease prefix + operator
    # so the "pad holds N co-located completions" claim is honest (not 1-per-name).
    def _lease(props: dict[str, Any]) -> str:
        return str(props.get("FAC_NAME", "")).split(" #")[0].strip()

    lease_name = _lease(top_props)
    pad_members = [
        c for c in ranked
        if _lease(c["props"]) == lease_name and str(c["props"].get("OPERATOR")) == top_operator
    ]
    n_pad = len(pad_members)

    # The DISTANCE-closest candidate is NOT necessarily the nearest-centerline one
    # (ranked is sorted by angle first). Compute it explicitly so comparative claims
    # are truthful: the nearest-centerline pad is favored by ANGLE, but a different
    # well may be physically closer to S.
    nd = min(ranked, key=lambda c: c["dist_km"])
    nd_name = str(nd["props"].get("FAC_NAME"))
    nd_id = int(nd["props"]["OGIM_ID"])

    # nearest VIIRS flaring detection in the wedge (corroboration only; dated)
    flare_ev = None
    for f in _features(subset, "Natural_Gas_Flaring_Detections"):
        c = shape(f["geometry"]).representative_point()
        rel = wedge.relate(c.y, c.x)
        if rel.within_wedge_2sigma:
            fid = int(f["properties"]["OGIM_ID"])
            fdate = str(f["properties"].get("SRC_DATE"))
            fmonths = _months_between(acq_date, fdate)
            flare_ev = EvidenceItem(
                kind="flaring_corroboration",
                statement=(
                    f"A VIIRS flaring detection (OGIM_ID {fid}) lies {rel.distance_km:.1f} km from S "
                    f"within the wedge, corroborating active O&G in the area."
                ),
                source=SourceRef(dataset=cfg.subset_rel, locator=f"ogim_id={fid} flaring",
                                 ogim_id=fid, ogim_layer="Natural_Gas_Flaring_Detections"),
                temporal_caveat=(
                    f"This detection is dated {fdate}, ~{fmonths} months AFTER the {acq_date} "
                    f"overpass — evidence of PERSISTENT activity, NOT about this plume, and NOT the "
                    f"located source. (Permian large emitters are intermittent: Cusworth et al. 2021, "
                    f"doi:10.1021/acs.estlett.1c00173.)"
                ),
            )
            break

    q_ref = SourceRef(dataset=f"stage_b_outputs/{event_id}/q_estimate.json",
                      locator=f"q_central_t_hr={q_t_hr:.3f}")
    subset_ref = SourceRef(dataset=cfg.subset_rel, locator=f"within-wedge well count (n={n_2sigma})")

    half_angle_assumption = (
        f"WEAKEST LINK: the wedge half-angle ({wedge.half_angle_1sigma_deg:.1f} deg at 1-sigma, "
        f"{wedge.half_angle_2sigma_deg:.1f} deg at 2-sigma) is approximated from the ERA5 wind SPEED "
        f"1-sigma ({wedge.u10_sigma_ms:.2f} m/s at |U10| {wedge.wind_speed_ms:.2f} m/s) treated as an "
        f"isotropic wind-vector uncertainty — NOT a measured wind-direction variance. The low wind "
        f"speed makes this wedge WIDE, which is the core reason facility-level isolation fails."
    )
    moderate_regime_assumption = (
        f"MODERATE-SOURCE REGIME: the retrieved rate (~{q_t_hr:.2f} t/hr [{q_lo:.2f}-{q_hi:.2f}]) is a "
        f"moderate point source, consistent with a SINGLE well, small equipment, or a tank battery — "
        f"not necessarily a large facility (Duren et al. 2019, doi:10.1038/s41586-019-1720-3; Cusworth "
        f"et al. 2021, doi:10.1021/acs.estlett.1c00173). So facility TYPE barely discriminates among "
        f"the well candidates; spatial proximity is the only real discriminator, and it is weak here."
    )
    global_assumptions = [
        f"Steady ERA5 wind over the ~{wedge.transit_time_s / 3600:.2f} h plume transit.",
        half_angle_assumption,
        cfg.localization_note,
        f"Plume-scale search radius {cfg.search_radius_km:.0f} km (the source of a compact ~3.3 km "
        f"plume sits at S +/- ~1 km, not tens of km upwind); wells beyond it are not candidates for "
        f"THIS plume.",
        moderate_regime_assumption,
        f"HEADLINE (dense-coverage discrimination): {n_2sigma} O&G wells fall within the plume-scale "
        f"2-sigma wedge ({n_1sigma} within 1-sigma). The nearest-CENTERLINE candidate (the {lease_name} "
        f"lease/pad, {n_pad} co-located completions, {top['dist_km']:.1f} km from S at {top['dev']:.1f} "
        f"deg) is FAVORED but NOT isolated: its only discriminating margin is angular, and a DIFFERENT "
        f"well ({nd_name}, OGIM_ID {nd_id}) is actually distance-closest at {nd['dist_km']:.1f} km. The "
        f"data RANKS candidates but cannot ESTABLISH one; no facility exceeds LOW. This is the "
        f"dense-coverage analogue of Goturdepe's sparse finding.",
    ]

    def comp(name: str, value: float, rationale: str) -> ScoreComponent:
        return ScoreComponent(name=name, value=value, weight=WEIGHTS[name], rationale=rationale)

    hyps: list[SourceHypothesis] = []

    # ---------------- H1: nearest-centerline well pad (favored, not isolated) -------
    h1_components = [
        comp("spatial_consistency", FAC_SPATIAL_NEAREST,
             f"The {lease_name} lease/pad is the nearest-CENTERLINE candidate ({top['dev']:.1f} deg off "
             f"the upwind azimuth, vs >=13 deg for every non-pad well), {top['dist_km']:.1f} km from S. "
             f"It is NOT the distance-closest well, however: {nd_name} (OGIM_ID {nd_id}) is closer at "
             f"{nd['dist_km']:.1f} km (though {nd['dev']:.0f} deg off-centerline). So the ONLY "
             f"discriminating margin is angular — and angular uncertainty is the self-declared weakest "
             f"link (speed-derived half-angle {wedge.half_angle_2sigma_deg:.0f} deg at 2-sigma), while "
             f"the distance margins (~{nd['dist_km']:.1f}-1.6 km) are comparable to S's ~1 km "
             f"NASA-inherited positional uncertainty. The favored ranking is REAL but NOT ESTABLISHED."),
        comp("type_prior", FAC_TYPE_WELL,
             "An active O&G well in a dense producing basin; a plausible moderate-source emitter. "
             "Type barely discriminates at this magnitude (see assumptions)."),
        comp("magnitude_consistency", FAC_MAGNITUDE_MODERATE,
             f"~{q_t_hr:.2f} t/hr is squarely in the moderate point-source regime — consistent with "
             f"single-well venting/leak (Duren 2019; Cusworth 2021), neither too small nor "
             f"super-emitter scale."),
    ]
    h1_score = round(sum(c.value * c.weight for c in h1_components), 4)
    h1_tier, h1_capped = _fac_capped_tier(h1_score)
    pad_id_list = ", ".join(str(int(c["props"]["OGIM_ID"])) for c in pad_members[:6])
    hyps.append(SourceHypothesis(
        id="H1", rank=1,
        candidate=Candidate(
            kind=CandidateKind.OGIM_FACILITY,
            descriptor=f"The {lease_name} lease/pad (operator {top_operator}; nearest completion OGIM_ID {top_id}) — nearest-centerline candidate",
            ogim_layer=_WELL_LAYER, ogim_id=top_id, ogim_name=top_name, operator=top_operator,
        ),
        claim=(
            f"The ~{q_t_hr:.2f} t/hr plume's nearest-CENTERLINE candidate is the {lease_name} lease/pad "
            f"({top_operator}), ~{top['dist_km']:.1f} km from the back-projected source S and "
            f"~{top['dev']:.1f} deg off the wind azimuth (vs >=13 deg for every non-pad well). It is NOT "
            f"the distance-closest well — {nd_name} (OGIM_ID {nd_id}) is closer at {nd['dist_km']:.1f} km. "
            f"Pad/operator-level RANKING only: the pad holds {n_pad} co-located completions, the specific "
            f"well CANNOT be isolated, and the other {n_2sigma - n_pad} in-wedge wells cannot be excluded."
        ),
        confidence_tier=h1_tier,
        confidence_rationale=(
            f"Heuristic score {h1_score:.2f} (band {_band(h1_score).value})"
            + (f" CAPPED to {h1_tier.value.upper()}: the only discriminating margin is angular, the "
               f"angular uncertainty is the self-declared weakest link, and the distance margins are "
               f"comparable to S's ~1 km NASA-inherited positional uncertainty — so the data RANKS this "
               f"pad first but cannot ESTABLISH it. LOW, not MODERATE (contrast Goturdepe, whose "
               f"MODERATE rests on S inside a 133 km^2 field, robust to that uncertainty)." if h1_capped
               else ": ranked first by angular proximity, but LOW — margins are within the localization "
                    "noise, so the ranking is real but not established.")
        ),
        score=h1_score, score_components=h1_components,
        evidence=[
            EvidenceItem(
                kind="spatial_proximity",
                statement=(
                    f"The {lease_name} lease/pad's nearest completion (OGIM_ID {top_id}, FAC_TYPE "
                    f"{top_props.get('FAC_TYPE')}, status {top_props.get('OGIM_STATUS')}) is "
                    f"{top['dist_km']:.1f} km from S at {top['dev']:.1f} deg off-centerline."
                ),
                source=SourceRef(dataset=cfg.subset_rel, locator=f"ogim_id={top_id} {top_name}",
                                 ogim_id=top_id, ogim_layer=_WELL_LAYER),
            ),
            EvidenceItem(
                kind="pad_multiplicity",
                statement=(
                    f"The {lease_name} lease/pad has {n_pad} co-located completions inside the wedge "
                    f"(OGIM_IDs {pad_id_list}{'...' if n_pad > 6 else ''}, operator {top_operator}); "
                    f"a single overpass cannot resolve which one emits."
                ),
                source=SourceRef(dataset=cfg.subset_rel, locator=f"ogim_id={top_id} pad",
                                 ogim_id=top_id, ogim_layer=_WELL_LAYER),
            ),
            EvidenceItem(
                kind="magnitude_range",
                statement=(
                    f"Emission rate {q_t_hr:.2f} t/hr [{q_lo:.2f}-{q_hi:.2f}] (NASA-footprint-anchored) "
                    f"is a moderate single-source magnitude, well below super-emitter scale."
                ),
                source=q_ref,
            ),
            *( [flare_ev] if flare_ev else [] ),
        ],
        assumptions=[
            "Wind back-projection places the source upwind; S (NASA-footprint-anchored upwind tip) is "
            "the best source estimate.",
            half_angle_assumption,
            cfg.localization_note,
        ],
        counter_considerations=[
            f"{nd_name} (OGIM_ID {nd_id}) is physically CLOSER to S ({nd['dist_km']:.1f} km) than this "
            f"pad — the pad wins only on angle, not distance.",
            f"{n_2sigma - n_pad} other O&G wells fall within the same wedge and cannot be excluded; "
            f"the data ranks the pad first but does not isolate it.",
            "The specific emitting well on the pad is unresolved; even pad-level rests on a wide, "
            "speed-derived wedge and a NASA-anchored source point.",
        ],
        falsification=(
            "A facility-resolved overpass (or measured wind-direction variance tightening the wedge) "
            "placing the source on a different pad/well, or off this pad entirely, would falsify this."
        ),
        generation_method=GENERATION_METHOD,
    ))

    # ---------------- H2: the non-pad in-wedge wells (indistinguishable) ---
    non_pad = [c for c in ranked if c not in pad_members]
    n_other = len(non_pad)
    alt = non_pad[: _RENDER_CAP]
    alt_lines = "; ".join(
        f"{c['props'].get('FAC_NAME')} (OGIM_ID {int(c['props']['OGIM_ID'])}, "
        f"{c['dist_km']:.1f} km, {c['dev']:.0f} deg)" for c in alt
    )
    h2_components = [
        comp("spatial_consistency", FAC_SPATIAL_OTHER,
             f"Any of the {n_other} in-wedge wells NOT on the {lease_name} lease/pad could be the source; "
             f"each is individually off-centerline or farther than the pad, but the wide wedge keeps them "
             f"all non-excludable."),
        comp("type_prior", FAC_TYPE_WELL, "Same O&G well prior as H1."),
        comp("magnitude_consistency", FAC_MAGNITUDE_MODERATE, "Same moderate-source magnitude as H1."),
    ]
    h2_score = round(sum(c.value * c.weight for c in h2_components), 4)
    h2_tier, _ = _fac_capped_tier(h2_score)
    hyps.append(SourceHypothesis(
        id="H2", rank=2,
        candidate=Candidate(
            kind=CandidateKind.SECTOR,
            descriptor=f"One of the {n_other} O&G wells in the wedge NOT on the {lease_name} lease/pad",
        ),
        claim=(
            f"The source may be any of the {n_other} in-wedge O&G wells that are NOT on the {lease_name} "
            f"lease/pad (and, within the pad, any of its {n_pad} completions) — alternatives the wide, "
            f"speed-derived wedge and NASA-anchored S cannot exclude. This non-discrimination IS the "
            f"dense-coverage finding."
        ),
        confidence_tier=h2_tier,
        confidence_rationale=(
            f"Heuristic score {h2_score:.2f}, band {_band(h2_score).value}: the indistinguishable-"
            f"alternatives hypothesis — first-class, because dense coverage makes it real."
        ),
        score=h2_score, score_components=h2_components,
        evidence=[
            EvidenceItem(
                kind="candidate_inventory",
                statement=(
                    f"{n_2sigma} O&G wells fall within the plume-scale 2-sigma wedge ({n_1sigma} within "
                    f"1-sigma). Rendered top {len(alt)} non-pad alternatives (cutoff at {_RENDER_CAP}; "
                    f"all {n_2sigma} are real OGIM records): {alt_lines}."
                ),
                source=subset_ref,
            ),
        ],
        assumptions=[half_angle_assumption, cfg.localization_note],
        counter_considerations=[
            f"The {lease_name} lease/pad is spatially favored (H1); these alternatives are ranked below it but "
            f"not excluded.",
        ],
        falsification=(
            "Tighter localization (measured wind-direction variance, or a plume-resolved inversion) "
            "collapsing the candidate set to one pad would demote this."
        ),
        generation_method=GENERATION_METHOD,
    ))

    # ---------------- H3: non-O&G (completeness) ----------------
    h3_components = [
        comp("spatial_consistency", FAC_SPATIAL_NEUTRAL,
             "Location does not discriminate sector; the discriminator against non-O&G is the type prior."),
        comp("type_prior", FAC_TYPE_NON_OG,
             "A ~0.85 t/hr point source coincident with a dense active O&G basin is overwhelmingly O&G; "
             "a non-O&G origin (natural seep, other sector) is a very low prior but not excluded."),
        comp("magnitude_consistency", FAC_MAGNITUDE_NON_OG,
             "A moderate point source is not characteristic of a natural seep here; magnitude disfavors it."),
    ]
    h3_score = round(sum(c.value * c.weight for c in h3_components), 4)
    h3_tier, _ = _fac_capped_tier(h3_score)
    hyps.append(SourceHypothesis(
        id="H3", rank=3,
        candidate=Candidate(kind=CandidateKind.SECTOR,
                            descriptor="Non-O&G source (natural geologic seep or other sector)"),
        claim=("A non-O&G origin is possible but unlikely in a dense active O&G basin; stated for "
               "completeness, not because of positive evidence."),
        confidence_tier=h3_tier,
        confidence_rationale=(
            f"Heuristic score {h3_score:.2f}, band {_band(h3_score).value}: the active-basin context "
            f"strongly disfavors a non-O&G origin but does not exclude it."
        ),
        score=h3_score, score_components=h3_components,
        evidence=[EvidenceItem(
            kind="sector_context",
            statement=("The wedge lies in a dense active O&G basin (thousands of wells), which argues "
                       "against a non-O&G origin; no in-situ measurement excludes a natural seep."),
            source=subset_ref,
        )],
        assumptions=["Sector priors are heuristic, not site-measured; isotopic/in-situ confirmation "
                     "would be needed to exclude a natural seep."],
        counter_considerations=["No committed dataset evidences a natural seep here; included for honesty."],
        falsification="Isotopic (delta-13C) or in-situ sampling indicating non-thermogenic origin would resolve sector.",
        generation_method=GENERATION_METHOD,
    ))

    return HypothesisSet(
        event_id=event_id,
        phenomenon=cfg.phenomenon,
        generated_method=GENERATION_METHOD,
        headline_finding=(
            f"DENSE-COVERAGE DISCRIMINATION: {n_2sigma} O&G wells fall within the plume-scale "
            f"back-projection wedge ({n_1sigma} within 1-sigma). The nearest-centerline candidate is "
            f"the {lease_name} lease/pad ({top_operator}, {n_pad} co-located completions, ~{top['dist_km']:.1f} "
            f"km from S), but it CANNOT be isolated — the wedge is wide, the source point S is inherited "
            f"from NASA's plume footprint (not self-derived), and the specific well is unresolved. No "
            f"facility reaches HIGH. This is the dense-coverage analogue of Goturdepe's sparse-data "
            f"finding, and gets the same first-class treatment."
        ),
        scoring_disclaimer=(
            "Scores are a documented additive heuristic (weighted components shown), NOT calibrated "
            "probabilities. Confidence reflects DISCRIMINATION POWER, not proximity alone; rely on the "
            "qualitative tiers and the visible component rationales."
        ),
        confidence_cap=(
            f"No hypothesis exceeds {FAC_CEILING.value.upper()}: dense, spatially-ambiguous coverage "
            f"plus a NASA-anchored source localization lets the data RANK candidates but not ESTABLISH "
            f"one. The favored pad wins only on an angular margin that rests on the weakest-link "
            f"half-angle, with distance margins within the ~1 km localization noise — so it is LOW, not "
            f"MODERATE (cf. Goturdepe's MODERATE, robust to the same uncertainty)."
        ),
        plume_summary={
            "emission_rate_ours_cal_t_hr": f"{q_t_hr:.3f}",
            "emission_rate_regime": "moderate point source (sub-super-emitter)",
            "upwind_source_S": f"{wedge.apex_lat:.5f} N, {wedge.apex_lon:.5f} E",
            "source_localization": "NASA-footprint-anchored (complex 000524), not self-derived",
            "upwind_azimuth_deg": f"{wedge.upwind_azimuth_deg:.1f}",
            "wedge_half_angle_1sigma_deg": f"{wedge.half_angle_1sigma_deg:.1f}",
            "wedge_half_angle_2sigma_deg": f"{wedge.half_angle_2sigma_deg:.1f}",
            "search_radius_km": f"{wedge.search_radius_km:.0f}",
            "wells_in_wedge_2sigma": str(n_2sigma),
            "wells_in_wedge_1sigma": str(n_1sigma),
            "nearest_by_centerline": f"{top_name} (OGIM_ID {top_id}, {top['dev']:.1f} deg, {top['dist_km']:.1f} km)",
            "nearest_by_distance": f"{nd_name} (OGIM_ID {nd_id}, {nd['dist_km']:.1f} km, {nd['dev']:.1f} deg)",
        },
        global_assumptions=global_assumptions,
        hypotheses=hyps,
        provenance={
            "ogim_subset": cfg.subset_rel,
            "ogim_doi": "10.5281/zenodo.15103476",
            "q_estimate": f"stage_b_outputs/{event_id}/q_estimate.json",
            "wind_location": f"stage_b_outputs/{event_id}/wind_location_check.json",
            "benchmark": f"eval/benchmark/{event_id}.yaml",
            "magnitude_prior_basis_1": "Duren et al. 2019, Nature 575, doi:10.1038/s41586-019-1720-3",
            "magnitude_prior_basis_2": "Cusworth et al. 2021, ES&T Lett 8, doi:10.1021/acs.estlett.1c00173",
        },
    )
