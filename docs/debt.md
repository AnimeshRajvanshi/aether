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
- ~~**Topbar "Acquired" readout (apps/web)**~~ — **RETIRED (Sprint 8 Item 4)**:
  the chip is now per-selected-event (renders only while an event is selected,
  with that event's own acquisition timestamp); the ambiguous global
  "first active event" readout is gone.
- **Comparative-claims guard** — **generalized (Sprint 8 Item 4)**:
  `packages/causal/tests/test_comparative_claims.py` parses proximity
  superlatives (nearest/closest/closer/farther/farthest) across ALL events'
  committed hypotheses and verifies them against each artifact's computed
  `nearest_by_*` table: unverifiable proximity claims fail, candidates must be
  nearest on a computed axis, distance-closer wells must be disclosed, and the
  Stage-C false phrasing is banned verbatim. **Remaining human-gate scope
  (permanent, by design):** size/count superlatives ("largest", "most active")
  and exclusivity claims ("the only…") need entity linking that is not cheap —
  they stay on the gate-review checklist, documented in the guard's docstring.
- ~~**No CI**~~ — **RETIRED (Sprint 8 Item 2)**: `.github/workflows/ci.yml`
  enforces ruff 0 + full pytest (deselection asserted visible) + guard-suite
  listing + web typecheck/build on every push/PR to main. (Green-on-a-real-push
  confirmation happens at the human `git push`, per the standing rule.)
