"""Sprint 9 Stage C — run the factor-attribution engine for a heat event.

Computes the factor diagnostics from the gitignored cache + committed Stage B
artifacts, commits them as diagnostics.json, then builds the deterministic
factor hypothesis set from that committed dict (the pure path the regen guard
re-runs offline).

Run: uv run python scripts/run_heat_attribution.py india_nw_heatwave_2022_04
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aether_causal.heat_factors import (
    build_factor_hypothesis_set,
    compute_diagnostics,
    render_factors_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    event_id = sys.argv[1] if len(sys.argv) > 1 else "india_nw_heatwave_2022_04"
    out_dir = REPO_ROOT / "attribution_outputs" / event_id
    out_dir.mkdir(parents=True, exist_ok=True)

    diag = compute_diagnostics(event_id)
    (out_dir / "diagnostics.json").write_text(json.dumps(diag, indent=2))

    # Build from the COMMITTED file (not the in-memory dict) so the artifact
    # path is exactly what the regen guard re-runs.
    committed = json.loads((out_dir / "diagnostics.json").read_text())
    hs = build_factor_hypothesis_set(event_id, committed)
    (out_dir / "factor_hypotheses.json").write_text(hs.model_dump_json(indent=2))
    (out_dir / "factor_hypotheses.md").write_text(render_factors_markdown(hs))

    print(json.dumps(committed, indent=1)[:1800])
    print("\nHEADLINE:", hs.headline_finding[:400])
    for f in hs.factors:
        print(f"  {f.id} rank={f.rank} score={f.score:.2f} tier={f.confidence_tier.value}"
              f" role={f.role.value} — {f.factor_name[:60]}")
    print(f"wrote {out_dir}/diagnostics.json, factor_hypotheses.json, factor_hypotheses.md")


if __name__ == "__main__":
    main()
