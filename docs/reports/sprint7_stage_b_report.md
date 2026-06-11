# Sprint 7 — Stage B — Permian per-granule k + end-to-end quantification — Gate Report

> Permian Basin / Carlsbad NM, EMIT granule **20220826T174642**. Per-granule
> independent v2 HITRAN k + the shared parameterized pipeline, run end-to-end.
> Committed gate report; **STOP for review** per the brief. Stages C/D gated.

## Verdict — CROSS-CHECKED (earned), with honest limits

A NASA L2B CH4ENH raster exists, so our independent retrieval is cross-checked
against it both spatially (full-scene Pearson **0.527**) and in integrated mass over
NASA's published plume footprint (**ours 0.85 vs NASA 0.88 t/hr, ratio 0.96×**). The
independent per-granule k — generated with no NASA target spectrum — is what makes
this granule quantifiable at all (the Sprint 6 independence dividend, proven on a
second event). It is **not** VALIDATED: the only flux figure (18.3 t/hr) is
press-release context, and the plume-scale pixel agreement is weak.

## Headline numbers (verbatim from committed artifacts)

| quantity | value | source |
|---|---|---|
| Q (ours, NASA-footprint-anchored) | **0.85 t/hr** | `q_estimate.json:q_central_t_hr` |
| Q (NASA L2B, same footprint + method) | **0.88 t/hr** | `q_estimate.json:q_nasa_l2b_same_footprint_t_hr` |
| ours/NASA integrated-mass ratio | **0.96×** | `q_estimate.json:enhancement_bias_factor` |
| Q range (all uncertainty) | [0.57, 1.15] t/hr | `q_estimate.json` |
| Pearson full / bbox | 0.527 / 0.518 | `stage_a_report.json` |
| footprint | 123 px, 0.379 km², L 615 m | `q_estimate.json` |
| |U₁₀| / U_eff | 3.58 / 1.87 m/s | `q_estimate.json` |
| surface state (ERA5) | 90897 Pa, 303.5 K | `stage_a_report.json` |
| self-segmentation isolated plume | **False** | `q_estimate.json` |
| background σ (ours / Goturdepe) | 289 / 423 ppm·m | `diagnostics.json` |

## What the brief asked for, and where it landed

1. **Per-granule k** — generated from this granule's geometry/SRF/ERA5 surface
   state; independence + reproducibility guards extended. **No NASA per-granule
   target exists → no k-shape cross-check**, stated explicitly.
2. **Shared pipeline** — one runner, `scripts/run_event_quantification.py`, with an
   EVENTS registry (the `acquire_ogim_subset` pattern). MF → ortho → Pearson →
   mask → IME → Q. No `_permian` fork.
3. **Scene checks (re-run)** — wind source-vs-centroid ΔQ = 0.0% (same ERA5 cell;
   0.90 km separation); U_eff regime in-range (3.58 m/s, margin 1.58 m/s to the low
   boundary, reported); mask-threshold sensitivity sweep (dominant budget term).
4. **From-scratch budget** — wind 0.261 + mask half-spread 0.245 → symmetric 0.358;
   MF amplitude carried as the Goturdepe prior (1.46×) **and** measured this scene
   (0.96×). **The +1.46× does NOT transfer** (it flips sign) — first cross-scene test.
5. **Internal consistency** — background stats, footprint cross-check, pixel-wise
   Pearson, self-segmentation confuser inspection; overlay + side-by-side PNGs.
6. **18.3 t/hr as context only** — and the decisive point: NASA's own L2B via this
   method also gives ~0.9 t/hr (~21× below 18.3), so the gap is method/definition,
   not retrieval error. Never framed as agreement/disagreement.
