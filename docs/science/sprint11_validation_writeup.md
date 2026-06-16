# Aether — the scientific validation story

> The rigor story in depth, for a reader who will check it. Every figure here is sourced from a
> committed artifact via the single source-of-truth snippet
> [`docs/key_results.json`](../key_results.json) (regenerate: `uv run python tools/build_key_results.py`),
> which records the aether SHA it was extracted at. Nothing is retyped from memory. Where a claim is a
> finding rather than a success, it is labeled as such — the failures are part of the argument.

This document is the deep version of the README's *What is validated, and what is not*. It exists
because, for this work, the honest accounting of uncertainty **is** the contribution. The headline is
not "we measured methane"; it is "we built a pipeline whose every number is traceable, whose validation
tiers are earned not asserted, and which reports its own systematics and failures on the screen."

## 1. The independent methane target spectrum

A matched-filter methane retrieval needs a **unit absorption spectrum** `k` — the per-wavelength
signature of a methane enhancement. NASA's EMIT tutorial ships a *per-granule* target spectrum
generated from that granule's own MODTRAN simulation. Using it is a valid *implementation test* of the
matched filter, but it is not an *independent* physical retrieval: the target and the operational L2B
share an origin.

Aether generates its own `k` from first principles instead: **HITRAN2020** line-by-line CH₄ absorption
(Gordon et al. 2022, doi `10.1016/j.jqsrt.2021.107949`) computed via **HAPI** (Kochanov et al. 2016,
doi `10.1016/j.jqsrt.2016.03.005`), Voigt-broadened, convolved to EMIT's spectral response function.
The unit absorption is **saturation-aware** — derived by a finite-enhancement log-radiance regression
(the Thompson / EMIT-ATBD method) rather than the optically-thin `c=0` Jacobian, which omits line-core
saturation. **No MODTRAN; NASA's per-granule file is never read in generation**
(`stage_a_outputs/turkmenistan_goturdepe_2022_08_15/stage_a_report.json#k_nasa_target_used = false`;
guard-tested).

NASA's per-granule target is **repositioned as a spectral-shape cross-check only**: our independent `k`
correlates with it at Pearson **r = 0.993**
(`hitran_k/hitran_k_sat_provenance.json#shape_pearson_r_vs_nasa`). High shape agreement against a file
we did not use confirms the physics is right without making it a pipeline input. The forward scale is
**1.0** (`stage_a_report.json#ppm_scaling_factor_forward`) — the retrieval is derived forward from
physics, **never reverse-fit** to a target flux.

## 2. End-to-end spatial fidelity, with exact definitions

After the matched filter, the enhancement is orthorectified and compared, pixel-for-pixel, against
NASA's operational **L2B CH4ENH** raster for the same granule. Two figures, both committed in
`stage_a_report.json`:

- **`pearson_in_bbox` = 0.731** (Goturdepe): Pearson correlation of our orthorectified, unsmoothed
  enhancement vs NASA L2B CH4ENH over the plume bounding box.
- **`pearson_full_scene` = 0.715** (Goturdepe): the same correlation over the entire scene.

These are spatial-agreement metrics, not flux-accuracy metrics. They establish that our independent
retrieval reconstructs the *same plume structure* NASA's operational product does — the basis for the
**CROSS-CHECKED** tier. (Sprint 6's control: feeding NASA's `k` through the identical pipeline
reproduces the Sprint 2 Pearson exactly, confirming the fidelity recovery is the `k`, not the plumbing.)

## 3. The flux, the two calibrations, and the +1.46× systematic

Flux **Q** is computed by the integrated-mass-enhancement (IME) method (Varon 2018): integrate the
plume's mass enhancement, divide by an effective plume length, multiply by an effective wind speed. Two
calibrations are reported and **both ship** — neither is silently chosen:

- **Q (ours-cal) = 23.4 t/hr** — our independent retrieval amplitude
  (`q_estimate.json#q_central_t_hr`).
- **Q (NASA-anchored) = 16.0 t/hr** — the same plume re-scaled to NASA's L2B amplitude
  (`#q_central_nasa_calibrated_t_hr`).

The gap between them is the **+1.46× matched-filter amplitude systematic**: our retrieval's mean
enhancement over the plume runs 1.46× NASA's (`#enhancement_bias_factor = 1.46`, *independently
measured* this run — not the older NASA-`k` run's hand-carried 1.66×). **It is left uncorrected.**
Correcting it would mean reverse-fitting to NASA, which would forfeit the independence the whole `k`
derivation buys. Reported honestly, it is a *known systematic* on the absolute scale — which is exactly
why the flux is CROSS-CHECKED (spatial + relative-mass agreement) and **not** VALIDATED (absolute
accuracy unproven).

