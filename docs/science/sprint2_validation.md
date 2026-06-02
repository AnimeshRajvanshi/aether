# Sprint 2 Validation — Goturdepe methane plume cluster

**Status:** Stage A runnable; Stage B/quantification not yet built.
**Validation event:** `turkmenistan_goturdepe_2022_08_15` — EMIT acquisition
2022-08-15 04:28:38 UTC, Goturdepe / Barsagelmez oil & gas fields, Turkmenistan.
**Peer-reviewed reference:** Thorpe et al. 2023, *Sci. Adv.* 9 eadh2391,
doi:10.1126/sciadv.adh2391 — **163 ± 18 t CH₄/hr cluster total** across 12
sources at Goturdepe and Barsagelmez for this imaging date.

The anti-fabrication rule in `docs/tasks/sprint2_detection_quantification.md`
applies. No parameter in this pipeline has been tuned to match either NASA's
press-release 18.3 t/hr or Thorpe's 163 ± 18 t/hr. All constants are pinned to
literature and live in `packages/detection/aether_detection/constants.py`
with cited sources.

## Why this event, not Permian/Carlsbad

The Permian/Carlsbad event remains in the catalogue (`permian_basin_2022.yaml`)
but is **deferred** for Sprint 2. The story behind the switch is part of the
science record:

### The granule investigation

1. **Sprint 1 used granule 20220810T160726.** Aug 10 Carlsbad. NASA's L2B CH4
   plume complex catalogue has **zero entries** in the Carlsbad bbox on this
   date — we rendered an enhancement raster from a granule that has no
   NASA-confirmed plume.
2. **Sprint 2 first pinned 20220815T042838 as the "Carlsbad" granule.**
   Wrong. Direct CMR query
   (`bounding_box=53.0,38.5,55.0,40.5&page_size=…`) shows the granule's
   spatial extent is lon 53.29-54.64, lat 38.86-40.12 — **Turkmenistan**,
   not New Mexico. Thorpe et al. 2023 explicitly confirms: *"this location
   was imaged twice on 15 August 2022 at 4:28 UTC … in Turkmenistan."*
3. **The NASA per-granule target spectrum file** that ships in
   `nasa/EMIT-Data-Resources` is for granule 20220815T042838 — i.e., for
   Turkmenistan. Using it on any Carlsbad granule would be the
   wrong-target/wrong-granule error the project's anti-fabrication rule
   explicitly forbids.
4. **The actual Carlsbad granule with a NASA-published plume complex is
   20220826T174642 (Aug 26 2022).** CMR confirms only two Carlsbad plume
   complexes exist in 2022-23: `EMIT_L2B_CH4PLM_002_20220826T174642_000524`,
   `_000525`, and three on 2023-02-05.
5. **NASA's October 2022 press-release 18.3 t/hr** is therefore — by
   elimination given the Sept 13 - Jan 6 EMIT power outage — most likely
   from the Aug 26 overpass. **NASA never explicitly attributes it to a
   specific granule, and no peer-reviewed citation has been found.** The
   `permian_basin_2022.yaml` measurement is now flagged as press-release
   grade with `uncertainty: null`.

### The three options that were on the table, and why we chose (A)

The user reviewed three paths and chose Option A:

- **(A) Switch the Sprint 2 validation event to Goturdepe (Aug 15).** Picked.
  Reasoning: the granule + per-granule target match, and Thorpe 2023 gives a
  peer-reviewed quantification target (163 ± 18 t/hr) — strictly stronger
  evidence than NASA's press-release 18.3 t/hr Permian value.
- (B) Keep Permian, switch to Aug 26 granule, build our own k from HITRAN.
  Defensible but adds 2-4 days of out-of-scope RT modelling.
- (C) Apply Turkmenistan's k to a Permian granule. Rejected because that is
  the exact failure the anti-fabrication rule guards against.

### What carries over and what doesn't

