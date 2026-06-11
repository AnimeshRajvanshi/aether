"""Generate facility-level source-attribution artifacts for a dense-coverage event.

Shared, event-parameterized (Sprint 7): the SAME engine that produced Goturdepe's
field/sector-level hypotheses, now run in its facility-level mode against an event
with dense OGIM coverage. No per-event fork — the event config lives in
``aether_causal.attribution.FACILITY_EVENTS``.

    uv run python scripts/run_attribution_event.py <event_id>

Writes attribution_outputs/<event_id>/hypotheses.{json,md}. Deterministic and
reproducible: same committed inputs -> identical outputs. No LLM, no randomness,
no fabricated entities (every OGIM record named is verified by the no-fabrication
guard against the committed subset).
"""

from __future__ import annotations

import sys
from pathlib import Path

from aether_causal.attribution import FACILITY_EVENTS, build_facility_hypothesis_set
from aether_causal.render import render_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in FACILITY_EVENTS:
        raise SystemExit(
            f"usage: run_attribution_event.py <event_id>; known: {sorted(FACILITY_EVENTS)}"
        )
    event_id = sys.argv[1]
    out_dir = REPO_ROOT / "attribution_outputs" / event_id
    out_dir.mkdir(parents=True, exist_ok=True)

    hs = build_facility_hypothesis_set(event_id, REPO_ROOT)
    (out_dir / "hypotheses.json").write_text(hs.model_dump_json(indent=2))
    (out_dir / "hypotheses.md").write_text(render_markdown(hs))

    print(f"Wrote attribution_outputs/{event_id}/hypotheses.json ({len(hs.hypotheses)} hypotheses)")
    for h in hs.hypotheses:
        print(f"  {h.id} rank{h.rank}  {h.confidence_tier.value:11s} score={h.score:.2f}  "
              f"{h.candidate.descriptor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
