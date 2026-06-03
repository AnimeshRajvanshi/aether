"""Benchmark event schema.

A `BenchmarkEvent` is a typed, validated description of a known phenomenon — used
as ground truth when scoring detection pipelines. Every event lives as a YAML file
in `eval/benchmark/` and is loaded into one of these objects.
"""

from __future__ import annotations

from datetime import datetime

from aether_ontology import (
    BBox,
    DetectionType,
    PhenomenonType,
    PlanetaryBody,
    Point,
    SensorType,
    TimeRange,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Measurement(BaseModel):
    """A known ground-truth measurement with uncertainty and unit.

    `note` is mandatory because uncertainty without context is misleading. Pin down
    whether this is a peak, mean, total, etc.
    """

    model_config = ConfigDict(extra="forbid")

    value: float
    uncertainty: float | None = Field(None, description="One-sigma absolute uncertainty in `unit`")
    unit: str
    note: str
    n_sources: int | None = Field(
        None,
        description=(
            "For cluster/aggregate measurements: how many distinct sources this "
            "value sums over. Makes single-vs-cluster comparability machine-readable "
            "(e.g. a single-plume estimate is not comparable to a 12-source total)."
        ),
    )


class Attribution(BaseModel):
    """Known source attribution. All fields optional — some events have unknown actors."""

    model_config = ConfigDict(extra="forbid")

    operator: str | None = None
    facility: str | None = None
    sector: str | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)


class ObservedBy(BaseModel):
    """A sensor that observed this event."""

    model_config = ConfigDict(extra="forbid")

    sensor: str
    sensor_type: SensorType
    note: str | None = None


class Reference(BaseModel):
    """A citation backing the known values of this event."""

    model_config = ConfigDict(extra="forbid")

    citation: str
    doi: str | None = None
    url: str | None = None


class CanonicalAcquisition(BaseModel):
    """A specific overpass pinned as the reference for a benchmark event.

    Some events have a particular overpass NASA's published values were derived
    from. Pinning it matters when downstream processing depends on per-granule
    artifacts (e.g., a per-granule unit absorption spectrum) that are only valid
    for the granule they were generated from. Optional: only set when the event
    has a defensible single-acquisition reference.
    """

    model_config = ConfigDict(extra="forbid")

    utc: datetime
    l1b_granule_ur: str | None = None
    l2a_mask_granule_ur: str | None = None
    l2b_ch4_granule_ur: str | None = None
    source: str = Field(..., min_length=1, description="Why this acquisition was pinned (citation)")


class BenchmarkEvent(BaseModel):
    """A ground-truth phenomenon used for evaluating Aether detection pipelines.

    Every field is required to be honest about what we know and don't know about
    the event. Free-form `notes` is where caveats live.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1, description="Stable filename-safe id")
    name: str
    planetary_body: PlanetaryBody = PlanetaryBody.EARTH

    phenomenon_type: PhenomenonType
    expected_detection_types: list[DetectionType] = Field(..., min_length=1)

    date_range: TimeRange
    location: Point
    bbox: BBox

    known_measurements: dict[str, Measurement] = Field(default_factory=dict)
    attribution: Attribution = Field(default_factory=Attribution)
    observed_by: list[ObservedBy] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    canonical_acquisition: CanonicalAcquisition | None = None

    notes: str | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_location_in_bbox(self) -> BenchmarkEvent:
        """A small sanity check: the point location should be inside the bbox."""
        lon, lat = self.location.lon, self.location.lat
        b = self.bbox
        if not (b.min_lon <= lon <= b.max_lon and b.min_lat <= lat <= b.max_lat):
            raise ValueError(
                f"location ({lon}, {lat}) is outside bbox "
                f"({b.min_lon}, {b.min_lat}) - ({b.max_lon}, {b.max_lat})"
            )
        return self

    @model_validator(mode="after")
    def _check_event_has_at_least_one_reference(self) -> BenchmarkEvent:
        """A benchmark event with no references can't be ground truth. Refuse it."""
        if not self.references:
            raise ValueError(
                f"BenchmarkEvent '{self.event_id}' has no references. "
                "Every benchmark event must cite at least one authoritative source."
            )
        return self
