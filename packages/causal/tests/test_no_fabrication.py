"""No-fabrication guard (the cardinal-rule test).

Every OGIM entity named anywhere in the committed hypotheses.json — candidate
records and evidence sources — MUST correspond to a real row in the committed
OGIM subset, by exact OGIM_ID, layer, and (for fields) NAME. Sector-level
candidates must carry NO OGIM id (they are honest non-records, not inventions).

If this test fails, the engine has named something the data does not contain.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_HYP = _ROOT / "attribution_outputs" / "turkmenistan_goturdepe_2022_08_15" / "hypotheses.json"
_SUBSET = _ROOT / "packages/causal/aether_causal/resources/ogim/ogim_v2.7_goturdepe_region.geojson"


@pytest.fixture(scope="module")
def ogim_index() -> dict[tuple[str, int], dict]:
    """(layer, OGIM_ID) -> properties, for every real record in the subset."""
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
    """Collect (layer, ogim_id, expected_name|None) from candidates + evidence sources."""
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


def test_hypotheses_artifact_exists(hyp: dict) -> None:
    assert hyp["hypotheses"]
    assert hyp["generated_method"] == "rule_based_deterministic_v1"


def test_every_named_ogim_entity_exists_in_subset(
    hyp: dict, ogim_index: dict[tuple[str, int], dict]
) -> None:
    refs = _ogim_refs(hyp)
    assert refs, "expected at least one OGIM-backed reference"
    for layer, ogim_id, expected_name in refs:
        assert (layer, ogim_id) in ogim_index, (
            f"FABRICATION: ({layer}, OGIM_ID {ogim_id}) not in committed OGIM subset"
        )
        if expected_name is not None:
            actual = ogim_index[(layer, ogim_id)].get("NAME")
            assert actual == expected_name, (
                f"FABRICATION: OGIM_ID {ogim_id} is named {actual!r}, hypothesis claims "
                f"{expected_name!r}"
            )


def test_sector_candidates_carry_no_ogim_id(hyp: dict) -> None:
    for h in hyp["hypotheses"]:
        if h["candidate"]["kind"] == "sector":
            assert h["candidate"]["ogim_id"] is None
            assert h["candidate"].get("ogim_name") is None


def test_only_barsagelmez_and_goturdepe_named_as_fields(
    hyp: dict, ogim_index: dict[tuple[str, int], dict]
) -> None:
    named_fields = {
        h["candidate"]["ogim_name"]
        for h in hyp["hypotheses"]
        if h["candidate"].get("ogim_layer") == "Oil_and_Natural_Gas_Fields"
    }
    assert named_fields == {"BARSAGELMEZ", "GOTURDEPE"}
    # and both are real records in the subset
    real_field_names = {
        p.get("NAME")
        for (layer, _), p in ogim_index.items()
        if layer == "Oil_and_Natural_Gas_Fields"
    }
    assert named_fields <= real_field_names


def test_committed_artifact_matches_regenerated(hyp: dict) -> None:
    """The committed hypotheses.json is reproducible from committed inputs."""
    from aether_causal.attribution import build_hypothesis_set

    regenerated = json.loads(build_hypothesis_set(_ROOT).model_dump_json())
    assert regenerated == hyp, "committed hypotheses.json is stale; re-run the generator"
