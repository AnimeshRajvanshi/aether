# PROJECT_STATUS.md

> Last verified by running tests + linter on 2026-06-09 14:02:04 MST.

```yaml
phase: "Sprint 6 - HITRAN Independence (v2 saturation-aware k: fidelity RESTORED; operational migration pending review)"
status: "In Progress"
last_updated: "2026-06-09"
updated_by: "Claude"
confidence: "High"
links:
  notion_hub: "TBD (no Notion hub created yet — do not fabricate a link)"
  adrs: ["docs/adr/0001-ontology-as-foundation.md"]
  key_commits:
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
  - "Sprint 6 review gate (owner: human + chat Claude): review the v2 saturation-aware result; authorize migrating the OPERATIONAL pipeline to the v2 k (changes the displayed headline ~27 -> ~23 t/hr ours-cal) so the dashboard retrieval is genuinely independent."
  - "Provenance-line UI update (GATED): the fidelity gate is now MET, but the line is intentionally NOT flipped this turn — the displayed numbers still come from the NASA-k run, so relabelling them 'independent' would misrepresent the screen. Flip only after the operational migration above."
  - "Eval harness still runs 'stub_pipeline' (0/3 recall); the real matched-filter detection is not yet wired in as the eval pipeline."
  - "Optional Permian stretch: now unblocked (Stage B fidelity restored) but not yet attempted — a clearly-caveated demonstration, not a validated result."
blockers:
  - "No hard blocker. Decision point: whether to re-run the committed operational Stage A/B with the v2 k (outward-facing — changes the displayed emission rate). Held for human review per the sprint's stop-and-report gate."
recent_changes:
  - "Sprint 6 v2: saturation-aware k via finite-enhancement log-radiance regression (Thompson/EMIT-ATBD method), replacing the c=0 optically-thin Jacobian that omitted line-core saturation. Still HITRAN/HAPI, no MODTRAN, NASA file never read, forward scale 1.0 (not reverse-fit). RESULT: shape vs NASA 0.928 -> 0.993; end-to-end Pearson vs NASA L2B 0.53 -> 0.73 (Sprint 2 was 0.75) = FIDELITY RESTORED; amplitude 0.79x -> 1.46x so the +1.66x over-amplitude is reproduced INDEPENDENTLY (a real MF systematic, not a NASA-convention artifact); NASA-anchored flux 16.0 t/hr ~ Sprint 2's 16.3."
  - "Sprint 6 Stage B (v1 linear): end-to-end with the c=0 k gave Pearson 0.53 / amplitude 0.79x; diagnosed to missing saturation (kept as the documented before-state)."
  - "Sprint 6 Stage A: independent methane k from HITRAN2020/HAPI; shape r=0.93 vs NASA target (cross-check only)."
  - "Sprint 5: SOURCE ATTRIBUTION inspector section rendering committed hypotheses.json verbatim. Sprint 4: field/sector source-attribution engine (OGIM-backed, no fabricated facilities)."
validation_status:
  verified_at: "2026-06-09 14:02:04 MST (fresh run of pytest + ruff)"
  tests: "uv run pytest -> 179 passed, 6 deselected, 2 warnings (exit code 0). NOT proof of the science thesis — see 'Validated vs. Unvalidated'."
  lint: "uv run ruff check . -> Found 74 errors (exit code 1, FAILING). All in PRE-EXISTING files, NOT Sprint 6 work: scripts/diagnose_*.py, packages/ontology/, eval/harness/, and the untracked tools/setup_rag.py (2). Rule counts: 37 E501, 19 N806, 7 F541, 3 F401, 1 each I001/F841/B905. All Sprint 6 hitran_k files lint clean per-file."
  sprint_gate: "Sprint 1 gate PASSED. Current gate: human review of the v2 result before migrating the operational dashboard retrieval to the independent k + flipping the provenance line."
  eval: "aether-eval run = stub_pipeline, 0/3 recall (baseline; real detection not yet registered as the eval pipeline)"
next_milestones:
  - "Authorize + run the operational migration: re-run committed Stage A/B with the v2 k, regenerate the dashboard artifacts, then flip the provenance line to independent HITRAN2020/HAPI and retire the NASA-dependence caveat."
  - "Optional: the deferred physics refinements (layered background, H2O/SZA LUT, per-pixel sensitivity, RFM cross-check) to close the residual 1.46x vs 1.66x."
  - "Wire the real matched-filter detection into the eval harness so aether-eval reflects actual performance."
notes_for_agents:
  "Read CLAUDE.md fully before changes. Run uv run pytest and (for detection/causal changes) aether-eval run before committing. Never fabricate data, granule IDs, coordinates, emission rates, or citations. NOTE: README.md and CLAUDE.md 'Where we are' sections are STALE (they still say Sprint 1) — trust the commits, stage outputs, and docs/science validation docs for true current state (Sprints 1-6)."
```

## Executive Summary

Aether is an AI-native dashboard and analysis engine for orbital/planetary monitoring data, unifying hyperspectral/thermal/atmospheric data through one typed ontology and turning raw observation into defensible, contextualized briefs. The MVP wedge is **super-emitter methane event reconstruction**: detect and quantify a plume, surface ranked source hypotheses, render it on a dashboard, produce a brief.

