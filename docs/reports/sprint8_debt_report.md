# Sprint 8 gate report — the debt sprint (verification infrastructure, no new capability)

**Status: COMPLETE — held for human review (gate).**
**Verification run: 2026-06-11 13:31 MST** — `uv run pytest` exit 0 (235 passed,
7 deselected); `uv run ruff check .` exit 0; committed Goturdepe + Permian
artifacts byte-identical (`git diff --stat` over `stage_a_outputs/`,
`stage_b_outputs/`, `attribution_outputs/`, `apps/api/aether_api/assets/` = 0
lines); `tsc --noEmit` + `next build` clean.

Commits (this sprint, in order):
- `b2beffe` feat(eval): Item 1 — real pipeline in aether-eval with honest metric semantics
- `39d12f7` fix(lint): Item 3 — ruff legacy burn-down, 72 → 0
- `5dd851e` ci: Item 2 — GitHub Actions enforcing the full guard suite
- `093dec8` feat(guards,web): Item 4 — small logged debts closed
- (this commit) gate report + PROJECT_STATUS re-verification

## Item 1 — Eval harness: real pipeline, honest semantics ✅

`uv run aether-eval run` now executes the REAL pipeline (per-granule HITRAN k →
matched filter → orthorectification → plume mask → IME → Q) end-to-end from
cached inputs, **in memory** — it writes nothing into the committed output
directories. The `stub_pipeline, recall 0/3` line is retired from every status
surface.

**Semantics (ADR 0002 + `docs/science/eval_semantics.md`)** — two metric
families, mirroring the tier system, exactly as specified in the brief:

- **REGRESSION** (always computed; the CI-meaningful family): fresh values vs
  committed gate-reviewed artifacts — Q ours-cal and NASA-cal ±1% fractional,
  Pearson full-scene and in-bbox ±0.01 absolute, plume centroid ≤0.5 km.
  Goturdepe re-runs the frozen Sprint-6 offline recipe (committed-baseline
  surface state + winds with the grid-cell-identity assertion, Varon
  self-segmentation); Permian re-runs the Sprint-7 shared-runner recipe (live
  ARCO-ERA5, NASA-footprint-anchored mask).
- **EXTERNAL-TRUTH** (only where a usable reference exists): detection recall
  at each reference's own stated precision — the new, schema-level
  `location_precision_km` (Goturdepe 40 km: its location is a field-center
  estimate for Thorpe's 12-source cluster; Permian 3 km: pinned to NASA
  complex 000524; Aliso 1 km: facility-precise). Quantification vs external
  flux requires `Measurement.reference_usability == comparable` — a **required**
  new schema field. Goturdepe 163±18 is declared `scope_mismatch` and Permian
  18.3 `context_only` (each with a machine-checked `usability_reason`), so the
  harness outputs **`not_comparable` with the reason — never a number**.
