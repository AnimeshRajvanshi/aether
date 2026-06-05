# Sprint 4 — Source-attribution validation & honesty document

**Event:** `turkmenistan_goturdepe_2022_08_15` (EMIT 2022-08-15 04:28:38 UTC)
**Scope:** field/sector-level source attribution for one quantified ~27 t/hr methane plume.
**Engine:** `aether_causal` — deterministic, templated, no LLM. Generated method `rule_based_deterministic_v1`.
**Outputs:** `attribution_outputs/turkmenistan_goturdepe_2022_08_15/hypotheses.{json,md}`.

This document is the auditable record behind the generated hypotheses: the search
geometry, the OGIM probe verbatim, the scoring definition and its rationale, every
assumption, the coverage caveats, and an explicit can/cannot-claim statement. It is
in the same spirit as `sprint2_validation.md`.

---

## 0. Headline finding (stated first, as a result — not an apology)

**OGIM v2.7 contains NO facility-level point infrastructure — zero wells, zero
compressor stations, zero gathering/processing, zero tank batteries, zero
equipment — anywhere in Turkmenistan.** (Verified; the reader is correct: the same
query returns 197,922 wells and 122 compressor stations for a Permian, USA bbox.)

Therefore **facility-level attribution is impossible with available data**, and all
attribution here is capped at **field/sector level**. This is a real, defensible
finding about infrastructure-data coverage — a feature of an honest attribution
tool — not a gap to paper over. Every confidence tier below reflects this cap.

---

## 1. Back-projection search wedge (Stage A geometry)

The emission source lies upwind. We reuse the committed Sprint 2 ERA5 wind and the
data-driven **upwind source point S** (the centroid of the top-5%-upwind CC-1213
pixels, `wind_location_check.json`) and open an angular search wedge upwind.

| Quantity | Value | Source |
|---|---|---|
| Upwind source apex **S** | 39.34331 °N, 53.98627 °E | `wind_location_check.json` `source_lat/lon` |
| Plume centroid C | 39.37140 °N, 53.69048 °E | `wind_location_check.json` `centroid_lat/lon` |
| ERA5 wind (u east, v north) | −6.742, −1.622 m/s (\|U₁₀\| 6.935) | `q_estimate.json` |
| Downwind azimuth (blows toward) | 256.5° (WSW) | derived: atan2(u, v) |
| **Upwind azimuth (wedge centerline)** | **76.5° (ENE)** | downwind + 180° |
| Wedge half-angle (1σ / 2σ) | **14.5° / 27.3°** | atan(k·σ_U10 / \|U₁₀\|), k=1,2 |
| Transit time | 1.52 h | plume length 13 878 m / U_eff 2.537 m/s |
| Search radius | 25 km of S | documented choice |

**The wedge half-angle is the weakest link.** It is approximated from the committed
ERA5 wind *speed* 1σ (1.79 m/s) **treated as an isotropic wind-vector uncertainty**
— it is **NOT** a measured wind-direction variance. Sub-field localization rests on
this approximation and should not be over-trusted.

**A second localization caveat (not buried):** the bearing from the plume centroid C
to the back-projected source S is **96.9°**, which disagrees with the ERA5 upwind
azimuth (76.5°) by **~20°**. This is within the 2σ wedge but widens source-
localization uncertainty; it is encoded as a first-class assumption on H1 and H2 and
is the basis for H2's existence.

---

## 2. OGIM probe — verbatim (Stage A result)

OGIM v2.7 (doi:10.5281/zenodo.15103476, SHA-256 `6025432a…`), regional subset bbox
52.5–55.0 °E, 38.5–40.0 °N, committed at
`packages/causal/aether_causal/resources/ogim/ogim_v2.7_goturdepe_region.geojson`
(114 features). Extraction: `scripts/acquire_ogim_subset.py`.

**Facility-level point layers in the region (and in all of Turkmenistan): empty.**

