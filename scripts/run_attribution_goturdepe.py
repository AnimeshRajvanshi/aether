"""Generate the Goturdepe source-attribution artifacts (Stage B).

Deterministically builds the ranked hypotheses from committed data joins and
writes:
  attribution_outputs/turkmenistan_goturdepe_2022_08_15/hypotheses.json
  attribution_outputs/turkmenistan_goturdepe_2022_08_15/hypotheses.md

Re-runnable and reproducible: same committed inputs -> identical outputs. No LLM,
no randomness, no fabricated entities.

Run from the repo root:  uv run python scripts/run_attribution_goturdepe.py
"""

from __future__ import annotations

from pathlib import Path

from aether_causal.attribution import EVENT_ID, build_hypothesis_set
from aether_causal.render import render_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "attribution_outputs" / EVENT_ID


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    hs = build_hypothesis_set(REPO_ROOT)

    json_path = OUT_DIR / "hypotheses.json"
    json_path.write_text(hs.model_dump_json(indent=2))
    md_path = OUT_DIR / "hypotheses.md"
    md_path.write_text(render_markdown(hs))

    print(f"Wrote {json_path.relative_to(REPO_ROOT)} ({len(hs.hypotheses)} hypotheses)")
    for h in hs.hypotheses:
        print(
            f"  {h.id} rank{h.rank}  {h.confidence_tier.value:11s} score={h.score:.2f}  "
            f"{h.candidate.descriptor}"
        )
    print(f"Wrote {md_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
