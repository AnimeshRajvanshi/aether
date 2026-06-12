"""Tier-rubric guard (Sprint 7 Stage D review).

A served validation tier must trace to the rubric in docs/science/validation_tiers.md:
  - VALIDATED is the RESERVED top tier (independent flux truth) and is held by NO
    event — so no active event may be served as VALIDATED while that criterion is unmet.
  - Every active event's tier is one of the rubric's tiers.
  - A CROSS-CHECKED event must actually have a NASA-L2B cross-check (reference_product
    + a real Pearson), and its explainer must state the no-independent-flux limit.
"""

from __future__ import annotations

from aether_api import config
from aether_api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
RUBRIC_TIERS = {"VALIDATED", "CROSS-CHECKED", "DEMONSTRATION"}
# Heat extension (rubric doc): area events carry PER-QUANTITY at event level,
# with each quantity's tier in EventDetail.heat.quantity_tiers (guards below).
EVENT_LEVEL_TIERS = RUBRIC_TIERS | {"PER-QUANTITY"}


def _active_details() -> list[dict]:
    out = []
    for e in client.get("/api/events").json():
        if e["status"] == "active":
            out.append(client.get(f"/api/events/{e['event_id']}").json())
    return out


def test_rubric_doc_reserves_validated() -> None:
    doc = (config.data_root() / "docs/science/validation_tiers.md").read_text()
    assert "RESERVED" in doc.upper()
    # VALIDATED is described as held by no event / requiring independent flux truth.
    assert "no event" in doc.lower() or "no current event" in doc.lower()
    assert "flux truth" in doc.lower()


def test_no_active_event_is_validated() -> None:
    """No event meets the reserved VALIDATED criterion (independent flux truth)."""
    for d in _active_details():
        assert d["validation_tier"] != "VALIDATED", (
            f"{d['event_id']} served as VALIDATED, but the rubric reserves that tier for "
            f"independent flux truth, which no event has"
        )


def test_every_tier_is_in_the_rubric() -> None:
    for d in _active_details():
        assert d["validation_tier"] in EVENT_LEVEL_TIERS
        if d["phenomenon_type"] == "emission_event":
            assert d["validation_tier"] in RUBRIC_TIERS  # flux rubric unchanged


def test_cross_checked_traces_to_a_real_reference() -> None:
    """A CROSS-CHECKED claim must rest on a real NASA-L2B cross-check + the honest
    no-independent-flux limit (the rubric criterion)."""
    for d in _active_details():
        if d["validation_tier"] != "CROSS-CHECKED":
            continue
        assert d["validation"]["reference_product"] == "NASA L2B CH4ENH"
        assert isinstance(d["validation"]["pearson_in_bbox"], (int, float))
        explainer = d["tier_explainer"].lower()
        assert "cross-checked" in explainer
        assert "no independent flux" in explainer or "no per-source" in explainer


# ---- heat-vertical extension (Sprint 9 Stage D): PER-QUANTITY tiers ---------


def _heat_details() -> list[dict]:
    return [d for d in _active_details() if d["phenomenon_type"] == "heat_wave"]


def test_heat_events_carry_per_quantity_badge() -> None:
    """Area events must NOT carry an event-level VALIDATED (it would overstate
    C3/C4); the rubric's heat extension assigns PER-QUANTITY at event level."""
    for d in _heat_details():
        assert d["validation_tier"] == "PER-QUANTITY"
        assert "per quantity" in d["tier_explainer"].lower()


def test_heat_validated_rows_trace_to_committed_pass_flags() -> None:
    """VALIDATED may appear ONLY on quantity rows whose pre-registered checks
    passed in the committed validation.json — never asserted at render time."""
    import json as _json

    for d in _heat_details():
        val = _json.loads(
            (
                config.data_root() / "stage_b_outputs" / d["event_id"] / "validation.json"
            ).read_text()
        )
        passes = {
            "C1": val["v1_station_peak_bracket"]["pass_v1"],
            "C2": val["v3_imd_anomaly_agreement"]["pass_v3a"]
            and val["v3_imd_anomaly_agreement"]["pass_v3b"],
            "C3": val["v4_duration_extent"]["pass_v4a"],
            "C4": val["v4_duration_extent"]["pass_v4b"],
        }
        for row in d["heat"]["quantity_tiers"]:
            if row["tier"] == "VALIDATED":
                assert passes.get(row["quantity"]) is True, (
                    f"{row['quantity']} served VALIDATED without a committed pass flag"
                )
            if row["quantity"] in passes and not passes[row["quantity"]]:
                assert row["tier"] != "VALIDATED"
            if row["lane"] == "LST":
                assert "CROSS-CHECKED" in row["tier"]  # the LST ceiling


def test_heat_duration_extent_carry_criterion_and_dataset() -> None:
    """Stage B gate rendering rule: duration/extent never render without their
    criterion and source dataset attached."""
    for d in _heat_details():
        rows = {r["quantity"]: r for r in d["heat"]["quantity_tiers"]}
        for q in ("C3", "C4"):
            assert rows[q]["criterion_dataset"], f"{q} rendered without criterion+dataset"
            assert "ERA5" in rows[q]["value_display"] and "IMD" in rows[q]["value_display"]


def test_methane_rubric_unchanged_by_heat() -> None:
    """The flux rubric still holds for emission events: no VALIDATED, tiers in set."""
    for d in _active_details():
        if d["phenomenon_type"] == "emission_event":
            assert d["validation_tier"] in RUBRIC_TIERS
            assert d["validation_tier"] != "VALIDATED"
