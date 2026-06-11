"""Tests for the BenchmarkEvent schema."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aether_eval.schema import (
    Attribution,
    BenchmarkEvent,
    Measurement,
    ObservedBy,
    Reference,
    ReferenceUsability,
)
from aether_ontology import BBox, DetectionType, PhenomenonType, PlanetaryBody, Point, TimeRange
from pydantic import ValidationError


def _valid_event_kwargs() -> dict:
    return dict(
        event_id="test_event",
        name="Test Event",
        phenomenon_type=PhenomenonType.EMISSION_EVENT,
        expected_detection_types=[DetectionType.METHANE_PLUME],
        date_range=TimeRange(
            start=datetime(2024, 6, 15, tzinfo=UTC),
            end=datetime(2024, 6, 16, tzinfo=UTC),
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
        m = Measurement(
            value=60000.0,
            uncertainty=5000.0,
            unit="kg/hr",
            note="Peak rate",
            reference_usability=ReferenceUsability.COMPARABLE,
        )
        assert m.value == 60000.0

    def test_uncertainty_optional(self) -> None:
        m = Measurement(
            value=60000.0,
            unit="kg/hr",
            note="No uncertainty estimate available",
            reference_usability=ReferenceUsability.COMPARABLE,
        )
        assert m.uncertainty is None

    def test_note_mandatory(self) -> None:
        with pytest.raises(ValidationError):
            Measurement(  # type: ignore[call-arg]
                value=60000.0,
                unit="kg/hr",
                reference_usability=ReferenceUsability.COMPARABLE,
            )

    def test_usability_mandatory(self) -> None:
        """ADR 0002: every benchmark measurement must declare how it can be used."""
        with pytest.raises(ValidationError):
            Measurement(value=60000.0, unit="kg/hr", note="Peak rate")  # type: ignore[call-arg]

    def test_non_comparable_requires_reason(self) -> None:
        """scope_mismatch / context_only without a stated reason is refused."""
        for usability in (ReferenceUsability.SCOPE_MISMATCH, ReferenceUsability.CONTEXT_ONLY):
            with pytest.raises(ValidationError):
                Measurement(
                    value=163.0, unit="t/hr", note="Cluster total", reference_usability=usability
                )
            m = Measurement(
                value=163.0,
                unit="t/hr",
                note="Cluster total",
                reference_usability=usability,
                usability_reason="12-source cluster total vs our single plume",
            )
            assert m.usability_reason is not None

    def test_blank_reason_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Measurement(
                value=18.3,
                unit="t/hr",
                note="Press release",
                reference_usability=ReferenceUsability.CONTEXT_ONLY,
                usability_reason="   ",
            )


class TestLocationPrecision:
    def test_optional_and_positive(self) -> None:
        kwargs = _valid_event_kwargs()
        event = BenchmarkEvent(**kwargs)
        assert event.location_precision_km is None

        kwargs["location_precision_km"] = 40.0
        event = BenchmarkEvent(**kwargs)
        assert event.location_precision_km == 40.0

        kwargs["location_precision_km"] = 0.0
        with pytest.raises(ValidationError):
            BenchmarkEvent(**kwargs)


class TestKnownMeasurements:
    def test_can_attach_measurements(self) -> None:
        kwargs = _valid_event_kwargs()
        kwargs["known_measurements"] = {
            "peak_emission_rate_kg_per_hr": Measurement(
                value=60000.0,
                uncertainty=5000.0,
                unit="kg/hr",
                note="Peak rate",
                reference_usability=ReferenceUsability.COMPARABLE,
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
