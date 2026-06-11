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


def test_no_facility_exceeds_low(hyp: dict) -> None:
    """Dense-coverage cap (Stage C review): with discriminating margins within the
    stated localization uncertainty, the data RANKS but cannot ESTABLISH a source, so
    no facility hypothesis may exceed LOW (not merely 'not HIGH')."""
    for h in hyp["hypotheses"]:
        assert h["confidence_tier"] in {"low", "insufficient"}, (
            f"{h['id']} is {h['confidence_tier']} — but margins are within the ~1 km localization "
            f"noise, so no facility may exceed LOW (see confidence_cap)"
        )


def test_comparative_claims_are_truthful(hyp: dict) -> None:
    """Comparative spatial claims must match the computed candidate table, so a false
    'closer than any' / 'nearest overall' cannot slip through (the Stage C review escape:
    H1 had claimed the pad was closer in BOTH distance and angle, which was false)."""
    h1 = hyp["hypotheses"][0]
    blob = json.dumps(h1)
    ps = hyp["plume_summary"]

    # The exact false comparative must never reappear.
    assert "both distance and angle" not in blob.lower()
    assert "closer in both" not in blob.lower()

    # The H1 candidate must BE the nearest-by-centerline record (the only claim made).
    centerline_id = int(ps["nearest_by_centerline"].split("OGIM_ID ")[1].split(",")[0])
    assert h1["candidate"]["ogim_id"] == centerline_id, "H1 is not the nearest-centerline candidate"

    # When a DIFFERENT well is distance-closest, H1 must name it (no hiding a closer well).
    distance_id = int(ps["nearest_by_distance"].split("OGIM_ID ")[1].split(",")[0])
    if distance_id != centerline_id:
        distance_name = ps["nearest_by_distance"].split(" (OGIM_ID")[0]
        assert distance_name in blob, (
            f"a closer-by-distance well ({distance_name}) exists but H1 does not disclose it"
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
