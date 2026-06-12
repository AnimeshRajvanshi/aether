# Sprint 9 — Stage B — Heat Vertical: Anomaly Detection + Quantification — Gate Report

> Stage B of the heat vertical: baseline/climatology definition with measured
> sensitivities, AIR-lane anomaly detection and quantification analogues with
> budgets, the **pre-registered** station validation (criteria committed at
> `011c72c` BEFORE any station data was read — docs/science/
> sprint9_heat_validation.md), the LST lane under its observation-time caveat,
> and the Delhi UHI analysis. **STOP at this gate for review.**

## Verdict — what was earned

**Per the pre-registered criteria (no threshold touched after seeing data):**

| claim | reference | verdict |
|---|---|---|
| **C1 — peak 2 m Tmax 46.68 °C** (Apr 10) | ISD stations (instrument truth; window max 45.0 °C, Δ1.68 K ≤ 2.5 K) | **V1 PASS → VALIDATED** |
| **C2 — window-mean regional anomaly +5.10 K** (native; 4.50 K on the 1° common grid) | IMD gridded (ERA5-independent, station-derived: 4.31 K; Δ0.19 K ≤ 1.0 K; pattern r 0.874 ≥ 0.6) | **V3a+V3b PASS → VALIDATED** |
| C3 — duration 26 days (Mar 26–Apr 20) | IMD gridded same criterion: 7 days (Apr 5–11); Δ19 > 2 | **V4a FAIL → NOT validated** |
| C4 — peak-day extent 889,700 km² | IMD gridded on the common grid: 606,300 km²; Δ46% > 30% | **V4b FAIL → NOT validated** |
| ERA5↔station consistency | bias 0.37 K ✓, RMSD 1.05 K ✓, **pooled r 0.728 < 0.85 ✗** | **V2 FAIL → consistency NOT claimed** |

**The first VALIDATED-tier claims in Aether's history are C1 and C2 — and only
those, for 2 m air temperature, per quantity, exactly as the Stage A ruling
scoped.** Duration and extent are honestly NOT validated: both are
criterion-edge–dominated quantities where two station-true datasets disagree
substantially (§3). All LST quantities remain CROSS-CHECKED-ceiling, and the
UHI result is a sign-level finding (§5) that the observation-time caveat
exists to protect.

## 0. Gate-ruling compliance (Stage A review, four rulings)

1. **Window kept:** scan-selected 2022-04-02→11; the §Stage-A reconciliation
   with IMD's spell list stands as documentation. No swap.
2. **Pre-registration enforced by commit order:** criteria + thresholds
   committed (`011c72c`) before any ISD/IMD byte was read by analysis code;
   the V1–V4 verdicts below are the pre-registered metrics, unchanged. Any
   deviation is listed in §7 — none was needed.
3. **ADR 0004 landed:** area-event recall is bbox-overlap (≥ 0.5 of the
   smaller box); point events bit-identical (guard-tested); the YAML's
   `location_precision_km` is documentation only.
4. **LST observation time:** every LST quantity in this stage carries the
   measured Terra view time (10.68 h local solar) and the "before the
   diurnal LST peak / not a daily maximum" statement; the Aqua gap is restated
   wherever LST coverage is described; `check_runnable` is phenomenon-aware
   and the heat recipe is wired (the EMIT-shaped reason is gone, guard-tested).

## 1. Baseline / climatology definition (the science heart)

- **Definition:** per 0.25° cell, per day, mean of daily Tmax (max of hourly
  T2m over 06–13 UTC) over 1991–2020 × ±10-day window — 630 samples/cell/day.
  Identical construction on IMD's native 1.0° grid from its own data (each
  dataset vs its OWN climatology; anomalies never cross datasets).
- **Sensitivities (measured, pre-registered S1–S3):**

| sensitivity | result | reading |
|---|---|---|
| S1 — baseline halves (1991–2005 vs 2006–2020) | window-mean anomaly **5.51 vs 4.70 K** (half-spread 0.40 K); peak-day extent 1,001,100 vs 761,800 km² | **the dominant budget term**: the warming trend *inside* the normals period means "anomaly vs 1991–2020" is ~0.8 K hotter-looking than "anomaly vs the recent half" — stated, not hidden |
| S2 — day window ±10 → ±15 | 5.103 → 5.159 K (shift 0.056 K) | negligible |
| S3 — hour set 06–13 UTC vs full 24 h (event days, measured) | mean residual **0.0004 K**, p99 0.000 K, max 0.618 K (isolated cells) | the pre-registered hour set captures the daily max; the proxy concern from Stage A is retired by measurement |

