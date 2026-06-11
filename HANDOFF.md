# HANDOFF.md — cold-start handoff for the next session

> Session-retirement handoff. Written to let a brand-new session pick up cold.
> Pair this with `PROJECT_STATUS.md`, `CLAUDE.md`, and the committed gate reports.

## Re-verify before trusting anything

**Verification results must NOT be transcribed forward. The next session must re-run
pytest and ruff itself and update PROJECT_STATUS.md per existing discipline.**

Concretely, before doing new work: `git status` + `git log --oneline -5`, then
`uv run pytest`, `uv run ruff check .`, and (for `packages/detection`/`packages/causal`
changes) `uv run aether-eval run`. Note: **PROJECT_STATUS.md is currently stale** — it
still describes Sprint 6 and predates the Sprint 7 commits below; update it after you
re-verify.

## Where things stand

- **Branch:** `main`, **ahead of `origin/main` by 6 commits (unpushed)**. Do not push
  unless explicitly told to.
- **Latest commit:** `984bb78` — *docs(reports): Sprint 7 Stage A — Permian
  reference-data probe (gate)*.
- **Current sprint: Sprint 7 (generality — Permian).** Stage A (reference-data probe)
  is **done and committed**; the brief gates Stages B/C/D behind human review of each
  prior stage. Build order: Stage A probe → **STOP (here now)** → Stage B → Stage C →
  Stage D, each a STOP gate.
- **Sprint 6 (HITRAN independence):** functionally **COMPLETE and green**, still
  **awaiting human review sign-off** to formally close (it was an outward-facing change
  — the Goturdepe headline moved 27.1 → 23.4 t/hr ours-cal). Two human decisions remain
  open (see Open threads).

## Migration gate status — what remains

- **Sprint 6 gate:** PASSED technically (operational migration done, all guards green).
  *Remaining to formally close:* human sign-off on `docs/reports/sprint6_migration_report.md`
  + `docs/reports/sprint6_dashboard_panels.md`, and the filing-decision confirmation
  (v2 lives at canonical operational filenames; NASA-k preserved as `*.nasa_k.*`
  siblings — the reviewer may request the inverse filing, which is just a rename).
- **Sprint 7 gate (current):** Stage A probe complete and stopped for review. *Remaining
  to pass into Stage B:* human review of the probe report, then run Stage B. The probe
  decided the earnable tier is **CROSS-CHECKED** (a NASA L2B CH4ENH raster exists for the
  granule → a Pearson spatial cross-check is possible), **not VALIDATED** (no
  peer-reviewed per-source flux; the 18.3 t/hr figure is press-release context only).

## Key decisions made in recent work (and why)

1. **Sprint 6 — v2 HITRAN k is now the OPERATIONAL Goturdepe retrieval.** Re-ran Stage
   A/B offline+reproducibly via `scripts/run_migration_v2_operational.py`; regenerated
   every derived artifact from the new outputs. Why: independence is only real if the
   *displayed* numbers come from the independent k, not just a validation artifact.
2. **"Alongside, not over" filing.** v2 results took the canonical operational filenames
   (so API/dashboard/guards validate the *served* artifacts); the NASA-k originals are
   preserved as committed `*.nasa_k.*` siblings. Why: keep the served data authoritative
   while never deleting the NASA-k scientific record. (Reviewer may prefer the inverse —
   flagged.)
3. **Uncertainty budget re-propagated, not transcribed.** Wind terms unchanged *by
   construction* (same ERA5 grid cell, asserted in the runner); mask sensitivity
   recomputed; MF-amplitude systematic is now the **independently measured 1.46×** (not
   the hand-carried 1.66×). The 1.46-vs-1.66 residual is labelled a **hypothesis**
   (effective-layer/flat-continuum), not an established cause.
4. **No-staleness guard suite** (`apps/api/tests/test_no_staleness.py`). Parses the
   numbers embedded in derived-artifact *prose* (hypotheses, brief, scope %, API notes,
   references) and asserts each traces to its upstream committed source — catching
   hardcoded literals that byte-match/regenerate guards cannot. It caught real stale
   `~27 t/hr` literals, a stale provenance reference still calling NASA's file "our k",
   and a stale `~20 deg` H1 bearing gap; all fixed by templating from source.
5. **Sprint 6 review fixes (`3319d64`).** The inspector's Provenance·References list is
   sourced from the **benchmark YAML** (`loaders._references`), not from
   `stage_a_report.target_spectrum_source` — which is why the first provenance flip
   missed it. Fixed the YAML entry (NASA target → spectral-shape cross-check only,
   r=0.993; added HITRAN2020 (Gordon 2022) + HAPI (Kochanov 2016) citations with
   verified DOIs). H1's bearing-gap rationale templated from the computed value.