7. Docs: `docs/science/sprint7_permian.md` (this run's full detail) + this report.

## Decisions made this stage — FLAGGED FOR REVIEW

These deviate from or extend the literal brief; calling them out so the reviewer can
object:

1. **NASA-footprint-anchored quantification (not our self-segmentation).** Our Varon
   self-segmentation does not isolate this weak plume (it grabs a confuser;
   NASA-mean over its CC = −35.9 ppm·m). For a CROSS-CHECKED event we anchor the
   plume mask to NASA's *published* complex-000524 footprint (NASA L2B > 200 ppm·m
   in-bbox) and integrate **our** enhancement. The magnitude is entirely ours; NASA
   defines only the location. This is the honest CROSS-CHECKED choice; the
   self-segmentation failure is reported as a first-class generality finding, not
   hidden.
2. **Measured this-scene amplitude ratio (0.96×) used for the NASA-cal, with the
   carried +1.46× shown as a transfer test.** The brief said carry +1.46× as an
   explicitly-unvalidated transfer. Because this granule HAS a NASA L2B, we can do
   better than assume: we measure the ratio (0.96×) and report that the +1.46×
   does NOT transfer. Both are in `q_estimate.json`. If the reviewer prefers the
   headline NASA-cal to use the carried 1.46×, that field is also stored
   (`q_central_nasa_calibrated_carried_1p46_t_hr`).
3. **Benchmark YAML coordinates corrected.** The Permian YAML's `location`/`bbox`
   were an approximate guess that missed the actual plume; replaced with NASA's
   published complex-000524 footprint, with provenance in the YAML comment.
4. **API activation gated on the UI asset (`assets/<id>/bounds.json`), not on
   `q_estimate.json` alone.** Permian's Stage B quantification now lands in
   `stage_b_outputs/permian_basin_2022/` but the event stays an honest **PENDING**
   in the API/UI until Stage D produces its render assets. This keeps the Stage B
   → Stage D gate intact and the two-event API tests green. (Goturdepe has both →
   unchanged.)
5. **Loaders scope-caveat parameterized** (cardinal-rule-2 generality, requirement 3):
   the scope block is now event-specific CONTENT — a cluster-fraction for a
   peer-reviewed cluster total (Goturdepe, byte-identical output) vs a CONTEXT-ONLY
   block for a press-release figure (Permian: no obs date, intermittency). Unit-tested.

## Generality findings (Goturdepe-shaped assumptions found + fixed)

- **Surface state** must come from ERA5, not a sea-level default, for events at
  elevation (Permian ~1 km → ~9% n_air correction). Fixed in the shared runner via
  `era5.get_surface_state_at_point`.
- **Self-segmentation** assumes a plume that dominates its scene; fails on a weak
  plume in a busy scene. Surfaced; CROSS-CHECKED events anchor to the NASA footprint.
- **The +1.46× MF-amplitude systematic is scene-specific** (Goturdepe over-amplifies,
  Permian slightly under) — do not carry it as universal.
- **Plume location** must come from NASA's published complex, not a YAML guess.

## Goturdepe untouched

Verified: `git status` shows no change to any
`stage_a_outputs/turkmenistan_goturdepe_2022_08_15/`,
`stage_b_outputs/turkmenistan_goturdepe_2022_08_15/`, or Goturdepe asset file. Its
numbers are closed. The shared runner refuses to run Goturdepe (its canonical
artifacts are the frozen Sprint-6 operational outputs).

## Guards + tests

- No-staleness guards extended to the Permian docs + report (the headline Q,
  cross-check, ratio, and Pearson in the prose are parsed and asserted against the
  committed `q_estimate.json` / `stage_a_report.json`).
- New unit tests: `era5.get_surface_state_at_point`, and the context-only
  scope-caveat branch.
- Independence: the per-granule k provenance records `nasa_target_used = False`.

## STOP — for review

Next (gated on review): **Stage C** — facility-level attribution against the dense
committed Permian OGIM subset (12,284 features), with dense-coverage
discrimination-honest confidence. Then **Stage D** — UI integration with visible
validation-tier badges. Do not start until this report is reviewed.
