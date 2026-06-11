# Sprint 7 — Permian/Carlsbad EMIT 2022-08-26 — independent per-granule retrieval

> The second event. Goturdepe was the first granule we quantified end-to-end; it
> had a NASA per-granule target spectrum. **Permian is the first event NASA never
> published a per-granule target for** — so it is the real test of the Sprint 6
> "independence dividend": our per-granule HITRAN `k` is precisely what makes a
> no-NASA-target granule quantifiable at all. It is also the first *generality*
> test: a second scene flushes out Goturdepe-shaped assumptions.
>
> **Validation tier: CROSS-CHECKED.** A NASA L2B CH4ENH raster exists for this
> granule, so we can cross-check our retrieval against it spatially and in
> integrated mass. There is **no** peer-reviewed per-source flux; the only
> emission figure (18.3 t/hr) is press-release context (see §6). Nothing here is
> tuned to any flux.

All artifacts are produced by the **shared, event-parameterized runner**
`scripts/run_event_quantification.py` (no `_permian` fork — see §7).

## 1. Granule + independent per-granule k

| item | value |
|---|---|
| L1B | `EMIT_L1B_RAD_001_20220826T174642_2223812_024` |
| L2A MASK | `EMIT_L2A_MASK_002_20220826T174642_2223812_024` |
| L2B CH4ENH | `EMIT_L2B_CH4ENH_002_20220826T174642_2223812_024` (the cross-check raster) |
| geometry | SZA 27.56°, VZA 9.61° (from this granule's OBS cube) |
| scene-mean elevation | 1086 m (Permian is at ~1 km — see §2) |
| surface state | p = 90897 Pa, T = 303.5 K (ARCO-ERA5 at the plume centroid + overpass) |

The methane unit-absorption spectrum `k` is generated **per-granule** with the
Sprint 6 v2 saturation-aware method (`hitran_k.generate_k_regression`): HITRAN2020
line-by-line via HAPI, Voigt cross-section at this granule's surface p/T, AMF from
its own SZA/VZA, Gaussian-SRF convolved onto its own 285-band wavelength/FWHM
grid. 52 in-window bands; the matched filter keeps 49. Forward scale 1.0 — `k` is
in 1/(ppm·m), nothing reverse-fit. **NASA's file is never read.**

**No k-shape cross-check exists for this granule.** Goturdepe could compare the
`k` *shape* to NASA's per-granule target (r = 0.993); NASA published no such target
here, so that cross-check is simply unavailable. We state it rather than fabricate
a comparison.

## 2. Surface state from ERA5 — not a sea-level default (generality)

Goturdepe (coastal Caspian, ~sea level) used a documented 101325 Pa / 295 K. The
Permian sits at ~1 km elevation; a sea-level pressure default would bias n_air —
and therefore IME and Q — by ~10%. So the runner fetches **surface pressure and 2 m
temperature from ARCO-ERA5** at the scene + overpass (the same trusted reanalysis
as the wind): p = 90897 Pa (≈909 hPa, consistent with 1086 m elevation), T = 303.5 K,
n_air = 36.02 mol/m³. This is a shared-code generalization, not a Permian special case.

## 3. Plume location — NASA's published complex 000524

The benchmark YAML's original bbox was an approximate "10 mi SE of Carlsbad" guess
that did **not** overlap the actual plume. We pin the plume to NASA's published L2B
**CH4PLM complex 000524** (CMR GPolygon: lon [−104.0997, −104.0742], lat [32.3504,
32.3916]; peak 5631 ppm·m at 32.357 N, −104.092 E) — the iconic ~3.3 km
press-release plume. This is the same provenance pattern as Goturdepe's bbox
(complex 000494). The secondary complex 000525 (~32.243 N, −104.054 E) is not the
press-release plume. The YAML's `location`/`bbox` were corrected to the
complex-000524 footprint with provenance.

## 4. Spatial cross-check vs NASA L2B

| Pearson (our ortho enhancement vs NASA L2B CH4ENH) | value |
|---|---|
| full scene | **0.527** |
| plume bbox | **0.518** |
| strong-signal subset (either > 200 ppm·m) | 0.036 |

Our independent retrieval reproduces NASA's broad spatial structure (full-scene
r ≈ 0.53), **degraded vs Goturdepe's 0.735** — an honest generality result. The
strong-signal subset r is low: at the plume scale the pixel-wise agreement is poor
(see §5b).

