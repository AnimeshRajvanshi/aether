# Task: Sprint 7 — Permian (generality + the independence dividend)

**Owner:** Claude Code
**Reviewer:** chat Claude (science/honesty) + human
**Scope:** Quantify the **Permian 2022-08-26 EMIT granule** end-to-end using a per-granule independent HITRAN k — the first second event, and the first event NASA never published a per-granule target for. Three gated stages: reference-data probe → pipeline run + quantification → (gated) facility-level attribution. UI integration is gated last. Goturdepe artifacts are untouched.

## Why this sprint

1. **Generality:** everything is validated on exactly one granule. A second event flushes out Goturdepe-shaped assumptions (hardcoded IDs, paths, window/geometry assumptions, scene-specific shortcuts).
2. **The independence dividend:** Sprint 6's per-granule k generation (granule's own geometry + SRF) is precisely what makes a no-NASA-target granule quantifiable. This sprint is the capability proof.
3. **The attribution engine's first real test:** OGIM has dense facility-level coverage in the Permian (~198k wells in the regional bbox, verified in Sprint 4's sanity check). Goturdepe could only ever exercise the sparse-coverage degradation path; Permian exercises facility-level ranking for the first time.

## Cardinal rules

1. **Validation tier is earned, not asserted.** The 18.3 t/hr figure for this event is press-release-only (`uncertainty: null` in the benchmark YAML — already recorded honestly). It is CONTEXT, never a validation target and never a tuning target. If the probe finds no independent reference raster, the result is labeled **DEMONSTRATION (unvalidated)** everywhere it appears — docs, API, UI — visually and semantically distinct from Goturdepe's validated grade.
2. **Generality means shared code, not a fork.** Where the pipeline assumes Goturdepe (granule IDs, bboxes, dates, paths, magic constants), fix it by **parameterizing the shared code path** — event config in, artifacts out. Do not copy-paste a `_permian` variant of any script. Every Goturdepe-shaped assumption found is itself a reportable finding.
3. **No fabrication, no tuning.** Same as always: scaling forward from physics; report whatever Q falls out, even if far from 18.3; no invented reference values; named OGIM entities must exist in a committed subset with the guard test extended to the new region.
4. **Re-verify, don't assume, the scene-specific checks.** The Sprint 2 validation doc explicitly says future granules must RE-RUN (not assume): the wind-location source-vs-centroid check (Goturdepe's 0.5% was scene-specific smoothness) and the Varon U_eff regime check (U₁₀ within the 2–8 m/s calibration range). Both are mandatory for Permian, with results reported either way.

## STAGE A — Reference-data probe (report, then STOP)

Before building anything, establish what actually exists for granule 2022-08-26 (read the exact granule UR from the committed Permian benchmark YAML):

1. **NASA L2B products:** does an EMIT L2B CH4ENH enhancement raster exist for this granule? A CH4PLM plume complex? Query LP DAAC/CMR honestly; report exactly what exists with IDs/DOIs. (Do NOT assume either way — Goturdepe taught us granule/product mismatches are real.)
2. **Carbon Mapper catalog:** any catalog entries for this scene/date/region? Report verbatim what's found.
3. **The 18.3 t/hr provenance:** locate the actual press-release/source already cited in the YAML; confirm what it claims (which source, which date, which method) so the doc can state precisely why it is context-only.
4. **ERA5 wind availability** for the scene datetime/region (ARCO-ERA5, token-free, as before).
5. **OGIM regional subset:** extract and commit the Permian regional subset (document the bbox; subset before committing — the global file is large). Report feature-type counts (wells, compressors, processing, pipelines, flaring) so Stage C's design is grounded.

**Stop and report.** The probe decides the validation design:
- If a NASA L2B CH4ENH raster exists → a Goturdepe-style spatial cross-check is possible → the result can earn a **CROSS-CHECKED** tier (Pearson vs L2B reported; still not Thorpe-grade flux validation).
- If not → internal-consistency checks only (see Stage B) → the result is **DEMONSTRATION (unvalidated)** and says so everywhere.

## STAGE B — Per-granule k + end-to-end quantification (report, then STOP)