**Baseline defense:** 1991–2020 (WMO standard normals) is kept as the
operational baseline — it is the convention reviewers and agencies use, and
every anomaly here names it. The S1 half-spread is carried as a first-class
budget term rather than "fixed" by cherry-picking a half-period; a
trend-aware baseline is a legitimate Stage C/D refinement if the reviewer
prefers it, and the committed per-half values make the conversion a constant.

## 2. AIR lane — quantification analogues (C1–C4) with budgets

Committed artifact: `stage_b_outputs/india_nw_heatwave_2022_04/air_lane.json`
(+ `anomaly_air_window_mean.png`). All values: ERA5 daily Tmax (06–13 UTC max),
anomalies vs own 1991–2020 ±10d climatology, bbox land cells.

- **C1 peak Tmax: 46.68 °C** on 2022-04-10 at (29.0 N, 72.5 E) — a border-region
  cell; the bbox legitimately spans the India–Pakistan border (the documented
  event includes southern Pakistan), and V1 brackets this gridded peak against
  *Indian* in-bbox stations (max 45.0 °C), so part of the 1.68 K gap is
  geography, stated here.
- **C2 anomaly:** peak regional-mean **+5.67 K on 2022-04-08** — the scan's
  anchor day confirmed at full rigor; window-mean regional-mean **+5.10 K**;
  peak cell **+11.88 K**.
- **C3 duration: 26 days (2022-03-26 → 2022-04-20)** at the ≥5%-area
  IMD-style criterion — the upgraded daily-Tmax definition merges the
  documented late-March wave (IMD's "26–31 Mar" spell) and the April wave into
  one continuous episode containing the canonical window. The 10-day canonical
  window remains the *analysis* window; the 26-day run is the *episode*.
- **C4 peak-day extent: 889,700 km²** (47.5% of bbox land) on 2022-04-08;
  essentially grid-stable (887,700 km² when computed on the 1° common grid).

### Budgets

**window-mean regional anomaly (central +5.10 K):**

| term | half-width |
|---|---|
| baseline halves (S1) | **0.40 K** (dominant) |
| day-window ±15 (S2) | 0.06 K |
| hour set vs 24 h (S3, measured) | 0.0004 K |
| ERA5-vs-station median bias (V2, measured) | 0.37 K (a *systematic*, sign +: ERA5 warm) |

**peak-day extent (central 889,700 km²):** baseline halves → [762k, 1,001k];
criterion family (p95 vs IMD-style) → 1,509k vs 890k — **the criterion choice
is the largest "uncertainty" and is really a semantics choice**; grid (1° vs
native) → −2k (negligible). Extent must always be quoted with its criterion.

**duration (central 26 d):** dataset family → ERA5 26 d vs IMD-gridded 7 d at
the same criterion — see §3 V4; duration at a fixed absolute criterion is not
robust across station-true datasets and is reported with that caveat, not as a
clean number.

## 3. Pre-registered validation (V1–V4) — executed after the criteria commit

Framing per the dependency graph (no cross-check claimed as more independent
than the graph allows):

Committed artifact: `validation.json` (per-station derived statistics with
provenance + the ISD license verbatim; raw station data never committed).

- **V1 (instrument validation of event temperatures) — PASS.** Max
  station-day Tmax across the 10 qualifying stations: **45.0 °C**; ERA5 bbox
  peak 46.68 °C; |Δ| = 1.68 K ≤ 2.5 K. The event's peak-temperature claim is
  checked against real thermometers. → **C1 VALIDATED.**
- **V2 (ERA5↔station consistency — assimilation-caveated) — FAIL, as
  pre-registered.** bias +0.37 K ✓ and RMSD 1.05 K ✓ pass comfortably, but
  pooled Pearson r = 0.728 < 0.85. **Consistency is therefore NOT claimed.**
  Exploratory diagnosis (committed as
  `validation_exploratory_minobs3.json`, labeled, NOT the verdict): the
  pre-registered ≥4-obs/day rule silently excluded 3-hourly synoptic stations
  (only 06/09/12 UTC fall in the hour range) — 100 of 110 stations dropped,
  leaving 10 stations × 10 days where the within-window temperature range is
  narrow and pooled r is fragile. With ≥3 obs (exploratory): 36 stations, 341
  station-days, bias 0.23 K, RMSD 1.67 K, **r = 0.946** — all inside the V2
  bounds. The pre-registered verdict stands; the gate may re-rule the
  criterion for Stage C/D with this diagnosis on the table.
- **V3 (anomaly vs the ERA5-independent station product) — PASS on both.**
  ERA5 4.50 K vs IMD 4.31 K on the common 1° grid (Δ0.19 K ≤ 1.0 K); spatial
  pattern r = 0.874 ≥ 0.6 over 130 common cells. Two products with different
  processing and error modes agree about the same upstream truth →
  **C2 VALIDATED** (with the dependency-graph framing, not as "independent
  reproduction").
- **V4a (duration) — FAIL.** ERA5 26 d vs IMD 7 d (Apr 5–11). At a fixed
  absolute criterion (40 °C + 4.5 K), a ~0.3–0.5 K systematic between
  datasets moves many cell-days across the threshold; ERA5's 06–13 UTC
  cell-mean Tmax runs slightly warm vs IMD's station-gridded Tmax (V2 bias
  +0.37 K measured at stations), and 1° station gridding smooths peaks.
  **Duration at this criterion is dataset-fragile — that finding IS the
  result.** → C3 NOT validated.
- **V4b (extent) — FAIL.** 887,700 vs 606,300 km² on the common grid (Δ46% >
  30%), same criterion-edge mechanism. → C4 NOT validated.

**Tier consequence:** the event earns **VALIDATED for exactly two
air-temperature claims (C1 peak, C2 regional anomaly)** — the first VALIDATED
claims on any Aether event — under the per-quantity scoping the Stage A gate
approved. C3/C4 remain CROSS-CHECKED-at-best (two station-true references
disagree); every LST quantity remains ≤ CROSS-CHECKED. The tier rubric
extension wording (per-quantity badges) is Stage D UI work and will cite this
section.

## 4. LST lane (ceiling: CROSS-CHECKED) — Terra ~10:30 snapshots, never a daily max

Committed artifact: `lst_lane.json` (+ `anomaly_lst_window_mean.png`).
**Measured mean day view time: 10.68 h local solar** — the observation-time
caveat as a number, attached to every LST output. No Aqua afternoon pass
exists for the window (Stage A measured gap), so nothing here is a daily
maximum.

- **L1 — MODIS LST anomaly (Terra-only, QC mandatory-good):** daily bbox-mean
  anomalies +3.13…+5.87 K across the window; **window mean +4.60 K** vs the
  2013–2021 same-composite-period Terra climatology (9 samples per
  tile/period). The day-by-day shape tracks the AIR lane's (both peak around
  Apr 6–8), reported as coherence, not equivalence — different physical
  quantities.
