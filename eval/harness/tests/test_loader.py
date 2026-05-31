"""Tests for the loader and full runner end-to-end."""

from __future__ import annotations

from pathlib import Path

import pytest

from aether_eval.loader import default_benchmark_dir, discover_events, load_event, load_event_file
from aether_eval.runner import run_evaluation, stub_pipeline


REPO_BENCHMARK_DIR = Path(__file__).resolve().parents[2] / "benchmark"


class TestLoader:
    def test_default_benchmark_dir_resolves_to_repo(self) -> None:
        # Sanity check: the loader points at eval/benchmark relative to the repo root
        d = default_benchmark_dir()
        assert d.name == "benchmark"
        assert d.parent.name == "eval"

    def test_loads_aliso_canyon(self) -> None:
        path = REPO_BENCHMARK_DIR / "aliso_canyon_2015.yaml"
        event = load_event_file(path)
        assert event.event_id == "aliso_canyon_2015"
        assert event.attribution.operator == "Southern California Gas Company"
        # The peer-reviewed peak rate is 60,000 kg/hr per Conley et al. 2016
        assert event.known_measurements["peak_emission_rate_kg_per_hr"].value == 60000.0

    def test_discover_events_finds_at_least_aliso(self) -> None:
        events = discover_events(REPO_BENCHMARK_DIR)
        ids = {e.event_id for e in events}
        assert "aliso_canyon_2015" in ids

    def test_load_event_by_id(self) -> None:
        event = load_event("aliso_canyon_2015", REPO_BENCHMARK_DIR)
        assert event.name.startswith("Aliso Canyon")

    def test_load_event_unknown_id_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_event("does_not_exist_12345", REPO_BENCHMARK_DIR)


class TestRunnerEndToEnd:
    def test_stub_pipeline_gives_zero_recall(self) -> None:
        """End-to-end: load real events, run the stub pipeline, expect recall == 0."""
        report = run_evaluation(
            pipeline=stub_pipeline,
            benchmark_dir=REPO_BENCHMARK_DIR,
            pipeline_name="stub_pipeline",
        )
        assert report.score.n_events >= 1
        assert report.score.recall == 0.0
        assert report.score.n_detections_total == 0
        # Latency for the stub should be tiny but >= 0
        assert report.score.mean_latency_seconds >= 0.0

    def test_pipeline_exception_does_not_crash_run(self) -> None:
        """A pipeline that raises should be captured, not propagate."""

        def broken(event):
            raise RuntimeError("boom")

        report = run_evaluation(
            pipeline=broken,
            benchmark_dir=REPO_BENCHMARK_DIR,
            pipeline_name="broken_pipeline",
        )
        # All events get zero detections but the run completes
        assert report.score.recall == 0.0
        # Error is captured on each PipelineRunResult
        for er in report.event_results:
            assert er.pipeline_result.error is not None
            assert "RuntimeError" in er.pipeline_result.error

    def test_summary_lines_render(self) -> None:
        report = run_evaluation(
            pipeline=stub_pipeline,
            benchmark_dir=REPO_BENCHMARK_DIR,
            pipeline_name="stub_pipeline",
        )
        lines = report.summary_lines()
        assert any("Pipeline:" in line for line in lines)
        assert any("recall = " in line for line in lines)
