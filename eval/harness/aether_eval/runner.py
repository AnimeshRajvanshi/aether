"""Evaluation runner — orchestrates pipeline execution and scoring across events."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from aether_ontology import Detection

from aether_eval.loader import discover_events
from aether_eval.metrics import PipelineRunResult, RunScore, score_run
from aether_eval.schema import BenchmarkEvent

# A Pipeline is anything callable that takes a BenchmarkEvent and returns a list
# of Detections. In Sprint 1 we use a stub. In Sprint 2 we'll wire up the real
# detection pipeline from packages/detection.
Pipeline = Callable[[BenchmarkEvent], list[Detection]]


def stub_pipeline(event: BenchmarkEvent) -> list[Detection]:
    """A pipeline that detects nothing. Used until packages/detection is real.

    Returning an empty list gives us a meaningful baseline: recall = 0, precision
    is undefined (no detections), quantification error is empty. As soon as
    Sprint 2 produces a real detector, this gets replaced and the harness starts
    catching regressions.
    """
    return []


@dataclass
class EventResult:
    """Single-event result captured during a run."""

    event_id: str
    pipeline_result: PipelineRunResult


@dataclass
class EvalReport:
    """Output of a complete evaluation run."""

    score: RunScore
    event_results: list[EventResult]
    spatial_tolerance_m: float
    temporal_tolerance_minutes: float
    pipeline_name: str

    def summary_lines(self) -> list[str]:
        """Plain-text summary suitable for stdout or a log file."""
        s = self.score
        lines = [
            f"Pipeline: {self.pipeline_name}",
            f"Events evaluated: {s.n_events}",
            f"Events recalled: {s.n_events_recalled} / {s.n_events}  (recall = {s.recall:.3f})",
            f"Detections produced: {s.n_detections_total}",
            f"Detections matched: {s.n_detections_matched}  (precision = {s.precision:.3f})",
            f"Mean latency: {s.mean_latency_seconds:.3f}s/event",
            f"Spatial tolerance: {self.spatial_tolerance_m:.0f}m",
            f"Temporal tolerance: {self.temporal_tolerance_minutes:.1f}min",
        ]
        if s.quantification_mape:
            lines.append("Quantification MAPE (mean absolute percentage error):")
            for name, mape in s.quantification_mape.items():
                lines.append(f"  {name}: {mape:.3f} ({mape * 100:.1f}%)")
        else:
            lines.append("Quantification MAPE: (no matched measurements yet)")
        return lines


def run_evaluation(
    pipeline: Pipeline = stub_pipeline,
    events: list[BenchmarkEvent] | None = None,
    benchmark_dir: Path | str | None = None,
    spatial_tolerance_m: float = 5000.0,
    temporal_tolerance_minutes: float = 60.0,
    pipeline_name: str = "stub_pipeline",
) -> EvalReport:
    """Run a pipeline against the full benchmark and return an `EvalReport`.

    If `events` is provided, use it directly. Otherwise discover events under
    `benchmark_dir` (or the default eval/benchmark/ folder if None).
    """
    if events is None:
        events = discover_events(benchmark_dir)

    run_results: list[PipelineRunResult] = []
    event_results: list[EventResult] = []

    for event in events:
        t0 = time.perf_counter()
        error_msg: str | None = None
        try:
            detections = pipeline(event)
        except Exception as e:  # noqa: BLE001
            detections = []
            error_msg = f"{type(e).__name__}: {e}"
        latency = time.perf_counter() - t0

        run_result = PipelineRunResult(
            event_id=event.event_id,
            detections=detections,
            latency_seconds=latency,
            error=error_msg,
        )
        run_results.append(run_result)
        event_results.append(EventResult(event_id=event.event_id, pipeline_result=run_result))

    score = score_run(
        run_results,
        events,
        spatial_tolerance_m=spatial_tolerance_m,
        temporal_tolerance_minutes=temporal_tolerance_minutes,
    )

    return EvalReport(
        score=score,
        event_results=event_results,
        spatial_tolerance_m=spatial_tolerance_m,
        temporal_tolerance_minutes=temporal_tolerance_minutes,
        pipeline_name=pipeline_name,
    )
