# Sprint 9 heat vertical — Stage B design + PRE-REGISTERED validation criteria

> **Pre-registration (required by the Stage A gate review, ruling 2).** This
> document is committed BEFORE any station comparison is computed. The criteria
> below — which claims, which references, which metrics, which thresholds —
> are fixed in advance. If a criterion fails, the claim is NOT validated and
> the Stage B report says so; thresholds are not adjusted after seeing the
> data. Any analysis beyond this list is labelled exploratory.

## 0. The two lanes (cardinal rule 2, structural)

Every quantity in this stage lives in exactly one lane:

- **AIR lane** — 2 m air temperature (ERA5 `2m_temperature`, ISD station TMP,
  IMD gridded daily Tmax). Validation tier earnable: **VALIDATED** (in-situ
  truth exists).
- **LST lane** — satellite skin temperature (MODIS MOD11A1/MOD11A2, Landsat
  C2L2 ST, ERA5 `skin_temperature` for product consistency only). Ceiling:
  **CROSS-CHECKED**. **Observation-time caveat is first-class on every LST
  quantity (gate ruling 4):** daytime LST here is a **Terra ~10:30-local
  snapshot** (the Aqua 13:30 pass is absent for the window — measured gap,
  Stage A §5), which is BEFORE the diurnal LST peak. No LST quantity may be
  framed as a daily maximum, and every LST panel/cross-check carries the
  observation time.

No comparison crosses lanes. ERA5 skin temperature is used only inside the LST
lane's product-consistency checks and is never presented as what people
experience.

## 1. Reference dependency graph (governs all framing)

Per the Stage A report: WMO synoptic stations are the in-situ truth anchor;
NOAA ISD republishes them; ERA5 ASSIMILATES them; IMD gridded is built from
them (IMD's network, overlapping ISD's). Therefore:

- **Station agreement validates the EVENT's temperatures** (instrument truth),
  and is claimed as "event temperatures are instrument-validated".
- **ERA5↔station agreement is CONSISTENCY, not independent reproduction** —
  ERA5 has seen these stations. Never framed as methodology confirmation.
- **ERA5↔IMD-gridded agreement is two downstream products with different
  error modes agreeing about the same upstream truth** — the strongest
  available check that is independent of ERA5's own processing.
- LST products are outside the 2 m graph entirely.

## 2. Definitions (fixed before computation)

- **Daily Tmax (gridded, ERA5):** max of hourly `2m_temperature` over
  06–13 UTC (11:30–18:30 IST) per 0.25° cell. The event window additionally
  fetches all 24 hours to MEASURE the residual of this hour-set vs the true
  24 h max (S3 below); baseline and event use the same 06–13 definition for
  consistency.
- **Daily Tmax (station, ISD):** max of QC-passing hourly TMP over the same
  06–13 UTC range, requiring ≥ 4 valid observations in that range for the day
  to count (else the station-day is excluded, counted, and reported).
- **Climatology (ERA5 lane):** per cell, per scan day, mean of daily Tmax over
  **1991–2020** with a **±10-day** day-of-year window (630 samples per
  cell/day) — the Stage A scan's definition carried forward at the upgraded
  hour set.
- **Climatology (IMD lane):** identical construction computed from IMD gridded
  daily Tmax 1991–2020 on its native 1.0° grid. Each dataset is compared
  against ITS OWN climatology — anomalies are never formed across datasets.
- **Anomaly:** daily Tmax − climatological mean (same dataset, same
  definition). **Qualifying cell (IMD-style criterion, from Stage A):**
  Tmax ≥ 40 °C AND anomaly ≥ +4.5 K.
- **Event bbox:** the benchmark YAML bbox (67.875–84.375 E, 22.375–32.875 N);
  land cells only (ERA5 `land_sea_mask` > 0.5 at 0.25°; all IMD 1° cells with
  non-missing data are land by construction).

## 3. Claims under validation (AIR lane) and their references/criteria

| id | claim (computed by our pipeline) | reference | pre-registered criterion | earns |
|----|----------------------------------|-----------|--------------------------|-------|
| C1 | Peak 2 m air temperature of the event window: max over days (Apr 2–11) and bbox land cells of ERA5 daily Tmax | ISD station daily Tmax (the instrument anchor) | **V1:** max station-day Tmax across qualifying stations in the window ∈ [ERA5 peak − 2.5 K, ERA5 peak + 2.5 K]. | C1 **VALIDATED** (instrument truth brackets the gridded peak) |
| C2 | Peak regional-mean anomaly: max over window days of bbox-land-mean ERA5 anomaly | IMD gridded (ERA5-independent, station-derived) | **V3a:** \|ERA5 window-mean regional-mean anomaly − IMD window-mean regional-mean anomaly\| ≤ 1.0 K, each vs its own 1991–2020 climatology, compared on the common 1.0° grid (ERA5 cell-mean-coarsened). **V3b:** spatial pattern Pearson r ≥ 0.6 between the two window-mean anomaly maps on that grid. | C2 **VALIDATED** if both hold |
| C3 | Duration: length of the consecutive-day run containing 2022-04-08 with qualifying area fraction ≥ 0.05 (ERA5) | IMD gridded, same criterion on its grid | **V4a:** durations agree within ±2 days. | C3 **VALIDATED** |
| C4 | Peak-day extent: qualifying area (km²) on the peak day (ERA5) | IMD gridded, same criterion, common 1.0° grid | **V4b:** extents (computed on the common grid for both) agree within ±30%. | C4 **VALIDATED** |
| —  | ERA5↔station consistency (NOT a validation of independence) | ISD station-days | **V2:** pooled over all qualifying station-days in the window: \|median bias\| ≤ 1.5 K, RMSD ≤ 2.5 K, Pearson r ≥ 0.85 (ERA5 nearest-land-cell daily Tmax vs station daily Tmax). | reported as **consistency at the anchor** (assimilation caveat verbatim) |

