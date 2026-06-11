# ADR 0002 — Eval metrics split into REGRESSION and EXTERNAL-TRUTH families; reference usability is schema data

**Status:** Accepted (Sprint 8)
**Context:** `docs/tasks/sprint8_debt.md` Item 1; `docs/science/eval_semantics.md` (companion);
`docs/science/validation_tiers.md`; `docs/science/sprint2_validation.md` §scope;
Sprint 7 Stage B/D rulings (18.3 t/hr context-only; VALIDATED reserved).

## Problem

Since Sprint 1 the eval harness has scored pipelines with a single metric family:
detection recall plus a quantification MAPE of our flux against each benchmark's
`known_measurements`. That design silently assumes every reference value is a
same-scope, usable truth. Our three benchmarks violate that assumption in three
different ways:

1. **Goturdepe** — Thorpe 2023's 163 ± 18 t/hr is a 12-source *cluster total*
   (multi-granule). Our retrieval quantifies ONE plume from one granule. Our own
   validation doc rules agreement/disagreement "not claimable". A MAPE against it
   is a number that *looks* like a validation result and isn't.
2. **Permian** — the 18.3 t/hr figure is a press release with no method, date, or
   uncertainty (`uncertainty: null`). Sprint 7 ruled it CONTEXT ONLY: NASA's own
   L2B through our same single-overpass IME method gives ~0.9 t/hr, so the ~21×
   gap is method/definition, not retrieval error. A MAPE against 18.3 would
   manufacture a fake ~95% "error".
3. **Aliso Canyon (2015)** — predates EMIT's launch (July 2022). The real EMIT
   pipeline *cannot* observe it, ever. Counting it as a recall miss (the old
   stub's 0/3 framing) or silently dropping it both misrepresent the benchmark.

Meanwhile the thing a harness on this repo *can* honestly enforce — that the real
pipeline still reproduces the committed, gate-reviewed results — was not measured
at all (`stub_pipeline`, 0/3).

## Decision

### 1. Two metric families, mirroring the validation-tier system

- **REGRESSION (always computed; the CI-meaningful family).** The real pipeline,
  re-run end-to-end from cached inputs, must reproduce our own committed,
  gate-reviewed artifacts within stated tolerances: plume centroid within
  0.5 km of the committed centroid, Pearson-vs-L2B within ±0.01, Q within ±1% of
  the committed `q_estimate.json`. The claim is "the pipeline still produces the
  reviewed science" — nothing stronger.
- **EXTERNAL-TRUTH (computed only where a usable external reference exists).**
  Detection recall against the benchmark's reference *location* (valid for both
  live events). Quantification vs an external flux is computed **only** when the
  reference is declared `comparable`; otherwise the harness outputs
  **`not_comparable` with the machine-readable reason** — never a number.

### 2. Reference usability is schema data, not prose

`Measurement` gains two fields (Pydantic v2, `extra="forbid"`):

- `reference_usability: ReferenceUsability` — **required**, one of
  `comparable` | `scope_mismatch` | `context_only`. No default: every benchmark
  measurement must declare how it may be used.
- `usability_reason: str` — required whenever usability is not `comparable`;
  the machine-readable reason the harness reports verbatim.

Current assignments: Goturdepe 163 ± 18 → `scope_mismatch` (12-source cluster
total vs our single plume); Permian 18.3 → `context_only` (press release, no
uncertainty/method; Sprint 7 ruling); Permian plume_length 3.3 km →
`context_only` (press-release-grade, and our mask is anchored to NASA's published
footprint, so plume geometry is not an independent prediction); Aliso's Conley
2016 measurements → `comparable` (peer-reviewed in-situ aircraft measurements of
the event itself — moot while the event is not runnable, but honest data).

### 3. Reference-location precision is schema data

`BenchmarkEvent` gains `location_precision_km: float | None`. Recall matching
uses it as the spatial tolerance when set (falling back to the CLI tolerance
when not). Rationale: Goturdepe's reference location is a *field-center
estimate* for a cluster spanning the Goturdepe and Barsagelmez fields (~60 km
extent); our committed plume centroid sits 30.2 km from it. Scoring that with a
5 km tolerance answers a question the reference cannot ask. The honest recall
question — "did we find a plume where the literature says one was?" — is asked
at the precision the literature actually has: ~40 km (field/cluster scale) for
Goturdepe, 3 km (NASA complex-000524 footprint scale) for Permian, 1 km
(facility scale, Conley) for Aliso.

### 4. Runnability is reported, never silently dropped

A pipeline that cannot run an event raises `EventNotRunnable(reason)`; the
harness reports the event as `not_runnable` with that reason and **excludes it
from the recall denominator** (it stays on the scoreboard). For the real EMIT
pipeline, an event with no pinned `canonical_acquisition` is not runnable; for
Aliso the stated reason is that no EMIT data exists for 2015 (EMIT launched
July 2022). Pipeline errors on runnable events are `error` status and DO count
against the denominator — a crash is not an excuse.

## Consequences

- The honest scoreboard for the current benchmark is: detection recall **2/2**
  (runnable events), regression **green**, quantification **`not_comparable`
  ×2 with reasons**, Aliso **`not_runnable` (no EMIT coverage in 2015)**. No
  quantification-MAPE number exists for any current event, and that is the
  correct output.
- The full real-pipeline run needs cached granules plus network (ERA5) and is
  local/network-gated (the `integration` pytest marker). CI runs the harness's
  logic tests and the regression-comparison assertions against committed
  artifacts; the split is documented in `docs/science/eval_semantics.md`.
- Adding a future event with a genuinely comparable reference (e.g. a
  peer-reviewed same-scope flux) requires only `reference_usability: comparable`
  — the MAPE machinery is retained and tested, not deleted.
- Schema change is additive but breaking for YAML authors (usability is
  required). All three committed YAMLs are updated in the same commit.
