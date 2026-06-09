# PROJECT_STATUS.md

> Last verified by running tests + linter on 2026-06-08 22:19:34 MST.

```yaml
phase: "Sprint 6 - HITRAN Independence (Stage A + B complete, awaiting human review)"
status: "In Progress"
last_updated: "2026-06-08"
updated_by: "Claude"
confidence: "High"
links:
  notion_hub: "TBD (no Notion hub created yet — do not fabricate a link)"
  adrs: ["docs/adr/0001-ontology-as-foundation.md"]
  key_commits:
    - "6ff5d46"  # chore: add comprehensive .dockerignore
    - "e0008de"  # Sprint 6 Stage B - end-to-end HITRAN k + honest verdict
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
  - "Sprint 6 review gate (owner: human + chat Claude): review the calibration verdict and the saturation diagnosis; decide whether to authorize a Stage C saturation-aware k."
  - "Provenance-line UI update (GATED, not done): only if/when an independent k preserves retrieval fidelity. Currently NOT updated — UI still names NASA's target, which is honest."
  - "Eval harness still runs 'stub_pipeline' (0/3 recall); the real matched-filter detection is not yet wired in as the eval pipeline."
  - "Optional Permian stretch (Sprint 6): not attempted — gated on a clean Stage B, which we did not get."
blockers:
  - "Sprint 6 not closeable: our independent HITRAN k matches NASA in spectral SHAPE (r=0.93) but end-to-end retrieval fidelity degrades (bbox Pearson 0.75 -> 0.53); independence is achieved spectroscopically but is NOT yet retrieval-ready. Awaiting review before any further k work."
recent_changes:
  - "Sprint 6 Stage B: ran Goturdepe detection + quantification with our independent k (algorithm unchanged), forward-derived scale (ppm_scaling=1.0, NOT reverse-fit). Pearson 0.53, Q(ours-cal) 11.9 t/hr, amplitude vs NASA L2B 0.79x (the +1.66x over-amplitude is NOT preserved). Diagnosed to missing line-core saturation in the Beer-Lambert-linear k; not patched toward NASA."
  - "Sprint 6 Stage A: generated independent methane unit absorption k from HITRAN2020/HAPI; spectral shape r=0.93 vs NASA target (cross-check only)."
  - "Sprint 5: SOURCE ATTRIBUTION section in the inspector rendering the committed hypotheses.json verbatim (caveats preserved)."
  - "Sprint 4: field/sector-level source-attribution engine (OGIM-backed, no fabricated facilities)."
validation_status:
  verified_at: "2026-06-08 22:19:34 MST (fresh run of pytest + ruff)"
  tests: "uv run pytest -> 175 passed, 6 deselected, 2 warnings (exit code 0). NOT proof of the science thesis — see 'Validated vs. Unvalidated'."
  lint: "uv run ruff check . -> Found 72 errors (exit code 1, FAILING). All in PRE-EXISTING files, not current Sprint 6 work: mostly scripts/diagnose_*.py (E501/N806), plus a few in packages/ontology/ and eval/harness/. Rule counts: 37 E501, 19 N806, 7 F541, 1 each I001/F841/F401/B905. Sprint 6 files lint clean per-file."
  sprint_gate: "Sprint 1 gate PASSED (aether reproduce renders a real methane plume). Current gate: Sprint 6 human review of the HITRAN independence calibration verdict before the provenance-line UI update."
  eval: "aether-eval run = stub_pipeline, 0/3 recall (baseline; real detection not yet registered as the eval pipeline)"
next_milestones:
  - "Sprint 6 review -> decide Stage C (saturation-aware k via layered/finite-dc Jacobian) vs park independence as a shape-validated prototype."
  - "If/when k is retrieval-ready: update the dashboard provenance line (the only in-scope UI change) and retire the NASA-dependence caveat."
  - "Wire the real matched-filter detection into the eval harness so aether-eval reflects actual performance."
notes_for_agents:
  "Read CLAUDE.md fully before changes. Run uv run pytest and (for detection/causal changes) aether-eval run before committing. Never fabricate data, granule IDs, coordinates, emission rates, or citations. NOTE: README.md and CLAUDE.md 'Where we are' sections are STALE (they still say Sprint 1) — trust the commits, stage outputs, and docs/science validation docs for true current state (Sprints 1-6)."
```

## Executive Summary

