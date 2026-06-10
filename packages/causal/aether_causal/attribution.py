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
