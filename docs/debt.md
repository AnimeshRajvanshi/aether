# Tracked technical debt

A living snapshot of known, deliberately-deferred debt so "pre-existing" stays a
tracked fact, not a standing policy. Update the snapshot date + counts whenever the
list materially changes.

## Lint debt — `ruff check .` (snapshot 2026-06-10)

`uv run ruff check .` reports **72 errors, all in pre-existing legacy files**. The
linter exits non-zero (1) repo-wide; this is not hidden. **Every file touched by
current sprint work lints clean per-file** — the policy is "no new lint debt", not
"repo-wide clean", until the legacy backlog below is paid down.

### By rule

| rule | count | what |
|---|---:|---|
| E501 | 37 | line too long (>100) |
| N806 | 19 | non-lowercase variable in function (scientific `P`, `T`, `N`, `U` etc.) |
| F541 | 7 | f-string without placeholders |
| RUF059 | 3 | unused unpacked variable |
| RUF010 | 2 | use explicit `str()` conversion in f-string |
| I001 | 1 | unsorted imports |
| F841 | 1 | unused local variable |
| F401 | 1 | unused import |
| B905 | 1 | `zip()` without `strict=` |

### By file

| file | count | nature |
|---|---:|---|
| `scripts/diagnose_stage_a.py` | 18 | one-off Stage A diagnostic |
| `scripts/diagnose_stage_a_confirm.py` | 15 | one-off diagnostic |
| `scripts/diagnose_stage_a_alignment.py` | 13 | one-off diagnostic |
| `scripts/diagnose_tail_and_streak.py` | 6 | one-off diagnostic |
| `packages/ontology/aether_ontology/entities.py` | 6 | E501 in docstrings/literals |
| `scripts/run_segmentation_blob_check.py` | 4 | one-off diagnostic |
| `eval/harness/aether_eval/cli.py` | 4 | CLI formatting |
| `packages/ontology/tests/test_models.py` | 2 | test line length |
| `eval/harness/tests/test_pipelines.py` | 2 | test line length |
| `scripts/diagnose_blob_mass_change.py` | 1 | one-off diagnostic |
| `eval/harness/aether_eval/metrics.py` | 1 | line length |

The bulk (52 of 72) is in `scripts/diagnose_*.py` — single-use investigation
scripts kept for the scientific record. The remainder is in the ontology package,
the eval harness, and a couple of tests.

### Paydown plan (not yet scheduled)

- Most are mechanically fixable (`ruff check --fix` clears 11; `--unsafe-fixes`
  more). The N806 cases are intentional scientific notation (`P`, `T`, `N_air`,
  `U_eff`) and should be addressed with a targeted per-file `# noqa: N806` or a
  scoped rule exclusion rather than renaming the physics.
- Suggested order: (1) the diagnostic scripts as a single sweep, (2) ontology +
  eval, (3) a ruff config decision on N806 for `packages/detection` / `scripts`.

## Other deferred items (cross-referenced)

- **Eval harness runs a `stub_pipeline`** (0/3 recall) — the real matched filter is
  not wired into `aether-eval`. Tracked in `PROJECT_STATUS.md` open tasks.
- **1.46× vs 1.66× MF over-amplitude residual** — a hypothesis (effective-layer /
  flat-continuum), not an established cause; awaits deferred physics refinements.
  See `docs/science/sprint6_hitran_independence.md` §8–9.
