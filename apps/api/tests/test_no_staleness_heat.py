"""No-staleness guards for the Sprint 9 heat-vertical Stage B artifacts.

Every headline number written in the Stage B gate report must equal the value
in the committed upstream artifact it derives from — same discipline as the
Goturdepe/Permian guards. No magic constants: expected values are read from
air_lane.json / validation.json / uhi.json / lst_lane.json.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from aether_api import config

HEAT = "india_nw_heatwave_2022_04"
REPORT = "docs/reports/sprint9_stage_b_report.md"


@pytest.fixture(scope="module")
def air() -> dict[str, Any]:
    return json.loads((config.stage_b_dir(HEAT) / "air_lane.json").read_text())


@pytest.fixture(scope="module")
def validation() -> dict[str, Any]:
    return json.loads((config.stage_b_dir(HEAT) / "validation.json").read_text())


@pytest.fixture(scope="module")
def uhi() -> dict[str, Any]:
    return json.loads((config.stage_b_dir(HEAT) / "uhi.json").read_text())


@pytest.fixture(scope="module")
def lst() -> dict[str, Any]:
    return json.loads((config.stage_b_dir(HEAT) / "lst_lane.json").read_text())


@pytest.fixture(scope="module")
def report() -> str:
    return (config.data_root() / REPORT).read_text()


class TestAirLaneHeadlines:
    def test_c1_peak(self, report: str, air: dict[str, Any]) -> None:
        v = air["c1_peak_tmax"]["value_c"]
        assert f"{v:.2f} °C" in report, f"stale C1 peak {v:.2f}"

    def test_c2_window_mean(self, report: str, air: dict[str, Any]) -> None:
        v = air["c2_anomaly"]["window_mean_regional_mean_anomaly_k"]
        assert f"+{v:.2f} K" in report, f"stale C2 window mean {v:.2f}"

    def test_c2_peak_regional(self, report: str, air: dict[str, Any]) -> None:
        v = air["c2_anomaly"]["peak_regional_mean_anomaly_k"]
        assert f"+{v:.2f} K" in report, f"stale C2 peak regional {v:.2f}"

    def test_c3_duration(self, report: str, air: dict[str, Any]) -> None:
        n = air["c3_duration"]["n_days"]
        assert f"{n} days ({air['c3_duration']['start']}" in report.replace("**", ""), (
            f"stale C3 duration {n}"
        )

    def test_c4_extent(self, report: str, air: dict[str, Any]) -> None:
        v = int(air["c4_extent"]["extent_km2"])
        assert f"{v:,} km²" in report, f"stale C4 extent {v:,}"

    def test_s1_halves(self, report: str, air: dict[str, Any]) -> None:
        s1 = air["sensitivities"]["s1_baseline_halves"]
        a = s1["1991-2005"]["window_mean_regional_mean_anomaly_k"]
        b = s1["2006-2020"]["window_mean_regional_mean_anomaly_k"]
        assert f"{a:.2f} vs {b:.2f} K" in report

    def test_s3_residual(self, report: str, air: dict[str, Any]) -> None:
        v = air["sensitivities"]["s3_hour_set"]["mean_residual_k"]
        assert f"{v:.4f} K" in report


class TestValidationHeadlines:
    def test_v1_station_max(self, report: str, validation: dict[str, Any]) -> None:
        v = validation["v1_station_peak_bracket"]["max_station_window_tmax_c"]
        assert f"{v:.1f} °C" in report

    def test_v2_metrics(self, report: str, validation: dict[str, Any]) -> None:
        v2 = validation["v2_era5_station_consistency"]
        assert f"{v2['median_bias_k']:.2f} K" in report
        assert f"{v2['rmsd_k']:.2f} K" in report
        assert f"r = {v2['pearson_r']:.3f}" in report
        assert v2["pass_v2"] is False  # the report claims V2 FAILED; keep them in sync

    def test_v3_metrics(self, report: str, validation: dict[str, Any]) -> None:
        v3 = validation["v3_imd_anomaly_agreement"]
        assert f"{v3['era5_window_mean_regional_anomaly_k_common_grid']:.2f} K" in report
        assert f"{v3['imd_window_mean_regional_anomaly_k_common_grid']:.2f} K" in report
        assert f"{v3['pattern_pearson_r']:.3f}" in report
        assert v3["pass_v3a"] and v3["pass_v3b"]

    def test_v4_verdicts_in_sync(self, report: str, validation: dict[str, Any]) -> None:
        v4 = validation["v4_duration_extent"]
        assert v4["pass_v4a"] is False and v4["pass_v4b"] is False
        assert f"{int(v4['extent_common_grid_imd_km2']):,} km²" in report
        dur = v4["duration_imd_days"]
        assert f"{dur} d" in report or f"{dur} days" in report

    def test_exploratory_artifact_matches(self, report: str) -> None:
        exp = json.loads(
            (config.stage_b_dir(HEAT) / "validation_exploratory_minobs3.json").read_text()
        )
        assert f"r = {exp['pearson_r']:.3f}" in report
        assert "exploratory" in exp["exploratory"].lower() or "MIN_OBS" in exp["exploratory"]


class TestLstLaneHeadlines:
    def test_window_mean_anomaly(self, report: str, lst: dict[str, Any]) -> None:
        v = lst["window_mean_bbox_anomaly_k"]
        assert f"+{v:.2f} K" in report or f"+{v:.1f} K" in report

    def test_view_time(self, report: str, lst: dict[str, Any]) -> None:
        v = lst["observation_time_caveat"]["measured_mean_day_view_time_local_h"]
        assert f"{v:.2f} h" in report

    def test_l3_offset(self, report: str, lst: dict[str, Any]) -> None:
        l3 = lst["l3_product_consistency"]
        expected = f"−{abs(l3['mean_diff_modis_minus_era5skt_k']):.2f} ± {l3['std_diff_k']:.2f} K"
        assert expected in report

    def test_composite_residual(self, report: str, lst: dict[str, Any]) -> None:
        v = lst["anomaly_baseline"]["composite_vs_daily_residual_k_2022"]
        assert f"−{abs(v):.2f} K" in report

    def test_no_daily_max_framing(self, lst: dict[str, Any]) -> None:
        """The lane's own artifact must carry the observation-time statement."""
        stmt = lst["observation_time_caveat"]["statement"]
        assert "NOT" in stmt or "Nothing in this lane is a daily maximum" in stmt
        assert "10." in stmt  # the measured hour, not boilerplate


