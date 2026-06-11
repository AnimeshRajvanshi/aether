"""Generalized comparative-claims guard — ALL events, not just the Permian H1 path.

Sprint 8 Item 4, closing the Stage C gap logged in docs/debt.md: a false
"nearest / closer-than" claim in hypothesis prose was only machine-caught for
the Permian H1 facility path. This guard parses PROXIMITY SUPERLATIVES
(nearest / closest / closer / farther / farthest) in every committed
``attribution_outputs/<event>/hypotheses.json`` and checks them against the
artifact's own computed candidate table (``plume_summary.nearest_by_*``):

1. Known-false phrasings from the Stage C review escape are banned everywhere.
2. A hypothesis that uses a proximity superlative must belong to an artifact
   whose plume_summary carries the machine-readable nearest-by-centerline and
   nearest-by-distance records — an UNVERIFIABLE proximity claim fails loudly.
3. A candidate described with a proximity superlative must actually BE the
   nearest record on at least one computed axis (centerline or distance).
4. If the candidate is nearest-by-centerline but a DIFFERENT well is
   distance-closest, that well's name must be disclosed in the hypothesis text
   (no hiding a closer well).

SCOPE (the honest limit of the cheap version): only spatial-proximity
superlatives are machine-checked. Other comparative classes — size/count
superlatives ("largest", "most active") and exclusivity claims ("the only…")
— remain HUMAN-GATE items: they would need entity linking against arbitrary
tables, which is not cheap. They stay flagged in the gate-review checklist.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_ATTRIBUTION_DIR = _ROOT / "attribution_outputs"

# The Stage C review escape, verbatim — must never reappear in any event.
_BANNED_PHRASES = ("closer in both", "both distance and angle")

_PROXIMITY = re.compile(r"\b(nearest|closest|closer|farther|farthest)\b", re.IGNORECASE)


def _all_hypothesis_files() -> list[Path]:
    return sorted(_ATTRIBUTION_DIR.glob("*/hypotheses.json"))


def _parse_table_id(entry: str) -> int:
    """Extract the OGIM_ID from a plume_summary nearest_by_* string."""
    return int(entry.split("OGIM_ID ")[1].split(",")[0].rstrip(")"))


def _hypothesis_text(h: dict) -> str:
    """The prose a reader sees: claim + rationale + candidate descriptor."""
    cand = h.get("candidate") or {}
    return " ".join(
        str(x) for x in (h.get("claim"), h.get("rationale"), cand.get("descriptor")) if x
    )


def test_attribution_artifacts_exist() -> None:
    assert _all_hypothesis_files(), "no committed hypotheses.json artifacts found"


@pytest.mark.parametrize("path", _all_hypothesis_files(), ids=lambda p: p.parent.name)
def test_no_banned_false_comparatives(path: Path) -> None:
    blob = path.read_text().lower()
    for phrase in _BANNED_PHRASES:
        assert phrase not in blob, (
            f"{path.parent.name}: the Stage-C false comparative {phrase!r} reappeared"
        )


@pytest.mark.parametrize("path", _all_hypothesis_files(), ids=lambda p: p.parent.name)
def test_proximity_superlatives_match_candidate_table(path: Path) -> None:
    artifact = json.loads(path.read_text())
    ps = artifact.get("plume_summary", {})

    for h in artifact["hypotheses"]:
        text = _hypothesis_text(h)
        if not _PROXIMITY.search(text):
            continue  # no proximity claim to verify

        # (2) A proximity claim requires the computed table to verify against.
        assert "nearest_by_centerline" in ps and "nearest_by_distance" in ps, (
            f"{path.parent.name} hypothesis {h.get('rank')}: proximity superlative "
            f"in prose but plume_summary has no nearest_by_* table — the claim is "
            "machine-unverifiable; add the computed table or remove the claim"
        )
        centerline_id = _parse_table_id(ps["nearest_by_centerline"])
        distance_id = _parse_table_id(ps["nearest_by_distance"])

        cand = h.get("candidate") or {}
        if cand.get("ogim_id") is None:
            # A proximity superlative with no identifiable candidate cannot be
            # checked against the table — refuse it rather than trust it.
            raise AssertionError(
                f"{path.parent.name} hypothesis {h.get('rank')}: proximity "
                "superlative on a candidate without an OGIM id is unverifiable"
            )

        # (3) The candidate must be nearest on at least one computed axis.
        cand_id = int(cand["ogim_id"])
        assert cand_id in (centerline_id, distance_id), (
            f"{path.parent.name} hypothesis {h.get('rank')}: candidate OGIM_ID "
            f"{cand_id} is described with a proximity superlative but is neither "
            f"nearest-by-centerline ({centerline_id}) nor nearest-by-distance "
            f"({distance_id})"
        )

        # (4) No hiding a closer well: if a different record is distance-closest,
        # it must be named in the hypothesis text.
        if cand_id == centerline_id and distance_id != centerline_id:
            distance_name = ps["nearest_by_distance"].split(" (OGIM_ID")[0]
            assert distance_name in text, (
                f"{path.parent.name} hypothesis {h.get('rank')}: a distance-closer "
                f"well ({distance_name}) exists but is not disclosed in the prose"
            )
