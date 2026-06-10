# PROJECT_STATUS.md

> Last verified by running tests + linter + tsc + web build on 2026-06-09 16:37:07 MST.

```yaml
phase: "Sprint 6 - HITRAN Independence COMPLETE (v2 saturation-aware k migrated to the OPERATIONAL retrieval; provenance flipped; held for human review to close)"
status: "Complete (pending review sign-off)"
last_updated: "2026-06-09"
updated_by: "Claude"
confidence: "High"
links:
  notion_hub: "TBD (no Notion hub created yet — do not fabricate a link)"
  adrs: ["docs/adr/0001-ontology-as-foundation.md"]
  key_commits:
    - "72f9731"  # Sprint 6 - migrate operational retrieval to v2 HITRAN k (steps 1-5)
    - "3e77fb2"  # Sprint 6 - no-staleness guard suite (step 6)
    - "e01c2c4"  # Sprint 6 - operational migration doc section (step 7)
    - "ddf84d0"  # Sprint 6 v2 - saturation-aware HITRAN k restores fidelity
    - "e0008de"  # Sprint 6 Stage B (v1 linear) - end-to-end + honest verdict
    - "26fe973"  # Sprint 6 Stage A - independent HITRAN methane k
    - "e6747e5"  # Sprint 5 - SOURCE ATTRIBUTION section in inspector
    - "d8fd19c"  # Sprint 4 Stage B - ranked field/sector attribution engine
    - "586d92d"  # Sprint 4 attribution validation & honesty doc
key_files:
  - "packages/ontology/"            # Pydantic v2 ontology (ADR 0001), extra=forbid
  - "packages/detection/"           # matched filter, IME quantification, hitran_k.py
  - "packages/causal/"              # source-attribution (hypothesis) engine
  - "eval/harness/"                 # benchmark runner + metrics (aether-eval)
  - "eval/benchmark/"               # benchmark event YAMLs (real references)
  - "apps/api/"                     # FastAPI: serves committed Stage A/B + hypotheses
  - "apps/web/"                     # Next.js + CesiumJS dashboard inspector
  - "docs/science/"                 # sprint2/4/6 validation & honesty docs
  - "stage_a_outputs/ , stage_b_outputs/ , attribution_outputs/"  # committed real results
open_tasks:
  - "Sprint 6 CLOSE-OUT review (owner: human): the operational migration is DONE and committed — review docs/reports/sprint6_migration_report.md + docs/reports/sprint6_dashboard_panels.md and sign off to declare Sprint 6 closed. The displayed headline moved ~27 -> 23.4 t/hr ours-cal; provenance flipped to independent HITRAN2020/HAPI."
  - "Filing-decision confirmation (owner: human): I kept the v2 result at the canonical operational filenames and preserved NASA-k as committed *.nasa_k.* siblings. If you prefer the inverse (NASA-k canonical, v2 in *.v2.*), it's a rename — flagged in the report."
  - "Eval harness still runs 'stub_pipeline' (0/3 recall); the real matched-filter detection is not yet wired in as the eval pipeline (separate task, NOT part of this migration)."
  - "Optional Permian stretch: now unblocked (Stage B fidelity restored) but not yet attempted — a clearly-caveated demonstration, not a validated result."
  - "Deferred physics to close the 1.46x-vs-1.66x residual (still a HYPOTHESIS: effective-layer/flat-continuum): layered background, H2O/SZA LUT, per-pixel sensitivity, RFM cross-check."
blockers:
  - "No blocker. The migration is complete and green; awaiting human review sign-off to formally close Sprint 6 (outward-facing emission-rate change, per the stop-and-report gate)."
recent_changes:
  - "Sprint 6 OPERATIONAL MIGRATION (this turn): the v2 saturation-aware HITRAN k is now the OPERATIONAL Goturdepe retrieval. Re-ran Stage A/B offline+reproducibly (scripts/run_migration_v2_operational.py); regenerated ALL derived artifacts (dashboard PNGs/bounds/mask, templated brief, hypotheses.{json,md}). Displayed Q ours-cal 27.09 -> 23.40 t/hr; nasa-cal 16.32 -> 16.03; Pearson bbox 0.749 -> 0.731; plume CC 1213 -> 1143; scope ~10-17% -> ~10-14% of the Thorpe cluster. RE-PROPAGATED budget: wind UNCHANGED BY CONSTRUCTION (same ERA5 grid cell, asserted), mask sensitivity shifted (half-spread 0.0195 -> 0.0150), MF-amplitude systematic now the MEASURED 1.46x (not hand-carried 1.66x). Provenance line FLIPPED honestly (target_spectrum_source = independent HITRAN2020/HAPI, NASA target shape cross-check only r=0.993). NASA-k originals preserved as committed *.nasa_k.* siblings. New no-staleness guard suite (apps/api/tests/test_no_staleness.py) parses numbers embedded in derived-artifact prose vs upstream sources (caught + fixed stale '~27 t/hr' literals). Gate report: docs/reports/sprint6_migration_report.md."
  - "Sprint 6 v2: saturation-aware k via finite-enhancement log-radiance regression (Thompson/EMIT-ATBD method), replacing the c=0 optically-thin Jacobian that omitted line-core saturation. Still HITRAN/HAPI, no MODTRAN, NASA file never read, forward scale 1.0 (not reverse-fit). RESULT: shape vs NASA 0.928 -> 0.993; end-to-end Pearson vs NASA L2B 0.53 -> 0.73 (Sprint 2 was 0.75) = FIDELITY RESTORED; amplitude 0.79x -> 1.46x so the +1.66x over-amplitude is reproduced INDEPENDENTLY (a real MF systematic, not a NASA-convention artifact); NASA-anchored flux 16.0 t/hr ~ Sprint 2's 16.3."
  - "Sprint 6 Stage B (v1 linear): end-to-end with the c=0 k gave Pearson 0.53 / amplitude 0.79x; diagnosed to missing saturation (kept as the documented before-state)."
  - "Sprint 6 Stage A: independent methane k from HITRAN2020/HAPI; shape r=0.93 vs NASA target (cross-check only)."
  - "Sprint 5: SOURCE ATTRIBUTION inspector section rendering committed hypotheses.json verbatim. Sprint 4: field/sector source-attribution engine (OGIM-backed, no fabricated facilities)."
validation_status:
  verified_at: "2026-06-09 16:37:07 MST (fresh run of pytest + ruff + tsc + web build)"
  tests: "uv run pytest -> 186 passed, 6 deselected, 2 warnings (exit code 0). +7 from the new no-staleness guard suite. NOT proof of the science thesis — see 'Validated vs. Unvalidated'."
  frontend: "apps/web: tsc --noEmit clean; next build -> compiled successfully, 5/5 static pages."
  lint: "uv run ruff check . -> 72 errors (exit code 1, FAILING). ALL pre-existing legacy debt (scripts/diagnose_*.py, packages/ontology/, eval/harness/cli.py, untracked tools/setup_rag.py); NOT migration work. Every file touched in the migration lints clean per-file (verified)."
  sprint_gate: "Sprint 1 gate PASSED. Sprint 6 gate: operational migration to the independent v2 k is DONE + green; awaiting human review sign-off (gate report committed at docs/reports/sprint6_migration_report.md) to formally close."
  eval: "aether-eval run = stub_pipeline, 0/3 recall (baseline, UNCHANGED; real detection not yet registered as the eval pipeline)"
next_milestones:
  - "Human review sign-off on the operational migration (gate report + dashboard-panel evidence) to close Sprint 6."
  - "Optional: the deferred physics refinements (layered background, H2O/SZA LUT, per-pixel sensitivity, RFM cross-check) to investigate the residual 1.46x vs 1.66x (a hypothesis, not an established cause)."
  - "Wire the real matched-filter detection into the eval harness so aether-eval reflects actual performance."
notes_for_agents:
  "Read CLAUDE.md fully before changes. Run uv run pytest and (for detection/causal changes) aether-eval run before committing. Never fabricate data, granule IDs, coordinates, emission rates, or citations. NOTE: README.md and CLAUDE.md 'Where we are' sections are STALE (they still say Sprint 1) — trust the commits, stage outputs, and docs/science validation docs for true current state (Sprints 1-6)."
```