Current state is well past the original Sprint 1 baseline. The end-to-end wedge is built and validated on one real event (**Turkmenistan Goturdepe, EMIT 2022-08-15**): matched-filter detection + IME quantification (~27.1 t/hr, 0.75 Pearson vs NASA L2B), field/sector-level source attribution (OGIM-backed, honest about sparse coverage), and a CesiumJS dashboard inspector that renders the committed results verbatim. The active work, **Sprint 6 (HITRAN independence)**, generates our own methane absorption spectrum `k` to retire the dependence on NASA's per-granule target. The **v2 saturation-aware k** (finite-enhancement log-radiance regression) now reproduces NASA's target shape (r=0.99) **and restores end-to-end retrieval fidelity** (Pearson vs NASA L2B back to 0.73 ≈ Sprint 2's 0.75) — independence is validated and retrieval-ready. The remaining step is **operational migration** (re-running the committed pipeline with the v2 k, which moves the displayed headline ~27 → ~23 t/hr ours-cal) and the gated provenance-line flip — held for human review rather than changing the user-facing number unilaterally.

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

- **Sprint 6 review gate** (human + chat Claude): review the v2 saturation-aware result and authorize the **operational migration** — re-running the committed Stage A/B with the v2 `k` so the dashboard retrieval is genuinely independent (moves the displayed headline ~27 → ~23 t/hr ours-cal).
- **Provenance-line UI update** — fidelity gate now **MET**, but intentionally **not flipped this turn**: the displayed numbers + `target_spectrum_source` still come from the NASA-`k` run, so relabelling them "independent" before re-deriving them would misrepresent the screen. Flip after the operational migration.
- **Eval harness** runs a `stub_pipeline` (0/3 recall); the real matched filter is not yet registered as the eval pipeline.
- **No hard blocker.** Decision point only: whether to change the user-facing emission rate by migrating the operational pipeline to the v2 `k` — held for review (outward-facing change).

## Validation & Testing

_Verbatim results of a fresh run on **2026-06-09 14:02:04 MST** (not transcribed from any prior doc)._

**`uv run pytest` — exit code 0**
```
================ 179 passed, 6 deselected, 2 warnings in 20.31s ================
```
The 6 deselected are network-gated integration tests. The suite includes the no-fabrication guard (attribution entities trace to the committed OGIM subset) and the HITRAN independence guards (both the v1 linear and the v2 saturation-aware `k` regenerate reproducibly and read no value from NASA's file). **What this proves: the plumbing, schema guards, and reproducibility hold — NOT that the science thesis is validated** (see Validated vs. Unvalidated below).

**`uv run ruff check .` — exit code 1**
```
Found 74 errors.
```
All 74 are in **pre-existing files, not current Sprint 6 work**: chiefly the diagnostic scripts (`scripts/diagnose_stage_a.py` 18, `..._confirm.py` 15, `..._alignment.py` 13, etc.), plus `packages/ontology/aether_ontology/entities.py` (6), `eval/harness/aether_eval/cli.py` (4), the untracked `tools/setup_rag.py` (2), and a couple of tests. Rule breakdown: 37 × E501, 19 × N806, 7 × F541, 3 × F401, and 1 each of I001/F841/B905. All Sprint 6 `hitran_k` files pass `ruff check` per-file; the repo-wide failure is legacy lint debt. **The linter currently fails (exit 1); this is not hidden.**

- **Sprint 1 gate:** PASSED — `aether reproduce <event_id>` renders a real methane plume; Goturdepe Stage A/B committed.
- **Eval:** `uv run aether-eval run` → stub_pipeline, recall 0/3 (baseline only; real detection not wired into the harness).
- **Sprint 6 control:** the Stage B runner fed NASA's `k` reproduces Sprint 2's Pearson exactly (full 0.7354 / bbox 0.7485), confirming the pipeline is faithful and the divergence is the `k` swap alone.

## Validated vs. Unvalidated

> ⚠️ **The 179 passing tests are NOT proof that the core thesis is validated.** They exercise plumbing, schema guards, reproducibility, and the no-fabrication guards. The scientific claims are validated only where explicitly stated below, against real reference data — on a **single event (Goturdepe)**.
>
> **Note:** an earlier instruction asked to distinguish PX4/Gazebo items (SIH telemetry, Gazebo DetachableJoint baseline, INDI+RLS offboard controller) and to pull from `ROADMAP.md`. **None of those exist in this repository** — there is no PX4, Gazebo, MAVLink, INDI/RLS, SIH, telemetry bridge, or `ROADMAP.md` here (verified by grep; the only ADR is 0001-ontology-as-foundation). Aether is a methane-detection/attribution engine, not a flight-control project. Rather than fabricate that content, the table below applies the same validated-vs-written discipline to Aether's *actual* state, from `docs/science/` and the task briefs.

**VALIDATED (verified against real reference data / reproducible runs):**
- **Matched-filter detection + IME quantification on the real Goturdepe EMIT granule**, validated against NASA's L2B CH4ENH product: bbox Pearson **0.7485** (`docs/science/sprint2_validation.md`, `stage_a_outputs/`, `stage_b_outputs/q_estimate.json`).
- **Independent HITRAN `k` (v2 saturation-aware) — shape AND retrieval fidelity validated:** spectral shape vs NASA target r = **0.993**; end-to-end Pearson vs NASA L2B = **0.731** (≈ Sprint 2's 0.749) — fidelity restored. NASA file never read in generation (guard tests). The +1.66× over-amplitude is reproduced independently (1.46×); NASA-anchored flux 16.0 t/hr ≈ Sprint 2's 16.3 (`docs/science/sprint6_hitran_independence.md` §8). NOTE: validated as a method/artifact; the *operational dashboard retrieval* is not yet migrated to it (see Unvalidated).
- **Pipeline faithfulness control (Sprint 6):** the runner fed NASA's `k` reproduces Sprint 2's Pearson exactly (full 0.7354 / bbox 0.7485) — so the v2 fidelity recovery is the `k`, not the pipeline.
- **API serves committed artifacts byte-for-byte** (endpoint tests assert API JSON == committed files; no-fabrication guard on attribution entities).

**UNVALIDATED (written/planned, or run but NOT proven against ground truth):**
- **The DISPLAYED dashboard quantification is still NASA-`k`-derived.** The committed operational result (27.1 t/hr, `stage_a/b_outputs`, `q_estimate.json`) was computed with NASA's `k`. Migrating it to the validated v2 `k` (→ ~23.4 t/hr ours-cal) is the pending, reviewable step; until then the UI provenance honestly names NASA.
- **Detection performance via the eval harness: UNVALIDATED.** `aether-eval` runs a `stub_pipeline` (0/3 recall); the real matched filter is **not wired into the harness**, so the eval number does not reflect actual detection performance.
- **Source attribution: not validated against ground truth.** The engine runs and is honest (field/sector-level, sparse-coverage caveats), but the ranked hypotheses are *not* checked against a confirmed source.
- **Generalization: UNVALIDATED beyond one event.** All quantitative validation is on Goturdepe only; Permian is deferred (press-release reference only, no per-granule NASA target).
- **AI orchestration layer (`packages/ai`): not built.**
- **Absolute flux accuracy:** the NASA-L2B-anchored flux (~16 t/hr) is consistent across methods but is NOT independently validated against an in-situ or peer-reviewed single-source measurement (Thorpe 2023 is a 12-source cluster total). The residual 1.46× vs 1.66× over-amplitude awaits the deferred physics refinements.

## Next Steps

1. Sprint 6 human review → authorize the **operational migration**: re-run committed Stage A/B with the v2 `k`, regenerate the dashboard artifacts, then flip the gated provenance line to independent HITRAN2020/HAPI and retire the NASA-dependence caveat.
2. Optional deferred physics refinements (layered background, H₂O/SZA LUT, per-pixel sensitivity, RFM cross-check) to close the residual 1.46× vs 1.66×.
3. Wire the real matched-filter detection into the eval harness so `aether-eval` reflects true performance.
4. Refresh README.md / CLAUDE.md "Where we are" to current state (Sprints 1–6).

## Context for Future Agents

- **Scientific integrity is the product.** Never fabricate data, granule IDs, plume coordinates, emission rates, or citations. Every benchmark event needs a real peer-reviewed/authoritative reference (schema-enforced). Hypotheses are ranked candidates with explicit assumptions and a falsification path — never asserted as truth. Uncertainty is structural (carried, not dropped). When a value isn't available, say so and leave a marked TODO.
- **Data sources are LOCKED:** EMIT, Sentinel-5P TROPOMI, Landsat 8/9 ST, ERA5, Carbon Mapper catalog, and a global oil & gas infrastructure database (OGIM v2.7, Zenodo doi:10.5281/zenodo.15103476). Do not add a seventh without explicit instruction. Ocean/marine, the 3D explorer, and SDA/orbital modules are deferred (architecture supports them; `planetary_body` is first-class).
- **Never commit raw data** (`.tif`, `.zarr`, `.nc`, large `.npz`) — gitignored; caches in `.aether_cache/`. Small derived artifacts (JSON/MD/PNG, the OGIM subset, the HITRAN line list) are committed for reproducibility.
- **Conventions:** uv workspace, Python 3.12 pinned, Pydantic v2 `extra="forbid"`, Ruff (line length 100), mypy strict (import-untyped on scientific deps is pre-existing). Frontend: pnpm, `tsc --noEmit` must pass. Commit small and focused; run the suite before committing.
- **Honesty examples already in the repo:** Permian renders "pending" (no invented numbers); attribution degrades to field/sector when OGIM has no facility data in Turkmenistan; the Sprint 6 provenance line is left unchanged even though the v2 `k` is validated — because the *displayed* numbers were computed with NASA's `k`, and relabelling them "independent" without re-deriving them would misrepresent the screen. Match this standard. Scaling is always derived forward from physics, never reverse-fit to a target flux.
