# aether-ontology

Typed Pydantic models for the Aether planetary ontology.

## What lives here

The core entity types every other Aether package depends on:

| Type          | Purpose                                                                  |
|---------------|--------------------------------------------------------------------------|
| `Observation` | A single scene or measurement from a sensor at a time and place.         |
| `Detection`   | Something found in one or more observations (plume, anomaly, object).    |
| `Phenomenon`  | A temporally extended thing detections belong to (event, heat wave...). |
| `Entity`      | A real-world object (facility, operator, satellite, vessel, region).     |
| `Hypothesis`  | A proposed explanation with evidence, assumptions, and a score.          |
| `Brief`       | A human-facing narrative artifact summarizing a phenomenon.              |

All entities carry a `planetary_body` field. Earth is the default; Moon and Mars are first-class from day 1 so later expansion is a data-source problem, not a refactor.

All entities carry `provenance` (where it came from and how) and optional `confidence` (uncertainty representation).

## Design principles

1. **Every entity is reproducible.** Provenance is mandatory; you can always trace back to raw inputs.
2. **Uncertainty is structural, not an afterthought.** Confidence has a value, bounds, method, and note.
3. **Geometry uses GeoJSON-compatible shapes.** PostGIS handles the storage side.
4. **No silent extra fields.** `extra="forbid"` on every model. If you need a new field, add it deliberately.
5. **Extensible enums.** New sensor types, detection types, and entity types are added by extending the enum, not by stuffing values into free-form strings.

## Usage

```python
from datetime import datetime
from aether_ontology import (
    Observation, Detection, DetectionType, SensorType,
    Provenance, Confidence, Point, GeoJSONGeometry, TimeRange,
)

obs = Observation(
    sensor="EMIT",
    sensor_type=SensorType.HYPERSPECTRAL,
    granule_id="EMIT_L2B_CH4ENH_001_20240615T...",
    time_range=TimeRange(start=datetime(2024, 6, 15, 18, 30)),
    footprint=GeoJSONGeometry(type="Polygon", coordinates=[[[-102.0, 31.0], ...]]),
    provenance=Provenance(source="EMIT L2B v1", source_id="..."),
)
```

## Tests

```bash
uv run pytest packages/ontology
```
