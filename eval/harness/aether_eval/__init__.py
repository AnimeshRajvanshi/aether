"""Aether evaluation harness — benchmark events, metrics, and runner."""

from aether_eval.loader import discover_events, load_event, load_event_file
from aether_eval.metrics import (
    MatchedPair,
    MatchResult,
    PipelineRunResult,
    QuantificationOutcome,
    RunStatus,
    haversine_meters,
    match_detections_to_event,
    score_run,
)
from aether_eval.regression import RegressionCheck, compare_to_committed
from aether_eval.runner import (
    EvalReport,
    EventNotRunnable,
    EventResult,
    PipelineOutput,
    run_evaluation,
)
from aether_eval.schema import (
    Attribution,
    BenchmarkEvent,
    Measurement,
    ObservedBy,
    Reference,
    ReferenceUsability,
)

__all__ = [
    "Attribution",
    "BenchmarkEvent",
    "EvalReport",
    "EventNotRunnable",
    "EventResult",
    "MatchResult",
    "MatchedPair",
    "Measurement",
    "ObservedBy",
    "PipelineOutput",
    "PipelineRunResult",
    "QuantificationOutcome",
    "Reference",
    "ReferenceUsability",
    "RegressionCheck",
    "RunStatus",
    "compare_to_committed",
    "discover_events",
    "haversine_meters",
    "load_event",
    "load_event_file",
    "match_detections_to_event",
    "run_evaluation",
    "score_run",
]

__version__ = "0.1.0"
