"""Detection-to-event matching and evaluation metrics.

The matching logic is the single most consequential thing in this harness — it
determines what counts as a "true positive." Three checks must all pass:

1. Spatial: detection within `spatial_tolerance_m` of event location (haversine).
2. Temporal: detection time within ±`temporal_tolerance_minutes` of event date range.
3. Type: detection.detection_type ∈ event.expected_detection_types.

A detection may match at most one event; ties are broken by smallest spatial
distance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from aether_ontology import Detection

from aether_eval.schema import BenchmarkEvent

EARTH_RADIUS_M = 6_371_008.8  # IUGG mean radius


def haversine_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance between two WGS84 points in meters.

    Sufficient for Earth-scale benchmark matching at the km-scale tolerances we use.
    For sub-meter precision or non-Earth bodies, switch to a proper geodesy library.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def _ensure_tzaware(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC to avoid surprises when comparing."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _detection_in_event_time_window(
    detection: Detection,
    event: BenchmarkEvent,
    temporal_tolerance_minutes: float,
) -> bool:
    """True if the detection's time_range overlaps the event's date_range (± tolerance)."""
    delta = timedelta(minutes=temporal_tolerance_minutes)

    event_start = _ensure_tzaware(event.date_range.start) - delta
    event_end = _ensure_tzaware(event.date_range.end) + delta if event.date_range.end else None

    det_start = _ensure_tzaware(detection.time_range.start)
    det_end = _ensure_tzaware(detection.time_range.end) if detection.time_range.end else det_start

    # If event is open-ended (ongoing at start), any detection at-or-after event_start matches.
    if event_end is None:
        return det_end >= event_start

    # Interval overlap test
    return det_start <= event_end and det_end >= event_start


@dataclass(frozen=True)
class MatchedPair:
    """A detection that matched a benchmark event."""

    detection: Detection
    event: BenchmarkEvent
    spatial_distance_m: float


@dataclass(frozen=True)
class MatchResult:
    """Result of matching a single benchmark event against a set of detections."""

    event: BenchmarkEvent
    matched: list[MatchedPair] = field(default_factory=list)
    unmatched_detections: list[Detection] = field(default_factory=list)

    @property
    def is_recalled(self) -> bool:
        """The event is recalled iff at least one detection matched it."""
        return len(self.matched) > 0


def match_detections_to_event(
    detections: list[Detection],
    event: BenchmarkEvent,
    spatial_tolerance_m: float = 5000.0,
    temporal_tolerance_minutes: float = 60.0,
) -> MatchResult:
    """Match detections to a single benchmark event."""
    matched: list[MatchedPair] = []
    unmatched: list[Detection] = []

    for det in detections:
        # Type check first (cheapest)
        if det.detection_type not in event.expected_detection_types:
            unmatched.append(det)
            continue

        # Temporal check
        if not _detection_in_event_time_window(det, event, temporal_tolerance_minutes):
            unmatched.append(det)
            continue

        # Spatial check
        dist = haversine_meters(
            det.location.lon, det.location.lat, event.location.lon, event.location.lat
        )
        if dist > spatial_tolerance_m:
            unmatched.append(det)
            continue

        matched.append(MatchedPair(detection=det, event=event, spatial_distance_m=dist))

    return MatchResult(event=event, matched=matched, unmatched_detections=unmatched)


# --------------------------------------------------------------------------- #
# Scoring across an entire run
# --------------------------------------------------------------------------- #


@dataclass
class PipelineRunResult:
    """The output of running a pipeline against a single event.

    `detections` is whatever the pipeline produced. `latency_seconds` is wall-clock
    time the pipeline took to produce them.
    """

    event_id: str
    detections: list[Detection]
    latency_seconds: float
    error: str | None = None


@dataclass
class RunScore:
    """Aggregate scores over a multi-event run."""

    n_events: int
    n_events_recalled: int
    n_detections_total: int
    n_detections_matched: int

    recall: float
    precision: float
    mean_latency_seconds: float

    # Per-measurement quantification error, keyed by measurement name.
    # Value is mean absolute percentage error across all matched pairs that
    # had that measurement in both detection and event.
    quantification_mape: dict[str, float] = field(default_factory=dict)

    # Per-event detail
    per_event_matches: list[MatchResult] = field(default_factory=list)


def _percentage_error(predicted: float, reference: float) -> float | None:
    """|predicted - reference| / |reference| as a fraction. None if reference is 0."""
    if reference == 0:
        return None
    return abs(predicted - reference) / abs(reference)


def score_run(
    run_results: list[PipelineRunResult],
    events: list[BenchmarkEvent],
    spatial_tolerance_m: float = 5000.0,
    temporal_tolerance_minutes: float = 60.0,
) -> RunScore:
    """Compute aggregate metrics over a full run.

    Each `PipelineRunResult` is associated with one event by `event_id`. Detections
    in that result are matched against that event only — we don't cross-match
    across events, because each run is a per-event invocation of the pipeline.
    """
    events_by_id = {e.event_id: e for e in events}

    n_events = len(run_results)
    n_recalled = 0
    n_dets_total = 0
    n_dets_matched = 0

    per_event: list[MatchResult] = []
    measurement_errors: dict[str, list[float]] = {}
    latencies: list[float] = []

    for result in run_results:
        if result.event_id not in events_by_id:
            raise KeyError(f"PipelineRunResult.event_id={result.event_id!r} has no matching event")
        event = events_by_id[result.event_id]

        match = match_detections_to_event(
            result.detections,
            event,
            spatial_tolerance_m=spatial_tolerance_m,
            temporal_tolerance_minutes=temporal_tolerance_minutes,
        )
        per_event.append(match)

        n_dets_total += len(result.detections)
        n_dets_matched += len(match.matched)
        if match.is_recalled:
            n_recalled += 1

        # Quantification error per measurement
        for pair in match.matched:
            for name, ref in event.known_measurements.items():
                if name not in pair.detection.measurements:
                    continue
                pred = pair.detection.measurements[name]
                err = _percentage_error(pred, ref.value)
                if err is None:
                    continue
                measurement_errors.setdefault(name, []).append(err)

        latencies.append(result.latency_seconds)

    recall = (n_recalled / n_events) if n_events > 0 else 0.0
    precision = (n_dets_matched / n_dets_total) if n_dets_total > 0 else 0.0
    mean_latency = (sum(latencies) / len(latencies)) if latencies else 0.0

    return RunScore(
        n_events=n_events,
        n_events_recalled=n_recalled,
        n_detections_total=n_dets_total,
        n_detections_matched=n_dets_matched,
        recall=recall,
        precision=precision,
        mean_latency_seconds=mean_latency,
        quantification_mape={name: sum(errs) / len(errs) for name, errs in measurement_errors.items()},
        per_event_matches=per_event,
    )
