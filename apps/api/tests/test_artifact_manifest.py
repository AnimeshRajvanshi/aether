"""GUARD manifest-staleness (Sprint 10 Stage B item 6).

Regenerates the integrity manifest from the working tree and fails on ANY
difference from the committed artifacts.manifest.json (endpoint tables and
hashes; the informational commit stamp is excluded so regeneration at a new
commit with unchanged artifacts is not a spurious diff). A red here means a
served artifact changed without `uv run python scripts/build_artifact_manifest.py`
being re-run — the deployment analogue of the no-staleness rule.

Also asserts the manifest's negative space: no ISD/NOAA raw path may ever
appear in the served-artifact contract (cardinal rule 3).
"""

from __future__ import annotations

import json

from aether_api import manifest


def _committed() -> dict:
    path = manifest.manifest_path()
    assert path.exists(), (
        "artifacts.manifest.json is missing — run "
        "`uv run python scripts/build_artifact_manifest.py` and commit it."
    )
    return json.loads(path.read_text())


def test_manifest_is_not_stale() -> None:
    committed = _committed()
    regenerated = manifest.build_manifest()
    for table in ("raw_endpoints", "composed_endpoints", "composed_sources"):
        assert regenerated[table] == committed[table], (
            f"artifacts.manifest.json is STALE in {table!r} — a served artifact "
            "changed without regenerating the manifest. Run "
            "`uv run python scripts/build_artifact_manifest.py` and commit the diff."
        )


def test_manifest_covers_every_raw_endpoint() -> None:
    committed = _committed()
    live = {url: entry for url, entry in committed["raw_endpoints"].items()}
    regenerated = manifest.raw_endpoint_files()
    assert set(live) == set(regenerated)
    # Floor: all three events contribute; collapse of the enumeration is a red.
    assert len(live) >= 14
    for event_id in (
        "turkmenistan_goturdepe_2022_08_15",
        "permian_basin_2022",
        "india_nw_heatwave_2022_04",
    ):
        assert any(event_id in url for url in live), f"no raw endpoints for {event_id}"


def test_manifest_negative_space_no_isd_raw() -> None:
    text = manifest.manifest_path().read_text().lower()
    for marker in ("isd", "noaa", "global-hourly", ".aether_cache"):
        assert marker not in text, (
            f"{marker!r} appears in the served-artifact manifest — the NOAA ISD "
            "raw data must be provably absent from the deployed artifact set."
        )
