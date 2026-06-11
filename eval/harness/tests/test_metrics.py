"""Tests for matching and metrics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from aether_eval.metrics import (
    EARTH_RADIUS_M,
    PipelineRunResult,
    RunStatus,
    haversine_meters,
    match_detections_to_event,
    score_run,
)
from aether_eval.schema import (
    BenchmarkEvent,
    Measurement,
    Reference,
    ReferenceUsability,
)
from aether_ontology import (
    BBox,
    Detection,
    DetectionType,
    PhenomenonType,
    Point,
    Provenance,
    TimeRange,
)


def _event(
    *,
    event_id: str = "evt",
    lon: float = -118.560,
    lat: float = 34.314,
    start: datetime | None = None,
    end: datetime | None = None,
    detection_types: list[DetectionType] | None = None,
    measurements: dict[str, Measurement] | None = None,
    location_precision_km: float | None = None,
) -> BenchmarkEvent:
    if start is None:
        start = datetime(2024, 6, 15, 18, 0, tzinfo=UTC)
    if end is None:
        end = datetime(2024, 6, 15, 19, 0, tzinfo=UTC)
    if detection_types is None:
        detection_types = [DetectionType.METHANE_PLUME]
    return BenchmarkEvent(
        event_id=event_id,
        name="Test event",
        phenomenon_type=PhenomenonType.EMISSION_EVENT,
        expected_detection_types=detection_types,
        date_range=TimeRange(start=start, end=end),
        location=Point(lon=lon, lat=lat),
        bbox=BBox(min_lon=lon - 0.1, min_lat=lat - 0.1, max_lon=lon + 0.1, max_lat=lat + 0.1),
        references=[Reference(citation="Test")],
        known_measurements=measurements or {},
        location_precision_km=location_precision_km,
    )


def _comparable(value: float, unit: str = "kg/hr", note: str = "Test") -> Measurement:
    return Measurement(
        value=value, unit=unit, note=note, reference_usability=ReferenceUsability.COMPARABLE
    )


def _detection(
    *,
    lon: float,
    lat: float,
    when: datetime,
    detection_type: DetectionType = DetectionType.METHANE_PLUME,
    measurements: dict[str, float] | None = None,
    measurement_units: dict[str, str] | None = None,
) -> Detection:
    return Detection(
        detection_type=detection_type,
        observation_ids=[uuid4()],
        location=Point(lon=lon, lat=lat),
        time_range=TimeRange(start=when),
        measurements=measurements or {},
        measurement_units=measurement_units or {},
        algorithm="test_stub",
        algorithm_version="0.0",
        provenance=Provenance(source="test"),
    )


# --------------------------------------------------------------------------- #
# haversine
# --------------------------------------------------------------------------- #


class TestHaversine:
    def test_zero_distance(self) -> None:
        assert haversine_meters(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0, abs=1e-6)

    def test_one_degree_lat(self) -> None:
        # One degree of latitude is ~111.2 km at the equator
        d = haversine_meters(0.0, 0.0, 0.0, 1.0)
        assert 110_000 < d < 112_000

    def test_symmetric(self) -> None:
        a = haversine_meters(-100.0, 30.0, -99.5, 30.5)
        b = haversine_meters(-99.5, 30.5, -100.0, 30.0)
        assert a == pytest.approx(b)

    def test_antipode_is_pi_r(self) -> None:
        # Approximate antipodal distance
        d = haversine_meters(0.0, 0.0, 180.0, 0.0)
        assert d == pytest.approx(EARTH_RADIUS_M * 3.14159265, rel=1e-3)


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #


class TestMatching:
    def test_direct_hit_matches(self) -> None:
        event = _event()
        det = _detection(
            lon=event.location.lon,
            lat=event.location.lat,
            when=event.date_range.start + timedelta(minutes=15),
        )
        result = match_detections_to_event([det], event)
        assert result.is_recalled
        assert len(result.matched) == 1
        assert result.matched[0].spatial_distance_m < 1.0

    def test_outside_spatial_tolerance(self) -> None:
        event = _event()
        # ~111 km north — well outside default 5 km tolerance
        det = _detection(
            lon=event.location.lon,
            lat=event.location.lat + 1.0,
            when=event.date_range.start + timedelta(minutes=15),
        )
        result = match_detections_to_event([det], event)
        assert not result.is_recalled
        assert len(result.unmatched_detections) == 1

    def test_outside_temporal_tolerance(self) -> None:
        event = _event()
        # ~3 hours after event end — outside default 60 min tolerance
        det = _detection(
            lon=event.location.lon,
            lat=event.location.lat,
            when=event.date_range.end + timedelta(hours=3),
        )
        result = match_detections_to_event([det], event)
        assert not result.is_recalled

    def test_within_temporal_tolerance(self) -> None:
        event = _event()
        # 30 min after event end — within default 60 min tolerance
        det = _detection(
            lon=event.location.lon,
            lat=event.location.lat,
            when=event.date_range.end + timedelta(minutes=30),
        )
        result = match_detections_to_event([det], event)
        assert result.is_recalled

    def test_wrong_detection_type(self) -> None:
        event = _event(detection_types=[DetectionType.METHANE_PLUME])
        det = _detection(
            lon=event.location.lon,
            lat=event.location.lat,
            when=event.date_range.start,
            detection_type=DetectionType.THERMAL_ANOMALY,
        )
        result = match_detections_to_event([det], event)
        assert not result.is_recalled

    def test_naive_datetimes_treated_as_utc(self) -> None:
        # A common bug: someone constructs a TimeRange with naive datetimes
        event = _event()
        naive = datetime(2024, 6, 15, 18, 15)  # no tzinfo
        det = _detection(lon=event.location.lon, lat=event.location.lat, when=naive)
        result = match_detections_to_event([det], event)
        assert result.is_recalled


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def _outcome(score, event_id: str, measurement: str):
    matches = [
        q for q in score.quantification
        if q.event_id == event_id and q.measurement == measurement
    ]
    assert len(matches) == 1
    return matches[0]


class TestScoreRun:
    def test_perfect_run(self) -> None:
        event = _event(
            measurements={"peak_emission_rate_kg_per_hr": _comparable(60000.0, note="Peak rate")}
        )
        det = _detection(
            lon=event.location.lon,
            lat=event.location.lat,
            when=event.date_range.start + timedelta(minutes=15),
            measurements={"peak_emission_rate_kg_per_hr": 60000.0},
            measurement_units={"peak_emission_rate_kg_per_hr": "kg/hr"},
        )
        run_result = PipelineRunResult(
            event_id=event.event_id, detections=[det], latency_seconds=0.5
        )
        score = score_run([run_result], [event])
        assert score.recall == pytest.approx(1.0)
        assert score.precision == pytest.approx(1.0)
        outcome = _outcome(score, event.event_id, "peak_emission_rate_kg_per_hr")
        assert outcome.is_comparable
        assert outcome.mape == pytest.approx(0.0)
        assert outcome.n_pairs == 1

    def test_quantification_error_computed(self) -> None:
        event = _event(
            measurements={"peak_emission_rate_kg_per_hr": _comparable(100.0)}
        )
        det = _detection(
            lon=event.location.lon,
            lat=event.location.lat,
            when=event.date_range.start,
            measurements={"peak_emission_rate_kg_per_hr": 120.0},  # +20% error
            measurement_units={"peak_emission_rate_kg_per_hr": "kg/hr"},
        )
        run_result = PipelineRunResult(
            event_id=event.event_id, detections=[det], latency_seconds=0.0
        )
        score = score_run([run_result], [event])
        outcome = _outcome(score, event.event_id, "peak_emission_rate_kg_per_hr")
        assert outcome.mape == pytest.approx(0.2)

    def test_empty_run_zero_recall(self) -> None:
        event = _event()
        run_result = PipelineRunResult(event_id=event.event_id, detections=[], latency_seconds=0.0)
        score = score_run([run_result], [event])
        assert score.recall == 0.0
        # Precision is 0.0 when there are no detections (defined that way; no detections, no signal)
        assert score.precision == 0.0

    def test_false_positive_lowers_precision(self) -> None:
        event = _event()
        det_match = _detection(
            lon=event.location.lon,
            lat=event.location.lat,
            when=event.date_range.start,
        )
        # Far away detection — won't match
        det_false = _detection(
            lon=event.location.lon + 2.0,
            lat=event.location.lat + 2.0,
            when=event.date_range.start,
        )
        run_result = PipelineRunResult(
            event_id=event.event_id,
            detections=[det_match, det_false],
            latency_seconds=0.0,
        )
        score = score_run([run_result], [event])
        assert score.recall == pytest.approx(1.0)
        assert score.precision == pytest.approx(0.5)


class TestAdr0002Semantics:
    """The honesty core: not_comparable references never yield numbers, and
    not_runnable events never count against recall (but are never dropped)."""

    def _matching_detection(self, event: BenchmarkEvent, **kw) -> Detection:
        return _detection(
            lon=event.location.lon,
            lat=event.location.lat,
            when=event.date_range.start,
            **kw,
        )

    def test_scope_mismatch_yields_not_comparable_never_mape(self) -> None:
        event = _event(
            measurements={
                "emission_rate_metric_tonnes_per_hr": Measurement(
                    value=163.0,
                    uncertainty=18.0,
                    unit="tonnes/hr",
                    note="Cluster total",
                    n_sources=12,
                    reference_usability=ReferenceUsability.SCOPE_MISMATCH,
                    usability_reason="12-source cluster total vs our single plume",
                ),
            }
        )
        # Even a detection CARRYING the measurement must not produce a MAPE.
        det = self._matching_detection(
            event,
            measurements={"emission_rate_metric_tonnes_per_hr": 23.4},
            measurement_units={"emission_rate_metric_tonnes_per_hr": "tonnes/hr"},
        )
        score = score_run(
            [PipelineRunResult(event_id=event.event_id, detections=[det], latency_seconds=0.0)],
            [event],
        )
        outcome = _outcome(score, event.event_id, "emission_rate_metric_tonnes_per_hr")
        assert outcome.usability is ReferenceUsability.SCOPE_MISMATCH
        assert outcome.mape is None
        assert outcome.reason == "12-source cluster total vs our single plume"

    def test_context_only_yields_not_comparable(self) -> None:
        event = _event(
            measurements={
                "emission_rate_metric_tonnes_per_hr": Measurement(
                    value=18.3,
                    unit="tonnes/hr",
                    note="Press release",
                    reference_usability=ReferenceUsability.CONTEXT_ONLY,
                    usability_reason="press-release value with no method or uncertainty",
                ),
            }
        )
        det = self._matching_detection(
            event,
            measurements={"emission_rate_metric_tonnes_per_hr": 0.85},
            measurement_units={"emission_rate_metric_tonnes_per_hr": "tonnes/hr"},
        )
        score = score_run(
            [PipelineRunResult(event_id=event.event_id, detections=[det], latency_seconds=0.0)],
            [event],
        )
        outcome = _outcome(score, event.event_id, "emission_rate_metric_tonnes_per_hr")
        assert outcome.usability is ReferenceUsability.CONTEXT_ONLY
        assert outcome.mape is None
        assert "press-release" in (outcome.reason or "")

    def test_not_runnable_excluded_from_recall_denominator(self) -> None:
        runnable = _event(event_id="runnable")
        unrunnable = _event(event_id="unrunnable")
        det = self._matching_detection(runnable)
        results = [
            PipelineRunResult(event_id="runnable", detections=[det], latency_seconds=0.0),
            PipelineRunResult(
                event_id="unrunnable",
                detections=[],
                latency_seconds=0.0,
                status=RunStatus.NOT_RUNNABLE,
                status_reason="no EMIT coverage in 2015",
            ),
        ]
        score = score_run(results, [runnable, unrunnable])
        assert score.n_events == 2
        assert score.n_events_runnable == 1
        assert score.n_events_not_runnable == 1
        assert score.recall == pytest.approx(1.0)  # 1/1, NOT 1/2

    def test_error_counts_against_recall(self) -> None:
        """A crash on a runnable event is a miss, not an excuse."""
        ok = _event(event_id="ok")
        crashed = _event(event_id="crashed")
        det = self._matching_detection(ok)
        results = [
            PipelineRunResult(event_id="ok", detections=[det], latency_seconds=0.0),
            PipelineRunResult(
                event_id="crashed",
                detections=[],
                latency_seconds=0.0,
                status=RunStatus.ERROR,
                status_reason="RuntimeError: boom",
            ),
        ]
        score = score_run(results, [ok, crashed])
        assert score.n_events_runnable == 2
        assert score.n_events_errored == 1
        assert score.recall == pytest.approx(0.5)

    def test_location_precision_used_as_spatial_tolerance(self) -> None:
        """A field-scale reference accepts a field-scale offset; a pinned one doesn't."""
        # ~30 km east of the reference location at this latitude
        offset_lon = 0.33
        field_scale = _event(location_precision_km=40.0)
        det = _detection(
            lon=field_scale.location.lon + offset_lon,
            lat=field_scale.location.lat,
            when=field_scale.date_range.start,
        )
        assert match_detections_to_event([det], field_scale).is_recalled

        pinned = _event(location_precision_km=3.0)
        det2 = _detection(
            lon=pinned.location.lon + offset_lon,
            lat=pinned.location.lat,
            when=pinned.date_range.start,
        )
        assert not match_detections_to_event([det2], pinned).is_recalled
