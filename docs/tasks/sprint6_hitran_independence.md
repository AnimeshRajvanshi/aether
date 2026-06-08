# Task: Sprint 6 — HITRAN Independence (generate our own methane target)

**Owner:** Claude Code
**Reviewer:** chat Claude (science/honesty) + human
**Scope:** Replace the dependence on NASA's per-granule methane target file (`emit20220815t042838_ch4_target`) with a **unit absorption spectrum `k` we generate independently from HITRAN line-by-line spectroscopy**, convolved to EMIT's spectral response, validated to reproduce the committed Goturdepe Stage A/B result. This retires the independence caveat now *visibly rendered* in the dashboard provenance panel.

Two-stage, gated like Sprint 2/4. **Stage A:** generate `k` + spectral-shape validation → report, stop. **Stage B:** end-to-end reproduction + calibration comparison → report, stop. No UI changes except a single provenance-line update, and only *after* validation proves independence (see below).

## Why this matters

Right now the retrieval is "reproduces NASA," not "independent of NASA" — and the UI says so out loud (the provenance line naming the NASA per-granule target as the source of our matched-filter `k`). Generating `k` ourselves from the spectroscopic line list makes the retrieval genuinely independent and unlocks quantifying granules NASA never published a target for (e.g. Permian). This is the last big rigor gap.

## The cardinal rule for this sprint

**NASA's per-granule target file may be used ONLY as a validation cross-check — never as an input to our `k`.** Our `k` is computed from HITRAN line data + an atmospheric model + EMIT's spectral response, with zero values read from NASA's file. If our computed `k` is in any way seeded, scaled, or shape-matched to NASA's file, independence is fake and the whole sprint is void. Diagnose-before-fix on any divergence; never tune our `k` toward NASA's to make a number match.

## Approach — the science

**Spectroscopy engine:** HITRAN via **HAPI** (HITRAN Application Programming Interface). Methane (HITRAN molecule ID 6). Free, scriptable, reproducible — and genuinely independent (the spectroscopic line list, not a precomputed target).
- Cite: HITRAN2020 (Gordon, I.E. et al. 2022, JQSRT) and HAPI (Kochanov, R.V. et al. 2016, JQSRT). **Verify exact DOIs/volumes before committing any citation — no fabricated references.**
- Fetch the methane line list over the EMIT SWIR methane fitting window. **Use the exact window already used in Sprint 2 detection** (read it from the codebase — do not hardcode a half-remembered nm range). Cache the fetched line subset and commit it (or a deterministic fetch+cache script) so `k` generation is reproducible offline.

**Unit absorption recipe (document every assumption):**
1. Compute methane absorption with a proper Voigt lineshape over a layered atmospheric profile (e.g. US Standard Atmosphere: P, T, CH₄ VMR per layer; background CH₄ ≈ 1.85–1.9 ppm). A layered column integration is preferred; a well-justified effective-layer approximation is acceptable if documented — state which and why.
2. Two-way path: downwelling (solar) + upwelling (to sensor), using the **granule's actual solar zenith and viewing geometry**. Integrate over the column (satellite path).
3. Derive the unit absorption as the Jacobian ∂(ln radiance, or transmittance)/∂(CH₄ enhancement in ppm·m), with the enhancement in a near-surface layer — i.e. the change per unit methane, consistent with the matched-filter `t = μ ⊙ k` definition.
4. **Convolve the high-resolution absorption to EMIT bands** using the granule's own wavelength + FWHM arrays (Gaussian SRF). This yields our independent `k` on EMIT's spectral grid.
5. Form `t = μ ⊙ k` and feed it into the **existing Sprint 2 matched filter unchanged** (do not modify the detection algorithm; only the source of `k` changes).

## STAGE A — generate k + spectral-shape validation (report, then stop)

- Produce our independent `k` per the recipe above; commit it with full provenance (line-data source, atmospheric profile, geometry, SRF arrays used).
- **Validation A (shape):** correlate our `k` against NASA's per-granule target file — *as a cross-check only*. High shape correlation means our independent computation captures the same absorption features. Report the correlation and overlay the two spectra. State explicitly that NASA's file was used only to validate, not to build, our `k`.
- Report and stop. I want to see the spectra and the correlation before the end-to-end run.