Aether is an AI-native dashboard and analysis engine for orbital/planetary monitoring data, unifying hyperspectral/thermal/atmospheric data through one typed ontology and turning raw observation into defensible, contextualized briefs. The MVP wedge is **super-emitter methane event reconstruction**: detect and quantify a plume, surface ranked source hypotheses, render it on a dashboard, produce a brief.

Current state is well past the original Sprint 1 baseline. The end-to-end wedge is built and validated on one real event (**Turkmenistan Goturdepe, EMIT 2022-08-15**): matched-filter detection + IME quantification (~27.1 t/hr, 0.75 Pearson vs NASA L2B), field/sector-level source attribution (OGIM-backed, honest about sparse coverage), and a CesiumJS dashboard inspector that renders the committed results verbatim. The active work, **Sprint 6 (HITRAN independence)**, generates our own methane absorption spectrum `k` to retire the dependence on NASA's per-granule target; Stage A (shape, r=0.93) and Stage B (end-to-end) are complete and **awaiting human review** — independence is achieved spectroscopically but the retrieval fidelity degraded (Pearson 0.53), so it is not yet operational.

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

- **Sprint 6 review gate** (human + chat Claude): review the HITRAN calibration verdict and the saturation diagnosis; decide on a Stage C saturation-aware `k`.
- **Provenance-line UI update** — GATED and intentionally **not done**: the dashboard still names NASA's per-granule target because the operational retrieval still uses NASA's `k`. Overstating independence would be dishonest.
- **Eval harness** runs a `stub_pipeline` (0/3 recall); the real matched filter is not yet registered as the eval pipeline.
- **Blocker:** Sprint 6 cannot be closed — our independent `k` reproduces NASA's spectral shape (r=0.93) but the end-to-end map Pearson drops 0.75 → 0.53 (and ~0.04 on strong plume pixels). Independence is achieved spectroscopically, not yet in retrieval fidelity. Diagnosed (missing line-core saturation in the linear `k`), not patched toward NASA.

## Validation & Testing

_Verbatim results of a fresh run on **2026-06-08 22:19:34 MST** (not transcribed from any prior doc)._

