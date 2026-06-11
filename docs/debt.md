# Tracked technical debt

A living snapshot of known, deliberately-deferred debt so "pre-existing" stays a
tracked fact, not a standing policy. Update the snapshot date + counts whenever the
list materially changes.

## Lint debt — RETIRED (Sprint 8)

`uv run ruff check .` exits **0** as of Sprint 8 (was 72 legacy errors, snapshot
2026-06-10). The burn-down: real fixes everywhere (line wraps with byte-identical
rendered output, `strict=` on `zip`, unused-variable cleanups, auto-fixes), plus
two documented exceptions where the rule is genuinely wrong for the file:

- `[tool.ruff.lint.per-file-ignores]` in the root `pyproject.toml` exempts
  `scripts/diagnose_stage_a_alignment.py` and `scripts/diagnose_stage_a_confirm.py`
  from **N806 only** — they use the matched-filter matrix notation from the
  literature (`X`, `S`, `T`, `C`, `G`), and lowercasing it would obscure the
  physics they document.
- One `# noqa: N818` on `aether_eval.runner.EventNotRunnable` — it is a
  control-flow signal ("report this event as not_runnable"), not an error; the
  `-Error` suffix would misname the semantics.

CI enforces `ruff check .` == 0 from Sprint 8 onward, which retires the
"72 pre-existing" line from gate reports permanently.

## Other deferred items (cross-referenced)

- ~~**Eval harness runs a `stub_pipeline`** (0/3 recall)~~ — **RETIRED (Sprint 8
  Item 1)**: `aether-eval run` now executes the real pipeline with honest
  semantics (ADR 0002, `docs/science/eval_semantics.md`).
- **1.46× vs 1.66× MF over-amplitude residual** — a hypothesis (effective-layer /
  flat-continuum), not an established cause; awaits deferred physics refinements.
  See `docs/science/sprint6_hitran_independence.md` §8–9.
- **Topbar "Acquired" readout (apps/web)** — shows the FIRST active event's
  acquisition timestamp as a global HUD field; with two live events this is
  ambiguous. Per-event acquisition is correct in each inspector. Cosmetic,
  non-scientific; logged at the Sprint 7 Stage D review. **In scope for Sprint 8
  Item 4.**
- **Comparative-claims guard gap (attribution)** — Sprint 7's
  `test_comparative_claims_are_truthful` asserts comparative spatial claims against
  the computed candidate table for the **Permian H1 facility path only**. There is
  no general guard parsing comparative language ("nearest", "closer than", "largest")
  across ALL hypothesis rationales/events, so a false comparative in a future event's
  prose would still need human gate review to catch. **In scope for Sprint 8
  Item 4** (cheap version, or formally re-logged as a permanent human-gate item).
- **No CI** — the test suite + guard suites run locally only. **In scope for
  Sprint 8 Item 2** (GitHub Actions: ruff 0 + pytest with visible deselection +
  guard suite + web typecheck/build).