**Uncertainty is structural, not decorative.** Q carries **±12.8 %**
(`#q_total_fractional_sigma = 0.128`), propagated from the wind term and the plume-mask threshold
sensitivity (the dominant budget terms), giving a central range **14.0–26.4 t/hr**
(`#q_low_t_hr, #q_high_t_hr`). The uncertainty is carried through to the dashboard, never dropped.

## 4. Generality — the Permian, and what broke

The second methane event (Permian/Carlsbad, EMIT 2022-08-26) is the first cross-scene test of the
independent retrieval, and it is reported with its failures intact:

- **The independent `k` works with no NASA target available.** No per-granule NASA target spectrum
  exists for this granule, so there is *no* k-shape cross-check
  (`stage_a_report.json#k_shape_crosscheck_available = false`) — the `k` is generated from this
  granule's own geometry / SRF / ERA5 surface state. Surface state is read from **ERA5** (P = 90 897 Pa,
  T = 303.5 K at ~1086 m elevation), **not** a sea-level default — a generality fix that matters at the
  Permian's altitude.
- **Integrated mass agrees; pixels do not.** Over NASA's published plume footprint, our flux is
  **0.85 t/hr** vs NASA's own L2B through the same method **0.88 t/hr** — a clean **0.96×** integrated-mass
  agreement (within ~4 %). But the **plume-scale pixel correlation is weak, r = 0.137**
  (`diagnostics.json#pixelwise_pearson_on_footprint_ours_vs_nasa`): the masses match even though
  pixel-level co-registration is poor, because the plume is weak relative to scene clutter. Both facts
  are carried — the agreement and the caveat.
- **The +1.46× systematic does NOT transfer.** On this scene it flips to 0.96×
  (`q_estimate.json#carried_goturdepe_mf_bias_note`). A systematic measured on one scene is not a
  calibration constant — stating that is the finding.
- **Our self-segmentation could not isolate this weak plume** — it grabbed a confuser
  (`#self_segmentation_isolated_plume = false`), so the mask is anchored to NASA's published footprint
  and the localization is labeled NASA-anchored, not self-derived. Full-scene Pearson degrades to
  **0.527**. The honest consequence: Permian is **CROSS-CHECKED (weaker)**, explicitly below Goturdepe.

## 5. The validation-tier rubric, and why VALIDATED is reserved

Tiers are **earned by evidence, never asserted** ([`validation_tiers.md`](validation_tiers.md)):

- **VALIDATED** requires *independent flux truth* — a controlled release, an in-situ measurement, or a
  peer-reviewed per-source flux at our scope. **No methane event qualifies, by design.** Goturdepe's
  only reference (Thorpe 2023, doi `10.1126/sciadv.adh2391`) is a **12-source cluster total** of
  163 ± 18 t/hr — a scope mismatch with our single-plume estimate, so agreement is *not claimable*. The
  Permian 18.3 t/hr is a press-release figure (no method/date/uncertainty) — context, not truth. The
  reserved-and-empty top tier is what gives the system an honest ceiling instead of a self-graded "best".
- **CROSS-CHECKED** is what an independent NASA L2B raster earns. Strength lives in the explainer, not
  the badge: Goturdepe is *strong* (pixel r ≈ 0.73, self-derived localization, k-shape r = 0.993);
  Permian is *weaker* (mass 0.96× but pixel r = 0.137, NASA-anchored localization, no k-shape check).

## 6. Pre-registration, and the failures that prove the method

The heat event's validation is the clearest demonstration of method maturity, because the discipline
**committed the pass/fail criteria before the station data was read**
(`validation.json#computed_after_pre_registration_commit = true`; criteria in
[`sprint9_heat_validation.md`](sprint9_heat_validation.md)). Tiers are **per quantity**, not per event:

