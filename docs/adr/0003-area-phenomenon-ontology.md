# ADR 0003 — Area-phenomenon ontology evolution (heat vertical)

- **Status:** Proposed (Sprint 9 Stage A; enum addition implemented now,
  `BaselineDefinition` implemented in Stage B)
- **Date:** 2026-06-11
- **Context owner:** Sprint 9 heat vertical (`docs/tasks/sprint9_heat.md`)

## Context

Aether's second phenomenon domain is surface-temperature anomalies — an AREA
phenomenon: no source point S, no plume mask, no facility to attribute. The brief
requires it to be an *instantiation* of the existing ontology (ADR 0001), not a
parallel schema. The Stage A probe (`docs/reports/sprint9_stage_a_report.md`)
found the ontology already fits area events almost everywhere:
`PhenomenonType.HEAT_WAVE`, `Phenomenon.region`, `SensorType.REANALYSIS` /
`GROUND_BASED`, `Detection.footprint`, and the parallel
measurements/units/uncertainty dicts all compose unchanged.

Two genuine gaps exist, plus one structural-honesty requirement from the heat
vertical's cardinal rule 2 (satellite land-surface "skin" temperature and 2 m air
temperature are different physical quantities and may never be conflated).

## Decision

Three additive evolutions; nothing methane-shaped changes.

### 1. `DetectionType.AIR_TEMPERATURE_ANOMALY` (implemented at Stage A)

`THERMAL_ANOMALY` is reserved for **skin/LST** anomalies (its existing semantics:
a thermal-sensor surface signal). A new enum value `AIR_TEMPERATURE_ANOMALY`
types 2 m-air-temperature anomaly detections (reanalysis- or station-grounded).

Rationale: the LST-vs-air distinction becomes *structural* — a `Detection` cannot
blur the two quantities, validation tiers can be earned per-quantity (in-situ 2 m
truth exists; in-situ skin truth does not), and guards can assert no Detection
mixes LST and air-temperature measurement keys. Implemented now because the
Stage A benchmark YAML must declare `expected_detection_types` honestly and the
schema validates against this enum. Additive StrEnum value — zero behavior
change for existing events (regression: methane artifacts byte-identical).

### 2. `BaselineDefinition` (specified here, implemented in Stage B)

An anomaly is only meaningful relative to a baseline; an anomaly detection
without a typed baseline is the heat-vertical analogue of a measurement without
provenance. New small model (Pydantic v2, `extra="forbid"`):

```python
class BaselineDefinition(BaseModel):
    dataset: str            # e.g. "ARCO-ERA5 v3 2m_temperature"
    period_start_year: int  # e.g. 1991
    period_end_year: int    # e.g. 2020
    day_window_days: int    # +/- half-window around the day of year
    statistic: str          # "mean" | "percentile"
    percentile: float | None
    hours_utc: list[int]    # which hours define the daily statistic
    note: str | None
```

Carried as `Detection.baseline: BaselineDefinition | None = None`, with a model
validator: detections of anomaly types (`THERMAL_ANOMALY`,
`AIR_TEMPERATURE_ANOMALY`, `SST_ANOMALY`) MUST carry a baseline; plume/other
detections leave it `None`. Deferred to Stage B so the field lands together with
the code that populates it and the guard that enforces it (no dead schema).

### 3. Area-detection location semantics (documentation + guard, no schema change)

For area detections, `Detection.location` is the **anomaly-weighted centroid**
(fly-to target), the peak-anomaly cell is carried in `measurements`, and
`footprint` is mandatory-by-guard. The attribution wedge machinery (bearings,
source point S) is explicitly NOT reused for area phenomena — Stage C's factor
hypotheses carry computed diagnostics instead of geometry.

## Consequences

- Methane events untouched: all changes are additive; existing YAMLs, artifacts,
  and guards are unaffected (verified by the full suite + byte-identity checks).
- The eval harness's `check_runnable` is EMIT-shaped and must become
  phenomenon-aware when the heat recipe is wired in (Stage B; flagged in the
  Stage A report). Until then a heat benchmark event reports `not_runnable`
  with an EMIT-shaped reason — mechanically safe, semantically stale, stated in
  the event YAML's notes.
- Stage C will add the factor-hypothesis evidence schema in `packages/causal`
  (per its own ADR), not in the ontology — same separation facility attribution
  uses today.
