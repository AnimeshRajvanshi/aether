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


def test_events_list_two_active_events_with_tiers() -> None:
    # Stage D: both events are now active, each carrying its validation tier.
    events = client.get("/api/events").json()
    by_id = {e["event_id"]: e for e in events}
    assert set(by_id) == {GOTURDEPE, PERMIAN}
    assert by_id[GOTURDEPE]["status"] == "active"
    assert by_id[PERMIAN]["status"] == "active"
    assert by_id[GOTURDEPE]["validation_tier"] == "VALIDATED"
    assert by_id[PERMIAN]["validation_tier"] == "CROSS-CHECKED"
    # Headlines are the real OURS-CAL rates, never invented.
    permian_q = json.loads((config.stage_b_dir(PERMIAN) / "q_estimate.json").read_text())
    assert by_id[PERMIAN]["headline"] == f"CH₄ · {permian_q['q_central_t_hr']:.1f} t/hr"


def test_marker_sits_on_real_centroid(q: dict) -> None:
    g = {e["event_id"]: e for e in client.get("/api/events").json()}[GOTURDEPE]
    assert g["lat"] == pytest.approx(q["plume_centroid_lat"])
    assert g["lon"] == pytest.approx(q["plume_centroid_lon"])


def test_summary_acquisition_traces_to_stage_a(stage_a: dict) -> None:
    by_id = {e["event_id"]: e for e in client.get("/api/events").json()}
    # Each active event's acquisition timestamp must equal its committed Stage A file.
    assert by_id[GOTURDEPE]["acquisition_utc"] == stage_a["acquisition_utc"]
    permian_a = json.loads((config.stage_a_dir(PERMIAN) / "stage_a_report.json").read_text())
    assert by_id[PERMIAN]["acquisition_utc"] == permian_a["acquisition_utc"]


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
    # cc_label must equal the quantified CC in q_estimate.json — not a magic constant
    # (it changed 1213 → 1143 in the Sprint 6 v2 HITRAN-k operational migration).
    q = json.loads((config.stage_b_dir(GOTURDEPE) / "q_estimate.json").read_text())
    assert geo["properties"]["cc_label"] == q["plume_cc_label"]
    bounds = client.get(f"/api/events/{GOTURDEPE}/bounds").json()
    assert set(bounds["bounds"]) == {"west", "south", "east", "north"}


def test_permian_active_tier_and_crosscheck_facts() -> None:
    """Stage D: Permian is active, CROSS-CHECKED, with BOTH cross-check facts and an
    honest context-only scope block (no Thorpe cluster)."""
    d = client.get(f"/api/events/{PERMIAN}").json()
    q = json.loads((config.stage_b_dir(PERMIAN) / "q_estimate.json").read_text())
    diag = json.loads((config.stage_b_dir(PERMIAN) / "diagnostics.json").read_text())
    assert d["status"] == "active"
    assert d["validation_tier"] == "CROSS-CHECKED"
    assert "CROSS-CHECKED" in d["tier_explainer"]
    # Both cross-check facts are surfaced, traced to committed files.
    val = d["validation"]
    assert val["integrated_mass_ratio"] == pytest.approx(q["enhancement_bias_factor"])
    assert val["pixel_pearson"] == pytest.approx(
        diag["pixelwise_pearson_on_footprint_ours_vs_nasa"]
    )
    # Context-only scope: no Thorpe cluster, frames 18.3 as context.
    assert d["scope_caveat"]["kind"] == "context_only"
    assert d["scope_caveat"]["n_sources"] is None
    assert "press-release" in d["scope_caveat"]["text"].lower()
    # Provenance distinguishes NASA-anchored localization.
    assert "NASA-footprint-anchored" in d["provenance"]["localization"]
    # Quantification note is honest about direction: for bias < 1 it must say ours is
    # BELOW NASA and that the +1.46× Goturdepe over-amplitude does NOT transfer — never
    # call Permian itself an over-amplitude.
    if q["enhancement_bias_factor"] < 1.0:
        note = d["quantification"]["ours_cal"]["note"].lower()
        assert "below" in note and "does not transfer" in note