**`uv run pytest` — exit code 0**
```
================ 175 passed, 6 deselected, 2 warnings in 11.55s ================
```
The 6 deselected are network-gated integration tests. The suite includes the no-fabrication guard (attribution entities trace to the committed OGIM subset) and the HITRAN independence guards (k generation reads no value from NASA's file; reproducible regeneration). **What this proves: the plumbing, schema guards, and reproducibility hold — NOT that the science thesis is validated** (see Validated vs. Unvalidated below).

**`uv run ruff check .` — exit code 1**
```
Found 72 errors.
[*] 11 fixable with the `--fix` option (5 hidden fixes can be enabled with the `--unsafe-fixes` option).
```
All 72 are in **pre-existing files, not current Sprint 6 work**: chiefly the diagnostic scripts (`scripts/diagnose_stage_a.py` 18, `..._confirm.py` 15, `..._alignment.py` 13, etc.), plus `packages/ontology/aether_ontology/entities.py` (6), `eval/harness/aether_eval/cli.py` (4), and a couple of tests. Rule breakdown: 37 × E501, 19 × N806, 7 × F541, and 1 each of I001/F841/F401/B905. New Sprint 6 files pass `ruff check` per-file; the repo-wide failure is legacy lint debt. **The linter currently fails (exit 1); this is not hidden.**

- **Sprint 1 gate:** PASSED — `aether reproduce <event_id>` renders a real methane plume; Goturdepe Stage A/B committed.
- **Eval:** `uv run aether-eval run` → stub_pipeline, recall 0/3 (baseline only; real detection not wired into the harness).
- **Sprint 6 control:** the Stage B runner fed NASA's `k` reproduces Sprint 2's Pearson exactly (full 0.7354 / bbox 0.7485), confirming the pipeline is faithful and the divergence is the `k` swap alone.

## Validated vs. Unvalidated

> ⚠️ **The 175 passing tests are NOT proof that the core thesis is validated.** They exercise plumbing, schema guards, reproducibility, and the no-fabrication guards. The scientific claims are validated only where explicitly stated below, against real reference data — on a **single event (Goturdepe)**.
>
> **Note on this request:** the instruction asked to distinguish PX4/Gazebo items (headless SIH telemetry path, bridge end-to-end, gate plumbing, Gazebo DetachableJoint baseline, INDI+RLS offboard controller) and to pull from `ROADMAP.md`. **None of those exist in this repository** — there is no PX4, Gazebo, MAVLink, INDI/RLS, SIH, telemetry bridge, or `ROADMAP.md` here (verified by grep; the only ADR is 0001-ontology-as-foundation). Aether is a methane-detection/attribution engine, not a flight-control project. Rather than fabricate that content (which the cardinal rule forbids), the table below applies the same validated-vs-written discipline to Aether's *actual* state, sourced from `docs/science/` and the task briefs.

**VALIDATED (verified against real reference data / reproducible runs):**
- **Matched-filter detection + IME quantification on the real Goturdepe EMIT granule**, validated against NASA's L2B CH4ENH product: bbox Pearson **0.7485** (`docs/science/sprint2_validation.md`, `stage_a_outputs/`, `stage_b_outputs/q_estimate.json`).
- **Pipeline faithfulness control (Sprint 6):** the Stage B runner fed NASA's `k` reproduces Sprint 2's Pearson exactly (full 0.7354 / bbox 0.7485).
- **HITRAN `k` spectral SHAPE** vs NASA's per-granule target (cross-check only): Pearson **0.93** (`docs/science/sprint6_hitran_independence.md`).
- **API serves committed artifacts byte-for-byte** (endpoint tests assert API JSON == committed files; no-fabrication guard on attribution entities).

**UNVALIDATED (written/planned, or run but NOT proven against ground truth):**
- **HITRAN independence at the RETRIEVAL level: NOT validated.** End-to-end map Pearson drops 0.75 → **0.53** (and ~0.04 on strong plume pixels); the independent `k` is NOT a proven drop-in for NASA's. A saturation-aware `k` (Stage C) is *planned but unbuilt*.
- **Detection performance via the eval harness: UNVALIDATED.** `aether-eval` runs a `stub_pipeline` (0/3 recall); the real matched filter is **not wired into the harness**, so the eval number does not reflect actual detection performance.
- **Source attribution: not validated against ground truth.** The engine runs and is honest (field/sector-level, sparse-coverage caveats), but the ranked hypotheses are *not* checked against a confirmed source.
- **Generalization: UNVALIDATED beyond one event.** All quantitative validation is on Goturdepe only; Permian is deferred (press-release reference only, no per-granule NASA target).
- **AI orchestration layer (`packages/ai`): not built.**
- **Absolute flux accuracy:** the NASA-L2B-anchored flux (~15–16 t/hr) is consistent across methods but is NOT independently validated against an in-situ or peer-reviewed single-source measurement (Thorpe 2023 is a 12-source cluster total).

## Next Steps

1. Sprint 6 human review → authorize/decline Stage C (saturation-aware `k`: layered column / finite-Δc Jacobian — better physics, never NASA-tuning).
2. Only if `k` becomes retrieval-ready: update the gated provenance line and retire the NASA-dependence caveat.
3. Wire the real matched-filter detection into the eval harness so `aether-eval` reflects true performance.
4. Refresh README.md / CLAUDE.md "Where we are" to current state (Sprints 1–6).

## Context for Future Agents

- **Scientific integrity is the product.** Never fabricate data, granule IDs, plume coordinates, emission rates, or citations. Every benchmark event needs a real peer-reviewed/authoritative reference (schema-enforced). Hypotheses are ranked candidates with explicit assumptions and a falsification path — never asserted as truth. Uncertainty is structural (carried, not dropped). When a value isn't available, say so and leave a marked TODO.
- **Data sources are LOCKED:** EMIT, Sentinel-5P TROPOMI, Landsat 8/9 ST, ERA5, Carbon Mapper catalog, and a global oil & gas infrastructure database (OGIM v2.7, Zenodo doi:10.5281/zenodo.15103476). Do not add a seventh without explicit instruction. Ocean/marine, the 3D explorer, and SDA/orbital modules are deferred (architecture supports them; `planetary_body` is first-class).
- **Never commit raw data** (`.tif`, `.zarr`, `.nc`, large `.npz`) — gitignored; caches in `.aether_cache/`. Small derived artifacts (JSON/MD/PNG, the OGIM subset, the HITRAN line list) are committed for reproducibility.
- **Conventions:** uv workspace, Python 3.12 pinned, Pydantic v2 `extra="forbid"`, Ruff (line length 100), mypy strict (import-untyped on scientific deps is pre-existing). Frontend: pnpm, `tsc --noEmit` must pass. Commit small and focused; run the suite before committing.
- **Honesty examples already in the repo:** Permian renders "pending" (no invented numbers); attribution degrades to field/sector when OGIM has no facility data in Turkmenistan; the Sprint 6 provenance line is left unchanged because independence is not yet retrieval-ready. Match this standard.
