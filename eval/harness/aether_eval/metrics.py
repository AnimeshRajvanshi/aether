"""Detection-to-event matching and evaluation metrics.

The matching logic is the single most consequential thing in this harness — it
determines what counts as a "true positive." Three checks must all pass:

1. Spatial — point events: detection within the event's `location_precision_km`
   (or the global `spatial_tolerance_m` fallback) of the event location
   (haversine). Area events (ADR 0004: `AREA_PHENOMENON_TYPES`): detection
   footprint bbox must overlap the event bbox by ≥ half the smaller box;
   centroid distance is reported but is not a criterion.
2. Temporal: detection time within ±`temporal_tolerance_minutes` of event date range.
3. Type: detection.detection_type ∈ event.expected_detection_types.

A detection may match at most one event; ties are broken by smallest spatial
distance.

Scoring separates the two ADR-0002 families: detection recall (over runnable
events only — `not_runnable` events are reported, never silently dropped, and
excluded from the denominator) and per-(event, measurement) quantification
outcomes, where only `comparable` references ever yield an error number; the
others yield `not_comparable` with the schema's machine-readable reason.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from aether_ontology import Detection, GeoJSONGeometry, PhenomenonType

from aether_eval.schema import BenchmarkEvent, ReferenceUsability

EARTH_RADIUS_M = 6_371_008.8  # IUGG mean radius

# Area phenomena are recall-matched by bbox OVERLAP, not centroid distance
# (ADR 0004): two valid analyses of the same heatwave can centroid hundreds of
# km apart while covering the same region. Extended deliberately, never inferred.
AREA_PHENOMENON_TYPES: frozenset[PhenomenonType] = frozenset(
    {PhenomenonType.HEAT_WAVE, PhenomenonType.MARINE_HEAT_WAVE}
)
# Minimum fraction of the smaller bbox that the intersection must cover.
AREA_OVERLAP_MIN_FRACTION = 0.5


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
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _geometry_bbox(geom: GeoJSONGeometry) -> tuple[float, float, float, float]:
    """(min_lon, min_lat, max_lon, max_lat) of any GeoJSON geometry's coordinates."""
    lons: list[float] = []
    lats: list[float] = []

    def walk(node: object) -> None:
        if (
            isinstance(node, list)
            and len(node) >= 2
            and all(isinstance(v, int | float) for v in node[:2])
        ):
            lons.append(float(node[0]))
            lats.append(float(node[1]))
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(geom.coordinates)
    if not lons:
        raise ValueError("geometry has no coordinates")
    return min(lons), min(lats), max(lons), max(lats)


def _bbox_area_km2(box: tuple[float, float, float, float]) -> float:
    """Equirectangular bbox area — adequate at heatwave scales (ADR 0004)."""
    min_lon, min_lat, max_lon, max_lat = box
    mean_lat = math.radians((min_lat + max_lat) / 2.0)
    km_per_deg = EARTH_RADIUS_M * math.pi / 180.0 / 1000.0
    return (max_lon - min_lon) * km_per_deg * math.cos(mean_lat) * (max_lat - min_lat) * km_per_deg


def area_overlap_match(
    det_box: tuple[float, float, float, float],
    event_box: tuple[float, float, float, float],
) -> bool:
    """ADR 0004: intersection covers ≥ AREA_OVERLAP_MIN_FRACTION of the smaller box."""
    inter = (
        max(det_box[0], event_box[0]),
        max(det_box[1], event_box[1]),
        min(det_box[2], event_box[2]),
        min(det_box[3], event_box[3]),
    )
    if inter[0] >= inter[2] or inter[1] >= inter[3]:
        return False
    inter_area = _bbox_area_km2(inter)
    smaller = min(_bbox_area_km2(det_box), _bbox_area_km2(event_box))
    return inter_area >= AREA_OVERLAP_MIN_FRACTION * smaller


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
    """Match detections to a single benchmark event.

    The spatial tolerance is the event's own `location_precision_km` when set
    (ADR 0002: reference locations have wildly different meanings — a
    field-center estimate for a 12-source cluster vs a pinned plume-complex
    footprint), falling back to `spatial_tolerance_m` otherwise.
    """
    matched: list[MatchedPair] = []
    unmatched: list[Detection] = []

    if event.location_precision_km is not None:
        spatial_tolerance_m = event.location_precision_km * 1000.0

    for det in detections:
        # Type check first (cheapest)
        if det.detection_type not in event.expected_detection_types:
            unmatched.append(det)
            continue

        # Temporal check
        if not _detection_in_event_time_window(det, event, temporal_tolerance_minutes):
            unmatched.append(det)
            continue

        # Spatial check. Area phenomena match by bbox overlap (ADR 0004); a
        # footprint-less detection of an area event does NOT match — an area
        # detection that cannot say what area it covers is not a detection.
        # Point events keep centroid-distance semantics bit-for-bit.
        if event.phenomenon_type in AREA_PHENOMENON_TYPES:
            if det.footprint is None:
                unmatched.append(det)
                continue
            event_box = (
                event.bbox.min_lon,
                event.bbox.min_lat,
                event.bbox.max_lon,
                event.bbox.max_lat,
            )
            if not area_overlap_match(_geometry_bbox(det.footprint), event_box):
                unmatched.append(det)
                continue
            dist = haversine_meters(
                det.location.lon, det.location.lat, event.location.lon, event.location.lat
            )  # recorded for reporting; not a matching criterion for area events
        else:
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