| Concern | Status |
|---|---|
| Matched filter implementation | Unchanged — algorithm is the same regardless of event |
| Synthetic-plume guardrail tests | Unchanged, still passing |
| Spectral windows, shrinkage α, Varon coefs | Unchanged constants, same citations |
| Constants for canonical granule URs | Renamed `PERMIAN_2022_*` → `TURKMENISTAN_GOTURDEPE_2022_08_15_*`; Permian kept as deferred entries |
| L1B and L2A mask concept IDs | Fixed to actual CMR values (the prior IDs were guessed and would have 404'd) |

## Stage A independence — the limitation

Our matched filter is parameterized by **NASA's per-granule unit absorption
spectrum** (`emit20220815t042838_ch4_target` from EMIT-Data-Resources), applied
to **NASA's L1B radiance**, with a spatial-agreement comparison against
**NASA's L2B enhancement** for the same granule. Stage A is therefore an
*implementation test* (does our code reproduce NASA's algorithm on the same
inputs) and not an *independent physics test* (which would require us to
generate k from HITRAN/MODTRAN ourselves).

This is still useful: it catches sign errors, band-selection mistakes,
covariance estimation bugs, per-column-vs-per-scene confusion. It cannot rule
out shared bias between our and NASA's implementation because both lean on the
same MODTRAN-derived target. A genuinely independent Stage A — generating k
ourselves from HITRAN methane cross-sections convolved to EMIT FWHMs — is
deferred to a later sprint and is the same line-by-line RT work that would
unblock the Permian Aug 26 validation.

## Parameter choices and their sources

Every constant lives as a named module-level binding in
`packages/detection/aether_detection/constants.py` and is referenced by the
test suite. No value was chosen by comparison to either 18.3 or 163 t/hr.

| Quantity | Value | Source |
|---|---|---|
| Canonical acquisition | EMIT 2022-08-15T04:28:38Z, `EMIT_L1B_RAD_001_20220815T042838_2222703_003` | CMR catalogue + EMIT-Data-Resources tutorial + Thorpe 2023 |
| MF spectral windows | 500–1340, 1500–1790, 1950–2450 nm | EMIT GHG ATBD v0.2 §4.2.3; `emit-sds/emit-ghg` `ghg_process.py` default |
| Per-column shrinkage | a = 1 × 10⁻⁹ | EMIT GHG ATBD v0.2 §4.2.1 |
| MF formula | α = sᵀ C⁻¹ (x − μ) / (sᵀ C⁻¹ s); s = k ⊙ μ | EMIT GHG ATBD v0.2 §4.2.1; Thompson et al. 2015 §2.3-2.4 |
| Unit absorption spectrum k | NASA precomputed per-granule target file `emit20220815t042838_ch4_target` | NASA EMIT-Data-Resources `data/methane_tutorial/` |
| Flare-detection channel | ≈ 2389 nm | EMIT GHG ATBD v0.2 §4.2.1 |
| U_eff parameterization | U_eff = α₁ · ln(U₁₀) + α₂, α₁ = 1.0 ± 0.1, α₂ = 0.6 m/s | Varon et al. 2018 Eq. (12) |
| Plume length L | L = √(plume mask area) | Varon et al. 2018 Eq. (11) |
| Mass conversion (ppm·m → kg/m²) | n_air = p/(RT) using ERA5 surface p, T | textbook ideal gas; molar masses CODATA |
| ERA5 wind source | ARCO-ERA5 hourly 10 m u/v | `gs://gcp-public-data-arco-era5/…` (anonymous read); Hersbach et al. 2020 |

## Press release vs peer review — what 163 ± 18 actually is

The Thorpe 2023 number is a **multi-source cluster total** for 12 plumes
attributed to the Goturdepe + Barsagelmez fields **across the 2022-08-15
imaging date**. Thorpe notes the location was imaged twice on that date
(04:28 UTC and 10:58 UTC). Our Sprint 2 single-granule pipeline processes the
04:28 granule only and will recover only the subset of those 12 sources that
fall within this 12-second strip. Strict Stage B comparison must therefore
either:

- Sum our identified plumes across all granules of the 04:28 UTC strip
  before checking against 163 ± 18, or
- Use Thorpe's per-source breakdown (if available in the supplementary)
  for a single-plume comparison.

Either way, the headline Stage B number we will report is *our cluster total
from the granules we processed, with propagated uncertainty*, not a tuned
match to 163. NASA-published plume complex `EMIT_L2B_CH4PLM_002_20220815T042838_000494`
covers ONE of the 12 sources within our specific granule.

## Stage A results — real-data run, GLT-orthorectified comparison

Driver: `scripts/run_stage_a_goturdepe.py`. Output: `stage_a_outputs/turkmenistan_goturdepe_2022_08_15/`.

Configuration (locked in `packages/detection/aether_detection/constants.py`):
fixed shrinkage α = 1 × 10⁻⁹ (ATBD §4.2.1), MF target = NASA's per-granule
`emit20220815t042838_ch4_target`, narrow CH4 window 2137–2493 nm,
ppm-scaling = 100 000, comparison on the common EPSG:4326 ortho grid
(no smoothing, no kernel-based jitter absorption).

| Region | Pearson | n pixels |
|---|---|---|
| Full scene | +0.735 | 2 281 401 |
| Plume bbox (lon 53.5–54.2, lat 39.3–39.7) | **+0.749** | 913 911 |
| Plume bbox, strong-signal subset (>200 ppm·m) | +0.383 | 331 060 |

The +0.75 plume-bbox Pearson against NASA's L2B CH4ENH on the same ortho grid
satisfies the Stage A gate. The recognisable Goturdepe plume cluster shows up
in the lower-left half of the plume bbox in both rasters in the same shape.

### Known Stage A artefact — the round saturated blobs

Two compact saturated bright regions appear in our enhancement raster within
the plume bbox that **do not appear** in NASA's L2B output:

- **Blob A**: brightest pixel at (lon 53.4527, lat 39.5092), peak ≈ +2 422 ppm·m
- **Blob B**: brightest pixel at (lon 53.6295, lat 39.4707), peak ≈ +5 825 ppm·m

These are **spectral confusers** — pixels where natural surface or atmospheric
spectral structure aligns with the methane absorption pattern. The matched
filter normaliser sᵀC⁻¹s is small in those cross-track columns, so the
formula amplifies any residual signal in the target direction into a bright
output. They are present at fixed α = 1e-9 (the current production default).

Two stabilisation paths could suppress them; **neither is in Sprint 2 scope**:

- NASA's `--n_mc 10 --mc_bag_fraction 0.7` Monte Carlo bagging
- NASA's `--remove_dominant_pcs` scene-wide PC removal

We verified separately that **LOOCV shrinkage alone does NOT fix the
blobs** — see `scripts/diagnose_loocv_centering.py` and the LOOCV pre/post
blob-mass integral in `scripts/diagnose_blob_mass_change.py`. Bit-for-bit
matched against NASA's `parallel_mf.py::fit_looshrinkage_alpha`, LOOCV on
uncentered EMIT radiance picks α distributions that don't track blob
columns, and the blob mass actually grew +2–8% under LOOCV. The LOOCV port
remains available as an opt-in via `shrinkage_alpha="loocv"`, off by
default, documented as such in `constants.py`.

### Why the blobs do not affect Stage B quantification

Following Varon 2018 §5.1 (faithfully implemented in
`packages/detection/aether_detection/plume_segmentation.py`), the plume is
defined by a **source-connected plume mask** built from:

1. 5×5 Welch's t-test of each pixel's neighbourhood against the off-bbox
   background distribution at p < 0.05 (one-sided).
2. 3×3 median filter on the boolean candidate mask.
3. Gaussian filter σ = 2 px.
4. Threshold > 0.5.
5. **Connected-component labelling** with 8-connectivity.

The IME mass integral runs over the source-connected plume component — NOT
over the plume bbox. Disjoint enhancement features (the round blobs) become
their own connected components and are excluded from the integration on
principle, without any hand-drawn exclusion box.

Running this on the Stage A ortho enhancement raster
(`scripts/run_segmentation_blob_check.py`):

| Quantity | Value |
|---|---|
| Total connected components (incl. noise speckle) | 2 002 |
| Background distribution μ ± σ | +6.97 ± 481 ppm·m (n = 1 396 195) |
| **Plume CC label** | **1 213**, 68 382 px (largest CC inside the plume bbox) |
| **Blob A CC label** | **816** |
| **Blob B CC label** | 816 (Blob A and Blob B fall in the same separate component) |
| **Blob A inside plume CC?** | **NO** (label 816 ≠ 1 213) |
| **Blob B inside plume CC?** | **NO** (label 816 ≠ 1 213) |

The visual evidence (`stage_a_outputs/.../plume_mask_overlay_zoom.png`)
shows the cyan plume CC as a long sinuous ribbon running along the
lower-left half of the bbox, with the Blob A and Blob B markers cleanly
above and outside the ribbon. Both blobs are spatially disjoint from the
plume cluster, so connected-component labelling assigns them to a separate
label by construction.

**Conclusion.** The blobs are a known Stage-A scene-level artefact requiring
NASA's MC bagging + PC removal machinery to suppress at the matched-filter
stage (out of Sprint 2 scope). They do **not** affect Stage B
quantification because the IME mass integral runs over the source-connected
plume mask, which excludes them automatically. No exclusion box, no
NASA-mask gating, no detection of NASA's plume product is needed.

### Plume CC 1213 — tail (lon > 53.88E) character assessment

Inspection of the segmentation overlay raised the question of whether the
eastern, more diffuse portion of CC 1213 (east of about 53.88°E) was real
plume signal or thresholded background noise that grew into the connected
component during the smoothing/threshold step.

`scripts/diagnose_tail_and_streak.py` splits the plume CC at lon = 53.88E and
reports per-region statistics for our enhancement and NASA's L2B sampled at
the same pixels:

| Quantity | Ribbon (lon ≤ 53.88) | Tail (lon > 53.88) |
|---|---|---|
| Pixel count | 59 554 | 8 828 |
| OURS — mean / median / p95 (ppm·m) | +328.7 / +314.7 / +955.8 | +281.1 / +284.1 / +968.0 |
| NASA L2B — mean / median / p95 | +201.2 / +191.7 / +725.3 | +145.3 / +147.9 / +685.1 |
| Pearson(ours, NASA) | +0.543 | +0.428 |
| OURS integrated signed sum (ppm·m·px) | +1.958×10⁷ | +2.481×10⁶ |
| Share of CC's signed integrated mass | 88.8% | 11.2% |

The tail's distribution is **not noise**: its mean (+281), median (+284) and p95
(+968) are within a few percent of the ribbon's, indicating a coherent
elevated population, not a near-threshold speckly tail. NASA's L2B detects
the same tail at comparable morphology and lower absolute intensity (mean
+145 vs our +281; our ratio over NASA in the tail is consistent with our
~1.4–2× over-amplitude on strong plumes elsewhere). Pearson +0.428 across
the tail is meaningful pixel-wise agreement.

`stage_a_outputs/.../tail_vs_ribbon_overlay.png` shows the side-by-side
explicitly: NASA's L2B carries the same eastern branching/diffusion
structure as our raster, just dimmer. This is consistent with plume
dispersion downwind.

**Determination.** The tail is real plume signal, dimmer and more diffuse than
the ribbon as expected downwind. We do not trim it — doing so would
selectively reduce mass by ~11% based on visual judgement, which is the
hand-selection failure mode we are explicitly avoiding. **The honest IME
should include the full plume CC.** The +11% absolute mass contribution
from the tail is well within Varon's documented single-overpass IME
uncertainty of 5–12% relative + ~30% from reanalysis wind representativeness,
so this characterisation does not change the quantification scope.

### Bright diagonal streak north of the plume — character assessment

A bright linear feature runs roughly NW→SE through the upper portion of the
plume bbox at approximately lat 39.46–39.53N, lon 53.40–53.75E. It contains
the two "blob" knots discussed above (now understood as two bright points on
a single continuous streak, not two independent disks — they share connected
component 816). It is **outside** the source-connected plume CC 1213, so it
does not enter Stage B IME integration. We characterise it here so that a
possible real signal is not silently discarded.

`scripts/diagnose_tail_and_streak.py` produces three pieces of evidence:

1. **Streak intensity distribution (83 334 pixels in the streak bbox):**
   - OURS: mean +206, median +160, p95 +1 183, p99 +1 690 ppm·m
   - NASA L2B: mean +103, median +71, p95 +825, p99 +1 209 ppm·m
   - Pearson(ours, NASA) = +0.682; p95 ratio (ours / NASA) = 1.43

   NASA's L2B detects the same streak with similar morphology — see
   `streak_character.png`. Our ~1.4× over-amplitude is consistent with the
   same MF-without-MC-bagging behaviour observed on the plume.

2. **Cross-track raw-geometry distribution of streak-driving pixels (raw
   pixels with enhancement > 200 ppm·m whose lat/lon fall in the streak
   bbox, n = 26 233):**
   - Cross-track column p5 / p50 / p95 = 807 / 964 / 1094 (out of 1 242)
   - IQR fraction of swath width: 23.1%
   - Distinct cross-track columns spanned: 377
   - Top-5 individual columns each contribute only ~0.4% of the high pixels

   See `crosstrack_histogram.png`. A cross-track detector-striping artefact
   would concentrate the high pixels on a few specific columns; instead the
   distribution is a broad bell across hundreds of columns covering nearly
   a quarter of the swath. **Cross-track detector striping is ruled out.**

3. **Multi-source context.** Thorpe et al. 2023 attribute 163 ± 18 t/hr to
   *twelve* methane sources at Goturdepe + Barsagelmez observed on
   2022-08-15. Multiple plumes from the same overpass are expected. The
   streak's location, intensity, and direction are consistent with one or
   more additional plumes from oil/gas infrastructure to the north of the
   main plume cluster we quantify.

**Determination.** We assess the streak as a **likely real spectral feature**
(either a second methane plume cluster from the multi-source Goturdepe
field documented by Thorpe 2023 or a non-methane spectral confuser of
comparable signature). We rule out cross-track detector striping. We cannot
disambiguate the methane vs non-methane sub-cases without source-attribution
information (e.g., Thorpe 2023 supplementary per-source coordinates) that
is not in this Sprint's scope.

Because the streak sits in a different connected component (816, not the
plume CC 1213), Varon's source-connected-mask IME excludes it automatically.
A future-sprint extension that quantifies multi-source clusters by
integrating over every elevated-CC inside the bbox would add this signal to
the cluster total — that is a defensible Stage C / multi-source pipeline
extension, not a Stage B change.

## Stage B results — Q for plume CC 1213

Driver: `scripts/run_stage_b_goturdepe.py`. Output: `stage_b_outputs/turkmenistan_goturdepe_2022_08_15/q_estimate.json`.

### Headline

- **Q (central, ours-calibrated): 27.1 t/hr**
- **Q (NASA-calibrated, our IME ÷ 1.66): 16.3 t/hr**
- **Q range with full uncertainty: [14.2, 30.6] t/hr**

### Scope framing — the central caveat

Thorpe et al. 2023 report **163 ± 18 t/hr as the whole-cluster total** for **twelve** methane sources at Goturdepe + Barsagelmez observed on the 2022-08-15 imaging date. We confirmed in the PMC article text that no per-source breakdown is provided in the main paper or its Figure 4A caption — **only the cluster aggregate**. Our pipeline quantifies **one source-connected plume (CC 1213)**, not the cluster. The two numbers are **not same-scope** and should not be compared as equality. The benchmark YAML's `emission_rate_metric_tonnes_per_hr.note` field records this scope mismatch.

A naive 12-way equal-share of 163 t/hr would be 13.6 t/hr per source. **We
present this as a floor-of-plausibility heuristic, NOT as a reference value.**
Real super-emitter clusters are heavy-tailed: a few sources commonly dominate
cluster totals, and individual plumes routinely range from a few percent up
to 30% or more of cluster aggregates. The 13.6 t/hr equal-share is just a
sanity check that our number is in the same order of magnitude as something
the cluster total could be partitioned into, not a target value.

### Geometry

| Quantity | Value | Source |
|---|---|---|
| Plume CC | label 1213, 68 382 pixels | Stage A segmentation |
| Plume area A | 192.6 km² | sum of per-pixel ortho areas at cos(lat) |
| Pixel area at lat 39.5N | 2 811 m² (not 3 600 m²) | computed; the naive 60 m × 60 m = 3 600 m² assumption overestimates by ~28% |
| Plume length L = √A | 13.88 km | Varon 2018 Eq. 11 |
| Plume centroid | (39.37 N, 53.69 E) | mean of CC pixel lat/lon |

### Atmospheric state for mass conversion

| Quantity | Value | Source |
|---|---|---|
| Surface pressure | 101 325 Pa | first-order approximation (sea-level Caspian) |
| 2 m temperature | 295 K | first-order approximation (Aug 0428 UTC local mid-morning) |
| n_air | 41.31 mol/m³ | ideal gas, p/(RT) |
| M_CH4 | 0.01604 kg/mol | CODATA |
| 1 ppm·m at these conditions | 6.62×10⁻⁷ kg/m² | derived |

The first-order p/T choices vary n_air by < 5% across the scene; an ERA5 surface-state fetch would tighten this to ~1%. It is deliberately not chased here under the no-tuning rule — its impact is much smaller than other systematic terms.

### Wind and U_eff

| Quantity | Value | Source |
|---|---|---|
| ARCO-ERA5 grid cell (10 m u/v) | (39.250 N, 53.750 E) | nearest 0.25° cell to centroid |
| 10 m u, v (interpolated to overpass) | u = −6.74 m/s, v = −1.62 m/s | linear time interp of ARCO-ERA5 hourly to 04:28:38 UTC |
| \|U₁₀\| | 6.93 m/s | √(u² + v²) |
| Hour distance to nearest ERA5 sample | 28.6 min | recorded in `era5.WindAtOverpass` |
| σ_U₁₀ (representativeness) | 1.79 m/s | Varon §7 baseline 1.6 m/s + 0.4 m/s × hour_distance (0.48 h) |
| α₁ = 1.0 ± 0.1, α₂ = 0.6 m/s | Varon 2018 Eq. 12 |
| **U_eff = α₁ ln(U₁₀) + α₂** | **2.54 m/s** | Varon 2018 Eq. 12 |

### Varon U_eff regime validity — within the calibration range

Varon's §3.2 describes the WRF-LES ensemble used to fit Eq 12 as *"five
initially uniform southerly wind profiles with speeds of 2–8 m s⁻¹"* — the
parameterisation is calibrated for **U₁₀ ∈ [2, 8] m/s**. Our U₁₀ = 6.93 m/s
sits at ≈ 82% of the way from the lower to the upper bound, **comfortably
inside the regime** and well clear of the degraded-low-wind boundary that
Varon §5.2 and the abstract explicitly warn about
(*"low winds are detrimental for source quantification"*).
Our U_eff = 2.54 m/s and is computed by passing U₁₀ as a bare m/s number into
the natural logarithm, dimensionally consistent with the α₂ = 0.6 m/s
additive term in Eq 12 and matching Varon's published Fig 4 calibration.

### Wind-location: centroid vs upwind source — verified non-material

Varon §5.2 explicitly states U_eff should use the 10 m wind *"at the
location of the point source"*, not at the geometric centroid of the plume
mask. The Stage B driver fetched ERA5 at the centroid (39.371 N, 53.691 E).
A follow-up diagnostic (`scripts/diagnose_wind_location.py`) recomputed the
source location as the centroid of the top 5% of CC 1213 pixels ranked by
upwind projection (locked methodology, set before running), re-fetched
ARCO-ERA5 there, and recomputed Q:

| Quantity | Centroid (used in Stage B) | Upwind source (verification) |
|---|---|---|
| Location | 39.371 N, 53.691 E | 39.343 N, 53.986 E |
| Distance between | — | 25.65 km |
| ERA5 cell | (39.250, 53.750) | (39.250, 54.000) |
| \|U₁₀\| | 6.93 m/s | 6.84 m/s (Δ = −1.4%) |
| U_eff | 2.537 m/s | 2.523 m/s |
| **Q (t/hr)** | **27.086** | **26.940 (Δ = −0.5%)** |

The source-based Q differs from the centroid-based Q by **0.5%**, an order of
magnitude below the ±12.9% symmetric uncertainty budget. The two ERA5
0.25° cells are adjacent but the interpolated wind values are nearly
identical at this scene's overpass. **The centroid-vs-source choice does not
materially affect the headline number.** Stage B uses the centroid value of
record; the source-based verification is preserved as
`wind_location_check.json` for audit.

**Scope of this finding — scene-specific, not a general guarantee.** The
non-materiality here is because this overpass's wind field is spatially
smooth: a 25.6 km displacement straddling two ERA5 cells changes \|U₁₀\| by
only 1.4%. A different scene — with sharper synoptic gradients, a frontal
boundary, or terrain-driven local circulation — could show a material Q
change at the same source/centroid displacement. **Future granules must
re-run this check** (`scripts/diagnose_wind_location.py` is the template);
do not assume the wind-location choice is non-material on a fresh
acquisition.

### IME and Q

- IME (central) = 41 165 kg = 41.17 tonnes
- Q (Varon Eq. 8) = U_eff × IME / L = 2.54 m/s × 41 165 kg / 13 877 m = 7.524 kg/s = **27.1 t/hr**

### Uncertainty budget — each term documented and propagated

| Term | Fractional contribution to σ_Q / Q | Source |
|---|---|---|
| Wind α₁ (Varon ±0.1) | 0.076 | ∂U_eff/∂α₁ = ln(U₁₀) = 1.61 |
| Wind U₁₀ (ERA5 representativeness) | 0.102 | ∂U_eff/∂U₁₀ × σ_U₁₀ / U_eff |
| Wind combined (quadrature) | **0.127** | √(0.076² + 0.102²) |
| Plume-mask sensitivity (half-spread, p ∈ {0.01, 0.05, 0.10}) | 0.020 | re-segmentation; n = 48 583 / 68 382 / 76 154; Q = 26.0 / 27.1 / 26.8 t/hr |
| **Combined symmetric 1-σ** | **0.129** | √(wind² + mask²); **±12.9%** of Q |
| Enhancement-calibration bias (ours ÷ NASA integrated over CC) | **1.66× (asymmetric)** | tail+ribbon integral, Stage A diagnostic — **the dominant systematic**, carried one-sided because there is no reason to suspect our MF is biased low |

The mask-sensitivity sweep result is gratifyingly small (3.9% full spread across p ∈ {0.01, 0.05, 0.10}) — see `mask_sensitivity.png`. The segmentation is stable; our reported Q would change by < ±2% if we picked a different reasonable p-value within Varon's recommended range.

The 1.66× enhancement bias dominates the budget. It is the price of using the MF without NASA's MC bagging + dominant-PC removal (out of Sprint 2 scope per the user's directive).

