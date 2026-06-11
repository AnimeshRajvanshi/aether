# Sprint 7 — Stage C — Permian facility-level attribution — Gate Report

> Permian / Carlsbad NM, EMIT 2022-08-26. The Sprint 4 attribution engine pointed
> at a DENSE-coverage region for the first time. Committed artifact:
> `attribution_outputs/permian_basin_2022/hypotheses.{json,md}`. **STOP for review**
> — read the hypotheses like the Sprint 4 gate. Stage D (UI) is gated behind this.

## Headline — discrimination power, not a named culprit

**21 oil & gas wells fall within the plume-scale back-projection wedge** (14 within
1-sigma). The **nearest-CENTERLINE** candidate is the **GOONCH FEDERAL COM 0409
lease/pad** (operator NOVO OIL & GAS NORTHERN DELAWARE, LLC; 14 co-located
completions in the wedge, ~0.6 km from S, **~0.4° off the wind azimuth** vs ≥13° for
every non-pad well). It is **not** the distance-closest well — **ARTEMIS FEDERAL COM
#002 (OGIM_ID 4325465) is closer at 0.26 km** (though 36° off-centerline). So the
pad's only discriminating margin is *angular*, the angular uncertainty is the
self-declared weakest link (speed-derived half-angle 25°/43° at 1σ/2σ, driven by the
low 3.58 m/s wind), the distance margins (~0.3–1.6 km) are comparable to S's ~1 km
NASA-inherited positional uncertainty, and S is itself **inherited from NASA's plume
footprint** (not self-derived). **The data RANKS candidates but cannot ESTABLISH one;
no facility exceeds LOW.** This is the dense-coverage analogue of Goturdepe's
sparse-data finding, and gets the same first-class treatment.

## Ranked hypotheses (deterministic; every OGIM record real + guard-verified)

| id | tier | score | candidate |
|---|---|---:|---|
| H1 | **LOW** (band MODERATE, **capped**) | 0.63 | GOONCH FEDERAL COM 0409 lease/pad — nearest-*centerline* only; ranked, not established |
| H2 | LOW | 0.51 | one of the 7 in-wedge wells NOT on that pad (the indistinguishable alternatives) |
| H3 | LOW | 0.37 | non-O&G (natural seep / other sector) — completeness |

> **Stage C review correction (recorded).** An earlier draft rated H1 MODERATE and
> claimed the pad was "closer in BOTH distance and angle than any other in-wedge well"
> — **false**: ARTEMIS FEDERAL COM #002 is distance-closest (0.26 km). The pad wins on
> *angle only*. The rationale was rewritten truthfully, the spatial component lowered
> 0.70→0.50 (its 0.70 had rested on the removed false claim), and facility hypotheses
> are now **capped at LOW** (`FAC_CEILING`). A new guard
> (`test_comparative_claims_are_truthful`) asserts comparative spatial claims against
> the computed candidate table so a false "closer/nearest" fails tests.

## How each Stage C requirement was met

1. **Magnitude prior re-derived for THIS plume's regime.** Goturdepe's priors were
   built for a ~27 t/hr super-emitter. Permian is **~0.85 t/hr [0.57–1.15]** — a
   *moderate* point source. New documented basis: **Duren et al. 2019** (Nature,
   doi:10.1038/s41586-019-1720-3 — O&G point-source rates are heavy-tailed, the bulk
   far below super-emitter scale) and **Cusworth et al. 2021** (ES&T Lett,
   doi:10.1021/acs.estlett.1c00173 — Permian point sources at facility scale,
   intermittent). Consequence encoded in the priors: a ~0.85 t/hr source is
   consistent with a *single well* (venting, unlit flare, casing leak, liquids
   unloading), small equipment, or a tank battery — so facility **type barely
   discriminates**, and spatial proximity is the only real (and here weak)
   discriminator. No super-emitter priors were reused.
2. **Dense-coverage discrimination honesty.** Wedge built from this scene's wind
   (3.58 m/s) with the half-angle carrying its **WEAKEST-LINK** label (speed-derived,
   not a measured wind-direction variance) as in Sprint 4. Total candidates in the
   search region are reported (21 in 2σ / 14 in 1σ; 2,720 within the inherited 25 km
   wedge — see note). Candidates are ranked transparently by (angular deviation,
   distance); the rendered alternative list is **capped at 8 with the cutoff and the
   total both stated**. The headline IS the discrimination finding. No facility
   reaches HIGH (guard-enforced).
