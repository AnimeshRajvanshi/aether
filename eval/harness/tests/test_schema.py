"""Tests for the BenchmarkEvent schema."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from aether_ontology import BBox, DetectionType, PhenomenonType, PlanetaryBody, Point, TimeRange

from aether_eval.schema import (
    Attribution,
    BenchmarkEvent,
    Measurement,
    ObservedBy,
    Reference,
)


def _valid_event_kwargs() -> dict:
    return dict(
        event_id="test_event",
        name="Test Event",
        phenomenon_type=PhenomenonType.EMISSION_EVENT,
        expected_detection_types=[DetectionType.METHANE_PLUME],
        date_range=TimeRange(
            start=datetime(2024, 6, 15, tzinfo=timezone.utc),
            end=datetime(2024, 6, 16, tzinfo=timezone.utc),
        ),
        location=Point(lon=-102.5, lat=31.8),
        bbox=BBox(min_lon=-103.0, min_lat=31.0, max_lon=-102.0, max_lat=32.0),
        references=[Reference(citation="Test citation")],
    )


class TestSchemaInvariants:
    def test_minimum_valid_event(self) -> None:
        event = BenchmarkEvent(**_valid_event_kwargs())
        assert event.planetary_body == PlanetaryBody.EARTH
        assert event.event_id == "test_event"

    def test_requires_reference(self) -> None:
        kwargs = _valid_event_kwargs()
        kwargs["references"] = []
        with pytest.raises(ValidationError):
            BenchmarkEvent(**kwargs)

    def test_requires_expected_detection_type(self) -> None:
        kwargs = _valid_event_kwargs()
        kwargs["expected_detection_types"] = []
        with pytest.raises(ValidationError):
            BenchmarkEvent(**kwargs)

    def test_location_must_be_in_bbox(self) -> None:
        kwargs = _valid_event_kwargs()
        kwargs["location"] = Point(lon=-50.0, lat=31.8)  # outside bbox
        with pytest.raises(ValidationError):
            BenchmarkEvent(**kwargs)

    def test_unknown_field_rejected(self) -> None:
        kwargs = _valid_event_kwargs()
        kwargs["this_field_does_not_exist"] = 42
        with pytest.raises(ValidationError):
            BenchmarkEvent(**kwargs)


class TestMeasurement:
    def test_basic(self) -> None:
        m = Measurement(value=60000.0, uncertainty=5000.0, unit="kg/hr", note="Peak rate")
        assert m.value == 60000.0

    def test_uncertainty_optional(self) -> None:
        m = Measurement(value=60000.0, unit="kg/hr", note="No uncertainty estimate available")
        assert m.uncertainty is None

    def test_note_mandatory(self) -> None:
        with pytest.raises(ValidationError):
            Measurement(value=60000.0, unit="kg/hr")  # type: ignore[call-arg]


class TestKnownMeasurements:
    def test_can_attach_measurements(self) -> None:
        kwargs = _valid_event_kwargs()
        kwargs["known_measurements"] = {
            "peak_emission_rate_kg_per_hr": Measurement(
                value=60000.0,
                uncertainty=5000.0,
                unit="kg/hr",
                note="Peak rate",
            ),
        }
        event = BenchmarkEvent(**kwargs)
        assert "peak_emission_rate_kg_per_hr" in event.known_measurements
        assert event.known_measurements["peak_emission_rate_kg_per_hr"].value == 60000.0


class TestAttribution:
    def test_all_optional(self) -> None:
        a = Attribution()
        assert a.operator is None

    def test_with_values(self) -> None:
        a = Attribution(operator="SoCalGas", facility="Aliso Canyon", sector="natural_gas_storage")
        assert a.operator == "SoCalGas"


class TestObservedBy:
    def test_basic(self) -> None:
        from aether_ontology import SensorType

        o = ObservedBy(sensor="EMIT", sensor_type=SensorType.HYPERSPECTRAL)
        assert o.sensor == "EMIT"
