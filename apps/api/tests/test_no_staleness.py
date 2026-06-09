"""No-staleness guard suite (Sprint 6 migration).

Every numeric claim embedded in a *derived artifact's prose* must equal the value
in the upstream committed file it is derived from. This is distinct from the
existing byte-match / regenerate==committed guards: those reproduce an artifact
from its generator, so a number HARDCODED in the generator (not read from the
data) would reproduce identically and slip through. Here we parse the rendered
text and check it against the real upstream source — so a literal that drifts
from the data (e.g. a stale "~27 t/hr" left over from the NASA-k run) fails.

Covered artifacts:
  - the committed hypotheses.{json}  (attribution prose: claims, evidence, summary)
  - the API-templated brief
  - the API scope-caveat percentages
  - the API quantification notes (the +bias x systematic)

Expected values are read from the committed files — no magic constants in the
assertions (except the parsing of how many decimals each surface renders).
"""

from __future__ import annotations

import json
import re

import pytest
import yaml
from aether_api import config
from aether_api.main import app
from fastapi.testclient import TestClient

GOTURDEPE = "turkmenistan_goturdepe_2022_08_15"
client = TestClient(app)


# --------------------------------------------------------------------------- #
# Upstream committed sources
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def q() -> dict:
    return json.loads((config.stage_b_dir(GOTURDEPE) / "q_estimate.json").read_text())


@pytest.fixture(scope="module")
def stage_a() -> dict:
    return json.loads((config.stage_a_dir(GOTURDEPE) / "stage_a_report.json").read_text())


@pytest.fixture(scope="module")
def wind() -> dict:
    return json.loads((config.stage_b_dir(GOTURDEPE) / "wind_location_check.json").read_text())


@pytest.fixture(scope="module")
def benchmark() -> dict:
    return yaml.safe_load(config.benchmark_yaml(GOTURDEPE).read_text())


@pytest.fixture(scope="module")
def hyp() -> dict:
    path = config.data_root() / "attribution_outputs" / GOTURDEPE / "hypotheses.json"
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def detail() -> dict:
    return client.get(f"/api/events/{GOTURDEPE}").json()


def _ref(benchmark: dict) -> tuple[float, float, int]:
    m = benchmark["known_measurements"]["emission_rate_metric_tonnes_per_hr"]
    return float(m["value"]), float(m["uncertainty"]), int(m["n_sources"])


# --------------------------------------------------------------------------- #
# 1. Attribution prose — every quoted rate traces to q_estimate.json
# --------------------------------------------------------------------------- #
def test_hypotheses_quoted_rate_matches_q(hyp: dict, q: dict) -> None:
    blob = json.dumps(hyp)
    q_central = q["q_central_t_hr"]

    # plume summary carries the rate at 3 dp.
    assert hyp["plume_summary"]["emission_rate_ours_cal_t_hr"] == f"{q_central:.3f}"

    # Every "~N t/hr" approximate rate in the prose must be round(Q) — this is the
    # token that was stale ("~27") before the migration. The reference cluster
    # total (163 t/hr) is written without a leading "~", so it is excluded.
    approx = {int(x) for x in re.findall(r"~(\d+)\s*t/hr", blob)}
    assert approx, "expected at least one '~N t/hr' rate in the attribution prose"
    assert approx == {round(q_central)}, (
        f"stale approximate rate(s) {approx}; q_central rounds to {round(q_central)}"
    )

    # Every "N.N t/hr" decimal rate must be round(Q, 1) (the OURS-CAL magnitude
    # statement). The cluster total/uncertainty are integers (163, 18), unmatched.
    decimals = {x for x in re.findall(r"(\d+\.\d+)\s*t/hr", blob)}
    assert decimals == {f"{q_central:.1f}"}, (
        f"decimal rate(s) {decimals} != round(q,1) {q_central:.1f}"
    )

    # The magnitude_range evidence locator pins the exact 3-dp value.
    for h in hyp["hypotheses"]:
        for e in h["evidence"]:
            if e["kind"] == "magnitude_range":
                assert e["source"]["locator"] == f"q_central_t_hr={q_central:.3f}"


def test_hypotheses_source_s_matches_wind_check(hyp: dict, wind: dict) -> None:
    expected = f"{wind['source_lat']:.5f} N, {wind['source_lon']:.5f} E"
    assert hyp["plume_summary"]["upwind_source_S"] == expected


def test_hypotheses_have_no_nasa_k_residue(hyp: dict, q: dict) -> None:
    """The pre-migration NASA-k rate (27) must not survive anywhere as a rate."""
    if round(q["q_central_t_hr"]) == 27:
        pytest.skip("q rounds to 27; this guard is vacuous for this retrieval")
    blob = json.dumps(hyp)
    assert "27 t/hr" not in blob and "27.1 t/hr" not in blob