## 5. Quantification — NASA-footprint-anchored (the CROSS-CHECKED approach)

### 5a. Why not our own segmentation — a generality finding

Goturdepe's plume dominated its scene, so our Varon self-segmentation isolated it
cleanly. The Permian plume is **weak relative to scene clutter**: our
self-segmentation grabbed a 171-pixel confuser (NASA-mean over that component was
**−35.9 ppm·m** — i.e. not NASA's plume at all). So `self_segmentation_isolated_plume
= False`. This is a real limit of the simplified narrow-window matched filter (no
dominant-PC removal / Monte-Carlo bagging — explicitly out of scope per
`constants.py`) on a bright, heterogeneous surface, and it is the kind of
scene-specific shortcut Sprint 7 was meant to surface.

For a CROSS-CHECKED event we therefore anchor the plume mask to **NASA's published
footprint** (NASA L2B > 200 ppm·m inside complex 000524's bbox; 123 px, 0.379 km²,
L = √A = 615 m) and integrate **our** independent enhancement over it. The magnitude
is entirely ours; NASA defines only *where* the plume is.

### 5b. Result + cross-check

| quantity | value |
|---|---|
| **Q (ours, over NASA's complex-000524 footprint)** | **0.85 t/hr** |
| **Cross-check: NASA's OWN L2B, same footprint + IME/Varon method** | **0.88 t/hr** |
| ours/NASA integrated-mass ratio | **0.96×** |
| Q range with all uncertainty | [0.57, 1.15] t/hr |
| footprint mean enhancement (ours / NASA) | 354.5 / 368.9 ppm·m |
| pixel-wise Pearson on the footprint | 0.137 |
| background clutter σ (ours) | 289 ppm·m (Goturdepe's was higher, 423) |

The integrated-mass agreement is the headline: **our independent retrieval and
NASA's own L2B give the same flux over the published footprint to within 4%**
(0.85 vs 0.88 t/hr). The pixel-wise Pearson on the footprint is low (0.137) because
the plume is weak relative to clutter — the masses agree even though pixel-level
co-registration does not. Background σ shows Permian is **not** unusually noisy
(289 vs Goturdepe's 423 ppm·m); the difference is plume *strength*, not scene noise.

### 5c. The +1.46× MF-amplitude systematic does NOT transfer

Goturdepe measured ours/NASA ≈ **+1.46×** (our matched filter over-amplified). The
Stage A report flagged that its transfer to a new scene was unvalidated. Here the
measured ratio is **0.96×** (ours slightly *low*) — the systematic flips sign and
does not transfer. This is the first cross-scene data point on transferability, and
it refutes carrying +1.46× as a universal correction. The budget records both.

## 6. The 18.3 t/hr figure — context only

The 18.3 t/hr is a NASA JPL press-release value (25 Oct 2022) with **no observation
date, no granule, no method, and no uncertainty** (WebFetch-confirmed in Stage A).
The granule was pinned to 2022-08-26 by NASA's plume-complex catalogue + the
Sept 13–Jan 6 EMIT power outage — *not* by the press release, which names no date.
So its correspondence to this overpass is inferred, not established, and
super-emitter intermittency makes a same-site / different-day comparison
meaningless.

Decisively: **NASA's own L2B enhancement, run through the same IME/Varon
single-overpass method over the published footprint, also yields ~0.9 t/hr — about
21× below 18.3.** The ~20× gap is therefore a method/definition difference (the 18.3
is not an IME/Varon single-overpass estimate), not a failure of our retrieval. We
report ours (~0.85 t/hr) and theirs (18.3, context) and never frame their agreement
or disagreement as validation.

## 7. Scene checks (re-run, not assumed)

- **Wind regime:** ERA5 |U₁₀| at the footprint centroid = **3.58 m/s**, inside the
  Varon 2–8 m/s calibration range; margin to the low boundary = **1.58 m/s** (not
  boundary-proximate, but on the lower half — reported explicitly per cardinal
  rule 4). U_eff = 1.87 m/s.
- **Wind source-vs-centroid:** source S (top-5% upwind footprint pixels) is 0.90 km
  from the centroid; both fall in the same 0.25° ERA5 cell, so ΔQ = **0.0%**
  (re-run for this scene, not assumed from Goturdepe's 0.5%).
- **Mask sensitivity:** sweeping the NASA-footprint threshold {100, 200, 500} ppm·m
  gives a Q half-spread of 0.245 (fractional). This is the dominant budget term —
  the weak/clutter-limited plume makes the mask choice matter more than for
  Goturdepe.

## 8. Uncertainty budget (from scratch)

| term | fractional |
|---|---|
| wind α₁ | (see q_estimate.json) |
| wind U₁₀ | (see q_estimate.json) |
| wind combined | 0.261 |
| mask (footprint-threshold) sensitivity, half-spread | 0.245 |
| **symmetric combined** | **0.358** |
| MF amplitude (measured this scene, one-sided) | 0.96× |
| MF amplitude (carried Goturdepe prior, transfer test) | 1.46× (does not transfer) |

## 9. Tier verdict — CROSS-CHECKED, and exactly why

- **Earned:** a NASA L2B CH4ENH raster exists → spatial Pearson (full 0.527) **and**
  integrated-mass cross-check over the published footprint (ours 0.85 vs NASA 0.88
  t/hr, 0.96×). The independent per-granule k makes this possible with no NASA
  target spectrum — the capability the sprint set out to prove.
- **Not VALIDATED:** no peer-reviewed per-source flux; 18.3 t/hr is press-release
  context. The pixel-wise plume-scale agreement is weak (r = 0.137) and our
  self-segmentation cannot isolate this plume unaided.
- **Honest limits surfaced (generality dividends):** (i) self-segmentation fails on
  a weak plume in a busy scene → we anchor to NASA's footprint; (ii) the +1.46×
  amplitude systematic does not transfer; (iii) surface state must come from ERA5,
  not a sea-level default, at elevation.

See `docs/reports/sprint7_stage_b_report.md` for the gate report and the exact
committed numbers.

## Stage C attribution — confidence-tier precedent (cross-event)

Stage C ran facility-level attribution on the dense Permian OGIM subset (see
`docs/reports/sprint7_stage_c_report.md`). It established a **cross-event tier
precedent** worth recording for future events:

- **MODERATE requires the spatial claim to be robust to the stated localization
  uncertainty.** Goturdepe earned field-level MODERATE because its back-projected
  source S sits *inside* a 133 km² field polygon — a containment that survives the
  same wind/localization wobble that the uncertainty budget carries.
- **A discrimination resting on margins within the noise is LOW**, however clearly it
  ranks. Permian's nearest-*centerline* candidate (the GOONCH FEDERAL COM 0409 pad)
  is favored only on an **angular** margin (~0.4° vs ≥13°); it is not even the
  distance-closest well (ARTEMIS FEDERAL COM #002 is, at 0.26 km), the angular
  discriminator rests on the self-declared weakest-link half-angle, and the distance
  margins (~0.3–1.6 km) are comparable to S's ~1 km NASA-inherited positional
  uncertainty. The data **ranks** candidates but cannot **establish** one, so every
  facility hypothesis is capped at **LOW** (`FAC_CEILING`), enforced by test.

This is the dense-coverage analogue of Goturdepe's sparse-coverage finding: in both,
the honest headline is the *limit of attribution*, not a named culprit — and the tier
reflects discrimination power, not proximity alone.