- **Found + fixed during this stage (worth the gate's attention):** the
  Planetary Computer `modis-11A2-061` collection mixes Terra (MOD) and Aqua
  (MYD) items. The first climatology build silently blended 13:30 Aqua
  composites into the 10:30 baseline (sample counts 18/tile/period instead of
  9 betrayed it), which biased the window-mean LST anomaly to +3.08 K. With
  the explicit Terra-only filter the correct value is **+4.60 K** — a 1.5 K
  error caught by the sample-count audit; the observation-time discipline is
  not pedantry.
- **Baseline-construction residual (measured):** 2022's own A2 composites vs
  the window-mean of 2022's A1 dailies = **−0.91 K** (tile-mean) — the
  composite-baseline error term, carried in the LST budget; the LST anomaly
  is quoted as +4.6 K with an ~1 K construction-term, never as a precise
  number.
- **L3 — product consistency:** MODIS bbox-mean LST vs ERA5 `skin_temperature`
  at the matching hour: MODIS − ERA5skt = **−5.31 ± 1.32 K** over 10 days.
  Framed strictly per pre-registration: distinct-but-not-independent skin
  products with different aggregation (QC-valid 1 km pixels vs all land
  cells); a stable offset with day-to-day σ of 1.3 K is coherence, not
  validation, and no tier follows from it.

## 5. UHI (Delhi) — LST lane

Committed artifact: `uhi.json`. Definition per pre-registration §5 (WorldCover
built-up ≥ 0.5 urban core ≤ 20 km; rural ring 20–40 km, built ≤ 0.1,
water/wetland excluded; MODIS 1 km grid, masks identical across sensors).

**Headline (sign-level finding): the daytime surface UHI is NEGATIVE during
the event window — Delhi's urban core reads COOLER than its rural ring at the
Terra ~10:30 snapshot: window mean −0.77 ± 0.80 K (10 valid days).** This is
the documented pre-monsoon semi-arid pattern (a daytime *surface* urban cool
island over dry bare surroundings); it is NOT a statement about the
nighttime/air-temperature UHI people experience, which this lane cannot
measure (no Aqua afternoon pass, no nighttime analysis in scope this stage,
and 2 m air is a different quantity — rule 2). Exactly this is why the gate
made the observation-time caveat first-class.

- Sensitivities (pre-registered): urban threshold 0.4 → −0.81 K, 0.6 →
  −0.74 K; ring 25–45 km → −1.05 K. The sign is robust to every
  pre-registered variation.
- **Landsat cross-check (same masks, 30 m → 1 km aggregated):** Apr 3 (L9)
  −2.31 K, Apr 4 (L8) +0.13 K, Apr 11 (L8) −6.75 K — sign agrees with MODIS
  on 2 of 3 scenes with large scene-to-scene spread (path/row geometry and
  ring coverage differ between the two paths; the Apr 11 scene's ring is
  partially clipped). Reported as scene-level corroboration of the sign, not
  as a tight magnitude check.
- **Classification uncertainty:** WorldCover v200's own validation reports
  **76.7 ± 0.5% global overall accuracy** (Product Validation Report V2.0,
  esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/docs/
  WorldCover_PVR_V2.0.pdf); the threshold/ring sensitivities above are this
  analysis's empirical handle on it. The 2021-map-for-2022 stationarity
  assumption is stated in the artifact.
- **Elevation confound guard: NOT APPLIED** (no 1 km elevation source in this
  stack) — stated; the Delhi region is low-relief alluvial plain, so the
  residual risk is small but unquantified.

## 6. Harness + shared-code discipline (methane-shaped assumptions found)

Found and fixed this stage (shared path, no `_heat` fork of anything):

1. **`check_runnable` assumed every event is an EMIT event** (Stage A flag) —
   now phenomenon-aware: emission events keep the exact prior logic
   (guard-tested, Aliso reason unchanged); non-emission events are runnable
   iff a recipe is wired, with an honest reason otherwise.
2. **`real_emit_pipeline` assumed a plume Detection** — area recipes now build
   their own `PipelineOutput` (the heat recipe constructs an
   `AIR_TEMPERATURE_ANOMALY` detection with mandatory footprint + baseline per
   ADR 0003).
3. **`compare_to_committed` was hardcoded to q_estimate.json** — it now
   dispatches on the committed artifact shape; methane comparisons
   bit-identical; heat regression = C1 ±0.05 K, C2 ±0.02 K, C3 exact,
   C4 ±1% vs the committed `air_lane.json`.
4. **Recall matching was centroid-only** — ADR 0004 overlap matching for area
   phenomena; point events untouched (guard-tested both ways).
5. **The event-registry pattern held:** `run_heat_stage_b.py` uses a
   `HEAT_EVENTS` registry exactly like `run_event_quantification.py`'s
   `EVENTS`; a second heat event is a registry entry + fetch run, not new code.
6. **MODIS route reality:** LP DAAC's HDF4 is unreadable in this stack (no
   GDAL HDF4 driver — probed); the SAME NASA v061 product is consumed as COGs
   via Planetary Computer, with per-container SAS signing (a first-asset-keyed
   token 403s — found, fixed) and reprocessing-duplicate de-duplication
   (found: duplicate A2022097.h24v06 items would have double-counted a day).