| Quantity | Result | Pre-registered criterion (committed before data) |
|---|---|---|
| **C1** peak 2 m Tmax **46.68 °C** | **VALIDATED** | V1: ERA5 peak vs max ISD station 45.0 °C, within ±2.5 K (Δ = 1.68 K) → pass |
| **C2** regional anomaly **+5.67 K** (window-mean +5.10 K) | **VALIDATED** | V3: ERA5 +4.501 K vs ERA5-independent IMD +4.307 K common-grid (|Δ| 0.194 K < 1.0), pattern r 0.874 > 0.6 → pass |
| **C3** duration **26 days** (ERA5) | **NOT VALIDATED** | V4a: vs IMD 7 days → **FAIL** |
| **C4** extent **889 700 km²** | **NOT VALIDATED** | V4b: ERA5 887 700 vs IMD 606 300 km² common-grid, rel diff 0.464 > 0.30 → **FAIL** |
| ERA5↔station consistency | **NOT CLAIMED** | V2: pooled r 0.728 < 0.85 → fail (bias and RMSD were within threshold) |

The **C3/C4 failures are the headline, not a footnote.** A heat wave's duration and extent are
criterion-edge quantities: ERA5 and the station-gridded IMD product disagree on them because the
threshold semantics differ, and a method that hid that would be overclaiming. C1/C2 VALIDATED rests on
the *station / IMD* anchors (V1, V3), which are independent of ERA5 for the anomaly pattern; V2's failure
is honestly reported because ERA5 assimilates synoptic stations, so ERA5↔station agreement would be
*consistency*, not independent verification — a circularity we refuse to launder into a validation.

This is the first VALIDATED claim in Aether's history (C1), and it is deliberately narrow.

## 7. Two lanes: air temperature vs skin temperature

Air temperature (2 m) and land-surface (skin) temperature are **different physical quantities** and are
kept in **separate lanes that are never conflated**. The air lane is validated against stations/IMD
(above). The LST lane (MODIS / Landsat) is **capped at CROSS-CHECKED** — there is no in-situ skin truth,
and the daytime LST is a **Terra ~10.7 h-local snapshot, never a daily maximum** (Aqua's ~13:30 pass is
absent for the window; `lst_lane.json#observation_time_caveat`). The MODIS-vs-ERA5-skin comparison
(−5.31 ± 1.32 K) is framed as a **coherence check between distinct-but-not-independent products**, not a
validation. No LST number is ever compared against an air-temperature claim.

## 8. The factor-attribution boundary

Heat attribution ranks **contributing factors** from computed ERA5 diagnostics; it establishes
**presence and rarity, not a quantified causal contribution**
(`factor_hypotheses.json#attribution_boundary`). The cap is **moderate** — HIGH is reserved, because
diagnostics cannot separate co-varying factors without counterfactual experiments. Three honesty
features ship:

- **The engine argues against popular priors when the data says so.** F1 (persistent synoptic ridge:
  z500 **+61.6 m**, 100th percentile of 30 climatology windows, 10/10 days above the pooled p90) scores
  1.00 but is **CAPPED to moderate**. The expected dry-soil/advection drivers score **LOW** (antecedent
  soil moisture near climatology; low-level flow essentially climatological) — the diagnostics
  contradicted the first-draft narrative and the narrative was rewritten.
- **Counter-evidence is reported, not buried.** F5 (urban fabric) is **COUNTER_EVIDENCE** (score 0.00):
  the measured daytime surface UHI is **negative (−0.77 K)**, arguing *against* the urban-heat prior.
- **External attribution is cited, never claimed.** Zachariah et al. (2023, doi
  `10.1088/2752-5295/acf4b6`) — the heatwave was ~30× likelier and ~1 °C hotter than preindustrial — is
  carried as a **cited external result**, never computed by Aether and never blended into a factor score.
  Aether does not perform probabilistic extreme-event attribution; saying so is the boundary.

**Scores are documented heuristics — not calibrated probabilities, not contribution fractions**
(`#scoring_disclaimer`). The tiers and the rationales are the product; the decimals are not.

## 9. Uncertainty and coverage, stated as findings

- Methane flux carries **±12.8 %** (Goturdepe) and the **+1.46×** uncorrected amplitude systematic.
- Source attribution is **capped by data coverage**: Goturdepe is field/sector-level only (OGIM has zero
  point infrastructure in Turkmenistan — a first-class finding); Permian ranks 21 wells in the wedge but
  **no facility exceeds LOW** (the favored pad wins on angle only; a closer well exists). The data ranks;
  it does not establish.
- Generalization is **one strong + one weaker cross-check**, not a validated detector. Detection recall
  is a coarse "found a plume where the literature flagged one" check over a handful of events — not a
  detection-performance benchmark, and labeled as such.

The throughline: at every step the system reports the ceiling of what it can claim, and stops there.