| OGIM layer | features in regional bbox | in all Turkmenistan |
|---|---:|---:|
| Oil_and_Natural_Gas_Wells | 0 | 0 |
| Natural_Gas_Compressor_Stations | 0 | 0 |
| Gathering_and_Processing | 0 | 6 (none in bbox) |
| Tank_Battery / Equipment / Injection / Refineries / LNG | 0 | 0 (in bbox) |
| Oil_and_Natural_Gas_Fields | 20 | 185 |
| Natural_Gas_Flaring_Detections | 19 | 127 |
| Oil_Natural_Gas_Pipelines | 21 | — |

**Every feature within 25 km of S (verbatim from the records):**

| dist | bearing | dev-from-upwind | wedge | layer | record |
|--:|--:|--:|--|--|--|
| **0.89 km** | 125° | 48° | — | Field (Polygon) | **BARSAGELMEZ** (OGIM_ID 2017938), OIL & GAS, 133 km², SRC_DATE 2014-01-01 — **S is INSIDE this polygon** |
| 3.44 km | 100° | 23° | **2σ** | Flaring (Point) | OGIM_ID 141883, UPSTREAM OIL, Balkan, **SRC_DATE 2023-05-26** |
| 13.05 km | 94° | 17° | **2σ** | Pipeline | OGIM_ID 1489327, OIL, 2014-01-01 |
| 14.28 km | 264° | 172° | — | Pipeline | OGIM_ID 1489290, GAS |
| 19.88 km | 283° | 153° | — | Flaring (Point) | OGIM_ID 141878, UPSTREAM OIL, 2023-05-26 |
| 23.27 km | 304° | 132° | — | Field (Polygon) | GOTURDEPE (OGIM_ID 2017939) — does NOT contain S |
| 23.77 km | 67° | 9° | **1σ** | Pipeline | OGIM_ID 1489328, OIL, 2014-01-01 |

Point-in-polygon (computed): **S ∈ BARSAGELMEZ = True**; S ∈ GOTURDEPE = False.

---

## 3. Scoring definition and rationale

Confidence is expressed two ways, both shown to the user: a **qualitative tier**
(High / Moderate / Low / Insufficient) and a **transparent additive heuristic
score** whose components are individually displayed with a rationale.

> **The score is a documented heuristic, NOT a calibrated probability.** We have no
> calibration basis for probabilities. Rely on the tiers and the visible component
> rationales, not on the decimal.

**Components and weights** (`attribution.WEIGHTS`):

| component | weight | meaning |
|---|---:|---|
| spatial_consistency | 0.60 | position vs the back-projection (containment / displacement / non-discriminating), the primary discriminator for a *located* plume |
| type_prior | 0.25 | how plausibly the sector produces a ~27 t/hr point plume |
| magnitude_consistency | 0.15 | is ~27 t/hr in the plausible super-emitter range for the sector |

**Component bases (documented heuristics):**
- *spatial* — H1 = **0.85**: S sits well inside the *large* BARSAGELMEZ polygon
  (133 km²). S's exact position is uncertain (the ~20° bearing gap and the speed-
  derived wedge — the same uncertainty H2 rests on), but because it lies well within
  such a large field, that wobble is very unlikely to move it across the field
  boundary. **High, not 1.0 — S is not a fixed point.** H2 = 0.30 because an
  alternative requires *displacing* the source from S (permitted by the localization
  uncertainty, not favored). H3 = 0.50 (neutral): location does not discriminate
  sector, so spatial is non-informative for a non-O&G claim.
- *type_prior* — O&G = 0.90: Thorpe et al. 2023 attribute *this cluster* to O&G
  super-emitters, and an isolated ~27 t/hr point source inside an active gas field is
  characteristically O&G. Non-O&G = 0.15: natural geologic seeps exist in the South
  Caspian but are a low prior here.
- *magnitude* — O&G = 0.90: ~27 t/hr is within documented O&G super-emitter range and
  ~2× the per-source mean of the Thorpe 163 ± 18 t/hr, 12-source cluster. Non-O&G =
  0.40: a 27 t/hr natural point seep is possible but high.

