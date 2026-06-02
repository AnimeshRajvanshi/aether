"""Test the Stage B quantification pipeline + end-to-end eval wiring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from aether_eval.loader import load_event_file
from aether_eval.pipelines import (
    PIPELINE_NAME,
    PIPELINE_VERSION,
    stage_b_quantification_pipeline,
)
from aether_eval.runner import run_evaluation


def _fixture_event_yaml(tmp_path: Path) -> Path:
    """Build a minimum-valid Goturdepe-shaped benchmark YAML for tests."""
    data = {
        "event_id": "goturdepe_test_event",
        "name": "Goturdepe test event",
        "phenomenon_type": "emission_event",
        "expected_detection_types": ["methane_plume"],
        "date_range": {"start": "2022-08-15T04:28:00Z", "end": "2022-08-15T04:30:00Z"},
        "location": {"lon": 54.0, "lat": 39.5},
        "bbox": {"min_lon": 53.0, "min_lat": 39.0, "max_lon": 55.0, "max_lat": 40.0},
        "known_measurements": {
            "emission_rate_metric_tonnes_per_hr": {
                "value": 163.0,
                "uncertainty": 18.0,
                "unit": "tonnes/hr",
                "note": "Thorpe 2023 cluster total — not same-scope as single plume.",
            },
        },
        "canonical_acquisition": {
            "utc": "2022-08-15T04:28:38Z",
            "l1b_granule_ur": "EMIT_L1B_RAD_001_20220815T042838_2222703_003",
            "source": "Fixture",
        },
        "references": [{"citation": "Fixture event for tests"}],
    }
    path = tmp_path / "fixture_event.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def _q_estimate_json(stage_b_dir: Path, event_id: str) -> Path:
    """Build a minimum q_estimate.json the pipeline can read."""
    payload = {
        "plume_cc_label": 1213,
        "plume_centroid_lon": 53.69,
        "plume_centroid_lat": 39.37,
        "plume_cc_area_km2": 192.6,
        "ime_central_kg": 41165.3,
        "q_central_t_hr": 27.086,
        "q_central_nasa_calibrated_t_hr": 16.32,
        "q_low_t_hr": 14.22,
        "q_high_t_hr": 30.57,
        "q_total_fractional_sigma": 0.129,
    }
    event_dir = stage_b_dir / event_id
    event_dir.mkdir(parents=True, exist_ok=True)
    json_path = event_dir / "q_estimate.json"
    json_path.write_text(json.dumps(payload))
    return json_path


def test_pipeline_returns_no_detection_when_q_estimate_missing(tmp_path: Path) -> None:
    """If the Stage B JSON does not exist, the pipeline returns an empty list
    rather than raising — so the eval harness can be run on any event."""
    event = load_event_file(_fixture_event_yaml(tmp_path))
    detections = stage_b_quantification_pipeline(event, stage_b_dir=tmp_path / "nonexistent")
    assert detections == []


def test_pipeline_emits_one_detection_when_q_estimate_present(tmp_path: Path) -> None:
    """The pipeline reads q_estimate.json and emits exactly one Detection
    with the central Q in the measurements dict, plus an asymmetric-Q range
    set, and the wind+mask 1-σ as measurement_uncertainty."""
    event = load_event_file(_fixture_event_yaml(tmp_path))
    stage_b_dir = tmp_path / "stage_b_outputs"
    _q_estimate_json(stage_b_dir, event.event_id)

    detections = stage_b_quantification_pipeline(event, stage_b_dir=stage_b_dir)
    assert len(detections) == 1
    d = detections[0]
    # Quantification headline
    assert d.measurements["emission_rate_metric_tonnes_per_hr"] == pytest.approx(27.086)
    assert d.measurement_units["emission_rate_metric_tonnes_per_hr"] == "tonnes/hr"
    # Asymmetric range — both bounds present
    assert d.measurements["emission_rate_metric_tonnes_per_hr_low"] == pytest.approx(14.22)
    assert d.measurements["emission_rate_metric_tonnes_per_hr_high"] == pytest.approx(30.57)
    assert d.measurements["emission_rate_metric_tonnes_per_hr_nasa_calibrated"] == pytest.approx(16.32)
    # Symmetric 1-σ uncertainty: Q × σ_fractional
    assert d.measurement_uncertainty["emission_rate_metric_tonnes_per_hr"] == pytest.approx(
        27.086 * 0.129
    )
    # Location is the plume centroid
    assert d.location.lon == pytest.approx(53.69)
    assert d.location.lat == pytest.approx(39.37)
    # Provenance and algorithm metadata
    assert d.algorithm == PIPELINE_NAME
    assert d.algorithm_version == PIPELINE_VERSION
    assert d.provenance.source == "aether_detection"
    assert d.provenance.pipeline == PIPELINE_NAME


def test_run_evaluation_with_stage_b_pipeline(tmp_path: Path) -> None:
    """End-to-end: run_evaluation with the Stage B pipeline against a single
    event produces a non-empty Detection list and computes a quantification
    MAPE (which will be huge because of the scope mismatch — that is
    expected and documented, not a bug)."""
    benchmark_dir = tmp_path / "bench"
    benchmark_dir.mkdir()
    event_path = _fixture_event_yaml(benchmark_dir)
    event_path.rename(benchmark_dir / "fixture_event.yaml")
    stage_b_dir = tmp_path / "stage_b_outputs"
    _q_estimate_json(stage_b_dir, "goturdepe_test_event")

    def pipeline_with_dir(event):
        return stage_b_quantification_pipeline(event, stage_b_dir=stage_b_dir)

    # Multi-source super-emitter clusters span 10s of km, so the per-plume
    # centroid is naturally far from the event's nominal field-center. Use
    # a tolerance suitable for cluster-scale events (Goturdepe spans >25 km).
    report = run_evaluation(
        pipeline=pipeline_with_dir,
        benchmark_dir=benchmark_dir,
        pipeline_name="stage_b_test",
        spatial_tolerance_m=50000.0,
    )
    assert report.score.n_events == 1
    assert report.score.n_detections_total == 1
    assert report.score.n_detections_matched == 1
    # Quantification MAPE was computed (a value, not the empty dict).
    # The scope mismatch (single plume vs cluster total) means it is large
    # — and that is the expected, documented outcome.
    assert report.score.quantification_mape != {}
    mape = report.score.quantification_mape["emission_rate_metric_tonnes_per_hr"]
    # 27 vs 163 → MAPE ≈ 0.83. Tests against >0.5 just to assert the scope
    # mismatch shows up clearly in the headline number.
    assert mape > 0.5