1. **Generate the Permian k** with the Sprint 6 v2 saturation-aware method, from THIS granule's own solar/view geometry and wavelength/FWHM arrays. Independence + reproducibility guards extended to the new k. (No NASA target exists to cross-check shape against — state this; if Stage A found one, cross-check and report.)
2. **Run the shared pipeline** (parameterized per cardinal rule 2): MF detection → orthorectification → segmentation (source-connected CC, same Varon t-test method) → IME → Q with U_eff from ERA5.
3. **Mandatory scene checks:** wind source-vs-centroid sensitivity (report ΔQ%); U_eff regime check (U₁₀ vs the 2–8 m/s Varon range — if outside, Q carries an explicit out-of-regime caveat and the tier degrades accordingly); plume-mask sensitivity sweep re-run for this scene.
4. **Re-propagate the uncertainty budget for this scene** from scratch (wind terms, mask sensitivity, the +1.46× systematic carried as measured-on-Goturdepe with an explicit assumption note that its transferability to a new scene is itself unvalidated — do not silently assume it transfers).
5. **Internal-consistency validation** (always, regardless of tier): enhancement-map sanity (plume coherence, background statistics, confuser inspection — the Sprint 2 diagnostic toolkit), segmentation overlay PNG evidence, and comparison of retrieved magnitude against the documented super-emitter range.
6. **Honest comparison to 18.3 t/hr as context:** state our Q, state theirs, state why they are not directly comparable (method unknown, source extent unknown, no uncertainty published). NEVER frame agreement or disagreement as validation.
7. Write `docs/science/sprint7_permian.md` (probe results, k provenance, every scene check, the budget, the tier verdict and exactly why) and the gate report to `docs/reports/sprint7_stage_b_report.md`. Extend the no-staleness guards to the new artifacts. **Stop for review.**

## STAGE C — Facility-level attribution (gated: only after Stage B review)

The Sprint 4 engine, pointed at a dense-coverage region for the first time:
1. Back-projection wedge from this scene's wind (same method; the wedge half-angle approximation carries its WEAKEST LINK label as before).
2. Candidate generation from the committed Permian OGIM subset. Expect MANY candidates (dense coverage) — the engine must handle candidate volume honestly: rank transparently, cap the rendered list (e.g. top N by score with the cutoff stated), and state how many candidates fell in the search region in total.
3. **New honesty challenge — dense-coverage humility:** in a region with hundreds of nearby facilities, the honest headline may be "N candidate facilities within the wedge; the data cannot discriminate among the top M under current wind uncertainty." That is the dense-coverage analogue of Turkmenistan's sparse-coverage finding, and it gets the same first-class treatment. Confidence tiers must reflect discrimination power, not proximity alone. No facility gets HIGH unless the evidence genuinely isolates it.
4. Same output artifacts, same no-fabrication guard against the Permian subset, same deterministic templating. `hypotheses.{json,md}` for Permian. **Stop for review** — I will read the actual hypotheses like Sprint 4's gate.

## STAGE D — UI integration (gated: only after Stage C review)

1. Flip Permian from "pending" to a real clickable event: globe marker, fly-to, plume overlay, inspector — all from committed Permian artifacts via the same API patterns.
2. **Validation-tier honesty in the UI:** the event carries a visible tier badge (VALIDATED / CROSS-CHECKED / DEMONSTRATION per the probe outcome) on the marker label and in the inspector header, with a first-class explainer of what the tier means for THIS event (mirroring the scope-caveat treatment). Goturdepe gains its tier label too, so the distinction is systematic, not ad hoc.
3. The 18.3 t/hr context appears ONLY inside an honest context block (like the Thorpe block for Goturdepe) that explains why it is not a validation reference.
4. Multi-event reality check: the events list, globe markers, and inspector must genuinely handle two events (state isolation, no Goturdepe data bleeding into Permian views). Endpoint + no-staleness guards extended.
5. Screenshots per the standard review package.

## Out of scope

- No changes to Goturdepe science/artifacts (its numbers are closed).
- No eval-harness wiring (still tracked separately), no H₂O/SZA LUT, no layered-background physics, no per-pixel sensitivity correction (all still deferred Sprint 6 refinements).
- No third event. No LLM anywhere.

## Definition of done

- Probe report committed; validation tier decided by evidence and stated.
- Permian k generated independently per-granule; pipeline runs via shared parameterized code (Goturdepe-shaped assumptions found are listed and fixed); Q + re-propagated budget + all mandatory scene checks reported.
- Tier-honest science doc + gate reports committed; guards extended (no-fabrication for the new OGIM subset, no-staleness for the new artifacts, independence for the new k).
- If Stage C authorized: dense-coverage attribution with discrimination-honest confidence.
- If Stage D authorized: Permian live in the UI with visible validation-tier labeling; two-event integrity verified; screenshots.
- Full suite green at every gate; every gate report a committed file.
- STOP at each stage gate. The reviews will check, in order: probe honesty, quantification honesty (especially that 18.3 was never a target), attribution discrimination honesty, and tier-labeling surviving the rendering.

## Build order

Stage A probe → STOP. Stage B k + pipeline + checks + budget → STOP. Stage C attribution → STOP. Stage D UI → STOP. Commit at every meaningful step; reports to committed files.