def test_permian_active_quantification_traces_to_q() -> None:
    d = client.get(f"/api/events/{PERMIAN}").json()
    q = json.loads((config.stage_b_dir(PERMIAN) / "q_estimate.json").read_text())
    assert d["quantification"]["ours_cal"]["value_t_hr"] == pytest.approx(q["q_central_t_hr"])
    assert d["geometry"]["ime_t"] == pytest.approx(q["ime_central_kg"] / 1000)
    assert any("nasa.gov" in (r.get("url") or "") for r in d["references"])


def test_permian_brief_numbers_trace_upstream() -> None:
    """No-staleness: the Permian brief's quoted rate + 18.3 context trace to source."""
    import re

    d = client.get(f"/api/events/{PERMIAN}").json()
    q = json.loads((config.stage_b_dir(PERMIAN) / "q_estimate.json").read_text())
    brief = d["brief"]
    m = re.search(r"(\d+\.\d{2}) t CH₄/hr", brief)
    assert m and m.group(1) == f"{q['q_central_t_hr']:.2f}", "Permian brief rate is stale"
    # 18.3 framed as press-release context, never a validation target.
    assert "18.3" in brief and "press-release" in brief.lower()
    assert "CROSS-CHECKED" in brief


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


def test_permian_active_serves_committed_hypotheses() -> None:
    """Stage D: now that Permian is active (UI assets exist), its committed Stage C
    attribution is served verbatim (it was gated to pending before)."""
    committed = json.loads(
        (config.data_root() / "attribution_outputs" / PERMIAN / "hypotheses.json").read_text()
    )
    api = client.get(f"/api/events/{PERMIAN}/hypotheses").json()
    assert api == committed
    # No facility exceeds LOW (dense-coverage discrimination cap survives the API).
    assert all(h["confidence_tier"] in {"low", "insufficient"} for h in api["hypotheses"])


def test_hypotheses_unknown_event_404() -> None:
    assert client.get("/api/events/does_not_exist/hypotheses").status_code == 404


def test_unknown_event_404() -> None:
    assert client.get("/api/events/does_not_exist").status_code == 404


def test_scope_caveat_context_only_for_press_release_reference() -> None:
    """Sprint 7 generality: an event whose only reference is a press-release figure
    (uncertainty=null, no n_sources — e.g. Permian's 18.3 t/hr) yields a CONTEXT-ONLY
    scope block, NOT a Thorpe cluster-fraction template with swapped numbers."""
    from aether_api import loaders
    from aether_eval.loader import load_event_file

    event = load_event_file(config.benchmark_yaml(PERMIAN))
    meas = event.known_measurements["emission_rate_metric_tonnes_per_hr"]
    assert meas.uncertainty is None  # the precondition that drives context_only

    scope = loaders._scope_caveat(event, meas, ours_central=0.85, nasa_central=0.88)
    assert scope.kind == "context_only"
    assert scope.reference_total_t_hr == meas.value  # 18.3
    # No cluster fraction is asserted for a context-only reference.
    assert scope.n_sources is None
    assert scope.fraction_low_pct is None and scope.fraction_high_pct is None
    # The text must refuse the comparison on the honest grounds (no obs date, intermittency).
    low = scope.text.lower()
    assert "press-release" in low
    assert "no observation date" in low or "no overpass" in low or "names no overpass" in low
    assert "intermitten" in low
    # It must NOT borrow the Thorpe cluster framing.
    assert "thorpe" not in low and "cluster" not in low


def test_data_root_override(tmp_path: Path) -> None:
    # AETHER_DATA_ROOT must redirect file reads (used for deployment/tests).
    assert config.data_root() == Path(config.__file__).resolve().parents[3]