## STAGE B — end-to-end reproduction + calibration comparison (report, then stop)

- Re-run **Goturdepe Stage A detection** with our `k` (NASA target swapped out). Compare the enhancement map to the committed NASA-target result. **Target: preserve the ~0.75 Pearson vs NASA L2B** (the existing independent benchmark). Report the new correlation.
- Re-run **Stage B quantification** with our `k`. Compare Q to the committed 27.1 / 16.3 t/hr.
- **THE HEADLINE QUESTION — report honestly:** does our independent `k` change the absolute amplitude, i.e. the +1.66× MF over-amplitude systematic? Three honest possible outcomes, any of which is a valid result:
  - (i) shape *and* amplitude reproduce → clean independence, caveat retired, 1.66× story unchanged.
  - (ii) shape reproduces but amplitude differs → independence achieved but calibration shifts; the 1.66× factor is revisited and re-derived. Report the new calibration transparently; do NOT tune `k` to preserve the old number.
  - (iii) divergence → diagnose before claiming anything; do not patch toward NASA's values.
- Write `docs/science/sprint6_hitran_independence.md`: the full recipe, every atmospheric/geometric assumption, the shape correlation, the end-to-end reproduction (Pearson + Q), the amplitude/calibration comparison, and a clear statement of **whether independence is achieved and at what (if any) calibration cost.** Same rigor and honesty as `sprint2_validation.md`.

## Provenance-line update (gated)

Only **after** Stage B confirms independence: update the dashboard provenance line that currently names the NASA per-granule target. Change it to state the target is now generated independently from HITRAN (cite HITRAN2020/HAPI). **Do not change this UI claim unless the validation backs it** — if independence is partial or costs a recalibration, the line must say exactly that, not overstate. This is the only UI change in scope.

## Out of scope (do NOT build)

- No changes to the matched-filter / segmentation / IME algorithms (Sprint 2) — only the source of `k` changes.
- No new events in the core sprint. (Permian is an optional stretch below.)
- No UI work beyond the single gated provenance-line update.
- No tuning of `k` toward NASA's file. No fabricated citations.

## Optional stretch (flag separately, only if Stage B is clean)

Quantify **Permian (Aug 26 granule)** with our independent `k` — the granule NASA never published a target for — as proof that independence unlocked new capability. Keep honest about Permian's weaker validation reference (no per-granule NASA target to check against; the 18.3 t/hr figure is press-release-only). If you attempt it, it's a *demonstration*, clearly caveated, not a validated result.

## Definition of done

- Independent `k` generated from HITRAN/HAPI, committed with provenance; line-data cached/reproducible.
- Stage A shape validation reported (correlation + overlay), with explicit statement that NASA's file was cross-check only.
- Stage B: Goturdepe re-run with our `k` — Pearson vs NASA L2B reported, Q reported, and the 1.66× calibration interaction honestly characterized.
- `docs/science/sprint6_hitran_independence.md` documents recipe, assumptions, results, and the independence/calibration verdict.
- Tests: `k`-generation reproducibility (regenerate → byte/array match), a guard that `k` generation reads no values from NASA's target file (independence guard), end-to-end still green.
- Provenance line updated only if/as validation supports.
- Commit at each step. Stop and report after Stage A, and again after Stage B. I review the spectra and the calibration verdict before we call it closed.

## Build order

1. HAPI + methane line list over the Sprint 2 window; cache/commit; verify citations.
2. Atmospheric model + two-way path + Jacobian → high-res unit absorption.
3. Convolve to EMIT SRF → our `k`; commit with provenance.
4. Stage A: shape correlation vs NASA target (cross-check only); **report, stop.**
5. Stage B: re-run Goturdepe Stage A + Stage B with our `k`; characterize the 1.66× interaction; validation doc; **report, stop.**

The review at each gate is about honesty, not just reproduction: was NASA's file truly only a cross-check, and is the calibration outcome reported straight — including if independence costs us a recalibration of the 1.66× systematic. Build it so those answers are unambiguous.
