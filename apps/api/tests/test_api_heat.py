"""Endpoint tests for the heat event (Sprint 9 Stage D).

Same no-fabrication discipline as test_api.py: every served value must equal
the committed artifact it claims to source — assertions read the artifacts
directly, no magic constants.
"""

from __future__ import annotations

import json

import pytest
from aether_api import config
from aether_api.main import app
from fastapi.testclient import TestClient

HEAT = "india_nw_heatwave_2022_04"
client = TestClient(app)


@pytest.fixture(scope="module")
def air() -> dict:
    return json.loads((config.stage_b_dir(HEAT) / "air_lane.json").read_text())


@pytest.fixture(scope="module")
def lst() -> dict:
    return json.loads((config.stage_b_dir(HEAT) / "lst_lane.json").read_text())


@pytest.fixture(scope="module")
def uhi() -> dict:
    return json.loads((config.stage_b_dir(HEAT) / "uhi.json").read_text())


@pytest.fixture(scope="module")
def detail() -> dict:
    r = client.get(f"/api/events/{HEAT}")
    assert r.status_code == 200
    return r.json()


def test_heat_event_active_with_window_acquisition(air: dict) -> None:
    by_id = {e["event_id"]: e for e in client.get("/api/events").json()}
    e = by_id[HEAT]
    assert e["status"] == "active"
    assert e["phenomenon_type"] == "heat_wave"
    # the "acquisition" is the canonical analysis window, honestly labeled
    assert air["window"][0] in e["acquisition_utc"] and "window" in e["acquisition_utc"]
    # headline numbers trace to air_lane.json
    assert f"+{air['c2_anomaly']['window_mean_regional_mean_anomaly_k']:.1f} K" in e["headline"]
    assert f"{air['c1_peak_tmax']['value_c']:.1f} °C" in e["headline"]


def test_heat_block_traces_to_artifacts(detail: dict, air: dict, lst: dict, uhi: dict) -> None:
    h = detail["heat"]
    assert h["peak_tmax_c"] == air["c1_peak_tmax"]["value_c"]
    assert h["window_mean_regional_anomaly_k"] == pytest.approx(
        air["c2_anomaly"]["window_mean_regional_mean_anomaly_k"]
    )
    assert h["peak_day_extent_km2"] == air["c4_extent"]["extent_km2"]
    assert h["episode"]["episode_days"] == air["c3_duration"]["n_days"]
    assert h["episode"]["window_start"] == air["window"][0]
    assert h["lst"]["window_mean_anomaly_k"] == lst["window_mean_bbox_anomaly_k"]
    assert h["lst"]["view_time_local_h"] == (
        lst["observation_time_caveat"]["measured_mean_day_view_time_local_h"]
    )
    assert h["lst"]["observation_time_statement"] == lst["observation_time_caveat"]["statement"]
    assert h["lst"]["uhi_window_mean_k"] == uhi["window_mean_uhi_k"]


def test_episode_vs_window_distinct(detail: dict) -> None:
    ep = detail["heat"]["episode"]
    assert ep["window_start"] != ep["episode_start"]  # 26d episode vs 10d window
    assert "never conflated" in ep["note"].lower() or "not conflated" in ep["note"].lower()


def test_lst_vs_air_block_first_class(detail: dict) -> None:
    block = detail["heat"]["lst_vs_air"]
    assert "AIR" in block and "SKIN" in block
    assert "VALIDATED" in block and "CROSS-CHECKED" in block


def test_factor_endpoint_serves_committed_artifact_verbatim() -> None:
    committed = json.loads(
        (config.data_root() / "attribution_outputs" / HEAT / "factor_hypotheses.json").read_text()
    )
    served = client.get(f"/api/events/{HEAT}/factor-hypotheses").json()
    assert served == committed  # verbatim — the API can neither add nor drop


def test_methane_events_have_no_factor_artifact() -> None:
    r = client.get("/api/events/turkmenistan_goturdepe_2022_08_15/factor-hypotheses")
    assert r.json() == {"factors": None, "status": "pending"}


def test_heat_layers_served_and_whitelisted() -> None:
    bounds = json.loads((config.assets_dir(HEAT) / "bounds.json").read_text())
    for layer in bounds["layers"]:
        r = client.get(f"/api/events/{HEAT}/layers/{layer}.png")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    # not in the whitelist -> 404 (and path traversal shapes don't resolve)
    assert client.get(f"/api/events/{HEAT}/layers/enhancement.png").status_code == 404
    assert client.get(f"/api/events/{HEAT}/layers/nope.png").status_code == 404


def test_heat_raster_meta_matches_bounds_json(detail: dict) -> None:
    bounds = json.loads((config.assets_dir(HEAT) / "bounds.json").read_text())
    hr = detail["heat"]["heat_raster"]
    assert hr["bounds"] == bounds["bounds"]
    assert hr["layers"] == bounds["layers"]
    assert hr["lst_view_time_local_h"] == bounds["lst_view_time_local_h"]


def test_heat_has_no_methane_blocks(detail: dict) -> None:
    """Two-domain integrity: the heat payload carries no plume-shaped science."""
    for key in ("quantification", "geometry", "atmosphere", "validation", "scope_caveat"):
        assert detail[key] is None
    assert detail["uncertainty_budget"] == []


def test_methane_details_have_no_heat_block() -> None:
    for eid in ("turkmenistan_goturdepe_2022_08_15", "permian_basin_2022"):
        d = client.get(f"/api/events/{eid}").json()
        assert d["heat"] is None