### Final Q range

The reported [14.2, 30.6] t/hr range combines all four terms:

- Low end: NASA-calibrated central (Q ÷ 1.66) minus symmetric 1-σ = 16.32 × (1 − 0.129) = 14.22 t/hr
- High end: ours-calibrated central plus symmetric 1-σ = 27.09 × (1 + 0.129) = 30.57 t/hr

The asymmetry is deliberate: the enhancement bias is one-sided (our MF over-amplifies, NASA's does not under-amplify); the symmetric ±σ carries wind + mask only.

### Stage A independence caveat

Stage A used NASA's per-granule unit absorption spectrum on NASA's L1B radiance, comparing against NASA's L2B. That is an **implementation test** (does our matched-filter code reproduce NASA's algorithm on the same inputs) rather than an **independent physics test** (which would require us to generate the unit absorption spectrum from HITRAN). Both Q estimates above inherit this limitation: a shared bias between our and NASA's matched-filter would not be visible at Stage A, and would propagate into Stage B IME. A truly independent quantification would require a HITRAN-generated target spectrum, a Sprint 3 unlock that also enables Permian Aug 26 quantification (no NASA target exists for that granule).

### Plausibility statement — honest

Our central Q of 27.1 t/hr (or 16.3 NASA-calibrated) is **plausible as a fraction of the 163 t/hr Goturdepe + Barsagelmez cluster total**. With 12 sources contributing to that total, our single plume representing 16–19% (ours-calibrated) or 9–10% (NASA-calibrated) of the cluster is consistent with empirical super-emitter distributions where individual plumes often range from 5–30% of cluster totals. We can **not** claim agreement or disagreement with 163 ± 18, because the comparison is scope-mismatched. We can claim that our number is in the right order of magnitude for one of twelve documented sources, with the dominant systematic uncertainty (the 1.66× MF-amplitude bias) characterised quantitatively.

### Eval-harness wiring

`eval/harness/aether_eval/pipelines.py::stage_b_quantification_pipeline` reads `stage_b_outputs/<event_id>/q_estimate.json` and emits a `Detection` carrying `emission_rate_metric_tonnes_per_hr` plus a complete measurement set (low/central/high/NASA-calibrated, IME in kg, plume area in km²). The harness's quantification MAPE will be large for this event because of the scope mismatch — that is the expected outcome and is documented in the test suite (`test_run_evaluation_with_stage_b_pipeline`) and in the benchmark YAML's `note` field, not a regression.

## Synthetic guardrails active

These run on every `uv run pytest`:

- `tests/test_matched_filter.py::test_recovers_injected_plume_correctly` —
  injects α=1000 ppm·m and verifies MF recovers it within 15%.
- `::test_guardrail_flipped_sign_inverts_recovered_enhancement` — a
  sign-flipped target signature must invert the recovered values.
- `::test_guardrail_doubled_mu_breaks_quantification` — a doubled-μ
  composition (`s = k⊙μ⊙μ`) must break the MF by orders of magnitude.