**Station qualification (fixed):** ISD stations inside the event bbox whose
2022 file yields a computable daily Tmax (≥4 valid 06–13 UTC obs) on ≥ 7 of
the 10 window days. Stations failing QC are excluded and counted. TMP QC:
value not `+9999`, ISD quality flag in the passing set {0,1,4,5,9} (ISD
format doc), and a physical-range gate (−40 °C to +55 °C).

**Threshold justifications (a priori):** ±2.5 K for V1 reflects ERA5 0.25°
cell-vs-point representativeness plus typical warm-extreme biases of reanalyses
over South Asia (order 1–2 K), with margin; V2's 1.5/2.5/0.85 are typical
published ERA5-vs-synop 2 m performance bounds, chosen as bounds we are
prepared to call "consistent"; V3's 1.0 K tolerance covers the two products'
differing networks/gridding at regional-mean scale; V4's ±2 days / ±30%
reflect threshold sensitivity at a criterion edge (a 0.1 K shift can move a
day/cells in or out near 40.0 °C / +4.5 K). Failing any bound ⇒ the claim is
reported NOT validated, with the measured value shown.

## 4. LST lane (CROSS-CHECKED ceiling) — what will be computed

All values carry "(Terra ~10:30 local snapshot — before the diurnal LST
peak)". No daily-max framing.

- **L1 — MODIS LST anomaly field (event window):** MOD11A1 v061 daily LST_Day
  (QC-filtered), per day Apr 2–11, anomaly vs a 2013–2021 same-period
  MOD11A2-composite climatology. The daily-vs-8-day-composite baseline
  mismatch is quantified by comparing 2022's own A2 composites against the
  window mean of 2022's A1 dailies; the residual enters the LST uncertainty
  budget.
- **L2 — Landsat ST (resolution sample):** C2L2 `lwir11`-derived ST for the
  scene(s) covering Delhi inside the window — the UHI lane's high-resolution
  member, and a same-overpass-window LST↔LST cross-check vs MODIS (both
  ~10:30 local).
- **L3 — product consistency:** MODIS LST vs ERA5 `skin_temperature` at the
  Terra overpass hour over the bbox (distinct-but-not-independent products;
  framed exactly so), and MODIS vs Landsat over the Delhi scene.

## 5. UHI (urban heat island, LST lane)

- **Definition (fixed):** UHI_LST = mean LST(urban cells) − mean LST(rural
  ring), Terra 10:30 snapshot per day, averaged over window days with valid
  retrievals. Urban cell: WorldCover v200 built-up (class 50) fraction ≥ 0.5
  at the 1 km MODIS cell, within 20 km of the Delhi center (28.61 N, 77.21 E);
  rural ring: built-up fraction ≤ 0.1, annulus 20–40 km, excluding water (80),
  wetland (90), and cells with mean elevation differing from the urban-core
  mean by > 150 m (elevation confound guard; SRTM-free proxy: ERA5 geopotential
  is too coarse, so the guard uses the WorldCover grid's cells only where the
  Landsat scene DEM band is unavailable — if no elevation source is available
  at 1 km, the guard is reported as NOT APPLIED, honestly).
- **Classification uncertainty (the brief's requirement):** WorldCover v200's
  own reported global accuracy is fetched and cited verbatim in the report;
  sensitivity = recompute UHI with urban threshold 0.4 and 0.6, and ring
  25–45 km; the spread enters the UHI budget. The 2021-map-for-2022
  stationarity assumption is stated.
- **Landsat cross-check:** same definition at 30 m on the in-window Delhi
  scene(s), aggregated to the same masks.

## 6. Quantification analogues and their budgets

Each analogue gets a budget table in the report (sources → half-widths →
combined), mirroring Q's budget discipline:

| analogue | budget terms |
|---|---|
| peak anomaly (K, AIR) | baseline-period halves (1991–2005 vs 2006–2020); day-window ±10→±15; hour-set 06–13 vs 24 h (event days, measured); ERA5-vs-station bias (V2's measured median bias) |
| extent (km², AIR) | criterion-edge sensitivity (40 °C/4.5 K vs p95-based); baseline halves; grid (0.25° native vs 1° common) |
| duration (days, AIR) | criterion-edge sensitivity; baseline halves |
| UHI intensity (K, LST) | classification thresholds; ring geometry; QC-filter strictness; day-to-day spread; composite-baseline residual (L1) |

## 7. Sensitivity analyses (pre-registered list)

S1 baseline halves 1991–2005 vs 2006–2020 (warming-trend sensitivity of the
climatology — expected to shift anomalies by several tenths K; reported, and
the 1991–2020 choice defended or amended in the report).
S2 day-window ±10 vs ±15.
S3 hour-set: 06–13 UTC max vs full-24 h max on the 10 event days (measured
residual; expected ≈ 0 for daytime peaks).
S4 extent criterion: IMD-style vs day-of-year p95 exceedance.
S5 UHI thresholds (§5).

## 8. Execution order (enforced)

1. This document + ADR 0004 + ontology BaselineDefinition + harness
   generalization are committed (no station data touched yet).
2. Data acquisition to the gitignored cache (ISD raw included — never
   committed; WMO Res. 40 handling per the interim ruling).
3. ERA5/IMD lanes computed; **only then** the V1/V2 station comparisons run,
   exactly as specified here.
4. LST lane + UHI.
5. Artifacts committed (derived statistics only for ISD/IMD-derived values,
   with provenance: station IDs, source, access date, license verbatim);
   report written; guards extended; STOP.

Deviations, if any become technically unavoidable, are recorded in the report
under "Deviations from pre-registration" with the reason — never silently.