class TestUhiHeadlines:
    def test_window_mean(self, report: str, uhi: dict[str, Any]) -> None:
        v = uhi["window_mean_uhi_k"]
        assert f"−{abs(v):.2f} ± {uhi['window_std_uhi_k']:.2f} K" in report

    def test_sign_negative_and_framed(self, report: str, uhi: dict[str, Any]) -> None:
        assert uhi["window_mean_uhi_k"] < 0
        assert "NEGATIVE" in report  # the sign is the headline, stated loudly

    def test_elevation_guard_honesty(self, uhi: dict[str, Any]) -> None:
        assert uhi["elevation_guard"]["applied"] is False  # stated, not silently skipped

    def test_isd_license_in_validation_provenance(self, validation: dict[str, Any]) -> None:
        prov = validation["provenance"]
        assert "cannot be redistributed" in prov["isd_license_verbatim"]
        assert "derived" in prov["isd_handling"]


class TestStageCReportHeadlines:
    """Stage C gate-report numbers trace to the committed attribution artifacts."""

    @pytest.fixture(scope="class")
    def diag(self) -> dict[str, Any]:
        return json.loads(
            (config.data_root() / "attribution_outputs" / HEAT / "diagnostics.json").read_text()
        )

    @pytest.fixture(scope="class")
    def factors(self) -> dict[str, Any]:
        return json.loads(
            (
                config.data_root() / "attribution_outputs" / HEAT / "factor_hypotheses.json"
            ).read_text()
        )

    @pytest.fixture(scope="class")
    def report_c(self) -> str:
        return (config.data_root() / "docs/reports/sprint9_stage_c_report.md").read_text()

    def test_z500_numbers(self, report_c: str, diag: dict[str, Any]) -> None:
        z = diag["z500"]
        report_c = report_c.replace("\u2212", "-")  # typographic minus -> ASCII
        assert f"+{z['anomaly_m']} m" in report_c
        assert f"{z['cross_store_offset_m']} m" in report_c
        assert f"{z['window_mean_2022_corrected_m']} m" in report_c
        assert f"{z['days_above_pooled_p90']}/{z['n_window_days']} days" in report_c

    def test_soil_dryness_rank(self, report_c: str, diag: dict[str, Any]) -> None:
        rank = round((1.0 - diag["soil_moisture"]["antecedent_percentile"]) * 100)
        assert f"{rank}%" in report_c

    def test_factor_scores_and_tiers(self, report_c: str, factors: dict[str, Any]) -> None:
        by_id = {f["id"]: f for f in factors["factors"]}
        for fid in ("F1", "F2", "F3", "F4", "F5"):
            assert f"{by_id[fid]['score']:.2f}" in report_c, f"{fid} score stale"
        assert by_id["F1"]["confidence_tier"] == "moderate"  # capped — report says so
        assert by_id["F5"]["role"] == "counter_evidence"
        gap = abs(by_id["F1"]["score"] - by_id["F2"]["score"])
        assert f"{gap:.2f}" in report_c

    def test_headline_quoted_faithfully(self, report_c: str, factors: dict[str, Any]) -> None:
        assert "did NOT materialize" in factors["headline_finding"]
        assert "did NOT materialize" in report_c

    def test_boundary_and_external_attribution(self, factors: dict[str, Any]) -> None:
        assert "does NOT perform probabilistic" in factors["attribution_boundary"]
        ext = factors["external_published_attribution"]
        assert len(ext) == 1 and "10.1088/2752-5295/acf4b6" in ext[0]["source"]["dataset"]
