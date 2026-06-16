"""Guard for the Sprint 11 source-of-truth snippet (docs/key_results.json).

The portfolio deliverables (README, validation write-up, arkaneworks case study) all quote
figures from this one committed snippet. This guard is its staleness defense: it re-runs the
extraction over the committed artifacts and asserts the committed snippet still matches —
so if an artifact moves and the snippet is not regenerated, the suite fails red instead of a
deliverable quoting a stale number. It also pins the gate invariants (F3 dual flux, F4 the
two literals) and the tier ceilings (methane never VALIDATED; heat C1/C2 VALIDATED, C3/C4 not).
"""

from __future__ import annotations

import json
from pathlib import Path

import build_key_results as bkr

REPO_ROOT = Path(__file__).resolve().parents[2]
INDIA = "india_nw_heatwave_2022_04"


def _committed() -> dict:
    return json.loads((REPO_ROOT / "docs" / "key_results.json").read_text())


def test_snippet_matches_artifacts() -> None:
    """The committed snippet equals a fresh extraction (everything but the volatile SHA)."""
    fresh = bkr.build(REPO_ROOT)
    committed = _committed()
    fresh.pop("as_of_sha", None)
    committed.pop("as_of_sha", None)
    assert committed == fresh, (
        "docs/key_results.json is stale vs its artifacts — run `uv run python "
        "tools/build_key_results.py` and commit the result."
    )


def test_f3_both_flux_calibrations_present() -> None:
    """F3: both the ours-cal AND the NASA-anchored Goturdepe flux ride the snippet."""
    got = _committed()["methane"]["goturdepe"]
    assert got["flux_ours_cal_t_hr"]["display"] == "23.4 t/hr"
    assert got["flux_nasa_anchored_t_hr"]["display"] == "16.0 t/hr"


def test_f4_pinned_literals() -> None:
    """F4: the Permian plume-scale pixel r (0.137 to 3 dp) and the Duren DOI are pinned."""
    perm = _committed()["methane"]["permian"]
    pixel = perm["pixel_pearson_on_footprint"]
    assert round(pixel["value"], 3) == 0.137
    assert "0.137" in pixel["display"]
    dois = {c.get("doi") for c in _committed()["citations"]}
    assert "10.1038/s41586-019-1720-3" in dois  # Duren 2019
    assert "10.1126/sciadv.adh2391" in dois  # Thorpe 2023


def test_methane_never_validated() -> None:
    """Cardinal rule 3: the flux is CROSS-CHECKED, never VALIDATED."""
    methane = _committed()["methane"]
    assert methane["goturdepe"]["tier"].startswith("CROSS-CHECKED")
    assert methane["permian"]["tier"].startswith("CROSS-CHECKED")
    for ev in methane.values():
        assert "VALIDATED" not in ev["tier"].replace("CROSS-CHECKED", "")


def test_heat_per_quantity_tiers() -> None:
    """C1/C2 VALIDATED (pre-registered); C3/C4 ship as honest negatives."""
    heat = _committed()["heat"][INDIA]
    assert heat["c1_peak_2m_tmax"]["tier"] == "VALIDATED"
    assert heat["c2_regional_anomaly"]["tier"] == "VALIDATED"
    assert "NOT VALIDATED" in heat["c3_duration_FAILED"]["tier"]
    assert "NOT VALIDATED" in heat["c4_extent_FAILED"]["tier"]
    # the pre-registered pass flags must be honest: C1/C2 pass, C3/C4 fail
    assert heat["c1_peak_2m_tmax"]["criterion"]["value"] is True
    assert heat["c4_extent_FAILED"]["criterion"]["value"] is False


def test_negative_uhi_is_present() -> None:
    """The negative daytime UHI (counter-evidence) survives into the snippet."""
    uhi = _committed()["heat"][INDIA]["uhi_window_mean_NEGATIVE"]["value"]
    assert uhi["value"] < 0
    assert "NEGATIVE" in uhi["display"]