3. **Segmentation-dependence caveat (first-class).** A global assumption, the H1/H2
   assumptions, and `plume_summary.source_localization` all state that S is derived
   from a **NASA-anchored** plume footprint (complex 000524), unlike Goturdepe's
   fully self-derived S. The attribution inherits NASA's plume location.
4. **Same machinery as Sprint 4.** Deterministic templating (`render_markdown`),
   evidence with sources + temporal caveats, assumptions, counter-considerations,
   falsification, qualitative tiers + transparent weighted components, and a
   no-fabrication guard against the Permian subset
   (`packages/causal/tests/test_no_fabrication_permian.py`). **VIIRS flaring date
   check:** every flaring detection in the wedge is dated **2023-05-26** —
   ~9 months AFTER the 2022-08-26 overpass — so flaring is carried only as a
   temporally-caveated corroboration of *persistent* activity, never as evidence
   about this plume or as the located source (intermittency: Cusworth 2021).

## A plume-appropriate search radius (a generality fix)

The Goturdepe wedge used a 25 km radius. For a compact ~3.3 km plume the source sits
at S ± ~1 km (the centroid→S back-projection was 0.90 km), so wells tens of km away
are not candidates for THIS plume. Stage C uses a **2 km** radius (a documented
per-event config field). For context, the full 25 km wedge would contain 2,720
wells — the radius choice is stated, not hidden, and the discrimination finding
holds either way (21 vs 2,720 indistinguishable wells).

## Shared code, not a fork

The dense-coverage capability is `build_facility_hypothesis_set(event_id)` in the
SAME module as Goturdepe's `build_hypothesis_set`, reusing the shared schema, wedge
geometry, scoring primitives, renderer, and no-fabrication pattern; the event config
lives in `FACILITY_EVENTS`. Goturdepe's field/sector-level builder and its committed
`hypotheses.json` are **untouched and byte-identical** (its regeneration guard still
passes). Goturdepe could only ever exercise the sparse-coverage degradation path;
Permian exercises facility-level discrimination for the first time — a new mode of
the one engine, selected by what the OGIM data contains.

## Honesty self-check (the things a reviewer should poke)

- **Why is H1 LOW, not MODERATE?** Its only discriminating margin is *angular*
  (~0.4° vs ≥13°); the angular uncertainty is the self-declared weakest link, and the
  distance margins (~0.3–1.6 km) are comparable to S's ~1 km NASA-inherited positional
  uncertainty — and ARTEMIS is actually distance-closer. The ranking is real but not
  established, so the tier is capped at LOW. MODERATE would require a spatial claim
  robust to the stated localization uncertainty (cf. Goturdepe, whose MODERATE rests
  on S sitting *inside* a 133 km² field polygon). Enforced by `test_no_facility_exceeds_low`.
- **Named a specific operator (NOVO OIL & GAS).** It is a real OGIM record, the
  nearest-centerline one, named for transparency — with the claim stating plainly
  that it is NOT the distance-closest well, the specific well is unresolved, and the
  other candidates are not excluded.
- **18.3 t/hr** plays no role in attribution (it is press-release context from
  Stage B; the magnitude prior uses our own retrieved 0.85 t/hr).

## Verification

- `uv run pytest` green (full suite). New: `test_no_fabrication_permian.py`
  (7 guards incl. the **no-above-LOW** cap, **comparative-claims truthfulness**,
  pad-multiplicity honesty, and regeneration byte-identity). Goturdepe attribution
  byte-identical.
- `attribution_outputs/permian_basin_2022/hypotheses.{json,md}` committed.

## STOP — for review

Next (gated): **Stage D** — UI integration. The tier badge must carry BOTH Stage B
cross-check facts (integrated-mass 0.96× agreement; pixel-level agreement weak at
r=0.137), and the provenance must distinguish Permian's NASA-anchored localization
from Goturdepe's end-to-end independence.
