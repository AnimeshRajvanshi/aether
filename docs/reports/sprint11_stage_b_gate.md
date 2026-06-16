# Sprint 11 — Stage B gate ruling

**Verdict: APPROVED.** The README, the scientific validation write-up, the source-of-truth snippet,
and the doc reconciliations in [`sprint11_stage_b_report.md`](sprint11_stage_b_report.md) are accepted.

## What the reviewer confirmed

- **Snippet + control sound.** `docs/key_results.json` is extracted (not retyped) by
  `tools/build_key_results.py`; `tools/tests/test_key_results.py` re-extracts and asserts the committed
  snippet matches its artifacts. F3 (both flux calibrations ride it) and F4 (Permian pixel r 0.137 +
  the Duren DOI) are honored.
- **README honesty correct** — the AI orchestration layer is marked **specified, not built**; it leads
  with traceability, not a marketing register; the Carbon Mapper boundary (F5) is stated honestly.
- **Write-up leads with the C3/C4 failures** as the demonstration of method maturity; **no tier is
  exceeded** (methane CROSS-CHECKED, heat per-quantity with VALIDATED only on C1/C2).
- **Both gate flags benign** — the snippet `as_of_sha` self-reference (a file cannot name its own
  commit; the guard excludes the SHA) and the F5-in-prose note.

## Verification at the gate

Suite **398 passed**, 6 skipped, 7 deselected; ruff **0**. Sprint 10 closeout count corrected
388 → 389; the automated visual-fidelity verification harness recorded as a deferred open-thread.

**Proceeding to Stage C: revamp `ape.html` in place in the arkaneworks website repo** under the
paramount website-preservation constraint (exactly one file changes; shared CSS/JS byte-identical;
dashboard colors only inside screenshots). The website deploy (push to the Pages source) is
approval-gated — propose, do not push. Aether-repo commits stay unpushed.