# --------------------------------------------------------------------------- #
# 2. API brief — every number traces to its upstream file
# --------------------------------------------------------------------------- #
def test_brief_numbers_trace_upstream(
    detail: dict, q: dict, stage_a: dict, benchmark: dict
) -> None:
    brief = detail["brief"]
    ref_total, ref_unc, n_sources = _ref(benchmark)

    m = re.search(r"r = (\d\.\d+)", brief)
    assert m and m.group(1) == f"{stage_a['pearson_in_bbox']:.2f}"

    m = re.search(r"(\d+\.\d+) t integrated mass", brief)
    assert m and m.group(1) == f"{q['ime_central_kg'] / 1000:.1f}"

    m = re.search(r"(\d+\.\d+) km² mask", brief)
    assert m and m.group(1) == f"{q['plume_cc_area_km2']:.1f}"

    m = re.search(r"(\d+\.\d+) m/s wind", brief)
    assert m and m.group(1) == f"{q['era5_u10_speed_ms']:.1f}"

    m = re.search(r"≈(\d+) t CH₄/hr", brief)
    assert m and int(m.group(1)) == round(q["q_central_t_hr"])

    m = re.search(r"one of (\d+) Thorpe", brief)
    assert m and int(m.group(1)) == n_sources

    m = re.search(r"at (\d+) ± (\d+) t/hr", brief)
    assert m and int(m.group(1)) == ref_total and int(m.group(2)) == ref_unc

    # The provenance claim must be honest: the brief asserts HITRAN independence,
    # which is only true post-migration (target_spectrum_source names HITRAN).
    assert "HITRAN2020" in brief
    assert "HITRAN" in (stage_a["target_spectrum_source"] or "")
    assert stage_a.get("k_nasa_target_used") is False


# --------------------------------------------------------------------------- #
# 3. Scope-caveat percentages — computed from Q, not transcribed
# --------------------------------------------------------------------------- #
def test_scope_caveat_pct_computed_not_transcribed(detail: dict, q: dict, benchmark: dict) -> None:
    ref_total, ref_unc, n_sources = _ref(benchmark)
    scope = detail["scope_caveat"]

    frac_low = q["q_central_nasa_calibrated_t_hr"] / ref_total * 100.0
    frac_high = q["q_central_t_hr"] / ref_total * 100.0
    assert scope["fraction_low_pct"] == pytest.approx(frac_low)
    assert scope["fraction_high_pct"] == pytest.approx(frac_high)

    m = re.search(r"≈(\d+)[–-](\d+)% of it", scope["text"])
    assert m, f"scope fraction range not found in: {scope['text']!r}"
    assert int(m.group(1)) == round(frac_low)
    assert int(m.group(2)) == round(frac_high)

    # Cluster figures in the prose trace to the benchmark.
    assert f"{ref_total:g} ± {ref_unc:g} t/hr" in scope["text"]
    assert f"{n_sources}-source" in scope["text"]


# --------------------------------------------------------------------------- #
# 4. API quantification notes — the systematic bias matches q_estimate
# --------------------------------------------------------------------------- #
def test_quantification_notes_bias_matches_q(detail: dict, q: dict) -> None:
    bias = q["enhancement_bias_factor"]
    quant = detail["quantification"]

    assert quant["ours_cal"]["value_t_hr"] == pytest.approx(q["q_central_t_hr"])
    assert quant["nasa_cal"]["value_t_hr"] == pytest.approx(q["q_central_nasa_calibrated_t_hr"])

    # The +bias× appears, at 2 dp, in BOTH cal notes and the budget display.
    token = f"{bias:.2f}×"
    assert token in quant["ours_cal"]["note"]
    assert token in quant["nasa_cal"]["note"]
    budget = {t["key"]: t for t in detail["uncertainty_budget"]}
    assert budget["mf_amplitude"]["display"] == f"+{token}"
    assert budget["mf_amplitude"]["factor"] == bias  # full precision retained

    # No NASA-k residue: the old hand-carried 1.66× must not appear as the systematic.
    if round(bias, 2) != 1.66:
        assert "1.66×" not in quant["ours_cal"]["note"]
        assert "1.66×" not in quant["nasa_cal"]["note"]


# --------------------------------------------------------------------------- #
# 5. Dashboard mask label traces to the quantified CC
# --------------------------------------------------------------------------- #
def test_mask_geojson_cc_label_matches_q(q: dict) -> None:
    geo = json.loads((config.assets_dir(GOTURDEPE) / "mask.geojson").read_text())
    assert geo["properties"]["cc_label"] == q["plume_cc_label"]
