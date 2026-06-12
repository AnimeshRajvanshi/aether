"""Tests for the real-pipeline eval wiring (ADR 0002).

Two layers:

* CI-SAFE — runnability semantics and the regression-comparison logic against
  the committed artifacts. These need no granule cache and no network (the
  runnability check is pure data; the regression logic reads only committed
  JSON), so they run on every push.
* INTEGRATION (network-gated, deselected by default) — the full real-pipeline
  run over the whole benchmark: cached granules + ARCO-ERA5. This is the
  honest scoreboard itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aether_eval.loader import discover_events, load_event
from aether_eval.metrics import RunStatus
from aether_eval.real_pipeline import check_runnable, real_emit_pipeline
from aether_eval.regression import (
    CENTROID_KM_TOL,
    compare_to_committed,
)
from aether_eval.runner import EventNotRunnable, run_evaluation
from aether_eval.schema import ReferenceUsability

REPO_ROOT = Path(__file__).resolve().parents[3]
REPO_BENCHMARK_DIR = REPO_ROOT / "eval" / "benchmark"

GOTURDEPE = "turkmenistan_goturdepe_2022_08_15"
PERMIAN = "permian_basin_2022"
ALISO = "aliso_canyon_2015"


def _committed_fresh_values(event_id: str) -> dict[str, float]:
    """The committed values themselves, shaped as a fresh-run dict."""
    q = json.loads((REPO_ROOT / "stage_b_outputs" / event_id / "q_estimate.json").read_text())
    a = json.loads((REPO_ROOT / "stage_a_outputs" / event_id / "stage_a_report.json").read_text())
    return {
        "q_central_t_hr": float(q["q_central_t_hr"]),
        "q_central_nasa_calibrated_t_hr": float(q["q_central_nasa_calibrated_t_hr"]),
        "pearson_full_scene": float(a["pearson_full_scene"]),
        "pearson_in_bbox": float(a["pearson_in_bbox"]),
        "centroid_lat": float(q["plume_centroid_lat"]),
        "centroid_lon": float(q["plume_centroid_lon"]),
    }


class TestRunnability:
    """Pure-data runnability checks — no scientific imports, CI-safe."""

    def test_aliso_is_not_runnable_with_stated_reason(self) -> None:
        event = load_event(ALISO, REPO_BENCHMARK_DIR)
        with pytest.raises(EventNotRunnable) as exc:
            check_runnable(event)
        msg = str(exc.value)
        assert "no EMIT coverage" in msg
        assert "2015" in msg  # the event window is named, not hand-waved

    def test_live_events_are_runnable(self) -> None:
        for event_id in (GOTURDEPE, PERMIAN):
            check_runnable(load_event(event_id, REPO_BENCHMARK_DIR))  # must not raise

    def test_aliso_reported_not_dropped(self) -> None:
        """Through the runner: NOT_RUNNABLE status, on the scoreboard, out of
        the recall denominator — never silently dropped, never a fake miss."""
        event = load_event(ALISO, REPO_BENCHMARK_DIR)
        report = run_evaluation(
            pipeline=real_emit_pipeline, events=[event], pipeline_name="real_emit_pipeline"
        )
        assert report.score.n_events == 1
        assert report.score.n_events_not_runnable == 1
        assert report.score.n_events_runnable == 0
        result = report.event_results[0].pipeline_result
        assert result.status is RunStatus.NOT_RUNNABLE
        assert result.status_reason is not None and "no EMIT coverage" in result.status_reason
        rendered = "\n".join(report.summary_lines())
        assert "NOT_RUNNABLE" in rendered and "no EMIT coverage" in rendered


class TestRegressionLogic:
    """The fresh-vs-committed comparison logic, fed committed values (CI-safe)."""

    @pytest.mark.parametrize("event_id", [GOTURDEPE, PERMIAN])
    def test_committed_values_pass(self, event_id: str) -> None:
        checks = compare_to_committed(event_id, _committed_fresh_values(event_id))
        assert len(checks) == 5
        assert all(c.passed for c in checks), [c.describe() for c in checks]

    def test_q_drift_beyond_one_percent_fails(self) -> None:
        fresh = _committed_fresh_values(GOTURDEPE)
        fresh["q_central_t_hr"] *= 1.02  # +2% — outside the ±1% tolerance
        checks = {c.name: c for c in compare_to_committed(GOTURDEPE, fresh)}
        assert not checks["q_central_t_hr"].passed

    def test_pearson_drift_beyond_tolerance_fails(self) -> None:
        fresh = _committed_fresh_values(GOTURDEPE)
        fresh["pearson_in_bbox"] += 0.02  # outside ±0.01
        checks = {c.name: c for c in compare_to_committed(GOTURDEPE, fresh)}
        assert not checks["pearson_in_bbox"].passed

    def test_centroid_drift_beyond_tolerance_fails(self) -> None:
        fresh = _committed_fresh_values(PERMIAN)
        fresh["centroid_lat"] += 0.02  # ~2.2 km north — outside the km tolerance
        checks = {c.name: c for c in compare_to_committed(PERMIAN, fresh)}
        assert not checks["plume_centroid"].passed
        assert checks["plume_centroid"].fresh > CENTROID_KM_TOL

    def test_event_without_committed_artifacts_raises(self) -> None:
        """Regression against nothing is meaningless; silence would hide it."""
        with pytest.raises(FileNotFoundError):
            compare_to_committed("no_such_event", _committed_fresh_values(GOTURDEPE))


@pytest.mark.integration
class TestRealPipelineFullRun:
    """The honest scoreboard, end-to-end. Needs the local granule cache and
    ARCO-ERA5 network access (Permian) — deselected by default, run locally:

        uv run pytest -m integration eval/harness/tests/test_real_pipeline.py
    """

    def test_full_benchmark_scoreboard(self) -> None:
        events = discover_events(REPO_BENCHMARK_DIR)
        committed_before = {
            event_id: (REPO_ROOT / "stage_b_outputs" / event_id / "q_estimate.json").read_text()
            for event_id in (GOTURDEPE, PERMIAN)
        }

        report = run_evaluation(
            pipeline=real_emit_pipeline, events=events, pipeline_name="real_emit_pipeline"
        )

        # Statuses: Aliso not_runnable; both live events ran.
        by_id = {r.event_id: r for r in report.event_results}
        assert by_id[ALISO].pipeline_result.status is RunStatus.NOT_RUNNABLE
        assert by_id[GOTURDEPE].pipeline_result.status is RunStatus.RAN
        assert by_id[PERMIAN].pipeline_result.status is RunStatus.RAN

        # External-truth: detection recall 2/2 over runnable events.
        assert report.score.n_events_runnable == 2
        assert report.score.n_events_recalled == 2
        assert report.score.recall == pytest.approx(1.0)

        # Regression: every check green for both events.
        for event_id in (GOTURDEPE, PERMIAN):
            checks = by_id[event_id].regression
            assert len(checks) == 5
            assert all(c.passed for c in checks), [c.describe() for c in checks]
        assert report.regression_all_green

        # Quantification: not_comparable with reasons — never a number.
        outcomes = {
            (q.event_id, q.measurement): q for q in report.score.quantification
        }
        goturdepe_q = outcomes[(GOTURDEPE, "emission_rate_metric_tonnes_per_hr")]
        assert goturdepe_q.usability is ReferenceUsability.SCOPE_MISMATCH
        assert goturdepe_q.mape is None
        permian_q = outcomes[(PERMIAN, "emission_rate_metric_tonnes_per_hr")]
        assert permian_q.usability is ReferenceUsability.CONTEXT_ONLY
        assert permian_q.mape is None
        permian_len = outcomes[(PERMIAN, "plume_length_km")]
        assert permian_len.usability is ReferenceUsability.CONTEXT_ONLY

        # The committed artifacts were the comparison target, not an output:
        # they must be byte-identical after the run.
        for event_id, before in committed_before.items():
            after = (
                REPO_ROOT / "stage_b_outputs" / event_id / "q_estimate.json"
            ).read_text()
            assert after == before, f"{event_id} q_estimate.json was modified by the eval run"


class TestHeatEventRunnability:
    """Non-emission phenomena get phenomenon-aware runnability (Sprint 9)."""

    def test_heat_event_with_recipe_passes_check_runnable(self) -> None:
        event = load_event("india_nw_heatwave_2022_04", REPO_BENCHMARK_DIR)
        check_runnable(event)  # recipe is wired; no EMIT-shaped objection

    def test_heat_recipe_honest_reason_when_cache_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import aether_eval.real_pipeline as rp

        monkeypatch.setattr(rp, "_HEAT_CACHE", tmp_path)
        event = load_event("india_nw_heatwave_2022_04", REPO_BENCHMARK_DIR)
        with pytest.raises(EventNotRunnable) as exc:
            rp.real_emit_pipeline(event)
        msg = str(exc.value)
        assert "heat ERA5 cache incomplete" in msg
        assert "EMIT" not in msg

    def test_unwired_area_phenomenon_gets_honest_reason(self) -> None:
        event = load_event("india_nw_heatwave_2022_04", REPO_BENCHMARK_DIR)
        unwired = event.model_copy(update={"event_id": "some_future_heat_event"})
        with pytest.raises(EventNotRunnable, match="no eval recipe is wired for phenomenon type"):
            check_runnable(unwired)

    def test_emission_event_reasons_unchanged(self) -> None:
        aliso = load_event("aliso_canyon_2015", REPO_BENCHMARK_DIR)
        with pytest.raises(EventNotRunnable, match="predates EMIT's July 2022 launch"):
            check_runnable(aliso)