7. **Eval scoreboard now:** `aether-eval run` → Events: 4 (3 runnable, 1
   not_runnable), recall 3/3, **regression 14/14 GREEN** (10 methane checks at
   +0.00% — byte-identical artifacts — plus 4 heat checks).

## 7. Deviations from pre-registration

**None.** Every V1–V4 verdict above is the pre-registered metric at the
pre-registered threshold. Two pre-registration *design lessons* surfaced (not
deviations — the criteria were executed verbatim): (a) the ≥4-obs/day station
rule excludes India's 3-hourly synoptic majority (100 of 110 stations) — the
≥3-obs exploratory artifact quantifies the consequence; (b) a pooled-r
criterion over a 10-day single-event window is range-restricted and fragile at
small station counts. Both are flagged for the gate to re-rule **for future
stages**, not retroactively.

## 8. Honest limits

- VALIDATED here means: *these two specific air-temperature claims were
  checked against in-situ instruments / a station-true product under
  pre-registered criteria for this one event*. It does not validate the
  pipeline's flux-style generality, other windows, or any LST quantity.
- The V1 bracket compares a bbox-wide gridded peak (which lands near the
  Pakistan border) against Indian stations only — geography contributes to the
  1.68 K gap; in-window Pakistani station data was not probed.
- ERA5 assimilates the very stations used in V1/V2 (dependency graph): V1 is
  ground-truth agreement at the anchor; only V3 carries cross-product weight,
  and IMD-gridded itself shares the upstream network.
- Duration/extent failures are findings about criterion fragility, not about
  "which dataset is right" — neither dataset is truth for an area integral.
- The LST anomaly baseline is 9 years (2013–2021) of 8-day composites — far
  shallower than the AIR lane's 30-year hourly baseline; its
  composite-vs-daily residual is measured and carried (§4).
- WorldCover-based UHI masks inherit a ~77%-OA classification; the
  sensitivity spread is the empirical handle, and the negative-UHI *sign* is
  robust to it, but magnitudes are soft.

## STOP — for review

Next (gated on your review): Stage C — hypothesis engine v2 (multi-factor
attribution with computed diagnostics per factor; non-discrimination as a
first-class headline), per the brief.