## Executive Summary

Aether is an AI-native dashboard and analysis engine for orbital/planetary monitoring data, unifying hyperspectral/thermal/atmospheric data through one typed ontology and turning raw observation into defensible, contextualized briefs. The MVP wedge is **super-emitter methane event reconstruction**: detect and quantify a plume, surface ranked source hypotheses, render it on a dashboard, produce a brief.

Current state is well past the original Sprint 1 baseline. The end-to-end wedge is built and validated on one real event (**Turkmenistan Goturdepe, EMIT 2022-08-15**): matched-filter detection + IME quantification, field/sector-level source attribution (OGIM-backed, honest about sparse coverage), and a CesiumJS dashboard inspector that renders the committed results verbatim. **Sprint 6 (HITRAN independence) is now COMPLETE.** We generate our own methane absorption spectrum `k` from HITRAN2020/HAPI, and this turn **migrated it to the OPERATIONAL retrieval** — the displayed dashboard quantification, uncertainty budget, provenance line, brief, scope caveat, and hypotheses are all re-derived from the v2 outputs. The **v2 saturation-aware k** (finite-enhancement log-radiance regression) reproduces NASA's target shape (r=0.993, a cross-check only) and preserves end-to-end retrieval fidelity (Pearson 0.731 vs NASA L2B). The displayed headline moved **27.1 -> 23.4 t/hr ours-cal** (16.0 t/hr NASA-anchored), the MF-amplitude systematic is now the **independently measured 1.46x**, and the provenance line is flipped honestly to independent HITRAN2020/HAPI. NASA's per-granule target is now a shape cross-check only, never a pipeline input. The migration is committed and **held for human review sign-off** (gate report: `docs/reports/sprint6_migration_report.md`) to formally close the sprint.

