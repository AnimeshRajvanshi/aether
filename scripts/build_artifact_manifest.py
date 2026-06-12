"""Generate artifacts.manifest.json — the deployed-integrity contract.

Run from the repo root after any change to served artifacts:

    uv run python scripts/build_artifact_manifest.py

The manifest is committed; apps/api/tests/test_artifact_manifest.py regenerates
it and fails on any endpoint-table diff (manifest staleness = the no-staleness
rule applied to deployment). Stage D's live verifier checks the deployed API
against this file at the pinned SHA.
"""

from __future__ import annotations

from aether_api import manifest


def main() -> None:
    path = manifest.manifest_path()
    path.write_text(manifest.render(manifest.build_manifest()))
    built = manifest.build_manifest()
    print(
        f"wrote {path} — {len(built['raw_endpoints'])} raw endpoints, "
        f"{len(built['composed_endpoints'])} composed endpoints, "
        f"{len(built['composed_sources'])} composed sources, "
        f"commit {built['generated_at_commit'][:12]}"
    )


if __name__ == "__main__":
    main()
