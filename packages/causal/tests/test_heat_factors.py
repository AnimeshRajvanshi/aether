"""Guards for the factor-attribution engine (Sprint 9 Stage C, ADR 0005).

The three gate rules are negative-tested:
1. no-fabrication-for-factors (a factor without diagnostics cannot exist),
2. urban fabric argued from this event's evidence (counter-evidence role),
3. attribution boundary (published attribution cited only, never scored).
Plus the regen guard: the committed factor_hypotheses.json re-derives
byte-identically from the committed diagnostics.json (pure builder).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from aether_causal.heat_factors import (
    DISCRIMINATION_RESOLUTION,
    FACTOR_CEILING,
    build_factor_hypothesis_set,
    render_factors_markdown,
)
from aether_causal.schema import (
    ConfidenceTier,
    Diagnostic,
    FactorHypothesis,
    FactorRole,
    ScoreComponent,
)
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
EVENT = "india_nw_heatwave_2022_04"


def synthetic_diagnostics() -> dict[str, Any]:
    """A complete, plausible diagnostics dict (no cache/network needed)."""
    return {
        "event_id": EVENT,
        "clim_years": [1991, 2020],
        "z500": {
            "window_mean_2022_m": 5870.0,
            "cross_store_offset_m": -2.0,
            "cross_store_offset_per_year_m": [-1.5, -2.5],
            "window_mean_2022_corrected_m": 5872.0,
            "anomaly_uncorrected_m": 60.0,
            "clim_window_mean_m": 5810.0,
            "clim_window_std_m": 20.0,
            "anomaly_m": 62.0,
            "percentile_vs_30_window_means": 1.0,
            "days_above_pooled_p90": 9,
            "n_window_days": 10,
            "pooled_day_percentile_of_window_mean": 0.99,
            "grids": "synthetic",
        },
        "soil_moisture": {
            "antecedent_march_2022_m3m3": 0.18,
            "antecedent_clim_mean_m3m3": 0.24,
            "antecedent_percentile": 0.03,
            "window_2022_m3m3": 0.15,
            "window_clim_mean_m3m3": 0.21,
            "window_percentile": 0.07,
            "layer": "synthetic",
        },
        "winds": {
            "window_mean_u_ms": 1.2,
            "window_mean_v_ms": -0.8,
            "window_mean_speed_ms": 1.44,
            "window_from_direction_deg": 304.0,
            "clim_mean_u_ms": 0.5,
            "clim_mean_v_ms": -0.2,
            "clim_from_direction_deg": 292.0,
            "anomaly_vector_ms": [0.7, -0.6],
            "anomaly_magnitude_ms": 0.92,
            "convention": "synthetic",
        },
        "dewpoint": {
            "window_mean_2022_k": 281.0,
            "clim_mean_k": 284.5,
            "anomaly_k": -3.5,
            "percentile": 0.05,
            "scope": "synthetic",
        },
        "uhi": {
            "window_mean_uhi_k": -0.77,
            "window_std_uhi_k": 0.8,
            "n_valid_days": 10,
            "sensitivity_range_k": [-1.05, -0.74],
            "observed_time": "Terra ~10:30 local snapshot",
            "source_artifact": f"stage_b_outputs/{EVENT}/uhi.json",
        },
        "provenance": {
            "era5_v3": "synthetic-store",
            "era5_coarse": "synthetic-coarse",
            "uhi_artifact": f"stage_b_outputs/{EVENT}/uhi.json",
            "fetch_script": "scripts/sprint9_fetch_factors.py",
            "sample_hour_utc": "06",
        },
    }


class TestNoFabricationForFactors:
    """Rule 1 — the centerpiece guard, negative-tested at the schema level."""

    def test_factor_without_diagnostics_rejected(self) -> None:
        with pytest.raises(ValidationError, match="diagnostics"):
            FactorHypothesis(
                id="FX",
                rank=1,
                factor_name="Fabricated factor",
                role=FactorRole.WARMING_CONTRIBUTOR,
                claim="asserted with no computed diagnostic behind it",
                confidence_tier=ConfidenceTier.LOW,
                confidence_rationale="n/a",
                score=0.5,
                score_components=[
                    ScoreComponent(name="x", value=0.5, weight=1.0, rationale="n/a")
                ],
                diagnostics=[],  # <- the violation
                evidence=[],
                assumptions=[],
                counter_considerations=[],
                falsification="n/a",
                generation_method="test",
            )

    def test_every_built_factor_carries_diagnostics(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        for f in hs.factors:
            assert len(f.diagnostics) >= 1, f"{f.id} has no diagnostics"
            for d in f.diagnostics:
                assert isinstance(d, Diagnostic)
                assert d.source.locator  # every diagnostic names its source


class TestUrbanFabricCounterEvidence:
    """Rule 2 — the engine argues AGAINST the popular prior because the data does."""

    def test_urban_factor_is_counter_evidence(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        urban = [f for f in hs.factors if "rban" in f.factor_name]
        assert len(urban) == 1
        f5 = urban[0]
        assert f5.role is FactorRole.COUNTER_EVIDENCE
        assert "NEGATIVE" in f5.claim
        assert "UNASSESSED" in f5.claim  # nighttime/air role explicitly open
        assert f5.score == 0.0
        assert f5.diagnostics[0].value < 0  # bound to the measured negative signal

    def test_no_warming_contributor_is_urban(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        for f in hs.factors:
            if f.role is FactorRole.WARMING_CONTRIBUTOR:
                assert "rban" not in f.factor_name

    def test_positive_uhi_would_be_a_different_artifact(self) -> None:
        """The claim text is templated from the diagnostic — a positive UHI must
        not silently produce the same 'negative' language."""
        diag = synthetic_diagnostics()
        diag["uhi"]["window_mean_uhi_k"] = +1.5
        hs = build_factor_hypothesis_set(EVENT, diag)
        f5 = next(f for f in hs.factors if "rban" in f.factor_name)
        assert "+1.50 K" in f5.claim  # the number flows from the diagnostic
        # NOTE: role re-evaluation for a positive signal is a deliberate future
        # decision (a positive measured UHI would need new gate review), but the
        # claim can never contradict the bound diagnostic value.


class TestAttributionBoundary:
    """Rule 3 — published attribution is cited evidence, never our claim/score."""

    def test_external_block_present_with_doi(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        assert len(hs.external_published_attribution) == 1
        ext = hs.external_published_attribution[0]
        assert "10.1088/2752-5295/acf4b6" in ext.source.dataset
        assert "CITED EXTERNAL RESULT" in ext.statement

    def test_attribution_never_in_factor_scores_or_claims(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        factor_text = json.dumps([f.model_dump(mode="json") for f in hs.factors])
        for marker in ("Zachariah", "30 times", "WWA", "preindustrial"):
            assert marker not in factor_text, (
                f"published attribution marker {marker!r} leaked into factor content"
            )
        assert "does NOT perform probabilistic" in hs.attribution_boundary

    def test_boundary_statement_in_markdown(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        md = render_factors_markdown(hs)
        assert "Attribution boundary." in md
        assert "cited, never scored" in md


class TestMachineryPorted:
    def test_deterministic(self) -> None:
        a = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        b = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        assert a.model_dump_json() == b.model_dump_json()

    def test_ceiling_enforced(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        order = [ConfidenceTier.HIGH, ConfidenceTier.MODERATE,
                 ConfidenceTier.LOW, ConfidenceTier.INSUFFICIENT]
        for f in hs.factors:
            if f.role is FactorRole.WARMING_CONTRIBUTOR:
                assert order.index(f.confidence_tier) >= order.index(FACTOR_CEILING)

    def test_non_discrimination_headline_when_gap_small(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        contributors = sorted(
            (f for f in hs.factors if f.role is FactorRole.WARMING_CONTRIBUTOR),
            key=lambda f: -f.score,
        )
        gap = abs(contributors[0].score - contributors[1].score)
        if gap < DISCRIMINATION_RESOLUTION:
            assert "CANNOT BE DISCRIMINATED" in hs.headline_finding
        else:
            assert "ranking, not an established apportionment" in hs.headline_finding

    def test_every_factor_has_honesty_fields(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        for f in hs.factors:
            assert f.assumptions and f.counter_considerations and f.falsification
        assert hs.scoring_disclaimer and hs.confidence_cap


class TestCommittedArtifactsRegen:
    """The committed factor set re-derives byte-identically from committed
    diagnostics (pure builder; offline)."""

    @pytest.fixture(scope="class")
    def out_dir(self) -> Path:
        d = REPO_ROOT / "attribution_outputs" / EVENT
        if not (d / "factor_hypotheses.json").exists():
            pytest.skip("Stage C artifacts not yet committed")
        return d

    def test_json_regenerates_byte_identically(self, out_dir: Path) -> None:
        diag = json.loads((out_dir / "diagnostics.json").read_text())
        hs = build_factor_hypothesis_set(EVENT, diag)
        assert hs.model_dump_json(indent=2) == (
            out_dir / "factor_hypotheses.json"
        ).read_text()

    def test_markdown_regenerates_byte_identically(self, out_dir: Path) -> None:
        diag = json.loads((out_dir / "diagnostics.json").read_text())
        hs = build_factor_hypothesis_set(EVENT, diag)
        assert render_factors_markdown(hs) == (out_dir / "factor_hypotheses.md").read_text()

    def test_committed_set_respects_all_gate_rules(self, out_dir: Path) -> None:
        committed = json.loads((out_dir / "factor_hypotheses.json").read_text())
        factor_text = json.dumps(committed["factors"])
        assert "Zachariah" not in factor_text
        urban = [f for f in committed["factors"] if "rban" in f["factor_name"]]
        assert urban and urban[0]["role"] == "counter_evidence"
        assert all(len(f["diagnostics"]) >= 1 for f in committed["factors"])


# Reconciles every level/baseline/anomaly triple rendered in a factor claim
# against simple arithmetic (Stage C review ruling 1). Tolerance covers the
# independent rounding of the three numbers.
TRIPLE_RE = (
    r"([\d.]+) m \(cross-store-corrected from [\d.]+ m\) "
    r"vs climatology ([\d.]+) m \(\+([\d.]+) m"
)
TRIPLE_TOL_M = 0.15


def reconcile_claim_triples(claim: str) -> list[tuple[float, float, float]]:
    """All (level, baseline, anomaly) triples in a claim that fail arithmetic."""
    import re

    bad = []
    for m in re.finditer(TRIPLE_RE, claim):
        level, baseline, anomaly = (float(g) for g in m.groups())
        if abs((level - baseline) - anomaly) > TRIPLE_TOL_M:
            bad.append((level, baseline, anomaly))
    return bad


class TestNumericReconciliation:
    """Stage C review ruling 1: rendered triples must close arithmetically."""

    def test_built_claims_reconcile(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        import re

        n_triples = 0
        for f in hs.factors:
            assert reconcile_claim_triples(f.claim) == [], f"{f.id} triple mismatch"
            n_triples += len(re.findall(TRIPLE_RE, f.claim))
        assert n_triples >= 1  # the guard must not pass vacuously (F1 has one)

    def test_committed_claims_reconcile(self) -> None:
        path = REPO_ROOT / "attribution_outputs" / EVENT / "factor_hypotheses.json"
        if not path.exists():
            pytest.skip("Stage C artifacts not yet committed")
        committed = json.loads(path.read_text())
        for f in committed["factors"]:
            assert reconcile_claim_triples(f["claim"]) == [], f"{f['id']} triple mismatch"

    def test_negative_mismatched_triple_caught(self) -> None:
        doctored = (
            "height 5871.4 m (cross-store-corrected from 5871.4 m) vs climatology "
            "5814.2 m (+61.6 m, ...)"  # 5871.4-5814.2 = 57.2 != 61.6
        )
        assert reconcile_claim_triples(doctored) == [(5871.4, 5814.2, 61.6)]

    def test_diagnostics_level_arithmetic_closes(self) -> None:
        path = REPO_ROOT / "attribution_outputs" / EVENT / "diagnostics.json"
        if not path.exists():
            pytest.skip("Stage C artifacts not yet committed")
        z = json.loads(path.read_text())["z500"]
        assert abs(
            (z["window_mean_2022_corrected_m"] - z["clim_window_mean_m"]) - z["anomaly_m"]
        ) <= TRIPLE_TOL_M


class TestFalsificationDirection:
    """Stage C review ruling 2: falsification targets the COMMITTED position
    (branch-generated), never the rejected prior."""

    def test_unsupported_precondition_branch(self) -> None:
        # synthetic fixture variant: NEAR-NORMAL antecedent (the committed event case)
        diag = synthetic_diagnostics()
        diag["soil_moisture"]["antecedent_percentile"] = 0.433  # dryness rank 57%
        hs = build_factor_hypothesis_set(EVENT, diag)
        f2 = next(f for f in hs.factors if f.id == "F2")
        assert "NOT supported" in f2.claim
        assert "anomalously DRY" in f2.falsification  # dry obs would OVERTURN
        assert "normal antecedent" not in f2.falsification

    def test_supported_precondition_branch(self) -> None:
        diag = synthetic_diagnostics()  # antecedent_percentile 0.03 -> dryness 97%
        hs = build_factor_hypothesis_set(EVENT, diag)
        f2 = next(f for f in hs.factors if f.id == "F2")
        assert "anomalously pre-dried" in f2.claim
        assert "normal-or-wetter" in f2.falsification  # wet obs would overturn

    def test_advection_branches(self) -> None:
        # climatological-flow branch (the committed event case)
        diag = synthetic_diagnostics()
        diag["winds"]["anomaly_magnitude_ms"] = 0.39
        diag["winds"]["window_mean_speed_ms"] = 1.41
        hs = build_factor_hypothesis_set(EVENT, diag)
        f3 = next(f for f in hs.factors if f.id == "F3")
        assert "no-anomalous-advection" in f3.falsification
        # anomalous-flow branch
        diag["winds"]["anomaly_magnitude_ms"] = 1.2
        hs2 = build_factor_hypothesis_set(EVENT, diag)
        f3b = next(f for f in hs2.factors if f.id == "F3")
        assert "outside the arid sector" in f3b.falsification

    def test_humidity_branches(self) -> None:
        diag = synthetic_diagnostics()
        diag["dewpoint"]["percentile"] = 0.533  # neutral (committed event case)
        hs = build_factor_hypothesis_set(EVENT, diag)
        f4 = next(f for f in hs.factors if f.id == "F4")
        assert "not-active finding" in f4.falsification
        diag["dewpoint"]["percentile"] = 0.05  # anomalously dry
        hs2 = build_factor_hypothesis_set(EVENT, diag)
        f4b = next(f for f in hs2.factors if f.id == "F4")
        assert "contradicting the" in f4b.falsification

    def test_urban_overturn_vs_establish_distinct(self) -> None:
        hs = build_factor_hypothesis_set(EVENT, synthetic_diagnostics())
        f5 = next(f for f in hs.factors if f.id == "F5")
        assert "OVERTURNED" in f5.falsification  # the committed daytime finding
        assert "ESTABLISHED" in f5.falsification  # the explicitly-open roles