## Architecture Overview

Five independently testable layers, all hanging off the ontology (ADR 0001):
1. **Data Spine** (`packages/data_spine`) — ingestion/normalization/caching of public datasets (EMIT L1B/L2A, NASA L2B, ERA5); COG/Zarr.
2. **Detection & Quantification** (`packages/detection`) — per-column matched filter, Varon-2018 IME quantification, and the new HITRAN `k` generator.
3. **Causal Suggestion Engine** (`packages/causal`) — ranked `Hypothesis` objects with evidence, assumptions, falsification (source attribution).
4. **AI Orchestration** (`packages/ai`) — Claude/Grok tool-use over the ontology (not yet built out).
5. **Presentation** (`apps/web` CesiumJS/Next.js + `apps/api` FastAPI) — globe → fly-to → plume → inspector.

Everything composes the ontology entities (`Observation`, `Detection`, `Phenomenon`, `Entity`, `Hypothesis`, `Brief`); no parallel schemas.

## Key Decisions & ADRs

- **ADR 0001 — The planetary ontology is the foundation** (Accepted 2026-05-28): a single Pydantic v2 typed ontology (`extra="forbid"`, mandatory `Provenance`, first-class `planetary_body`) that every layer consumes. Cross-source reasoning, structural reproducibility, and hypothesis credibility all depend on it. Every new feature extends/composes existing entities rather than inventing parallel schemas.

(Only ADR 0001 exists. Method/honesty decisions for individual sprints live in `docs/science/sprint2_validation.md`, `sprint4_attribution.md`, `sprint6_hitran_independence.md` rather than as ADRs.)

## Open Tasks & Blockers

- **Sprint 6 close-out review** (human): the operational migration to the independent v2 `k` is **DONE, committed, and green**. Review `docs/reports/sprint6_migration_report.md` + `docs/reports/sprint6_dashboard_panels.md` and sign off to declare Sprint 6 closed. Displayed headline moved 27.1 -> 23.4 t/hr ours-cal; provenance flipped to independent HITRAN2020/HAPI.
- **Filing-decision confirmation** (human): v2 kept at canonical operational filenames; NASA-`k` preserved as committed `*.nasa_k.*` siblings. Inverse filing (NASA-`k` canonical, v2 in `*.v2.*`) is a rename on request — flagged in the report.
- **Eval harness** runs a `stub_pipeline` (0/3 recall); the real matched filter is not yet registered as the eval pipeline (separate task, NOT part of this migration).
- **No blocker.** The migration is complete; awaiting human review sign-off (outward-facing emission-rate change, per the stop-and-report gate).

