# ADR 0004 — Area-event recall semantics (eval harness)

- **Status:** Accepted (Sprint 9 Stage B; required by the Stage A gate review,
  ruling 3)
- **Date:** 2026-06-11
- **Extends:** ADR 0002 (eval metric families)

## Context

ADR 0002's recall matching is centroid-distance (haversine within the event's
`location_precision_km`). That is the right shape for point-source events: a
plume has a source, and "found a plume where the literature says one was" is a
distance question. It is the wrong shape for AREA phenomena: two valid analyses
of the same heatwave can produce anomaly-field centroids hundreds of km apart
(the centroid moves with the threshold and the day weighting) while describing
the same physical event over the same region. Sprint 9 Stage A set
`location_precision_km: 300` on the heat benchmark as an explicitly provisional
placeholder; the gate review approved it only until this ADR lands.

## Decision

For events whose `phenomenon_type` is an **area phenomenon** (`heat_wave`,
`marine_heat_wave` — the set is a named constant, extended deliberately, never
inferred), spatial recall matching uses **bbox overlap**, not centroid distance:

- A detection matches spatially when
  `area(det_bbox ∩ event_bbox) ≥ 0.5 × min(area(det_bbox), area(event_bbox))` —
  the intersection covers at least half of the smaller of the two boxes.
- `det_bbox` is the bounding box of `Detection.footprint`; area is computed on
  an equirectangular approximation (lon degrees scaled by cos of the box's mean
  latitude) — adequate at heatwave scales, documented here rather than hidden.
- A detection of an area event **without a footprint does not match** — an area
  detection that cannot say what area it covers is not a detection of an area
  event. (`Detection.footprint` is mandatory-by-guard for anomaly detections
  per ADR 0003.)
- The temporal criterion is unchanged from ADR 0002.
- Point events (everything else, including all methane events) keep the
  existing centroid-distance semantics, bit-for-bit.

Rationale for `0.5 × min(...)` rather than IoU: the benchmark bbox is the
peak-day qualifying cluster while an honest detection may cover the window's
union extent (or one sensor's subset of it); IoU punishes that asymmetry,
min-overlap does not, while still rejecting incidental edge contact.

`location_precision_km` on area events becomes **documentation of the
centroid's meaningful scale only** — it no longer participates in matching.
The heat benchmark YAML notes this.

## Consequences

- `eval/harness/aether_eval/metrics.py` implements the area branch; the
  point-event path is untouched (regression: full suite + the committed
  methane eval values must not move).
- The heat event remains `not_runnable` until its recipe is wired (this same
  stage generalizes `check_runnable`'s reason to stop being EMIT-shaped for
  non-emission phenomena), so this ADR changes no current eval numbers; it
  defines the semantics the heat recipe will be scored under.
