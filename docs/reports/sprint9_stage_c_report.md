# Sprint 9 — Stage C — Hypothesis Engine v2: Multi-Factor Heat Attribution — Gate Report

> The sprint's center of gravity: the Sprint 4 attribution machinery
> generalized from "which facility" to "which physical factors, with what
> weight" (ADR 0005), with the three gate rules structural: no-fabrication-
> for-factors, urban fabric argued from this event's evidence, and the hard
> attribution boundary. Committed artifacts:
> `attribution_outputs/india_nw_heatwave_2022_04/{diagnostics,factor_hypotheses}.json`
> + `factor_hypotheses.md`. **STOP at this gate** — the factor hypotheses are
> written to be read like every attribution gate before this one.

## Verdict — the ranked factors

| rank | factor | role | score (heuristic) | tier |
|---|---|---|---|---|
| 1 | **F1 Persistent synoptic ridge** (+61.6 m regional z500 anomaly, above all 30 climatology windows, 10/10 days above pooled p90) | warming contributor | 1.00 | **MODERATE (capped — ceiling)** |
| 2 | F2 Antecedent soil-moisture deficit | warming contributor | 0.31 | LOW |
| 3 | F3 Arid-sector advection | warming contributor | 0.28 | LOW |
| 4 | F4 Airmass humidity | severity framing | 0.07 | INSUFFICIENT (not active) |
| 5 | F5 Urban fabric | **counter-evidence** | 0.00 | INSUFFICIENT (as warming role) |

**Headline (verbatim from the committed artifact):** F1 leads F2 by 0.69 — a
ranking, not an established apportionment — and **the expected
ridge-vs-dry-soil entanglement did NOT materialize**, because the diagnostics
argue against several popular priors: antecedent soil moisture was **near
climatology** (dryness rank 57% — the pre-dried-land narrative is
unsupported), low-level flow was **essentially climatological** (anomaly
0.39 m/s), airmass humidity was **near-normal**, and the urban-fabric prior is
argued **against** by the measured negative daytime surface UHI (−0.77 K).
What remains, by these diagnostics, is a rare and persistent ridge over a
region whose in-window drying *followed* the heat.

The Stage A/Permian non-discrimination machinery is fully ported (resolution
0.15; the headline switches to a first-class CANNOT-BE-DISCRIMINATED statement
when the gap is inside it — exercised in tests). For THIS event the data
discriminated; that, too, is the data's call, not a template's.

## 0. Gate-rule compliance

1. **No-fabrication-for-factors (centerpiece):** `FactorHypothesis.diagnostics`
   is schema-required non-empty (`min_length=1`) — a factor without a computed
   diagnostic cannot be constructed. **Negative-tested**
   (`test_factor_without_diagnostics_rejected`). Every committed factor binds
   to named diagnostics with source locators into
   `diagnostics.json`/`uhi.json`; the regen guard re-derives the committed
   factor set byte-identically from the committed diagnostics (pure builder —
   no hidden inputs).
2. **Urban fabric from this event's evidence:** F5 carries the measured
   −0.77 K (±0.80, sign robust across the pre-registered sensitivity range
   −1.05..−0.74 K) as `counter_evidence`; its claim states the data argues
   AGAINST daytime urban warming at the only observed time, with the
   nighttime/2 m-air roles **explicitly UNASSESSED** (no diagnostic exists in
   this stack — the falsification field says exactly what observation would
   open them). Guard-tested: no warming-contributor factor is urban; the claim
   text is templated from the diagnostic (a positive UHI produces different
   text — tested); score support is 0.
3. **Attribution boundary:** the artifact carries an `attribution_boundary`
   statement; the WWA/Zachariah ~30× result appears ONLY in
   `external_published_attribution` with its DOI (10.1088/2752-5295/acf4b6),
   exactly like the Thorpe block pattern. Guard-tested: the markers
   (Zachariah / 30 times / WWA / preindustrial) never appear in any factor's
   claims, components, or rationales.

## 1. The engine's first real test: arguing AGAINST priors

This stage's most important finding is methodological. The first engine draft
templated claims that followed the textbook heatwave narrative ("the land was
pre-dried", "the heat was dry", sector-membership scored as advection
support). The computed diagnostics then CONTRADICTED three of them:

| prior | diagnostic | engine's corrected position |
|---|---|---|
| pre-dried soil preconditioning | antecedent March swvl1 at the 43rd percentile (near median); only in-window moisture is low (87th dryness), concurrent with the heat | "the pre-dried-soil narrative is NOT supported"; in-window drying cannot establish preconditioning; score from rarity-above-median ⇒ 0.31, LOW |
| dry heat (humidity framing) | window dewpoint anomaly +0.13 K, 53rd percentile | framing factor "NOT active for this event at the sampled hour"; INSUFFICIENT |
| anomalous arid-sector advection | flow FROM 265.6° vs climatological 267.5°, anomaly 0.39 m/s | "essentially climatological flow — no anomalous advective contribution"; direction is state, not event evidence; scored on the anomaly only ⇒ 0.28 |

The engine was rewritten so templates and scores follow the diagnostics
(rarity-above-median scoring: a 57th-percentile state earns ~0.14, not 0.57),
and the corrected behavior is what is committed. Combined with the negative
daytime UHI (rule 2), **the engine now argues against four popular priors in
one artifact because the data says so** — which is precisely what this stage
was meant to prove the machinery could do.