**Tier assignment with the structural cap.** Raw score bands are High ≥ 0.80,
Moderate ≥ 0.55, Low ≥ 0.30, else Insufficient. **A structural ceiling of MODERATE
is then applied** because no OGIM point data exists — no hypothesis may be reported
above field/sector-level confidence. Thus H1's raw band (High, 0.87) is **capped to
MODERATE**; the cap is stated in H1's `confidence_rationale`.

**Result:**

| id | candidate | score | raw band | reported tier |
|---|---|--:|---|---|
| H1 | O&G within BARSAGELMEZ field | 0.87 | high | **moderate (capped)** |
| H2 | different/adjacent O&G (localization can't exclude) | 0.54 | low | low |
| H3 | non-O&G (seep / other) | 0.40 | low | low |

---

## 4. Assumptions (first-class)

Applied to all hypotheses (`HypothesisSet.global_assumptions`), plus per-hypothesis
assumptions in the JSON:

1. Steady ERA5 wind over the ~1.52 h plume transit (transit = plume length / U_eff).
2. **WEAKEST LINK** — the wedge half-angle is approximated from the ERA5 wind *speed*
   1σ treated as isotropic, NOT a measured wind-direction variance.
3. The ~20° disagreement between the centroid→S bearing (96.9°) and the upwind
   azimuth (76.5°) widens source-localization uncertainty; sub-field placement is not
   over-trusted.
4. OGIM field boundaries are accepted as drawn (BARSAGELMEZ SRC_DATE 2014-01-01);
   field extent/accuracy is not independently verified here.
5. The O&G sector prior rests on Thorpe et al. 2023 attributing this cluster to O&G
   and on the active-gas-field context.

---

## 5. Coverage caveats

- **No facility-level data.** OGIM has no wells/compressors/processing/tanks/equipment
  in Turkmenistan; no facility can be named. (§0.)
- **Field polygons are 2014-vintage** (SRC_DATE 2014-01-01) and accepted as drawn.
- **The VIIRS flaring detection postdates the plume by ~9 months** (2023-05-26 vs
  2022-08-15). It is encoded as a `temporal_caveat` on the evidence item: it is
  evidence of *persistent O&G area activity only*, **never** evidence about this
  specific plume, and **is not** the located source. No rendering implies otherwise.

---

## 6. What we can and cannot claim

**We CAN claim, at MODERATE (field/sector-level) confidence:**
- The back-projected upwind source of this ~27 t/hr plume falls **inside the
  BARSAGELMEZ oil & gas field** (point-in-polygon). The field is large (133 km²) and
  S sits well within it, so the ~20° localization wobble is very unlikely to move S
  across the field boundary — the *field-level* containment is robust even though S's
  *exact* position is uncertain. This is within the Goturdepe–Barsagelmez producing
  complex Thorpe et al. 2023 attribute to O&G super-emitters.
- The sector is **most plausibly oil & gas**, corroborated by persistent VIIRS
  flaring in the area (with the temporal caveat).

**We CANNOT claim:**
- Any **specific facility, operator, well, compressor, or pipeline** as the source —
  OGIM contains no such records here. Naming one would be fabrication.
- A **precise within-field location** — the localization is limited by the speed-
  derived wedge and the ~20° bearing disagreement; an alternative location within
  BARSAGELMEZ or in adjacent GOTURDEPE (H2) cannot be excluded.
- A **non-O&G origin is excluded** — H3 is low but stated; only isotopic/in-situ
  sampling would resolve sector definitively.
- Any **calibrated probability** — the scores are documented heuristics only.

---

## 7. Reproducibility

All inputs are committed; the engine is deterministic (same inputs → identical
outputs, asserted by `test_no_fabrication.test_committed_artifact_matches_regenerated`).

```
uv run python scripts/acquire_ogim_subset.py        # subset (one-time 3 GB download, cached)
uv run python scripts/run_attribution_goturdepe.py  # hypotheses.json + hypotheses.md
uv run pytest packages/causal                        # incl. the no-fabrication guard
```
