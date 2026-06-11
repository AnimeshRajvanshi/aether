# Eval harness semantics — what `aether-eval run` measures and what it refuses to fake

**Sprint 8.** Companion to ADR 0002. This is the contract for every number the
harness prints. If a metric here cannot be computed honestly for an event, the
harness prints a status with a reason — it never substitutes a lookalike number.

## The two metric families

### 1. REGRESSION (always computed; what CI is allowed to care about)

The real pipeline — per-granule HITRAN k → matched filter → orthorectification
→ plume mask → IME → Q — is re-run **end-to-end from cached inputs, in memory**
(it writes nothing into `stage_a_outputs/`, `stage_b_outputs/`, or anywhere in
the repo), and its fresh values are compared against the committed,
gate-reviewed artifacts:

| Check | Committed source | Tolerance |
|---|---|---|
| Q (ours-calibrated, t/hr) | `stage_b_outputs/<id>/q_estimate.json` `q_central_t_hr` | ±1% (fractional) |
| Q (NASA-calibrated, t/hr) | same, `q_central_nasa_calibrated_t_hr` | ±1% (fractional) |
| Pearson vs NASA L2B (full scene) | `stage_a_outputs/<id>/stage_a_report.json` | ±0.01 (absolute) |
| Pearson vs NASA L2B (in plume bbox) | same | ±0.01 (absolute) |
| Plume centroid | `q_estimate.json` centroid lat/lon | ≤0.5 km (haversine) |

What a green regression row claims: **"the pipeline still produces the reviewed
science."** It does NOT claim the science is externally validated — that is the
tier system's job (`docs/science/validation_tiers.md`), and no event is
VALIDATED.

Each event re-runs its own canonical recipe:

- **Goturdepe** mirrors the frozen Sprint-6 operational recipe
  (`scripts/run_migration_v2_operational.py`): fully offline — cached L1B/L2A
  zarr + L2B GeoTIFF, surface p/T and ERA5 wind carried from the committed
  NASA-k baseline with the same grid-cell-identity assertion, Varon
  self-segmentation (p=0.05) and largest CC in the plume bbox.
- **Permian** mirrors the Sprint-7 shared runner
  (`scripts/run_event_quantification.py`): cached granules + live ARCO-ERA5
  fetches (surface state + wind), per-granule k from the granule's own
  geometry/SRF/surface state, NASA-footprint-anchored mask (L2B > 200 ppm·m in
  the complex-000524 bbox).

The frozen scripts remain the historical record of how the committed artifacts
were produced; the eval recipes are the living re-verification of the same
computation. They are intentionally redundant — if they drift apart, the
regression checks are exactly what catches it.

### 2. EXTERNAL-TRUTH (computed only where a usable reference exists)

**Detection recall** — "did we find a plume where the literature says one
was?" — is valid for both live events. A detection matches when it is the right
type, inside the event's time window, and within the event's
`location_precision_km` of the reference location. That precision is schema
data because reference locations have wildly different meanings:

- Goturdepe: **40 km** — the reference location (54.0, 39.5) is a field-center
  estimate for Thorpe 2023's 12-source cluster spanning the Goturdepe +
  Barsagelmez fields (~60 km extent). Our committed single-plume centroid is
  30.2 km from it; that *is* "a plume in the field the literature flagged",
  which is the only granularity the reference supports.
- Permian: **3 km** — the location is pinned to NASA's published complex-000524
  footprint (~3.2 × 5.6 km); committed centroid sits 1.0 km away.
- Aliso: **1 km** — facility-precise (Conley 2016, well SS-25). Moot while the
  event is not runnable; declared for honesty.

**Quantification vs external flux** is computed **only** for measurements
declared `reference_usability: comparable`. The current scoreboard therefore
contains NO quantification-MAPE:

- Goturdepe 163 ± 18 t/hr → **`not_comparable(scope_mismatch)`**: a 12-source,
  multi-granule cluster total vs our single-plume, single-granule retrieval.
  Per `docs/science/sprint2_validation.md`, agreement/disagreement is not
  claimable.
- Permian 18.3 t/hr → **`not_comparable(context_only)`**: press-release value,
  `uncertainty: null`, no method or granule attribution. Sprint 7 ruling: NASA's
  own L2B through the same IME method gives ~0.9 t/hr, so the gap is
  method/definition, not retrieval. 18.3 is context, never a target.

These are outcomes, not failures. A MAPE against either reference would be a
fabricated validation number; the harness refuses it structurally (the schema
requires every measurement to declare its usability; the metrics code never
computes error terms for non-comparable references).

## Runnability

- **Aliso Canyon (2015)** predates EMIT's launch (July 2022). The real EMIT
  pipeline raises `EventNotRunnable` with the stated reason; the scoreboard
  shows **`not_runnable — no EMIT coverage: the event window
  (2015-10-23..2016-02-11) predates EMIT's July 2022 launch; no canonical EMIT
  acquisition is pinned`**. It is excluded from the recall denominator and
  never silently dropped from the report.
- An event the pipeline *should* handle but crashes on is `error` and DOES
  count against recall — a crash is not an excuse.

## The honest scoreboard (expected)

```
aliso_canyon_2015                   NOT_RUNNABLE (no EMIT coverage in 2015)
turkmenistan_goturdepe_2022_08_15   recalled; regression 5/5 green;
                                    quantification: not_comparable (scope_mismatch)
permian_basin_2022                  recalled; regression 5/5 green;
                                    quantification: not_comparable (context_only) ×2
Detection recall (runnable): 2/2    Regression: green    Quantification MAPE: none claimable
```

## The CI / local split

The full `aether-eval run` needs cached EMIT granules (~GB, gitignored) and
network (ARCO-ERA5 for Permian). It is therefore **local and network-gated**,
by the same mechanism as the other integration tests: the full-run eval test is
marked `@pytest.mark.integration` and auto-deselected by the root
`pyproject.toml` (`-m 'not integration'`). The deselected count is asserted in
CI (visible, not hidden).

What CI **does** run, on every push:

- the harness logic tests: schema usability/precision validation, matching,
  not_comparable semantics, runnability accounting, scoreboard rendering;
- the regression-comparison assertions against committed artifacts that need no
  granule data (committed values fed through the tolerance logic must pass;
  values perturbed beyond tolerance must fail);
- the full guard suite (no-fabrication, no-staleness, independence, byte-match,
  tier rubric).

What only a local operator can run: `uv run aether-eval run` (the real
pipeline, both events, ~minutes) and `uv run pytest -m integration`.

## What this harness can never do

It cannot upgrade a validation tier. Regression-green means reproducibility of
reviewed results; recall 2/2 means coarse localization against literature
locations; `not_comparable` means exactly what it says. Independent flux truth
(the reserved VALIDATED tier) requires a new kind of reference, not a new
metric.
