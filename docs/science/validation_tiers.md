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
