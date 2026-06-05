"""Endpoint tests for the dashboard API.

The point of these tests is the no-fabrication guarantee: every value the API
serves must equal the value in the committed Stage A/B file it claims to source.
So we read q_estimate.json / stage_a_report.json / the benchmark YAML directly
and assert the JSON responses match — no magic constants in the assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from aether_api import config
from aether_api.main import app
from fastapi.testclient import TestClient

GOTURDEPE = "turkmenistan_goturdepe_2022_08_15"
PERMIAN = "permian_basin_2022"

client = TestClient(app)


@pytest.fixture(scope="module")
def q() -> dict:
    return json.loads((config.stage_b_dir(GOTURDEPE) / "q_estimate.json").read_text())


@pytest.fixture(scope="module")
def stage_a() -> dict:
    return json.loads((config.stage_a_dir(GOTURDEPE) / "stage_a_report.json").read_text())


@pytest.fixture(scope="module")
def benchmark() -> dict:
    return yaml.safe_load(config.benchmark_yaml(GOTURDEPE).read_text())


def test_health() -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_events_list_two_events_one_pending() -> None:
    events = client.get("/api/events").json()
    by_id = {e["event_id"]: e for e in events}
    assert set(by_id) == {GOTURDEPE, PERMIAN}
    assert by_id[GOTURDEPE]["status"] == "active"
    assert by_id[PERMIAN]["status"] == "pending"
    # Permian must NOT carry an invented rate.
    assert by_id[PERMIAN]["headline"] == "pending"


def test_marker_sits_on_real_centroid(q: dict) -> None:
    g = {e["event_id"]: e for e in client.get("/api/events").json()}[GOTURDEPE]
    assert g["lat"] == pytest.approx(q["plume_centroid_lat"])
    assert g["lon"] == pytest.approx(q["plume_centroid_lon"])


def test_summary_acquisition_traces_to_stage_a(stage_a: dict) -> None:
    by_id = {e["event_id"]: e for e in client.get("/api/events").json()}
    # Active event's acquisition timestamp must equal the committed Stage A file.
    assert by_id[GOTURDEPE]["acquisition_utc"] == stage_a["acquisition_utc"]
    # Pending event has no processed overpass — we must not imply one.
    assert by_id[PERMIAN]["acquisition_utc"] is None


def test_quantification_matches_q_estimate(q: dict) -> None:
    d = client.get(f"/api/events/{GOTURDEPE}").json()
    quant = d["quantification"]
    assert quant["ours_cal"]["value_t_hr"] == pytest.approx(q["q_central_t_hr"])
    assert quant["ours_cal"]["range_low_t_hr"] == pytest.approx(q["q_low_t_hr"])
    assert quant["ours_cal"]["range_high_t_hr"] == pytest.approx(q["q_high_t_hr"])
    assert quant["nasa_cal"]["value_t_hr"] == pytest.approx(q["q_central_nasa_calibrated_t_hr"])
    # NASA-cal range is ours range / bias — assert the derivation, not a constant.
    bias = q["enhancement_bias_factor"]
    assert quant["nasa_cal"]["range_low_t_hr"] == pytest.approx(q["q_low_t_hr"] / bias)
    assert quant["nasa_cal"]["range_high_t_hr"] == pytest.approx(q["q_high_t_hr"] / bias)
    assert quant["enhancement_bias_factor"] == bias


def test_uncertainty_budget_terms(q: dict) -> None:
    d = client.get(f"/api/events/{GOTURDEPE}").json()
    terms = {t["key"]: t for t in d["uncertainty_budget"]}
    assert terms["alpha1"]["value_pct"] == pytest.approx(q["wind_fractional_alpha1"] * 100)
    assert terms["era5_u10"]["value_pct"] == pytest.approx(q["wind_fractional_u10"] * 100)
    # Mask term is half the peak-to-peak segmentation spread.
    assert terms["mask"]["value_pct"] == pytest.approx(
        q["seg_sensitivity_q_spread_fractional"] / 2 * 100
    )
    assert terms["mf_amplitude"]["factor"] == q["enhancement_bias_factor"]
    assert terms["mf_amplitude"]["kind"] == "systematic"


def test_geometry_and_atmosphere(q: dict) -> None:
    d = client.get(f"/api/events/{GOTURDEPE}").json()
    assert d["geometry"]["ime_t"] == pytest.approx(q["ime_central_kg"] / 1000)
    assert d["geometry"]["area_km2"] == pytest.approx(q["plume_cc_area_km2"])
    assert d["geometry"]["length_km"] == pytest.approx(q["plume_length_m"] / 1000)
    assert d["atmosphere"]["u10_speed_ms"] == pytest.approx(q["era5_u10_speed_ms"])
    assert d["atmosphere"]["u_eff_ms"] == pytest.approx(q["u_eff_ms"])


def test_validation_matches_stage_a(stage_a: dict) -> None:
    d = client.get(f"/api/events/{GOTURDEPE}").json()
    assert d["validation"]["pearson_in_bbox"] == pytest.approx(stage_a["pearson_in_bbox"])
    assert d["validation"]["n_pixels_bbox"] == stage_a["n_pixels_compared_bbox"]
    assert d["provenance"]["l1b_granule_ur"] == stage_a["l1b_granule_ur"]
    assert d["provenance"]["bands_used"] == stage_a["bands_used"]


def test_scope_caveat_from_benchmark(benchmark: dict, q: dict) -> None:
    d = client.get(f"/api/events/{GOTURDEPE}").json()
    meas = benchmark["known_measurements"]["emission_rate_metric_tonnes_per_hr"]
    caveat = d["scope_caveat"]
    assert caveat["reference_total_t_hr"] == meas["value"]
    assert caveat["reference_uncertainty_t_hr"] == meas["uncertainty"]
    assert caveat["n_sources"] == meas["n_sources"]
    assert caveat["fraction_high_pct"] == pytest.approx(q["q_central_t_hr"] / meas["value"] * 100)


def test_references_have_dois(benchmark: dict) -> None:
    d = client.get(f"/api/events/{GOTURDEPE}").json()
    dois = {r.get("doi") for r in d["references"]}
    assert "10.1126/sciadv.adh2391" in dois  # Thorpe 2023
    assert "10.5067/EMIT/EMITL2BCH4ENH.002" in dois


def test_raster_assets_served() -> None:
    for layer in ("enhancement", "nasa", "diff"):
        r = client.get(f"/api/events/{GOTURDEPE}/{layer}.png")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
    geo = client.get(f"/api/events/{GOTURDEPE}/mask.geojson").json()
    assert geo["properties"]["cc_label"] == 1213
    bounds = client.get(f"/api/events/{GOTURDEPE}/bounds").json()
    assert set(bounds["bounds"]) == {"west", "south", "east", "north"}


def test_pending_event_has_no_quantification() -> None:
    d = client.get(f"/api/events/{PERMIAN}").json()
    assert d["status"] == "pending"
    assert d["quantification"] is None
    assert d["geometry"] is None
    assert d["pending_reason"]
    # References are still real.
    assert any("nasa.gov" in (r.get("url") or "") for r in d["references"])


def test_hypotheses_equals_committed_artifact() -> None:
    committed = json.loads(
        (config.data_root() / "attribution_outputs" / GOTURDEPE / "hypotheses.json").read_text()
    )
    api = client.get(f"/api/events/{GOTURDEPE}/hypotheses").json()
    # The API must serve the artifact verbatim — equal values AND equal field sets
    # at every level (no fields added, none dropped).
    assert api == committed


def test_hypotheses_preserve_the_caveats() -> None:
    api = client.get(f"/api/events/{GOTURDEPE}/hypotheses").json()
    h1 = api["hypotheses"][0]
    # the flaring temporal_caveat survives the API round-trip
    flare = next(e for e in h1["evidence"] if e["kind"] == "flaring_corroboration")
    assert "NOT the located source" in flare["temporal_caveat"]
    # H1's cap rationale survives
    assert "CAPPED" in h1["confidence_rationale"]
    assert "NO facility-level point infrastructure" in api["headline_finding"]
    assert "not calibrated" in api["scoring_disclaimer"].lower()


def test_pending_event_hypotheses_absent_not_fabricated() -> None:
    r = client.get(f"/api/events/{PERMIAN}/hypotheses")
    assert r.status_code == 200
    body = r.json()
    assert body == {"hypotheses": None, "status": "pending"}


def test_hypotheses_unknown_event_404() -> None:
    assert client.get("/api/events/does_not_exist/hypotheses").status_code == 404


def test_unknown_event_404() -> None:
    assert client.get("/api/events/does_not_exist").status_code == 404


def test_data_root_override(tmp_path: Path) -> None:
    # AETHER_DATA_ROOT must redirect file reads (used for deployment/tests).
    assert config.data_root() == Path(config.__file__).resolve().parents[3]
