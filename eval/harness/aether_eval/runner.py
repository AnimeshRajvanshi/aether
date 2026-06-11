"""Evaluation runner — orchestrates pipeline execution and scoring across events.

ADR 0002 semantics: a pipeline may, per event,
  * return detections (optionally with regression values via `PipelineOutput`),
  * raise `EventNotRunnable(reason)` — the event is reported with that reason
    and excluded from the recall denominator (never silently dropped),
  * raise anything else — the event is an ERROR and counts against recall.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from aether_ontology import Detection

from aether_eval.loader import discover_events
from aether_eval.metrics import (
    PipelineRunResult,
    RunScore,
    RunStatus,
    score_run,
)
from aether_eval.regression import RegressionCheck, compare_to_committed
from aether_eval.schema import BenchmarkEvent, ReferenceUsability


# N818 wants an -Error suffix; this is a control-flow signal ("report this event
# as not_runnable"), not an error — the suffix would misname the semantics.
class EventNotRunnable(Exception):  # noqa: N818
    """Raised by a pipeline when it cannot observe an event at all.

    The message is the machine-readable reason shown on the scoreboard, e.g.
    "no EMIT coverage: the event window predates EMIT's July 2022 launch".
    """


@dataclass
class PipelineOutput:
    """Rich per-event pipeline output.

    `regression_values` (when provided) are compared against the event's
    committed artifacts (see `aether_eval.regression`). Pipelines that only do
    detection can keep returning a plain `list[Detection]`.
    """

    detections: list[Detection]
    regression_values: dict[str, float] | None = None


# A Pipeline takes a BenchmarkEvent and returns detections (plain or wrapped).
Pipeline = Callable[[BenchmarkEvent], "list[Detection] | PipelineOutput"]


def stub_pipeline(event: BenchmarkEvent) -> list[Detection]:
    """A pipeline that detects nothing. Kept for harness logic tests.

    Returning an empty list gives a meaningful floor: recall = 0 over all
    events (the stub "runs" everything, even pre-EMIT events, because it
    observes nothing in the first place).
    """
    return []


@dataclass
class EventResult:
    """Single-event result captured during a run."""

    event_id: str
    pipeline_result: PipelineRunResult
    regression: list[RegressionCheck] = field(default_factory=list)


@dataclass
class EvalReport:
    """Output of a complete evaluation run."""

    score: RunScore
    event_results: list[EventResult]
    spatial_tolerance_m: float
    temporal_tolerance_minutes: float
    pipeline_name: str

    @property
    def regression_all_green(self) -> bool:
        """True iff every regression check passed AND no runnable event errored."""
        checks = [c for r in self.event_results for c in r.regression]
        return all(c.passed for c in checks) and self.score.n_events_errored == 0

    def summary_lines(self) -> list[str]:
        """The honest scoreboard (ADR 0002), suitable for stdout or a log file."""
        s = self.score
        lines = [
            f"Pipeline: {self.pipeline_name}",
            f"Events: {s.n_events} ({s.n_events_runnable} runnable, "
            f"{s.n_events_not_runnable} not_runnable)",
        ]

        events_by_id = {m.event.event_id: m for m in s.per_event_matches}
        for res in self.event_results:
            pr = res.pipeline_result
            if pr.status is RunStatus.NOT_RUNNABLE:
                lines.append(f"  {pr.event_id}: NOT_RUNNABLE — {pr.status_reason}")
                continue
            if pr.status is RunStatus.ERROR:
                lines.append(f"  {pr.event_id}: ERROR — {pr.status_reason}")
                continue

            match = events_by_id.get(pr.event_id)
            if match is not None and match.is_recalled:
                best = min(p.spatial_distance_m for p in match.matched)
                recalled = f"recalled ({best / 1000.0:.1f} km from reference location)"
            else:
                recalled = "NOT recalled"
            lines.append(f"  {pr.event_id}: ran in {pr.latency_seconds:.1f}s — {recalled}")

            for check in res.regression:
                lines.append(f"    regression  {check.describe()}")

            for q in s.quantification:
                if q.event_id != pr.event_id:
                    continue
                if q.usability is ReferenceUsability.COMPARABLE:
                    val = f"MAPE {q.mape:.3f} ({q.n_pairs} pairs)" if q.mape is not None \
                        else "comparable, no matched measurement"
                    lines.append(f"    quantification vs {q.measurement}: {val}")
                else:
                    lines.append(
                        f"    quantification vs {q.measurement}: "
                        f"NOT_COMPARABLE ({q.usability.value}) — {q.reason}"
                    )

        lines.append(
            f"Detection recall (runnable events): {s.n_events_recalled}/{s.n_events_runnable}"
            f"  (precision {s.precision:.3f} over {s.n_detections_total} detections)"
        )
        n_checks = sum(len(r.regression) for r in self.event_results)
        if n_checks:
            n_pass = sum(1 for r in self.event_results for c in r.regression if c.passed)
            verdict = "GREEN" if self.regression_all_green else "FAILING"
            lines.append(f"Regression vs committed artifacts: {n_pass}/{n_checks} — {verdict}")
        else:
            lines.append("Regression vs committed artifacts: (none computed by this pipeline)")
        n_comparable = sum(
            1 for q in s.quantification if q.usability is ReferenceUsability.COMPARABLE
        )
        if n_comparable == 0 and s.quantification:
            lines.append(
                "Quantification MAPE: none claimable — every external flux reference is "
                "not_comparable (reasons above)."
            )
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
        detections: list[Detection] = []
        regression: list[RegressionCheck] = []
        status = RunStatus.RAN
        reason: str | None = None
        try:
            output = pipeline(event)
            if isinstance(output, PipelineOutput):
                detections = output.detections
                if output.regression_values is not None:
                    regression = compare_to_committed(event.event_id, output.regression_values)
            else:
                detections = output
        except EventNotRunnable as e:
            status = RunStatus.NOT_RUNNABLE
            reason = str(e)
        except Exception as e:
            status = RunStatus.ERROR
            reason = f"{type(e).__name__}: {e}"
        latency = time.perf_counter() - t0

        run_result = PipelineRunResult(
            event_id=event.event_id,
            detections=detections,
            latency_seconds=latency,
            status=status,
            status_reason=reason,
        )
        run_results.append(run_result)
        event_results.append(EventResult(
            event_id=event.event_id, pipeline_result=run_result, regression=regression,
        ))

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
