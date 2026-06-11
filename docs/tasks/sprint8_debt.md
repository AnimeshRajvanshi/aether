# Task: Sprint 8 — The Debt Sprint (verification infrastructure, no new capability)

**Owner:** Claude Code
**Reviewer:** chat Claude + human
**Scope:** Three core items — (1) the eval harness off `stub_pipeline` and onto the real pipeline with honest metric semantics, (2) CI enforcing the full guard suite on every push, (3) the ruff legacy burn-down — plus the small logged debts. **No new science, no new events, no UI redesign, no chatbot.** This sprint exists because the portfolio is next: the repo must verify what it claims before strangers read it.

## Why this sprint is non-negotiable

`uv run aether-eval run → stub_pipeline, recall 0/3` is the one artifact in this repo that contradicts everything else the repo claims to be. We built a benchmarking system in Sprint 1 and have never once scored the real pipeline with it. A reviewer who finds that line concludes the validation story is theater. Likewise, guards that run only when someone remembers to run them are not guards — CI is what makes the no-fabrication/no-staleness/independence suite an enforced property instead of a habit.

## Item 1 — Eval harness: real pipeline, honest semantics

**The design problem (decided here, not improvised):** our three benchmarks have fundamentally different reference characters, and the harness must NOT pretend otherwise:

- **Goturdepe:** reference flux = Thorpe 163±18 for a 12-source CLUSTER — scope-mismatched to our single plume by our own validation doc ("agreement/disagreement is not claimable"). A naive quantification-MAPE against it would be fake.
- **Permian:** reference flux = 18.3 t/hr press-release, `uncertainty: null`, context-only by Sprint 7's own ruling. Same problem.
- **Aliso Canyon (2015):** predates EMIT's launch entirely. The real EMIT pipeline CANNOT run it. It must be reported as `not_runnable` with the stated reason (no EMIT data exists for 2015) — never silently dropped, never faked.

**Therefore the harness separates two metric families, mirroring the tier system:**

1. **REGRESSION metrics (always computed, the CI-meaningful ones):** the real pipeline, run end-to-end from cached inputs, must reproduce our own committed, gate-reviewed results within tight tolerance — detection localization (plume centroid/source within a stated km tolerance of the committed value), Pearson-vs-L2B within ±0.01, Q within ±1% of the committed `q_estimate.json`. This is "the pipeline still produces the reviewed science," which is what a regression harness can honestly claim.
2. **EXTERNAL-TRUTH metrics (computed only where a usable reference exists):** detection recall against the benchmark's reference *location* (valid for both events — did we find a plume where the literature says one was?). Quantification vs external flux: for Goturdepe and Permian the harness must output **`not_comparable` with the machine-readable reason** (scope-mismatch / context-only), NOT a number. The schema gains whatever field this needs (`reference_usability` or similar) — extend the Sprint 1 schema with an ADR if the change is structural.

**Implementation:** wire the real MF→ortho→segmentation→IME pipeline (the shared parameterized runner) into `aether-eval run`. Pipeline runs need cached granule data + network for ERA5, so the full eval run is **local/network-gated** (same mechanism as the 6 deselected tests); what CI runs is the harness's *logic* tests + the regression assertions against committed artifacts that don't need granule downloads. Document the split. Expected honest output: Goturdepe + Permian detection recall 2/2, regression green, quantification column `not_comparable(reason)` ×2, Aliso `not_runnable(no EMIT coverage in 2015)`. **Update the README/status so "0/3 stub" is replaced by this real, honest scoreboard.**

## Item 2 — CI (GitHub Actions)

`.github/workflows/ci.yml`, two jobs, on push + PR to main:
- **python:** `uv sync` → `uv run ruff check .` (must be zero after Item 3) → `uv run pytest` (network-gated tests auto-deselect in CI exactly as they do locally; the deselected count is asserted/visible, not hidden).
- **web:** pnpm install → `pnpm typecheck` → `pnpm build`.
Cache uv + pnpm stores for speed. The full guard suite (no-fabrication, no-staleness, independence, byte-match, tier guards) runs in the python job — confirm by listing the guard test files in the workflow's log output or a summary step. Add the CI status badge to the README. If any test currently depends on local-only state in a way that breaks CI, fixing that dependency is in scope (commit fixtures or gate it properly); skipping it silently is not.

## Item 3 — Ruff legacy burn-down

The 72 pre-existing errors go to **zero**: fix the real ones; for any rule that is genuinely wrong for a file (e.g. a diagnostic script's intentional style), use targeted `# noqa: RULE` with a one-line justification or a documented per-path ignore in the ruff config — no blanket disables. After this sprint `ruff check .` exits 0 and CI enforces it forever, which retires the "72 pre-existing" line from gate reports permanently. Delete `docs/debt.md`'s ruff entry on completion.

## Item 4 — Small logged debts (close or formally re-log, none silently dropped)

- **Topbar "Acquired" readout** shows the first event's timestamp globally → make it per-selected-event (cosmetic fix, small).
- **Comparative-claims guard** (the Stage C gap: a false "nearest/closer-than" claim isn't machine-caught): implement the cheap version — parse comparative superlatives in hypothesis rationales/claims against the computed candidate table. If genuinely not cheap, write the gap into the testing notes as a permanent human-gate item with rationale, and remove it from floating debt.
- **`py.typed` markers** for workspace packages (retires the long-standing mypy `import-untyped` noise) — cheap, do it.

## Out of scope

No new events, science changes, UI redesign (beyond the topbar fix), chatbot, deployment/hosting (that's the portfolio sprint), or H2O/SZA-LUT physics. Goturdepe and Permian committed artifacts remain byte-identical — this sprint touches infrastructure, not results.

## Definition of done

- `uv run aether-eval run` executes the REAL pipeline locally: regression metrics green against committed artifacts; external-truth columns honest (`2/2` recall, `not_comparable` ×2 with reasons, Aliso `not_runnable`); semantics documented in `docs/science/eval_semantics.md` (+ ADR if schema changed).
- CI green on main: ruff 0, pytest green with deselection visible, typecheck + build clean, guard suite demonstrably included, badge in README.
- Ruff at zero with justified-noqa only; debt log updated.
- Topbar fixed; comparative-claims guard implemented or formally re-logged; py.typed added.
- Gate report to `docs/reports/sprint8_debt_report.md`; PROJECT_STATUS.md re-verified (real exit codes) showing the new eval scoreboard.
- STOP for review. If the eval-metric semantics prove unworkable as specified, STOP EARLY at that point and report the conflict rather than improvising different semantics — the metric meaning is the one judgment call in this sprint and it stays at the gate.

## Build order

1. Eval semantics doc + schema extension (ADR if needed) → wire real pipeline → local full run → honest scoreboard.
2. Ruff burn-down (before CI, so CI starts at zero).
3. CI workflow + badge; verify a real push goes green.
4. Small debts. Gate report. Commit at each step; STOP.