6. **Sprint 7 Stage A — generality via parameterization, not a fork.** The OGIM acquire
   script was Goturdepe-hardcoded; refactored it to an `EVENTS` registry keyed by
   `event_id` (one shared code path). Goturdepe's committed outputs are byte-identical/
   untouched. The committed Permian OGIM subset is **dense** (12,284 features incl.
   10,744 wells vs Goturdepe's 114) — the first real test of facility-level attribution,
   and a ~12 MB artifact flagged for review.
7. **Cardinal rule honored throughout Sprint 7 probe:** 18.3 t/hr is context only (NASA
   JPL press release, no date/method/uncertainty — WebFetch-confirmed). The validation
   tier is decided by probe evidence, never asserted.

## Open threads & exact next steps (priority order)

1. **Sprint 7 Stage B** (the immediate next gated step, after human review of the probe):
   - Generate the Permian **per-granule v2 HITRAN k** from this granule's own
     geometry/SRF; extend independence + reproducibility guards to the new k. (No NASA
     per-granule target exists for this granule → no shape cross-check available; state
     it.)
   - Run the **shared parameterized pipeline** (MF → ortho → segmentation → IME → Q with
     ERA5 U_eff). **Parameterize the Goturdepe-shaped assumptions** still in the run/
     attribution/loader code (listed in the Stage A report) — do NOT fork a `_permian`
     variant.
   - Mandatory scene checks (re-run, don't assume): wind source-vs-centroid ΔQ%; U_eff
     regime vs the Varon 2–8 m/s range (preliminary |U₁₀|≈3.83 m/s, in-range but re-check
     at the true source); plume-mask sensitivity sweep.
   - Re-propagate the uncertainty budget from scratch; carry the +1.46× systematic as a
     Goturdepe-measured value with an explicit "transfer to this scene is unvalidated"
     note.
   - Internal-consistency diagnostics; honest comparison to 18.3 t/hr as context only.
   - Write `docs/science/sprint7_permian.md` + `docs/reports/sprint7_stage_b_report.md`;
     extend the no-staleness guards to the new artifacts. **STOP for review.**
2. **Sprint 6 close-out** (human): sign off the migration gate report + confirm the
   filing decision (canonical-v2 vs inverse). Until then Sprint 6 is "complete pending
   sign-off".
3. **Update PROJECT_STATUS.md** to reflect Sprint 7 (it currently stops at Sprint 6) —
   only after re-running verification (see top section).
4. **Stage C / Stage D** (gated, later): dense-coverage facility attribution with
   discrimination-honest confidence; then UI integration with visible validation-tier
   badges. Do not start until Stage B is reviewed.
5. **Lower priority / still deferred:** wire the real matched filter into the eval
   harness (it runs a `stub_pipeline`, 0/3 recall); the deferred physics refinements for
   the 1.46×-vs-1.66× residual; refresh README.md / CLAUDE.md "Where we are" (stale,
   still say Sprint 1). The 72 pre-existing ruff errors are tracked in `docs/debt.md`.

## Relevant file paths

- **Task brief / gates:** `docs/tasks/sprint7_permian.md`
- **Sprint 7 probe report:** `docs/reports/sprint7_stage_a_report.md`
- **Sprint 6 gate reports:** `docs/reports/sprint6_migration_report.md`,
  `docs/reports/sprint6_dashboard_panels.md`,
  `docs/reports/screenshots/provenance_panel_fixed.png`
- **Science docs:** `docs/science/sprint6_hitran_independence.md` (§9 = migration),
  `docs/science/sprint2_validation.md`, `docs/science/sprint4_attribution.md`
- **Tech-debt register:** `docs/debt.md`
- **Operational runner (Sprint 6):** `scripts/run_migration_v2_operational.py`
- **OGIM subset (parameterized):** `scripts/acquire_ogim_subset.py`;
  committed subset `packages/causal/aether_causal/resources/ogim/ogim_v2.7_permian_basin_region.geojson`
  (+ `.provenance.json`); Goturdepe `ogim_v2.7_goturdepe_region.geojson`
- **Guards:** `apps/api/tests/test_no_staleness.py`, `packages/causal/tests/test_no_fabrication.py`
- **Pipeline/attribution to parameterize in Stage B:** `scripts/run_stage_a_goturdepe.py`,
  `scripts/run_stage_b_goturdepe.py`, `packages/causal/aether_causal/attribution.py`,
  `scripts/build_dashboard_assets.py`, `apps/api/aether_api/loaders.py`
- **Benchmarks:** `eval/benchmark/turkmenistan_goturdepe_2022_08_15.yaml`,
  `eval/benchmark/permian_basin_2022.yaml`
- **Status:** `PROJECT_STATUS.md` (stale re Sprint 7), `CLAUDE.md` (operating manual)

## Environment notes (no secrets)

- `uv` workspace, Python 3.12 pinned. Frontend: `pnpm` in `apps/web` (`tsc --noEmit`
  must pass; `next build`).
- Caches in `~/.aether_cache/` (gitignored): EMIT L1B/L2A/L2B granules, the OGIM v2.7
  global GeoPackage (~2.9 GB, SHA-256 verified — no re-download needed), ERA5 via
  ARCO (token-free). NASA Earthdata auth via the user's `~/.netrc` (do not print it).
- Never commit raw data (`.tif`/`.zarr`/`.nc`/large `.npz`) — gitignored.
