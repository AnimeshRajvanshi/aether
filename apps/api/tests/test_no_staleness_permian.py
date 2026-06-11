"""No-staleness guards for the Sprint 7 Permian Stage B artifacts.

Every headline number written in the Permian prose (the science doc, the gate
report, and the generated q_estimate_report.md) must equal the value in the
committed upstream file it is derived from — so a literal that drifts from the
data fails, exactly as the Sprint 6 guards do for Goturdepe. No magic constants:
expected values are read from q_estimate.json / stage_a_report.json.
"""

from __future__ import annotations

import json

import pytest
from aether_api import config

PERMIAN = "permian_basin_2022"


@pytest.fixture(scope="module")
def q() -> dict:
    return json.loads((config.stage_b_dir(PERMIAN) / "q_estimate.json").read_text())


@pytest.fixture(scope="module")
def stage_a() -> dict:
    return json.loads((config.stage_a_dir(PERMIAN) / "stage_a_report.json").read_text())


def _doc(rel: str) -> str:
    return (config.data_root() / rel).read_text()


SCIENCE = "docs/science/sprint7_permian.md"
REPORT = "docs/reports/sprint7_stage_b_report.md"
RUN_MD = "stage_b_outputs/permian_basin_2022/q_estimate_report.md"


@pytest.mark.parametrize("rel", [SCIENCE, REPORT, RUN_MD])
def test_permian_headline_rates_trace_to_q(rel: str, q: dict) -> None:
    text = _doc(rel)
    q_ours = q["q_central_t_hr"]
    q_nasa = q["q_nasa_l2b_same_footprint_t_hr"]
    bias = q["enhancement_bias_factor"]
    # Q ours and the NASA cross-check are quoted at 2 dp + " t/hr".
    assert f"{q_ours:.2f} t/hr" in text, f"{rel}: stale/missing Q ours {q_ours:.2f}"
    assert f"{q_nasa:.2f} t/hr" in text, f"{rel}: stale/missing NASA cross-check {q_nasa:.2f}"
    # The ours/NASA amplitude ratio is quoted at 2 dp + the × sign.
    assert f"{bias:.2f}×" in text, f"{rel}: stale/missing amplitude ratio {bias:.2f}×"


@pytest.mark.parametrize("rel", [SCIENCE, REPORT])
def test_permian_pearson_traces_to_stage_a(rel: str, stage_a: dict) -> None:
    text = _doc(rel)
    assert f"{stage_a['pearson_full_scene']:.3f}" in text, f"{rel}: stale full-scene Pearson"
    assert f"{stage_a['pearson_in_bbox']:.3f}" in text, f"{rel}: stale bbox Pearson"


@pytest.mark.parametrize("rel", [SCIENCE, REPORT])
def test_permian_18p3_is_context_not_target(rel: str) -> None:
    text = _doc(rel)
    low = text.lower()
    assert "18.3" in text
    assert "context" in low
    # The +1.46x transfer test must be stated as NOT transferring (no stale "carry it").
    assert "does not transfer" in low or "does NOT transfer" in text


def test_permian_self_seg_finding_recorded(q: dict) -> None:
    """The self-segmentation generality finding must be present and honest."""
    assert q["self_segmentation_isolated_plume"] is False
    assert q["self_segmentation_nasa_mean_ppm_m"] < 0  # NASA-negative over the confuser CC
    for rel in (SCIENCE, REPORT):
        assert "self-segmentation" in _doc(rel).lower()
