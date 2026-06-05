"""Tests for the Stage B attribution engine: structure, scoring, honesty fields."""

from __future__ import annotations

import pytest
from aether_causal.attribution import build_hypothesis_set
from aether_causal.render import render_markdown
from aether_causal.schema import CandidateKind, ConfidenceTier, HypothesisSet


@pytest.fixture(scope="module")
def hs() -> HypothesisSet:
    return build_hypothesis_set()


def test_exactly_three_ranked_hypotheses(hs: HypothesisSet) -> None:
    assert [h.id for h in hs.hypotheses] == ["H1", "H2", "H3"]
    assert [h.rank for h in hs.hypotheses] == [1, 2, 3]


def test_score_components_sum_to_score(hs: HypothesisSet) -> None:
    for h in hs.hypotheses:
        assert sum(c.contribution for c in h.score_components) == pytest.approx(h.score, abs=1e-3)
        for c in h.score_components:
            assert c.contribution == pytest.approx(c.value * c.weight, abs=1e-4)


def test_confidence_cap_no_hypothesis_exceeds_moderate(hs: HypothesisSet) -> None:
    for h in hs.hypotheses:
        # MODERATE is the ceiling; HIGH must never appear.
        assert h.confidence_tier != ConfidenceTier.HIGH


def test_h1_is_capped_field_level_moderate(hs: HypothesisSet) -> None:
    h1 = hs.hypotheses[0]
    assert h1.candidate.kind == CandidateKind.OGIM_FIELD
    assert h1.candidate.ogim_name == "BARSAGELMEZ"
    assert h1.confidence_tier == ConfidenceTier.MODERATE
    assert h1.score >= 0.8  # raw score is high...
    assert "CAPPED" in h1.confidence_rationale  # ...but explicitly capped
    assert "facility" in h1.confidence_rationale.lower()


def test_h2_and_h3_are_low(hs: HypothesisSet) -> None:
    assert hs.hypotheses[1].confidence_tier == ConfidenceTier.LOW
    assert hs.hypotheses[2].confidence_tier == ConfidenceTier.LOW
    # H3 is a sector-level non-O&G hypothesis, stated not dropped.
    assert hs.hypotheses[2].candidate.kind == CandidateKind.SECTOR
    assert hs.hypotheses[2].candidate.ogim_id is None


def test_flaring_evidence_carries_temporal_caveat(hs: HypothesisSet) -> None:
    flare = [e for e in hs.hypotheses[0].evidence if e.kind == "flaring_corroboration"]
    assert len(flare) == 1
    caveat = flare[0].temporal_caveat
    assert caveat is not None
    # must say it is NOT about this plume / NOT the source, and is later in time
    assert "NOT evidence about this specific plume" in caveat
    assert "NOT the located source" in caveat
    assert "months AFTER" in caveat


def test_bearing_disagreement_surfaced(hs: HypothesisSet) -> None:
    joined = " ".join(hs.global_assumptions)
    assert "disagrees with the ERA5 upwind azimuth" in joined
    assert "~20 deg" in joined  # the centroid->S vs upwind azimuth gap


def test_half_angle_weakest_link_assumption(hs: HypothesisSet) -> None:
    joined = " ".join(hs.global_assumptions)
    assert "WEAKEST LINK" in joined
    assert "isotropic" in joined
    assert "NOT a measured wind-direction variance" in joined


def test_headline_and_cap_are_first_class(hs: HypothesisSet) -> None:
    assert "NO facility-level point infrastructure" in hs.headline_finding
    assert "Turkmenistan" in hs.headline_finding
    assert "field/sector" in hs.headline_finding.lower()
    assert "MODERATE" in hs.confidence_cap
    assert "heuristic" in hs.scoring_disclaimer.lower()
    assert "not calibrated" in hs.scoring_disclaimer.lower()


def test_every_hypothesis_has_assumptions_and_counters(hs: HypothesisSet) -> None:
    for h in hs.hypotheses:
        assert h.assumptions
        assert h.counter_considerations
        assert h.falsification
        assert h.generation_method == "rule_based_deterministic_v1"  # no LLM


def test_json_roundtrip_and_extra_forbidden(hs: HypothesisSet) -> None:
    dumped = hs.model_dump_json()
    again = HypothesisSet.model_validate_json(dumped)
    assert again.event_id == hs.event_id
    with pytest.raises(ValueError):
        HypothesisSet.model_validate({**hs.model_dump(), "bogus_field": 1})


def test_render_is_deterministic_and_mentions_key_honesty(hs: HypothesisSet) -> None:
    md1 = render_markdown(hs)
    md2 = render_markdown(build_hypothesis_set())
    assert md1 == md2  # deterministic
    assert "Headline finding" in md1
    assert "documented heuristic, not a probability" in md1
    assert "temporal caveat" in md1
