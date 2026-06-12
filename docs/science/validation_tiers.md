# Validation-tier rubric

> The honest ceiling on what each event's numbers mean. A tier is **earned by
> evidence**, never asserted. The badge shows the tier; cross-check **strength**
> lives in the per-event explainer, not the badge. This rubric is the single source
> of the criteria; the API (`apps/api/aether_api/loaders.py`) and the gate reports
> must trace to it, and a guard (`apps/api/tests/test_tier_rubric.py`) enforces that.

## The tiers

### VALIDATED — *reserved; currently held by no event*
Requires **independent flux truth**: a controlled-release experiment, an in-situ
measurement, or a **peer-reviewed per-source flux** at the same scope as our
estimate. This is the reserved top tier and is deliberately empty today, so the
system has an honest ceiling rather than a self-graded "best".

**Why no current event qualifies:**
- **Goturdepe** has no per-source flux reference. Thorpe et al. 2023 report
  163 ± 18 t/hr for the **12-source cluster** — a scope mismatch with our
  single-plume estimate. Per Sprint 2's own validation doc we explicitly **cannot
  claim agreement or disagreement** with that cluster total, so it cannot validate a
  single-source flux.
- **Permian** has only the 18.3 t/hr press-release figure (no date, method, or
  uncertainty) — context, not truth.

### CROSS-CHECKED — *an independent reference raster exists*
A NASA L2B CH4ENH (or equivalent independent) raster exists for the granule, so our
independent retrieval is checked against it spatially and/or in integrated mass. This
earns CROSS-CHECKED. It is **not** VALIDATED — no independent flux truth. Cross-check
**strength** is reported in the explainer:

| event | strength | evidence (in the explainer) |
|---|---|---|
| Goturdepe | **strong** | pixel-level spatial agreement r ≈ 0.73; fully **self-derived** localization; methane k-shape verified vs NASA's per-granule target (r ≈ 0.993); NASA-cal anchored. Limit: single overpass, no independent flux reference. |
| Permian | (weaker) | integrated mass over NASA's published footprint agrees to ≈0.96× **but** pixel-level agreement is weak (r ≈ 0.14); localization **NASA-footprint-anchored** (not self-derived); no k-shape check available. Limit: no independent flux reference; 18.3 t/hr is context. |

### DEMONSTRATION — *no independent reference*
No independent reference raster exists for the granule. The retrieval is internally
consistent but UNVALIDATED. (No current event is in this tier; it is defined so a
future no-reference granule is labelled honestly.)

## Encoding

- The tier per event is read from `stage_a_report.validation_tier` when present, else
  the documented `_TIER_DEFAULT` map in `loaders.py` (Goturdepe → CROSS-CHECKED; its
  Sprint-6 report predates the field). No tier is invented at render time.
- The badge is the tier string only. Strength is in `EventDetail.tier_explainer`.
- A CROSS-CHECKED event must have a NASA-L2B cross-check (a real `reference_product`
  + Pearson). No event may carry VALIDATED while the reserved-tier criterion (flux
  truth) is unmet — enforced by `test_tier_rubric.py`.

## History

- Sprint 7 Stage D first shipped Goturdepe as VALIDATED; the Stage D review corrected
  this to CROSS-CHECKED (strong) on the rationale above — VALIDATED requires
  per-source flux truth Goturdepe does not have. Both events are CROSS-CHECKED.

## Heat-vertical extension — PER-QUANTITY tiers (Sprint 9 Stage D)

Area events earn tiers **per quantity**, not per event (Stage B gate ruling:
VALIDATED is earnable for 2 m air-temperature claims specifically; the Stage D
gate ordered per-quantity badges). For `india_nw_heatwave_2022_04`:

| quantity | tier | basis |
|---|---|---|
| C1 peak 2 m Tmax | **VALIDATED** | pre-registered V1 vs ISD station instruments (criteria committed before computation — docs/science/sprint9_heat_validation.md) |
| C2 regional Tmax anomaly | **VALIDATED** | pre-registered V3 vs the ERA5-independent IMD station-gridded product |
| C3 duration / C4 extent | NOT VALIDATED | pre-registered V4 failed across two station-true datasets (criterion-edge fragility — the finding); always rendered with criterion + dataset attached |
| ERA5↔station consistency | NOT CLAIMED | V2 failed its pooled-r criterion; permanently not-claimed for this event (gate ruling) |
| LST quantities (anomaly, UHI) | ≤ CROSS-CHECKED | no in-situ skin-temperature truth; Terra ~10:41 local snapshot only, never a daily maximum |

**The event-level badge for an area event is `PER-QUANTITY`** — an event-level
VALIDATED badge would overstate C3/C4, and an event-level NOT-VALIDATED badge
would bury C1/C2. The marker badge points at the per-quantity table; the
methane (flux) rubric above is unchanged, and VALIDATED at event level remains
reserved and held by no event. Encoding: heat events serve
`validation_tier = "PER-QUANTITY"` with `EventDetail.heat.quantity_tiers`
carrying each quantity's tier; `test_tier_rubric.py` enforces that VALIDATED
appears ONLY on quantity rows whose committed pass flags
(`stage_b_outputs/<id>/validation.json`) are true.
