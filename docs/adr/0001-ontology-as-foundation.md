# ADR 0001: The planetary ontology is the foundation

**Status:** Accepted (2026-05-28)

## Context

Aether spans multiple sensor modalities (hyperspectral, thermal, SAR, reanalysis, space-object catalogs), multiple use cases (emissions, heat, ocean, orbital), and eventually multiple planetary bodies (Earth, Moon, Mars). Each of these has its own native data models and conventions. Without a unifying schema, the platform becomes a federation of fragile point integrations and the "causal suggestion" claim is impossible — you cannot reason across data sources that don't share a vocabulary.

## Decision

We define a single typed ontology (`packages/ontology`) that every other layer consumes. Six core entity types:

- `Observation` — a sensor measurement
- `Detection` — something found in observations
- `Phenomenon` — a temporally extended real-world thing detections cluster into
- `Entity` — a real-world object (facility, operator, satellite, vessel...)
- `Hypothesis` — a ranked candidate explanation with evidence and assumptions
- `Brief` — a human-facing narrative artifact

Every entity carries: stable UUID, `planetary_body` field, mandatory `Provenance`, optional `Confidence`, free-form `tags`. Geometry is GeoJSON-compatible on the Python side; PostGIS handles storage.

The ontology is implemented in Pydantic v2 with `extra="forbid"` on every model. Unknown fields are rejected loudly. Validators catch obvious mistakes (inverted bboxes, end-before-start time ranges).

## Why this matters more than any other architectural decision

1. **Cross-source reasoning depends on it.** "Was there a thermal anomaly co-located with this plume?" is trivial if both are `Detection`s with shared spatial/temporal/provenance fields. It's a multi-week integration if they're not.
2. **Reproducibility is structural.** Mandatory `Provenance` with `parents` UUIDs creates a derivation graph from raw scenes through detections, phenomena, hypotheses, and briefs. Any output can be traced back to its inputs.
3. **Mars/Moon expansion is data-source plumbing, not refactoring.** `planetary_body` is first-class from day 1.
4. **Hypothesis credibility lives here.** A `Hypothesis` requires `claim`, `assumptions`, `falsification`, `score`, `rank`, and `generation_method`. The schema enforces the discipline that makes the "causal suggestion" feature defensible to scientists.

## Alternatives considered

- **No ontology, sensor-native models per package.** Rejected: makes cross-source reasoning O(n²) in implementation effort.
- **Pure relational schema, no Pydantic.** Rejected: we want the same types in Python services and (via codegen) TypeScript frontend without divergence.
- **Pydantic but no UUID provenance graph.** Rejected: provenance is the basis of reproducibility, which is the basis of scientific defensibility.

## Consequences

- Every new feature must extend or compose existing entities, not invent parallel schemas.
- Breaking changes to the ontology are major-version events for the whole platform.
- TypeScript types must be generated from these Pydantic models (planned: pydantic2ts or equivalent in a later sprint).
- We pay a small upfront cost (this sprint) for compounding leverage over the project lifetime.

## Review

To be revisited after sprint 6 (end of Phase 1 MVP). Likely refinements: a dedicated `Source` entity for data providers/missions; a `Relationship` edge type if implicit relationships via UUID lists become unwieldy; a versioning strategy for backwards-compatible entity evolution.
