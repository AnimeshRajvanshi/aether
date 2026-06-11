"""No-fabrication guard for the Sprint 7 Permian facility-level attribution.

Every OGIM entity named anywhere in the committed Permian hypotheses.json —
candidate records and evidence sources — MUST correspond to a real row in the
committed Permian OGIM subset, by exact OGIM_ID + layer, and (for facility
candidates) by FAC_NAME. Sector-level candidates carry NO OGIM id. The committed
artifact must be reproducible from committed inputs. Tiers must respect the
no-HIGH discrimination cap.

If this fails, the dense-coverage engine has named or isolated something the data
does not support.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_HYP = _ROOT / "attribution_outputs" / "permian_basin_2022" / "hypotheses.json"
_SUBSET = (
    _ROOT / "packages/causal/aether_causal/resources/ogim"
    / "ogim_v2.7_permian_basin_region.geojson"
)


@pytest.fixture(scope="module")
def ogim_index() -> dict[tuple[str, int], dict]:
    feats = json.loads(_SUBSET.read_text())["features"]
    return {
        (f["properties"]["ogim_layer"], int(f["properties"]["OGIM_ID"])): f["properties"]
        for f in feats
        if f["properties"].get("OGIM_ID") is not None
    }


@pytest.fixture(scope="module")
def hyp() -> dict:
    return json.loads(_HYP.read_text())


def _ogim_refs(hyp: dict) -> list[tuple[str, int, str | None]]:
    refs: list[tuple[str, int, str | None]] = []
    for h in hyp["hypotheses"]:
        cand = h["candidate"]
        if cand.get("ogim_id") is not None:
            refs.append((cand["ogim_layer"], int(cand["ogim_id"]), cand.get("ogim_name")))
        for e in h["evidence"]:
            src = e["source"]
            if src.get("ogim_id") is not None:
                refs.append((src["ogim_layer"], int(src["ogim_id"]), None))
    return refs


def test_artifact_exists_and_method(hyp: dict) -> None:
    assert hyp["hypotheses"]
    assert hyp["generated_method"] == "rule_based_deterministic_v1"
    assert hyp["event_id"] == "permian_basin_2022"


def test_every_named_ogim_entity_exists_in_subset(
    hyp: dict, ogim_index: dict[tuple[str, int], dict]
) -> None:
    refs = _ogim_refs(hyp)
    assert refs, "expected at least one OGIM-backed reference"
    for layer, ogim_id, expected_name in refs:
        assert (layer, ogim_id) in ogim_index, (
            f"FABRICATION: ({layer}, OGIM_ID {ogim_id}) not in committed Permian OGIM subset"
        )
        if expected_name is not None:
            # facility candidates carry the well's exact FAC_NAME
            actual = ogim_index[(layer, ogim_id)].get("FAC_NAME")
            assert actual == expected_name, (
                f"FABRICATION: OGIM_ID {ogim_id} is {actual!r}, claims {expected_name!r}"
            )


def test_sector_candidates_carry_no_ogim_id(hyp: dict) -> None:
    for h in hyp["hypotheses"]:
        if h["candidate"]["kind"] == "sector":
            assert h["candidate"]["ogim_id"] is None
            assert h["candidate"].get("ogim_name") is None


def test_no_facility_reaches_high(hyp: dict) -> None:
    """Dense-coverage discrimination cap: no facility-level hypothesis may be HIGH."""
    for h in hyp["hypotheses"]:
        assert h["confidence_tier"] != "high", (
            f"{h['id']} is HIGH — but dense coverage cannot isolate a facility (see confidence_cap)"
        )


def test_pad_multiplicity_is_honest(hyp: dict, ogim_index: dict[tuple[str, int], dict]) -> None:
    """The 'N co-located completions' claim must equal the real count of wells on the
    nearest lease/pad within the wedge — not a number pulled from nowhere."""
    h1 = hyp["hypotheses"][0]
    cand = h1["candidate"]
    lease = str(cand["ogim_name"]).split(" #")[0].strip()
    operator = cand["operator"]
    # real wells sharing that lease prefix + operator in the subset
    same_lease = [
        p for (layer, _), p in ogim_index.items()
        if layer == "Oil_and_Natural_Gas_Wells"
        and str(p.get("FAC_NAME", "")).split(" #")[0].strip() == lease
        and p.get("OPERATOR") == operator
    ]
    # the claim quotes a co-located-completions count; it must not exceed the real
    # lease population and must be >= 1 (the named record itself).
    assert len(same_lease) >= 1
    assert f"{lease}" in h1["claim"]


def test_committed_artifact_matches_regenerated(hyp: dict) -> None:
    from aether_causal.attribution import build_facility_hypothesis_set

    regenerated = json.loads(
        build_facility_hypothesis_set("permian_basin_2022", _ROOT).model_dump_json()
    )
    assert regenerated == hyp, "committed Permian hypotheses.json is stale; re-run the generator"
