# ADR 0005 — Phenomenon-agnostic factor attribution (hypothesis engine v2)

- **Status:** Accepted (Sprint 9 Stage C)
- **Date:** 2026-06-12
- **Extends:** the Sprint 4 source-attribution schema (`packages/causal/
  aether_causal/schema.py`); composes with ADR 0001/0003.

## Context

Methane attribution asks "which facility?" — candidates are point entities,
evidence is geometry (a back-projection wedge), and the no-fabrication rule
binds every named candidate to a real OGIM record. Heat is an AREA phenomenon
with entangled causation: there is no facility, no wedge, no single cause. The
engine must rank **contributing factors** instead, and the Stage C gate set
three requirements beyond the brief: a no-fabrication-for-factors centerpiece,
data-over-prior handling of urban fabric, and a hard attribution boundary.

## Decision

Additive models in the same schema module (existing methane models untouched):

1. **`Diagnostic`** — one computed number (name, value, unit, definition,
   `SourceRef` to the committed artifact / cached dataset it came from).
2. **`FactorHypothesis`** — the factor analogue of `SourceHypothesis`, with
   `diagnostics: list[Diagnostic]` required **non-empty** (`min_length=1`).
   This is the no-fabrication-for-factors rule in structural form: *a factor
   with no computed diagnostic cannot be constructed*, just as a methane
   candidate cannot name a facility without an OGIM id. Negative-tested.
3. **`FactorRole`** — `warming_contributor` / `severity_framing` /
   `counter_evidence`. The third role exists so the engine can carry a factor
   the data argues AGAINST (Stage C's urban-fabric case: the measured daytime
   surface UHI is negative) — a popular prior is surfaced and refuted rather
   than silently presumed or silently dropped.
4. **`FactorHypothesisSet`** — adds `attribution_boundary` (the engine ranks
   physical contributing factors; it does NOT perform probabilistic
   anthropogenic event attribution) and `external_published_attribution`, the
   ONLY field where published attribution results (WWA/Zachariah) may appear:
   cited evidence with a DOI, never blended into factor scores. Guard-tested:
   no score component may reference the published attribution.

## Machinery ported, not forked

Deterministic templating from computed values, weighted score components with
rationales, a scoring disclaimer (heuristic, not calibrated probability),
qualitative tiers with a ceiling (`FACTOR_CEILING = MODERATE` — diagnostics
can rank co-occurring factors but cannot establish causal separation without
counterfactual experiments, which are out of scope), assumptions,
counter-considerations, and falsification per factor. Non-discrimination
between top factors, when the score gap is inside the diagnostics' resolving
power, is the headline finding — the Permian dense-coverage lesson ported.

## Reproducibility split

`compute_diagnostics()` (cache/network) writes a committed `diagnostics.json`;
`build_factor_hypothesis_set()` is a pure function of that committed file, so
the regen guard re-derives the committed `factor_hypotheses.json`
byte-identically offline in CI — same pattern as the methane hypotheses regen
guard.