class RunStatus(StrEnum):
    """Per-event run outcome.

    NOT_RUNNABLE events are excluded from the recall denominator (the pipeline
    cannot observe them, e.g. a pre-EMIT event vs an EMIT pipeline) but stay on
    the scoreboard with their reason. ERROR events DO count against recall —
    a crash on a runnable event is a miss, not an excuse.
    """

    RAN = "ran"
    NOT_RUNNABLE = "not_runnable"
    ERROR = "error"


@dataclass
class PipelineRunResult:
    """The output of running a pipeline against a single event.

    `detections` is whatever the pipeline produced. `latency_seconds` is wall-clock
    time the pipeline took to produce them. `status_reason` carries the
    machine-readable reason for NOT_RUNNABLE / ERROR statuses.
    """

    event_id: str
    detections: list[Detection]
    latency_seconds: float
    status: RunStatus = RunStatus.RAN
    status_reason: str | None = None


@dataclass(frozen=True)
class QuantificationOutcome:
    """The quantification verdict for one (event, measurement) pair (ADR 0002).

    Only `comparable` references carry an error number (`mape`, when at least
    one matched detection reported the measurement). Non-comparable references
    carry the schema's `usability_reason` verbatim and NO number — emitting a
    lookalike MAPE against a scope-mismatched or context-only reference would
    fabricate a validation result.
    """

    event_id: str
    measurement: str
    usability: ReferenceUsability
    reason: str | None  # usability_reason, verbatim, for non-comparable references
    mape: float | None  # only for comparable references with >=1 matched pair
    n_pairs: int

    @property
    def is_comparable(self) -> bool:
        return self.usability is ReferenceUsability.COMPARABLE


@dataclass
class RunScore:
    """Aggregate scores over a multi-event run."""

    n_events: int
    n_events_runnable: int
    n_events_not_runnable: int
    n_events_errored: int
    n_events_recalled: int
    n_detections_total: int
    n_detections_matched: int

    recall: float  # over runnable events only (ran + errored)
    precision: float
    mean_latency_seconds: float

    # One outcome per (event, measurement-with-a-reference); see
    # QuantificationOutcome. The same measurement name can be comparable on one
    # event and not on another, so this is NOT keyed by name alone.
    quantification: list[QuantificationOutcome] = field(default_factory=list)

    # Per-event detail (RAN events only; NOT_RUNNABLE/ERROR events have no match)
    per_event_matches: list[MatchResult] = field(default_factory=list)


def _percentage_error(predicted: float, reference: float) -> float | None:
    """|predicted - reference| / |reference| as a fraction. None if reference is 0."""
    if reference == 0:
        return None
    return abs(predicted - reference) / abs(reference)


def _quantification_outcomes(
    event: BenchmarkEvent, match: MatchResult
) -> list[QuantificationOutcome]:
    """One outcome per benchmark measurement, honoring `reference_usability`."""
    outcomes: list[QuantificationOutcome] = []
    for name, ref in event.known_measurements.items():
        if ref.reference_usability is not ReferenceUsability.COMPARABLE:
            outcomes.append(QuantificationOutcome(
                event_id=event.event_id,
                measurement=name,
                usability=ref.reference_usability,
                reason=ref.usability_reason,
                mape=None,
                n_pairs=0,
            ))
            continue
        errs: list[float] = []
        for pair in match.matched:
            if name not in pair.detection.measurements:
                continue
            err = _percentage_error(pair.detection.measurements[name], ref.value)
            if err is not None:
                errs.append(err)
        outcomes.append(QuantificationOutcome(
            event_id=event.event_id,
            measurement=name,
            usability=ReferenceUsability.COMPARABLE,
            reason=None,
            mape=(sum(errs) / len(errs)) if errs else None,
            n_pairs=len(errs),
        ))
    return outcomes


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

    Recall is computed over RUNNABLE events only (status ran/error); events the
    pipeline cannot observe (NOT_RUNNABLE) are reported but not scored against it.
    """
    events_by_id = {e.event_id: e for e in events}

    n_events = len(run_results)
    n_not_runnable = 0
    n_errored = 0
    n_recalled = 0
    n_dets_total = 0
    n_dets_matched = 0

    per_event: list[MatchResult] = []
    quantification: list[QuantificationOutcome] = []
    latencies: list[float] = []

    for result in run_results:
        if result.event_id not in events_by_id:
            raise KeyError(f"PipelineRunResult.event_id={result.event_id!r} has no matching event")
        event = events_by_id[result.event_id]

        if result.status is RunStatus.NOT_RUNNABLE:
            n_not_runnable += 1
            continue
        if result.status is RunStatus.ERROR:
            n_errored += 1
            latencies.append(result.latency_seconds)
            continue

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

        quantification.extend(_quantification_outcomes(event, match))
        latencies.append(result.latency_seconds)

    n_runnable = n_events - n_not_runnable
    recall = (n_recalled / n_runnable) if n_runnable > 0 else 0.0
    precision = (n_dets_matched / n_dets_total) if n_dets_total > 0 else 0.0
    mean_latency = (sum(latencies) / len(latencies)) if latencies else 0.0

    return RunScore(
        n_events=n_events,
        n_events_runnable=n_runnable,
        n_events_not_runnable=n_not_runnable,
        n_events_errored=n_errored,
        n_events_recalled=n_recalled,
        n_detections_total=n_dets_total,
        n_detections_matched=n_dets_matched,
        recall=recall,
        precision=precision,
        mean_latency_seconds=mean_latency,
        quantification=quantification,
        per_event_matches=per_event,
    )
