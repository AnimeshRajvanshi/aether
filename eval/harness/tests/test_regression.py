"""Tests for the heat branch of the ADR-0002 regression family (Sprint 9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aether_eval.regression import compare_to_committed


class TestHeatRegression:
    """compare_to_committed dispatches to the heat branch on air_lane.json."""

    @staticmethod
    def _write_air_lane(root: Path) -> None:
        d = root / "stage_b_outputs" / "heat_evt"
        d.mkdir(parents=True)
        (d / "air_lane.json").write_text(
            json.dumps(
                {
                    "c1_peak_tmax": {"value_c": 45.5},
                    "c2_anomaly": {"window_mean_regional_mean_anomaly_k": 4.1},
                    "c3_duration": {"n_days": 10},
                    "c4_extent": {"extent_km2": 800000.0},
                }
            )
        )

    def _fresh(self) -> dict[str, float]:
        return {
            "c1_peak_c": 45.5,
            "c2_window_mean_anomaly_k": 4.1,
            "c3_duration_days": 10.0,
            "c4_extent_km2": 800000.0,
        }

    def test_exact_values_pass(self, tmp_path: Path) -> None:
        self._write_air_lane(tmp_path)
        checks = compare_to_committed("heat_evt", self._fresh(), repo_root=tmp_path)
        assert len(checks) == 4
        assert all(c.passed for c in checks)

    def test_anomaly_drift_fails(self, tmp_path: Path) -> None:
        self._write_air_lane(tmp_path)
        fresh = self._fresh()
        fresh["c2_window_mean_anomaly_k"] = 4.2  # > 0.02 K tolerance
        checks = compare_to_committed("heat_evt", fresh, repo_root=tmp_path)
        assert any(c.name == "c2_window_mean_regional_anomaly_k" and not c.passed for c in checks)

    def test_duration_must_be_exact(self, tmp_path: Path) -> None:
        self._write_air_lane(tmp_path)
        fresh = self._fresh()
        fresh["c3_duration_days"] = 11.0
        checks = compare_to_committed("heat_evt", fresh, repo_root=tmp_path)
        assert any(c.name == "c3_duration_days" and not c.passed for c in checks)

    def test_extent_fractional_tolerance(self, tmp_path: Path) -> None:
        self._write_air_lane(tmp_path)
        fresh = self._fresh()
        fresh["c4_extent_km2"] = 800000.0 * 1.02  # > 1%
        checks = compare_to_committed("heat_evt", fresh, repo_root=tmp_path)
        assert any(c.name == "c4_extent_km2" and not c.passed for c in checks)

    def test_methane_path_untouched_when_no_air_lane(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            compare_to_committed("heat_evt", self._fresh(), repo_root=tmp_path)
