"""Tests for the Aether ontology v0.1.

Covers the invariants that make the rest of the platform safe:
- Models reject unknown fields (no silent typos).
- Provenance is mandatory.
- Spatial and temporal validators catch obvious mistakes.
- Round-tripping through JSON works for every entity type.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aether_ontology import (
    BBox,
    Brief,
    Confidence,
    Detection,
    DetectionType,
    Entity,
    EntityType,
    GeoJSONGeometry,
    Hypothesis,
    Observation,
    Phenomenon,
    PhenomenonType,
    PlanetaryBody,
    Point,
    Provenance,
    SensorType,
    TimeRange,
)
from pydantic import ValidationError

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def basic_provenance() -> Provenance:
    return Provenance(source="EMIT L2B v1", source_id="EMIT_L2B_CH4ENH_001_TEST")


@pytest.fixture
def permian_point() -> Point:
    return Point(lon=-102.5, lat=31.8)


@pytest.fixture
def permian_footprint() -> GeoJSONGeometry:
    return GeoJSONGeometry(
        type="Polygon",
        coordinates=[
            [
                [-102.6, 31.7],
                [-102.4, 31.7],
                [-102.4, 31.9],
                [-102.6, 31.9],
                [-102.6, 31.7],
            ]
        ],
    )


@pytest.fixture
def observation(basic_provenance: Provenance, permian_footprint: GeoJSONGeometry) -> Observation:
    return Observation(
        sensor="EMIT",
        sensor_type=SensorType.HYPERSPECTRAL,
        granule_id="EMIT_L2B_CH4ENH_001_TEST",
        time_range=TimeRange(start=datetime(2024, 6, 15, 18, 30, tzinfo=UTC)),
        footprint=permian_footprint,
        provenance=basic_provenance,
    )


# --------------------------------------------------------------------------- #
# Base invariants
# --------------------------------------------------------------------------- #


class TestBaseInvariants:
    def test_provenance_is_mandatory(self) -> None:
        with pytest.raises(ValidationError):
            Observation(  # type: ignore[call-arg]
                sensor="EMIT",
                sensor_type=SensorType.HYPERSPECTRAL,
                time_range=TimeRange(start=datetime.now(UTC)),
                footprint=GeoJSONGeometry(type="Point", coordinates=[0, 0]),
            )

    def test_unknown_field_rejected(self, basic_provenance: Provenance) -> None:
        with pytest.raises(ValidationError):
            Observation(  # type: ignore[call-arg]
                sensor="EMIT",
                sensor_type=SensorType.HYPERSPECTRAL,
                time_range=TimeRange(start=datetime.now(UTC)),
                footprint=GeoJSONGeometry(type="Point", coordinates=[0, 0]),
                provenance=basic_provenance,
                this_field_does_not_exist=True,
            )

    def test_planetary_body_defaults_to_earth(self, observation: Observation) -> None:
        assert observation.planetary_body == PlanetaryBody.EARTH

    def test_planetary_body_can_be_set(self, basic_provenance: Provenance) -> None:
        obs = Observation(
            sensor="CRISM",
            sensor_type=SensorType.HYPERSPECTRAL,
            time_range=TimeRange(start=datetime.now(UTC)),
            footprint=GeoJSONGeometry(type="Point", coordinates=[0, 0]),
            provenance=basic_provenance,
            planetary_body=PlanetaryBody.MARS,
        )
        assert obs.planetary_body == PlanetaryBody.MARS


# --------------------------------------------------------------------------- #
# Confidence
# --------------------------------------------------------------------------- #


class TestConfidence:
    def test_basic(self) -> None:
        c = Confidence(value=0.82, lower=0.71, upper=0.91, method="bootstrap_n1000")
        assert c.value == 0.82

    def test_value_must_be_in_unit_interval(self) -> None:
        with pytest.raises(ValidationError):
            Confidence(value=1.5)
        with pytest.raises(ValidationError):
            Confidence(value=-0.1)


# --------------------------------------------------------------------------- #
# Spatial
# --------------------------------------------------------------------------- #


class TestSpatial:
    def test_point_bounds(self) -> None:
        Point(lon=-180.0, lat=-90.0)
        Point(lon=180.0, lat=90.0)
        with pytest.raises(ValidationError):
            Point(lon=181.0, lat=0.0)
        with pytest.raises(ValidationError):
            Point(lon=0.0, lat=91.0)

    def test_bbox_validates_order(self) -> None:
        BBox(min_lon=-103.0, min_lat=31.0, max_lon=-102.0, max_lat=32.0)
        with pytest.raises(ValueError):
            BBox(min_lon=-102.0, min_lat=31.0, max_lon=-103.0, max_lat=32.0)


# --------------------------------------------------------------------------- #
# Temporal
# --------------------------------------------------------------------------- #


class TestTimeRange:
    def test_basic(self) -> None:
        tr = TimeRange(
            start=datetime(2024, 6, 15, tzinfo=UTC),
            end=datetime(2024, 6, 16, tzinfo=UTC),
        )
        assert not tr.is_instantaneous
        assert not tr.is_ongoing

    def test_instantaneous(self) -> None:
        t = datetime(2024, 6, 15, tzinfo=UTC)
        tr = TimeRange(start=t, end=t)
        assert tr.is_instantaneous

    def test_ongoing(self) -> None:
        tr = TimeRange(start=datetime(2024, 6, 15, tzinfo=UTC))
        assert tr.is_ongoing

    def test_end_before_start_rejected(self) -> None:
        with pytest.raises(ValueError):
            TimeRange(
                start=datetime(2024, 6, 16, tzinfo=UTC),
                end=datetime(2024, 6, 15, tzinfo=UTC),
            )


# --------------------------------------------------------------------------- #
# Detection, Phenomenon, Entity, Hypothesis, Brief
# --------------------------------------------------------------------------- #


class TestDetection:
    def test_methane_plume(
        self,
        basic_provenance: Provenance,
        permian_point: Point,
        observation: Observation,
    ) -> None:
        d = Detection(
            detection_type=DetectionType.METHANE_PLUME,
            observation_ids=[observation.id],
            location=permian_point,
            time_range=TimeRange(start=datetime(2024, 6, 15, 18, 30, tzinfo=UTC)),
            measurements={"emission_rate_kg_per_hr": 543.0, "ime_kg": 215.0},
            measurement_units={"emission_rate_kg_per_hr": "kg/hr", "ime_kg": "kg"},
            measurement_uncertainty={"emission_rate_kg_per_hr": 120.0, "ime_kg": 40.0},
            algorithm="matched_filter_cmf",
            algorithm_version="0.1.0",
            provenance=basic_provenance,
        )
        assert d.detection_type == DetectionType.METHANE_PLUME
        assert d.measurements["emission_rate_kg_per_hr"] == 543.0

    def test_requires_at_least_one_observation(
        self, basic_provenance: Provenance, permian_point: Point
    ) -> None:
        with pytest.raises(ValidationError):
            Detection(
                detection_type=DetectionType.METHANE_PLUME,
                observation_ids=[],
                location=permian_point,
                time_range=TimeRange(start=datetime.now(UTC)),
                algorithm="matched_filter_cmf",
                algorithm_version="0.1.0",
                provenance=basic_provenance,
            )


class TestEntity:
    def test_facility(self, basic_provenance: Provenance, permian_point: Point) -> None:
        e = Entity(
            entity_type=EntityType.FACILITY,
            name="Compressor Station Alpha",
            location=permian_point,
            attributes={"subtype": "natural_gas_compressor", "operator": "Example Corp"},
            external_ids={"rystad": "fac-12345"},
            provenance=basic_provenance,
        )
        assert e.attributes["subtype"] == "natural_gas_compressor"


class TestHypothesis:
    def test_basic(self, basic_provenance: Provenance) -> None:
        phenomenon_id = uuid4()
        h = Hypothesis(
            phenomenon_id=phenomenon_id,
            claim="Source is likely a fugitive emission from a natural gas compressor station.",
            assumptions=[
                "Wind direction from ERA5 is accurate within 30 degrees.",
                "The infrastructure database is current as of 2024-Q1.",
            ],
            falsification="Repeat overpass with no plume during similar wind conditions "
            "would weaken this hypothesis.",
            score=0.78,
            rank=1,
            generation_method="llm_claude_sonnet_4.6",
            provenance=basic_provenance,
        )
        assert h.rank == 1
        assert h.score == 0.78

    def test_rank_must_be_positive(self, basic_provenance: Provenance) -> None:
        with pytest.raises(ValidationError):
            Hypothesis(
                phenomenon_id=uuid4(),
                claim="x",
                score=0.5,
                rank=0,
                generation_method="manual",
                provenance=basic_provenance,
            )


class TestBrief:
    def test_basic(self, basic_provenance: Provenance) -> None:
        b = Brief(
            phenomenon_id=uuid4(),
            title="Methane plume detected over Permian Basin, June 15 2024",
            summary="A ~540 kg/hr methane plume was observed by EMIT...",
            body_markdown="# Overview\n\nA methane plume...",
            citations=[
                {
                    "claim": "Plume emission rate ~540 kg/hr",
                    "evidence_id": str(uuid4()),
                    "evidence_type": "detection",
                },
            ],
            provenance=basic_provenance,
        )
        assert b.title.startswith("Methane plume")


# --------------------------------------------------------------------------- #
# JSON round-tripping
# --------------------------------------------------------------------------- #


class TestJsonRoundTrip:
    def test_observation_roundtrip(self, observation: Observation) -> None:
        payload = observation.model_dump_json()
        restored = Observation.model_validate_json(payload)
        assert restored == observation

    def test_phenomenon_roundtrip(self, basic_provenance: Provenance) -> None:
        p = Phenomenon(
            phenomenon_type=PhenomenonType.EMISSION_EVENT,
            name="Permian super-emitter 2024-06-15",
            time_range=TimeRange(start=datetime(2024, 6, 15, tzinfo=UTC)),
            region=BBox(min_lon=-103.0, min_lat=31.0, max_lon=-102.0, max_lat=32.0),
            provenance=basic_provenance,
        )
        restored = Phenomenon.model_validate_json(p.model_dump_json())
        assert restored == p
