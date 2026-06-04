# Task: Sprint 4 — Hypothesis-Surfacing Engine (source attribution for a quantified plume)

**Owner:** Claude Code
**Reviewer:** chat Claude (architecture/science/honesty) + human
**Scope:** Take ONE already-quantified plume (Goturdepe) and produce **ranked candidate source hypotheses, each with its real evidence, its explicit assumptions, and an honestly-expressed confidence.** This is the project's differentiator. It is also the single highest fabrication-risk component we have built. Read the cardinal rule below before anything else.

This sprint builds the engine + its validation/honesty document and then STOPS for review. **No dashboard/UI integration in this sprint** — that is the next sprint, gated on me reviewing the actual generated hypotheses for honesty.

## What this is — and what it is NOT

- This is **source attribution**: "which sector / facility most plausibly produced this methane plume, and how sure can we honestly be?" Framed externally as **hypothesis surfacing**: ranked candidates with evidence + assumptions, not a single black-box answer.
- This is **NOT** general causal inference, and **NOT** the multi-dataset "why is there extreme heat" reasoning from the long-term vision. That is a later phase. Do not build it.
- The differentiator vs. Carbon Mapper's portal is **transparency and multi-hypothesis honesty**: we surface competing explanations, each with its evidence trail, its stated assumptions, and a confidence we can defend — and we make the reasoning auditable. We are NOT claiming to attribute better than they do; we are claiming to attribute *legibly and humbly*.

## THE CARDINAL RULE (this sprint lives or dies on it)

A hypothesis engine is trivially easy to fake — feed plume metadata to a model, get a confident-sounding story with invented facility names and made-up confidence numbers. **That is the most damaging possible failure for this project.** Therefore:

1. **No fabricated entities.** Every candidate facility, operator, pipeline, or feature named MUST come from a real record in a real dataset (OGIM, see below). If the dataset has no feature near the source, the honest output is *"no facility-level match in OGIM within the search region"* — never an invented facility.
2. **No invented confidence.** Do NOT emit calibrated-looking probabilities (no "87% likely"). We have no calibration basis for that. Use **qualitative tiers (High / Moderate / Low / Insufficient evidence)** AND/OR a **transparent additive score whose components are shown to the user**, with an explicit disclaimer that the score is a documented heuristic, not a calibrated probability.
3. **No LLM-invented facts.** The hypothesis set, the evidence items, the rankings, and the confidence are ALL computed deterministically from real data joins. For this first version, render the hypothesis prose **deterministically from templates** populated by the real evidence structure. Do NOT use a free-form LLM to generate hypotheses or narratives in this sprint. (LLM phrasing as a constrained, fact-locked rendering layer is a possible *later* enhancement, not now.)
4. **Assumptions are first-class.** Every hypothesis states the assumptions its ranking depends on (wind back-projection accuracy, OGIM completeness in this region, field-boundary source, etc.). Surfacing what we assume is the product.
5. **Sparse coverage is an honest finding, not a gap to paper over.** If OGIM is thin over Turkmenistan, say so explicitly and let confidence reflect it. "Infrastructure database coverage is sparse here, so facility-level attribution is low-confidence" is a *feature* of this tool, not a failure.

## Data — the real infrastructure backbone (verified)

- **OGIM (Oil and Gas Infrastructure Mapping database)**, EDF/MethaneSAT. Global, public-domain, purpose-built for methane source attribution. Includes wells, pipelines, compressor stations, gathering/processing facilities, tank batteries, LNG, refineries, with attributes incl. **facility type, operator name, operational status, install date**.
  - Dataset: O'Brien, M., Omara, M., Himmelberger, A., & Gautam, R. (2025). OGIM database (OGIM_v2.7). Zenodo. **doi:10.5281/zenodo.15103476**
  - Methods/citation: Omara, M. et al. (2023). Earth System Science Data 15, 3761–3790. **doi:10.5194/essd-15-3761-2023**
- Acquire OGIM v2.7 from Zenodo. **Extract only the regional subset** around the event (bbox roughly 38.5–40.0°N, 52.5–55.0°E — mind the full file is large; subset before committing). Commit the subset (or a deterministic extraction script + the subset) so attribution is reproducible offline, consistent with project reproducibility norms.
- Reuse the **ERA5 wind** and the **upwind-source projection** already built in Sprint 2 (`wind_location_check.json` and the source-projection method). Do not recompute the science — read committed Stage A/B outputs.

## STAGE A — Data-availability probe (do this FIRST, then report before building the ranking)

Before writing any scoring, ground-truth what actually exists:

1. Compute the **back-projection search region**: from the plume's upwind source point, project upwind along the ERA5 wind direction, with an **angular uncertainty wedge** derived from wind-direction variability over the plume's transit time (transit time ≈ plume length / U_eff). This produces a *search wedge/cone*, not a point. Document the geometry.
2. Query the OGIM regional subset for **all features within the search region** (and within a documented radius, e.g. ≤25 km, of the upwind source).
3. **Report exactly what OGIM contains there:** feature types, counts, operator names, statuses, source dates, distances from the source point. Verbatim from the records.

**Stop and report this probe.** The ranking design adapts to what's actually there:
- If OGIM has specific features in/near the wedge → facility-level hypotheses are possible.
- If OGIM is sparse/empty there → degrade honestly to **field/sector-level** attribution (the plume source falls within the known Goturdepe–Barsagelmez producing field; sector prior for an isolated ~27 t/hr point source in an active gas field strongly favors O&G), with explicitly lower confidence and the sparse-coverage caveat. This is still a valid, honest, valuable output.

## STAGE B — The attribution engine

Build the ranked-hypothesis pipeline. Populate the existing `Hypothesis` ontology model (from Sprint 1) — extend it only if genuinely needed, with an ADR if so.

**Candidate generation:** each OGIM feature in the search region is a candidate; plus sector-level candidates (O&G field, natural seep, other) so the hypothesis set is honest even when facility data is thin.

**Transparent scoring (show every component — no black box):**
- *Spatial consistency* — position of the candidate relative to the back-projection wedge and distance from the upwind source, weighted by the wedge's angular uncertainty.
- *Type prior* — how plausibly this feature type produces a ~27 t/hr point plume (compressor/processing/large well/tank battery = higher; small well/minor feature = lower; document the prior and its basis).
- *Magnitude consistency* — is ~27 t/hr in the plausible super-emitter range for this feature type.
- Combine into a documented heuristic score with each component visible. **State in the output that this is a heuristic, not a calibrated probability.**

**Per-hypothesis output must contain:**
- The candidate (real OGIM record id/type/operator, or the sector-level descriptor) — never invented.
- **Evidence**: the specific facts supporting it — facility type, distance from source, operator, OGIM source date, spatial relationship to the wedge, the field context — each traceable to a committed file/record.
- **Assumptions**: what the ranking depends on (wind steadiness/back-projection validity, OGIM completeness in this region, field-boundary source, transit-time estimate).
- **Confidence**: qualitative tier + the transparent score components. No false-precision percentage.
- A counter-consideration where relevant ("cannot be distinguished from feature X 1.2 km away under current wind uncertainty").

**Output artifacts:**
- `hypotheses.json` — structured, schema-validated, every field traceable.
- A human-readable rendering (deterministic template) — the kind of thing that will later populate the inspector.
- `docs/science/sprint4_attribution.md` — the validation/honesty doc: the search-wedge geometry, the OGIM probe results verbatim, the scoring definition and its rationale, every assumption, the coverage caveats, and an explicit statement of what we can and cannot claim. Same spirit as `sprint2_validation.md`.

## Out of scope (do NOT build)

- No dashboard/UI integration (next sprint, after review).
- No LLM-generated hypotheses or narratives (templated/deterministic only).
- No new detection/quantification; no changes to Stage A/B science — read committed outputs.
- No multi-dataset causal reasoning (heat/ocean/land-use). Methane source attribution only.
- No second event. Goturdepe only.
- No calibrated probabilities.

## Definition of done (this sprint)

- OGIM v2.7 regional subset acquired and committed (or reproducibly extractable), with provenance.
- Stage A probe reported: exactly what infrastructure exists near the back-projected source, verbatim.
- Stage B engine produces ranked hypotheses for Goturdepe with evidence + assumptions + honest confidence, all schema-validated and every fact traceable to a committed source.
- `docs/science/sprint4_attribution.md` documents geometry, probe, scoring, assumptions, coverage caveats, and the can/cannot-claim statement.
- Tests: scoring components, schema validation, and a no-fabrication guard test (assert every named entity in the output exists in the committed OGIM subset).
- Full suite green; lints clean.
- **STOP after Stage B and report.** Do not start UI integration. I will review the actual generated hypotheses for honesty before we proceed.

## Build order

1. Acquire + subset OGIM; commit with provenance. 
2. Stage A: back-projection wedge geometry (reuse Sprint 2 wind work) → OGIM query → **report the probe**, stop.
3. Stage B: scoring → ranked hypotheses populating the ontology → output artifacts → validation doc.
4. Tests incl. the no-fabrication guard. Commit at each step. Stop and report.

The thing I will be checking at the review gate is not "does it run" — it is "is every hypothesis honest." Every named facility real, every assumption stated, every confidence defensible, sparse coverage admitted rather than hidden. Build it so that check passes.