- **Aliso Canyon** is reported **`not_runnable`** ("no EMIT coverage: the event
  window (2015-10-23..2016-02-11) predates EMIT's July 2022 launch...") via
  `EventNotRunnable` control flow — excluded from the recall denominator,
  never silently dropped.

**Verified local full run (exit 0):**

```
Events: 3 (2 runnable, 1 not_runnable)
  aliso_canyon_2015: NOT_RUNNABLE — no EMIT coverage (window predates EMIT's July 2022 launch)
  turkmenistan_goturdepe_2022_08_15: ran in 13.9s — recalled (30.2 km, field-scale reference)
    regression 5/5 PASS, all at +0.00% / +0.0000 / 0.000 km deltas
    quantification vs emission_rate: NOT_COMPARABLE (scope_mismatch)
  permian_basin_2022: ran — recalled (1.0 km)
    regression 5/5 PASS, all at +0.00% deltas
    quantification vs emission_rate: NOT_COMPARABLE (context_only)
    quantification vs plume_length_km: NOT_COMPARABLE (context_only)
Detection recall (runnable events): 2/2  (precision 1.000)
Regression vs committed artifacts: 10/10 — GREEN
Quantification MAPE: none claimable
```

The 0.00% regression deltas confirm the eval recipes reproduce the frozen
scripts' computation exactly, not merely within tolerance. The integration-
marked full-run test (`eval/harness/tests/test_real_pipeline.py`) passed
locally (33.6s) and additionally asserts the committed `q_estimate.json` files
are byte-identical after the run.

**The eval-semantics spec proved workable as written — no early STOP was
needed.** One addition was required to make recall honest (flagged for review):
`location_precision_km`, because Goturdepe's committed plume centroid is
30.2 km from the YAML's field-center reference location, so any single global
km-tolerance would have been either meaningless (5 km → fake miss against a
field-scale reference) or absurd for Permian (40 km). The brief's "the schema
gains whatever field this needs" covers it; ADR 0002 documents both fields.

## Item 2 — CI (GitHub Actions) ✅ (real-push verification pending, human)

`.github/workflows/ci.yml`, two jobs on push + PR to main, uv + pnpm caches:

- **python:** `uv sync --frozen` → `uv run ruff check .` (zero) → full
  `uv run pytest` → an assertion step that the deselected count **equals** the
  integration-marked set (collect-only), with the gated test list written to
  the job summary → a guard-suite step that asserts the guard files exist and
  lists them + their collected test count in the summary (no-fabrication ×2,
  no-staleness ×2, tier rubric, comparative claims, HITRAN independence, eval
  regression logic; byte-match/regen guards live inside the no-fabrication
  files).
- **web:** `pnpm install --frozen-lockfile` → `pnpm typecheck` → `pnpm build`.

Badge added to the README. Every step was verified locally with the exact CI
commands, including the deselection assert (7 == 7) and a full-suite run under
a **scratch `HOME`** proving no test depends on `~/.aether_cache` or
`~/.netrc` (the brief's "local-only state" risk — none found, nothing needed
gating fixes).

**Deviation, flagged:** the brief says "verify a real push goes green", but the
standing repo rule is do-not-push (the branch carries 11 unpushed commits and
the PUSH task is owner: human). I did not push. First green run on GitHub is
confirmed at your `git push`; if anything environmental breaks (runner version,
action pinning), it's a CI-config fix, not a science change.

## Item 3 — Ruff legacy burn-down ✅

72 → **0**; `ruff check .` exits 0 and CI enforces it permanently. Real fixes
everywhere (line wraps with byte-identical rendered output, `zip(strict=True)`
where lengths are guaranteed, unused-variable cleanups, auto-fixes for
I001/F541/RUF010/F401); two documented exceptions, no blanket disables:

- `per-file-ignores`: **N806 only** for `scripts/diagnose_stage_a_alignment.py`
  and `scripts/diagnose_stage_a_confirm.py` — frozen diagnostics using the
  literature's matched-filter matrix notation (X, S, T, C, G).
- one `# noqa: N818` on `EventNotRunnable` — a control-flow signal, not an
  error; the `-Error` suffix would misname the semantics.

`docs/debt.md`'s ruff entry is deleted (section now records the retirement and
the two exceptions). The "72 pre-existing" line is retired from gate reports.

## Item 4 — Small logged debts ✅

- **Topbar "Acquired"**: per-selected-event — the chip renders only while an
  event is selected, with that event's own timestamp. tsc + build green.
- **Comparative-claims guard (cheap version implemented)**:
  `packages/causal/tests/test_comparative_claims.py` parses proximity
  superlatives across ALL events' hypotheses and verifies them against each
  artifact's computed `nearest_by_*` table; unverifiable claims fail loudly;
  distance-closer wells must be disclosed; the Stage-C false phrasing is banned
  verbatim. Negative-tested against three doctored artifacts (all rejected).
  **Formally re-logged remaining scope** (docs/debt.md + guard docstring):
  size/count superlatives and exclusivity claims stay human-gate — entity
  linking is not cheap.
- **py.typed** added to all seven workspace packages.

## What this sprint did NOT do (scope discipline)

No new events, no science changes, no UI redesign beyond the topbar chip, no
chatbot, no deployment. **Goturdepe and Permian committed artifacts are
byte-identical** (verified after the eval full run, after the integration test,
and at this closeout: 0 diff lines across all four artifact trees). No
validation tier moved; VALIDATED remains reserved and unearned.

## Flagged for human review

1. `location_precision_km` per-event recall tolerances (40 / 3 / 1 km) — the
   one judgment call added beyond the brief's letter; rationale in ADR 0002.
2. The real-push CI verification (one `git push` publishes 11 commits and
   triggers the first run; badge goes live then).
3. The comparative-claims guard's permanent human-gate remainder (exclusivity +
   size/count claims) — confirm you accept that as the documented boundary.
4. Permian's `plume_length_km` was declared `context_only` partly on
   circularity grounds (our mask is anchored to NASA's footprint, so plume
   geometry is not an independent prediction) — confirm the framing.
