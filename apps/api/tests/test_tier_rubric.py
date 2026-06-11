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
        assert d["validation_tier"] in RUBRIC_TIERS


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
