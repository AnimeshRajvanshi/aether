"""Aether evaluation harness — benchmark events, metrics, and runner."""

from aether_eval.loader import discover_events, load_event, load_event_file
from aether_eval.metrics import (
    MatchedPair,
    MatchResult,
    PipelineRunResult,
    haversine_meters,
    match_detections_to_event,
    score_run,
)
from aether_eval.runner import EvalReport, EventResult, run_evaluation
from aether_eval.schema import (
    Attribution,
    BenchmarkEvent,
    Measurement,
    ObservedBy,
    Reference,
)

__all__ = [
    "Attribution",
    "BenchmarkEvent",
    "EvalReport",
    "EventResult",
    "MatchResult",
    "MatchedPair",
    "Measurement",
    "ObservedBy",
    "PipelineRunResult",
    "Reference",
    "discover_events",
    "haversine_meters",
    "load_event",
    "load_event_file",
    "match_detections_to_event",
    "run_evaluation",
    "score_run",
]

__version__ = "0.1.0"