## Validation & Testing

_Verbatim results of a fresh run on **2026-06-09 16:37:07 MST** (not transcribed from any prior doc)._

**`uv run pytest` — exit code 0**
```
============ 186 passed, 6 deselected, 2 warnings in 20.42s ============
```
The 6 deselected are network-gated integration tests. The +7 vs the prior 179 are the new no-staleness guard suite (`apps/api/tests/test_no_staleness.py`), which parses numbers embedded in derived-artifact prose and asserts each traces to its upstream committed source. The suite also includes the no-fabrication guard and the HITRAN independence guards (the k regenerates reproducibly and reads no value from NASA's file). Frontend: `tsc --noEmit` clean, `next build` compiled successfully (5/5 static pages). **What this proves: the plumbing, schema guards, and reproducibility hold — NOT that the science thesis is validated** (see Validated vs. Unvalidated below).

**`uv run ruff check .` — exit code 1**
```
Found 72 errors.
```
All 72 are in **pre-existing legacy files, not migration work**: the diagnostic scripts (`scripts/diagnose_*.py`), `packages/ontology/`, `eval/harness/aether_eval/cli.py`, and the untracked `tools/setup_rag.py`. **Every file touched in this migration lints clean per-file** (verified: `run_migration_v2_operational.py`, `test_no_staleness.py`, `loaders.py`, `attribution.py`, the changed tests, `build_dashboard_assets.py`). The repo-wide failure is legacy lint debt. **The linter currently fails (exit 1); this is not hidden.**

- **Sprint 1 gate:** PASSED — `aether reproduce <event_id>` renders a real methane plume; Goturdepe Stage A/B committed.
- **Eval:** `uv run aether-eval run` → stub_pipeline, recall 0/3 (baseline only; real detection not wired into the harness).
- **Sprint 6 control:** the Stage B runner fed NASA's `k` reproduces Sprint 2's Pearson exactly (full 0.7354 / bbox 0.7485), confirming the pipeline is faithful and the divergence is the `k` swap alone.

## Validated vs. Unvalidated

> ⚠️ **The 186 passing tests are NOT proof that the core thesis is validated.** They exercise plumbing, schema guards, reproducibility, and the no-fabrication guards. The scientific claims are validated only where explicitly stated below, against real reference data — on a **single event (Goturdepe)**.
>
> **Note:** an earlier instruction asked to distinguish PX4/Gazebo items (SIH telemetry, Gazebo DetachableJoint baseline, INDI+RLS offboard controller) and to pull from `ROADMAP.md`. **None of those exist in this repository** — there is no PX4, Gazebo, MAVLink, INDI/RLS, SIH, telemetry bridge, or `ROADMAP.md` here (verified by grep; the only ADR is 0001-ontology-as-foundation). Aether is a methane-detection/attribution engine, not a flight-control project. Rather than fabricate that content, the table below applies the same validated-vs-written discipline to Aether's *actual* state, from `docs/science/` and the task briefs.

**VALIDATED (verified against real reference data / reproducible runs):**
- **Matched-filter detection + IME quantification on the real Goturdepe EMIT granule**, validated against NASA's L2B CH4ENH product: bbox Pearson **0.7485** (`docs/science/sprint2_validation.md`, `stage_a_outputs/`, `stage_b_outputs/q_estimate.json`).
- **Independent HITRAN `k` (v2 saturation-aware) — shape AND retrieval fidelity validated:** spectral shape vs NASA target r = **0.993**; end-to-end Pearson vs NASA L2B = **0.731** (≈ Sprint 2's 0.749). NASA file never read in generation (guard tests). The over-amplitude is reproduced independently as a **measured 1.46×**; NASA-anchored flux 16.0 t/hr ≈ Sprint 2's 16.3 (`docs/science/sprint6_hitran_independence.md` §8-9). **NOW OPERATIONAL:** the displayed dashboard retrieval has been migrated to this independent `k` this turn (Q ours-cal 23.4 t/hr), with the provenance line flipped and all derived artifacts re-generated.
- **Pipeline faithfulness control (Sprint 6):** the runner fed NASA's `k` reproduces Sprint 2's Pearson exactly (full 0.7354 / bbox 0.7485) — so the v2 fidelity recovery is the `k`, not the pipeline.
- **API serves committed artifacts byte-for-byte** (endpoint tests assert API JSON == committed files; no-fabrication guard on attribution entities).

**UNVALIDATED (written/planned, or run but NOT proven against ground truth):**
- **The DISPLAYED dashboard quantification is now the independent v2 `k`** (migrated this turn; Q ours-cal 23.4 t/hr, provenance flipped to HITRAN2020/HAPI). What remains UNVALIDATED is **absolute flux accuracy** — the NASA-L2B-anchored 16.0 t/hr is internally consistent but not checked against an in-situ single-source measurement (see below). The migration changes provenance/independence, not ground-truth validation.
- **Detection performance via the eval harness: UNVALIDATED.** `aether-eval` runs a `stub_pipeline` (0/3 recall); the real matched filter is **not wired into the harness**, so the eval number does not reflect actual detection performance.
- **Source attribution: not validated against ground truth.** The engine runs and is honest (field/sector-level, sparse-coverage caveats), but the ranked hypotheses are *not* checked against a confirmed source.
- **Generalization: UNVALIDATED beyond one event.** All quantitative validation is on Goturdepe only; Permian is deferred (press-release reference only, no per-granule NASA target).
- **AI orchestration layer (`packages/ai`): not built.**
- **Absolute flux accuracy:** the NASA-L2B-anchored flux (~16 t/hr) is consistent across methods but is NOT independently validated against an in-situ or peer-reviewed single-source measurement (Thorpe 2023 is a 12-source cluster total). The residual 1.46× vs 1.66× over-amplitude is a hypothesis (effective-layer/flat-continuum), not an established cause, and awaits the deferred physics refinements.

## Next Steps

1. Sprint 6 human review sign-off → close the sprint (the operational migration is DONE; review `docs/reports/sprint6_migration_report.md` + the dashboard-panel evidence).
2. Optional deferred physics refinements (layered background, H₂O/SZA LUT, per-pixel sensitivity, RFM cross-check) to investigate the residual 1.46× vs 1.66× (a hypothesis, not an established cause).
3. Wire the real matched-filter detection into the eval harness so `aether-eval` reflects true performance.
4. Refresh README.md / CLAUDE.md "Where we are" to current state (Sprints 1–6).

## Context for Future Agents

- **Scientific integrity is the product.** Never fabricate data, granule IDs, plume coordinates, emission rates, or citations. Every benchmark event needs a real peer-reviewed/authoritative reference (schema-enforced). Hypotheses are ranked candidates with explicit assumptions and a falsification path — never asserted as truth. Uncertainty is structural (carried, not dropped). When a value isn't available, say so and leave a marked TODO.
- **Data sources are LOCKED:** EMIT, Sentinel-5P TROPOMI, Landsat 8/9 ST, ERA5, Carbon Mapper catalog, and a global oil & gas infrastructure database (OGIM v2.7, Zenodo doi:10.5281/zenodo.15103476). Do not add a seventh without explicit instruction. Ocean/marine, the 3D explorer, and SDA/orbital modules are deferred (architecture supports them; `planetary_body` is first-class).
- **Never commit raw data** (`.tif`, `.zarr`, `.nc`, large `.npz`) — gitignored; caches in `.aether_cache/`. Small derived artifacts (JSON/MD/PNG, the OGIM subset, the HITRAN line list) are committed for reproducibility.
- **Conventions:** uv workspace, Python 3.12 pinned, Pydantic v2 `extra="forbid"`, Ruff (line length 100), mypy strict (import-untyped on scientific deps is pre-existing). Frontend: pnpm, `tsc --noEmit` must pass. Commit small and focused; run the suite before committing.
- **Honesty examples already in the repo:** Permian renders "pending" (no invented numbers); attribution degrades to field/sector when OGIM has no facility data in Turkmenistan; the Sprint 6 provenance line is left unchanged even though the v2 `k` is validated — because the *displayed* numbers were computed with NASA's `k`, and relabelling them "independent" without re-deriving them would misrepresent the screen. Match this standard. Scaling is always derived forward from physics, never reverse-fit to a target flux.
