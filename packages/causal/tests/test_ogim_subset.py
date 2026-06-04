"""Integrity tests for the committed OGIM regional subset.

These pin the Stage A probe finding so it can't silently change: the subset is
real OGIM data, and the back-projected source sits inside the BARSAGELMEZ field
while facility-level point layers (wells/compressors/processing) are absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import shapely
from shapely.geometry import Point, shape

_RES = Path(__file__).resolve().parents[1] / "aether_causal" / "resources" / "ogim"
_SUBSET = _RES / "ogim_v2.7_goturdepe_region.geojson"

# Sprint 2 upwind source point S (wind_location_check.json), committed value.
_S = Point(53.98627293651168, 39.343310851273706)


def _load() -> dict:
    return json.loads(_SUBSET.read_text())


def test_subset_and_provenance_exist() -> None:
    assert _SUBSET.exists()
    prov = json.loads((_RES / "provenance.json").read_text())
    assert prov["doi"] == "10.5281/zenodo.15103476"
    assert prov["total_features_in_subset"] == len(_load()["features"])


def test_subset_is_real_ogim_no_facility_points() -> None:
    layers = {f["properties"]["ogim_layer"] for f in _load()["features"]}
    # Facility-level point layers are genuinely absent over this region in OGIM.
    for absent in (
        "Oil_and_Natural_Gas_Wells",
        "Natural_Gas_Compressor_Stations",
        "Gathering_and_Processing",
        "Tank_Battery",
    ):
        assert absent not in layers
    # What IS present: fields, flaring detections, pipelines.
    assert "Oil_and_Natural_Gas_Fields" in layers


def test_source_point_inside_barsagelmez_field() -> None:
    fields = {
        f["properties"].get("NAME"): shape(f["geometry"])
        for f in _load()["features"]
        if f["properties"]["ogim_layer"] == "Oil_and_Natural_Gas_Fields"
    }
    assert "BARSAGELMEZ" in fields
    assert fields["BARSAGELMEZ"].contains(_S)
    # Goturdepe is a separate polygon that does NOT contain S.
    assert not fields["GOTURDEPE"].contains(_S)


def test_every_feature_is_real_ogim_record() -> None:
    # No-fabrication: every feature carries a real OGIM_ID and a known source layer.
    for f in _load()["features"]:
        assert "OGIM_ID" in f["properties"]
        assert f["properties"]["ogim_layer"]
        assert shapely.geometry.shape(f["geometry"]).is_valid or not f["geometry"]