Honest caveats attached in-artifact: ERA5 swvl1 is a land-surface-model
product (weakly observation-constrained); 06 UTC sampling is morning
(pre-mixing) for humidity; no trajectory analysis for advection; all
diagnostics are one model family (ERA5) — cross-product replication is future
work.

## 2. The ridge diagnostic and the cross-store audit

- Window-mean regional z500: **5875.8 m corrected** vs climatology 5814.2 m →
  **+61.6 m (~2.9× the 21.2 m climatological std of window means)**;
  above ALL 30 climatology window means; 10/10 days above the pooled p90.
- **Cross-store offset measured, not assumed:** the 2022 value comes from the
  0.25° store, the climatology from the 1.5° conservative store. On overlap
  years (2019, 2020) present in both, the offset is −3.3 / −5.5 m (mean
  **−4.4 m**); the 2022 value is offset-corrected before ranking, and the
  engine REFUSES to run without the overlap check (a silent regridding bias
  cannot enter the percentile). At −4.4 m vs a +61.6 m anomaly the correction
  is immaterial — but now that is a measured statement.

## 3. Machinery ported, not forked

- Deterministic templating (no LLM anywhere), weighted score components with
  rationales, scoring disclaimer ("documented heuristics, not calibrated
  probabilities, not contribution fractions"), per-factor assumptions /
  counter-considerations / falsification.
- **`FACTOR_CEILING = MODERATE`**: warming-contributor tiers are capped —
  diagnostics establish presence and rarity of co-varying factors but cannot
  causally separate them without counterfactual experiments (out of scope).
  F1's 1.00 banded HIGH and was CAPPED; HIGH is reserved-and-unearned, exactly
  like VALIDATED was for methane tiers and FAC_CEILING for facilities.
- Methane attribution untouched: Goturdepe/Permian artifacts byte-identical
  (`git status` clean over `attribution_outputs/` methane dirs); their
  builders and guards pass unchanged; the factor models are additive in the
  same schema module.
- Suite: **322 passed** (+28 this stage: schema negative tests, urban/boundary
  guards, determinism, ceiling, both headline branches, regen byte-identity
  ×2, committed-artifact rule audit), ruff 0.

## 4. Reproducibility

`compute_diagnostics()` (cache + committed Stage B artifacts) → committed
`diagnostics.json`; `build_factor_hypothesis_set()` is a pure function of that
file → committed `factor_hypotheses.json`/`.md` re-derive **byte-identically
offline** in CI (guard-tested), the same regen discipline as the methane
hypotheses. Inputs: ERA5 v3 (06 UTC samples; z500/swvl1/u10/v10/d2m), the
1.5° store (z500 climatology), and the gate-approved Stage B `uhi.json`.

## 5. Honest limits

- Scores are presence/rarity heuristics over CO-VARYING diagnostics from ONE
  reanalysis family; the ranking orders evidence strength, never apportions
  the +5.10 K anomaly among factors.
- The soil and humidity "against-prior" findings are statements about ERA5's
  layer-1 soil moisture and 06 UTC dewpoint specifically — both carry stated
  representation limits; independent soil-moisture or station-humidity data
  could overturn them (their falsification fields say how).
- F5's counter-evidence covers one city at one observed time; the unassessed
  nighttime/air-temperature urban roles remain genuinely open.
- The comparative-claims guard family does not yet parse factor claims
  (different artifact shape); the factor claims contain percentile statements
  generated from the diagnostics themselves — flagged as a Stage D guard
  extension candidate.

## STOP — for review

The factor hypotheses (`factor_hypotheses.md`) are written for your read, like
the Sprint 4/7C gates. Next (gated on your review): Stage D — heat in the UI
(area rendering, factor hypotheses with all honesty elements, per-quantity
tier badges, LST-vs-air as a first-class block), methane pixel-identical.

---

## Addendum — Stage C review corrections (applied before Stage D)

The artifact read passed with two required fixes, both found by reconciling
claims against `diagnostics.json`, both regenerated into the committed
artifacts and both now guarded:

1. **F1 arithmetic closure.** The claim had quoted the UNCORRECTED window mean
   (5871.4 m) beside the corrected anomaly (+61.6 m) — a reader's subtraction
   gave 57.2. The claim now quotes **5875.8 m (cross-store-corrected from
   5871.4 m) vs 5814.2 m → +61.6 m**. New guard
   (`TestNumericReconciliation`): every level/baseline/anomaly triple rendered
   in a factor claim must reconcile arithmetically within 0.15 m rounding
   tolerance, non-vacuously (≥1 triple asserted), on both built and COMMITTED
   claims — negative-tested with a deliberately mismatched triple.
2. **Falsification direction.** F2's falsification targeted the rejected prior
   ("normal moisture would falsify preconditioning") instead of the committed
   against-prior position. All five factors audited; falsifications are now
   **generated from the taken position branch**: F2 (unsupported branch →
   anomalously-DRY observations would overturn), F3 (climatological-flow
   branch → anomalously strong arid-sector transport would overturn), F4
   (not-active branch → any anomalous humidity would overturn), F5 (the
   committed daytime finding's OVERTURN condition stated separately from the
   ESTABLISH condition for the explicitly-open nighttime/air roles). F1 was
   already directionally correct. New guard (`TestFalsificationDirection`):
   both branches of F2/F3/F4 are built from fixture variants and the
   falsification text is asserted to match the branch — the cheap structural
   form of the ruling.
3. Rounding nit: the climatological FROM-direction renders at one decimal
   (267.5°) everywhere.

Regenerated artifacts are committed; the byte-identity regen guards now hold
against the corrected outputs; suite green.
