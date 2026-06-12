# Sprint 9 — Stage A — Heat-Vertical Data-Spine + Event Probe — Gate Report

> The heat vertical's reference-data probe: what data genuinely exists and is
> legally accessible, which flagship Indian heat event the DATA selects, and what
> the ontology needs for an area phenomenon. **Probe only — no anomaly detection,
> no quantification, no UI.** Committed gate report; STOP for review per the brief.
>
> Cardinal rule 1 discharged as follows: the flagship event was selected by an
> ERA5 percentile scan (`scripts/sprint9_scan_era5_heat.py`, committed, re-runnable,
> resumable from `~/.aether_cache/sprint9_heat_scan/`) over 2013–2026, against a
> 1991–2020 WMO-normals climatology, and the top-ranked windows were then verified
> against documented reporting fetched live (citations below). No event, window, or
> region in this report originates from assistant memory; every one traces to the
> committed scan output (`stage_a_outputs/sprint9_heat_probe/era5_scan_results.json`)
> or to a fetched, cited source.

## Verdict — earnable validation tier

**Flagship event (probe-selected): the documented March–April 2022
northwest/central India heat wave, canonical analysis window 2022-04-02 →
2022-04-11 (peak day 2022-04-08), benchmark
`eval/benchmark/india_nw_heatwave_2022_04.yaml`. For its 2 m air-temperature
claims, VALIDATED is earnable — the first Aether event for which that is true.
For its LST claims, CROSS-CHECKED is the ceiling.**

**The tier is split by physical quantity, per cardinal rule 2 (LST ≠ 2 m air
temperature):**

- **Air-temperature (2 m) claims: VALIDATED is earnable** — for the first time on
  any Aether event. Usable, legally accessible in-situ 2 m air temperature exists
  for the event window (NOAA ISD synoptic stations; §4). Stage B's air-temperature
  anomaly claims (peak anomaly, duration at station locations) can be checked
  against real ground-truth thermometers, which is the rubric's in-situ criterion
  (`docs/science/validation_tiers.md` — "a controlled-release experiment, an
  in-situ measurement, or a peer-reviewed per-source flux at the same scope").
  Two honesty caveats are first-class and flagged for the human gate to ratify:
  1. **ERA5 is not independent of the stations.** ERA5's 2 m temperature analysis
     assimilates synoptic station observations, so "ERA5 anomaly vs ISD station"
     is *ground-truth agreement*, not independent-model verification. The
     mitigation: IMD's own gridded daily Tmax product (§4.3) is built from IMD
     stations only — no ERA5 anywhere in it — giving a second, ERA5-independent,
     station-grounded reference for the same air-temperature claims.
  2. **License handling (WMO Resolution 40): APPROVED at the interim probe
     review, with conditions.** ISD non-US data "cannot be redistributed to other
     users or customers" (verbatim, §4.1). Raw station data stays in the
     gitignored local cache; the repo commits only **genuinely derived
     statistics** — comparison metrics and summaries, never a re-hosted or
     thinned observation series. Every committed derived artifact carries
     provenance: station IDs, source, access date, and the license text verbatim.
     The same verbatim-license check applies to IMD gridded data before anything
     from it is committed (§4.3): cache-raw/commit-derived there too unless its
     stated terms clearly permit redistribution.
- **LST (satellite skin-temperature) claims: CROSS-CHECKED is the ceiling.** No
  in-situ skin-temperature truth exists in any accessible source probed. MODIS LST
  vs Landsat ST vs ERA5 skin temperature are cross-checks between
  distinct-but-not-independent products (stated as such per the brief). No LST
  panel may inherit the air-temperature tier — rule 2 is structural here.

## Reference dependency graph (required by the interim probe review)

No cross-check in this vertical may be framed as more independent than this graph
allows — the heat-domain analogue of Permian's NASA-anchored-localization caveat.

```
  WMO synoptic surface stations (incl. the Indian stations ISD republishes)
        │  the in-situ truth anchor: actual 2 m thermometers
        ├────────────► NOAA ISD archive          (republication of station obs;
        │                                         QC + format, no model content)
        ├────────────► ERA5 / ERA5T 2m analysis  (ASSIMILATES synoptic 2 m obs —
        │                                         downstream of the same stations)
        └────────────► IMD gridded daily Tmax    (gridded FROM IMD stations,
                                                  ~180 real-time post-2008 —
                                                  overlapping the ISD network)

  MODIS LST / Landsat ST   (satellite SKIN temperature — a different physical
                            quantity; not in the 2 m graph at all; relatable to
                            ERA5 skin temperature only, never to 2 m claims)
```

Consequences, stated plainly:

- **ERA5-vs-station agreement is partially circular** — ERA5's 2 m analysis
  assimilates synoptic station observations, including those ISD republishes. It
  is *ground-truth agreement at the anchor*, not independent verification, and
  every artifact that reports it must say so.
- **IMD gridded is itself station-derived** and its input network overlaps ISD's.
  ERA5 ↔ IMD-gridded agreement is two *downstream products with different
  processing and error modes* (different QC, gridding, and assimilation physics)
  agreeing about the same upstream truth — valuable, but not two independent
  witnesses.
- **Stations are the only in-situ truth anchor.** The VALIDATED-tier question for
  air-temperature claims is decided at the station level; ERA5 and IMD-gridded
  corroborate with different error modes.
- **LST products never enter the 2 m graph.** Any LST↔ERA5 comparison uses ERA5's
  *skin* temperature and is reported in the LST lane only (rule 2).

## Probe results

### 1. ERA5 via the existing ARCO path — ALL REQUIRED VARIABLES AVAILABLE

Probed (`scripts/sprint9_probe_era5_metadata.py` →
`stage_a_outputs/sprint9_heat_probe/era5_metadata.json`), not assumed. Store:
`gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3` — the same
store `packages/data_spine/era5.py` already uses (anonymous, token-free).

| variable (heat-vertical need) | present | layout |
|---|---|---|
| `2m_temperature` | YES | hourly 0.25°, chunks [1, 721, 1440] |
| `2m_dewpoint_temperature` (humidity) | YES | same |
| `10m_u/v_component_of_wind` (advection) | YES | same |
| `volumetric_soil_water_layer_1..4` (soil-moisture deficit) | YES | same |
| `geopotential` (synoptic ridge; 37 pressure levels incl. 500 hPa) | YES | chunks [1, 37, 721, 1440] |
| `surface_pressure`, `mean_sea_level_pressure`, `total_precipitation` | YES | same as t2m |
| `land_sea_mask` (static) | YES | sample at a valid-data date — the time axis is allocated 1900–2050 |

- **Measured coverage** (store attrs, not the allocated axis): final ERA5 to
  **2025-12-31**; preliminary **ERA5T to ~2026-06-05** (`valid_time_stop_era5t`,
  read on 2026-06-11). Any 2026 event would rest on ERA5T preliminary data — a
  provenance note, not a blocker, but it must be carried.
- **Cost reality (drives every scan design):** v3 chunks are whole-globe per
  single hour (~4 MB raw each), so cost scales with *hours touched*, not spatial
  subset. One India-subset hour ≈ 0.6 s. The 1° coarsened ARCO store would be
  ~30× cheaper per hour but ends 2021-12-31 and lacks soil moisture + dewpoint —
  rejected to keep one store, one grid, no cross-store regrid bias.
- The coarse-store/v3 tradeoff and the 2-hour daily-max proxy that falls out of
  the chunk economics are documented in the scan script header and §2.

### 2. Event selection — ERA5 percentile scan (the reanalysis half of rule 1)

Scan design (full rationale in `scripts/sprint9_scan_era5_heat.py`; every choice
is a documented assumption, revisited at full rigor in Stage B for the selected
event only):

- **Daily-max proxy:** max of T2m at 09:00/10:00 UTC (14:30/15:30 IST — the
  climatological afternoon peak). Slightly underestimates the true daily max but
  is applied identically to baseline and candidates, so percentile exceedance is
  consistent. Choosing 2 hours/day is the chunk-economics compromise (each extra
  hour = +1 whole-globe chunk/day); Stage B uses all 24 hours for the selected
  event.
- **Climatology:** per 0.25° land cell, per scan day, mean + 95th percentile over
  1991–2020 (WMO standard normals) × ±10-day window = 630 samples/cell/day.
- **Season scanned:** Mar 1 – Jun 30 (pre-monsoon), 2013–2026 (Landsat-8 era
  onward). Events outside Mar–Jun would not be found — a stated scope choice.
- **Domain:** 6.5–37.5 N, 68–97.5 E, ERA5 land cells (9,578 of 14,875). The bbox
  includes neighbouring countries; candidate geolocation is reconciled against
  reporting afterwards.
- **Daily index — two families, both committed.** The first run used only a
  percentile family (land fraction exceeding the cell's day-of-year p95;
  severity = area-weighted mean exceedance in K). **Found defect, kept and
  documented:** its top windows centroided in the Himalaya/Tibetan-plateau
  cells inside the bbox (e.g., 30.5 N 81.1 E, 29.4 N 86.6 E) — raw-K p95
  exceedances over snow/elevation margins are enormous, so the index found
  mountain warm spells, not human-relevant heatwaves. The fix is not an ad-hoc
  elevation mask but a second, documented family: the **IMD-style index** —
  IMD's own published plains heat-wave criterion (Tmax ≥ 40 °C AND departure
  ≥ +4.5 K; the definition is quoted verbatim in IMD's MAUSAM diagnosis paper,
  §3) applied to the ERA5 proxy. The absolute threshold removes the plateau
  naturally. Candidate window = contiguous run (1-day gaps tolerated) with
  qualifying area fraction ≥ 0.05, ranked by Σ(area_frac × severity). Both
  families' candidate lists are committed in `era5_scan_results.json`;
  selection uses the IMD-style family.
- **ERA5 vs ERA5T (interim-review ruling):** all else equal, an event inside the
  final-ERA5 window (≤ 2025-12-31) is preferred over one resting on preliminary
  ERA5T data. If an ERA5T-window event were selected anyway, its provisional
  status would be a first-class provenance note in the YAML and report.

**Result:** 15 IMD-style candidate windows in 2013–2026 (47 in the p95 family;
both in `era5_scan_results.json`). Top of the IMD-style ranking, with the
coverage screen the brief asks for ("strong data coverage across the above
sources"):

| rank | window | score | peak area | peak anom | centroid | coverage screen |
|---|---|---|---|---|---|---|
| 1 | 2019-06-02..16 | 7.74 | 0.21 | +10.1 K | 23.9 N 78.2 E | **no Landsat 9** (pre-launch) — half the ST revisit |
| 2 | 2017-04-12..20 | 5.77 | 0.12 | +12.1 K | 27.8 N 73.1 E | **no Landsat 9** |
| 3 | **2022-04-02..11** | **5.72** | 0.14 | +12.1 K | 27.3 N 74.0 E | **passes all**: L8+L9, Terra MODIS, final ERA5, IMD gridded, 130 in-bbox ISD stations |
| 4 | 2024-06-11..19 | 4.56 | 0.11 | +9.0 K | 27.3 N 79.7 E | coverage OK; reference hygiene weaker (see rejected list) |
| 5 | 2014-06-05..11 | 4.38 | 0.16 | +8.9 K | 25.8 N 78.6 E | no Landsat 9 |

(The scan also surfaced sibling 2022 windows — Apr 27–May 1 and May 12–15 —
consistent with the documented multi-wave March–May 2022 season; and the p95
family's 2022-03 windows correspond to the documented March waves, though that
family's centroids are mountain-biased as described above.)

**Selected flagship event: the March–April 2022 northwest/central India heat
wave, canonical analysis window 2022-04-02..2022-04-11** (the top-scoring
candidate that passes every coverage criterion). Event-region extraction
(`scripts/sprint9_extract_event_region.py` →
`event_region_2022_04.json`): peak qualifying-area day **2022-04-08** (1,330
qualifying 0.25° cells, largest 4-connected cluster 1,307 cells), window mean
anomaly over qualifying cells +5.0..+6.8 K by day, max cell anomaly +12.1 K,
max proxy 45.5 °C; peak-day cluster bbox **lon 67.875..84.375, lat
22.375..32.875** (the NW/central Indian plains, reaching the India–Pakistan
border region — consistent with the documented event's extent, which includes
southern Pakistan).

**Why this one (in rank order of the brief's criteria):** (1) top-ranked
candidate passing the full coverage screen — Landsat 8 **and** 9, Terra MODIS
daily LST, final-ERA5 window (no ERA5T dependence, per the interim-review
ruling), IMD gridded Tmax coverage (product ends 2024), and 130 ISD stations
in-bbox for the window; (2) the strongest documented-reporting base of any
candidate: a peer-reviewed attribution study with an explicit event definition
(Zachariah et al. 2023), IMD's own peer-reviewed diagnosis paper (Srivastava
et al. 2024, MAUSAM), and dated agency/observatory accounts (§3); (3) the
probe's in-situ spot-check corroborates the window from ground truth (§4).

**Rejected alternatives (recorded per the brief):**
- **June 2019 (scan rank 1, score 7.74):** genuinely severe and documented
  (e.g., Churu 50.8 °C on 2019-06-01, near-record; one of the longest waves on
  record — Wikipedia/Business Standard accounts fetched at probe time).
  Rejected on coverage: predates Landsat 9, so the ST revisit is halved.
  Documentation status: verified severe, NOT undocumented.
- **April 2017 (rank 2, 5.77):** rejected on coverage (no Landsat 9); its
  documentation was not further verified once coverage failed.
- **May/June 2024 (ranks 4/6):** full sensor coverage, lower scan scores, and
  weaker reference hygiene — the iconic 52.9 °C Delhi (Mungeshpur) reading of
  May 2024 was officially questioned as a sensor anomaly, making the headline
  reference values contested; a benchmark event should not be anchored to
  disputed readings.
- **March 2026 (p95-family rank 1):** falls in the preliminary-ERA5T window
  (final ERA5 ends 2025-12-31) — deprioritized per the interim-review ruling;
  additionally its p95-family centroid (30.5 N 81.1 E) is in the
  mountain-biased regime, and Terra's drifting orbit makes 2026 MODIS LST a
  data-quality question of its own.
- **2022 March windows (p95 family):** part of the same documented event but
  centroided over the plateau in the defective index family; the IMD-style
  family places the season's strongest plains wave at Apr 2–11, which is the
  window selected.

### 3. Documented-reporting verification (the reporting half of rule 1)

All sources below were fetched live on 2026-06-11; none of the event facts in
this report rest on assistant memory.

1. **Peer-reviewed attribution study (the event definition):** Zachariah, M.,
   et al. (2023). *Attribution of 2022 early-spring heatwave in India and
   Pakistan to climate change…* Environmental Research: Climate, 2(4), 045005,
   DOI 10.1088/2752-5295/acf4b6. Event = March–April 2022 daily-maximum
   temperature averaged over the north Indian plains west of the Himalayas and
   southern Pakistan; ~1-in-100-year in the 2022 climate; ~30× likelier and
   ~1 °C hotter than preindustrial. (Also the precursor WWA rapid study, May
   2022.) Our canonical window sits entirely inside this event definition.
2. **IMD's own peer-reviewed diagnosis:** Srivastava, A., Kumar, N., &
   Mohapatra, M. (2024). *Unprecedented hot weather diagnosis in India during
   March-April 2022.* MAUSAM, 75(2), 551–558, DOI 10.54302/mausam.v75i2.6196
   (PDF fetched and read). Verbatim facts used: March 2022 maximum temperatures
   highest in 122 years (since 1901); April 2022 maximum temperatures third
   highest; all-India mean temperature anomalies +1.61 °C (March) and +1.36 °C
   (April), 2nd highest since 1901; major HW spells "particularly during the
   11th–21st March, 26th–31st March, and 25th–30th April"; ~10–20 April HW days
   over major parts of NW/central India vs a normal of 1–5; and the IMD
   heat-wave definition this probe's scan criterion is built from (≥40 °C
   plains threshold; departure 4.5–6.4 °C = heat wave, >6.4 °C = severe).
3. **Honest reconciliation (spell-list discrepancy, stated rather than
   smoothed):** our scan's top window (Apr 2–11) is not one of the MAUSAM
   paper's three "particularly" listed spells. The list is non-exhaustive (10–20
   April HW days over NW/central India cannot come from the ≤6-day Apr 25–30
   spell alone), the peer-reviewed event definition contains our window, and
   the in-situ spot-check (§4: Jaipur ISD 42.0 °C at 15:30 IST on 2022-04-08 —
   the scan's peak-area day; IMD gridded 42.7 °C, nearest cell, same day)
   corroborates it from two non-ERA5 sources. The discrepancy is recorded; if
   the reviewer prefers an IMD-listed spell as the canonical window, that is a
   one-line change to the scan-window parameters and a YAML re-derivation.
4. **Dated agency/observatory accounts (context + the LST framing):** NASA
   Earth Observatory, 2022-04-29 (*Early Season Heat Waves Strike India*) —
   Prayagraj 45.9 °C on Apr 27, Barmer 45.1 °C on Apr 26, anomalies +4.5..8.5 °C
   over east/central/NW India; ESA Sentinel-3 SLSTR image page (acquired
   2022-04-29 10:30 local) — LST > 60 °C in places while air temperatures were
   43–46 °C, with ESA's own explicit LST-vs-air-temperature distinction —
   an official articulation of cardinal rule 2, cited in the YAML.
5. **IMD primary press releases:** the two `internal.imd.gov.in` press-release
   URLs cited inside the MAUSAM paper both 404 (probed). The end-of-April IMD
   DG figures (NW India April average max 35.9 °C, hottest April in 122 years;
   central India 37.78 °C) are therefore carried via dated press reporting
   (BusinessToday, 2022-04-30) **with the secondary-source status declared** in
   the YAML rather than laundered into a primary citation.

### 4. In-situ stations — the VALIDATED question — USABLE DATA EXISTS

#### 4.1 NOAA ISD (Integrated Surface Database) — the decisive finding

- Station inventory (`isd-history.csv`, fetched 2026-06-11): **545 Indian
  stations** total; **387** with data spanning 2013→2022+; **~368–400** current
  through mid-2024/2025 (END-year histogram: 383 stations end in 2025 — i.e.,
  still reporting; the inventory's END field trails real time).
- **Actual retrievability verified, not assumed:** anonymous download of
  `https://www.ncei.noaa.gov/data/global-hourly/access/<year>/<station>.csv`
  works (probe: SAFDARJUNG, IN 421820-99999, year 2024 — hourly FM-12 synoptic
  reports with TMP/DEW/SLP/WND, scaled-integer + QC-flag format).
- **License (verbatim, fetched from NCEI's ISD readme):** "The non-U.S. data in
  ISD are subject to WMO Resolution 40 restrictions, and cannot be redistributed
  to other users or customers." GSOD's readme adds: non-US "data or any derived
  product shall not be provided to other users or be used for the re-export of
  commercial services," while data are "intended for free and unrestricted use in
  research, education, and other non-commercial activities."
  **Handling:** raw station files live only in the gitignored `~/.aether_cache/`;
  the repo commits derived comparison statistics with attribution. Flagged for
  human ratification (the GSOD phrasing reaches "any derived product"; the ISD
  phrasing reaches only the data — we follow the stricter reading until ruled
  otherwise: commit *aggregate statistics*, never per-observation series).
- **Event-region density: 130 stations inside the event bbox** (67.875..84.375
  E, 22.375..32.875 N) with inventory spans covering the canonical window.
- **In-window spot-check (retrieved, parsed, verified):** JAIPUR (424800-range
  ID 42348099999), year-2022 file: 551 valid hourly TMP observations inside
  Apr 2–11; window maximum **42.0 °C at 2022-04-08T10:00 UTC (15:30 IST) — on
  the scan's peak-area day**. Independent in-situ corroboration of the
  data-selected window (and of the afternoon-peak proxy-hour choice).

#### 4.2 IMD Data Supply Portal — NOT usable autonomously

Registration + payment-gated with a formal request/approval workflow (fetched
2026-06-11, dsp.imdpune.gov.in). Reported for completeness; not used.

#### 4.3 IMD Pune gridded daily Tmax — FREE, the ERA5-independent reference

`imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html`: 1.0° gridded daily maximum
temperature, **1951–2024**, free download, no registration, binary format
(documented record layout; 7.5–37.5 N, 67.5–97.5 E). Built from IMD's station
network (~180 stations real-time post-2008 — IMD's own stated caveat). This is an
authoritative, station-only (ERA5-free) analysis of exactly the quantity our
air-temperature claims are about.

**Programmatic access verified, not assumed:** `POST maxtemp.php` with
`maxtemp=2022` returns exactly 365×31×31 float32 (1,403,060 bytes; 99.9 =
missing; **lat-major layout confirmed empirically** — the lon-major reading
gives 99.9/garbage). In-window sanity read: 2022-04-08 at the cell nearest
Jaipur → **42.7 °C**, neighborhood 42.2–43.8 °C — coherent with the ISD Jaipur
observation (42.0 °C) and the ERA5 proxy field. **Interim-review condition
carried forward:** before any IMD-gridded-derived artifact is committed,
fetch and record its license terms verbatim; until then, cache-raw /
commit-derived, same as ISD.

### 5. MODIS LST (LP DAAC) — AVAILABLE, same auth as EMIT

- CMR collections confirmed: **MOD11A1 v061** (daily 1 km), **MOD11A2 v061**
  (8-day 1 km), **MYD11A1 v061** (Aqua daily) — all LP DAAC.
- Granules over NW India confirmed for test windows in 2024 AND for Apr–Jun 2026
  (Terra v061 still producing — checked, not assumed, given Terra's orbit drift;
  the drift itself is a Stage B data-quality consideration for trend-consistency,
  noted here).
- **Authenticated download verified:** range-read of a real MOD11A1 granule from
  `data.lpdaac.earthdatacloud.nasa.gov` returned 206 via the existing
  `~/.netrc` Earthdata credentials — the same auth path EMIT already uses. No new
  credentials needed.
- **Event-window coverage (CMR, probe-verified):** MOD11A1 (Terra daily) **72
  granules** over the event bbox for 2022-04-01..12 across 6 sinusoidal tiles
  (h23–25, v05–06); MOD11A2 (8-day) 12 granules.
- **Found gap: Aqua MYD11A1 has ZERO granules in the window.** Delimited by
  CMR query, not assumed: last Aqua LST day before the gap = 2022-03-31
  (A2022090), first after = 2022-04-17 (A2022107) — the gap covers the
  canonical window exactly. Consequence (first-class Stage B caveat): daytime
  LST sampling in the window is **Terra ~10:30 local only** — no ~13:30
  afternoon pass — so LST anomalies sample late morning, not the afternoon
  skin-temperature peak. Landsat (also ~10:30) does not recover the afternoon.
  The cause of the Aqua outage is not asserted here; the measured gap is what
  matters.

### 6. Landsat 8/9 Collection-2 Level-2 Surface Temperature — TWO ROUTES, ONE FREE

| route | works? | cost | notes |
|---|---|---|---|
| element84 earth-search STAC (`landsat-c2-l2`) | YES (probed) | search free; assets point at `s3://usgs-landsat` | bucket is **requester-pays** — fetching pixels there bills us |
| **Microsoft Planetary Computer STAC** (`landsat-c2-l2`) | YES (probed) | **free** (Azure-hosted mirror, SAS-token signing, anonymous OK) | `lwir11` (ST_B10 surface-temperature band) asset present; selected route |
| USGS M2M API | not probed | free but requires account + approval workflow | fallback only |

**Event-window coverage (MPC STAC, probe-verified):** 165 C2L2 scenes
intersect the event bbox for 2022-04-01..12 — **Landsat 8: 73, Landsat 9: 58**
(Landsat 7: 34, excluded — end-of-life drifting orbit, and the brief locks
Landsat 8/9). **Median cloud cover 0.0%**; 158 of 165 scenes under 20% — the
pre-monsoon season is ideal for thermal work. The `lwir11` (ST_B10)
surface-temperature asset is present on the probed items.

### 7. Land cover — ESA WorldCover v200 (2021) — OPEN, ANONYMOUS

- Anonymous S3 access verified with an HTTP range-read (COG-friendly) on a real
  India tile (`esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/...`,
  HTTP 206). 10 m resolution, 3°×3° tiles, license **CC BY 4.0**.
- v200 is the 2021 map. Using a 2021 land-cover map for an event in another year
  assumes urban-fabric stationarity at the event date — a stated classification
  assumption whose uncertainty Stage B carries into the UHI numbers (the brief's
  "classification's own uncertainty noted").

## Benchmark YAML

`eval/benchmark/india_nw_heatwave_2022_04.yaml` — validates against the
existing `BenchmarkEvent` schema (loads via `aether-eval show`), with one
additive ontology change behind it (ADR 0003, below). Key honesty decisions:

- **`date_range` = 2022-03-01..2022-04-30** (the peer-reviewed event
  definition's window). The canonical analysis window (Apr 2–11) is recorded in
  `notes` with provenance to the committed scan artifact — it is OUR analysis
  choice, not a claim about the documented event's bounds.
- **`canonical_acquisition` stays null** — it is an EMIT-shaped model (granule
  URs); pinning one satellite overpass would misrepresent a multi-day area
  phenomenon. Consequence: the current harness reports the event
  `not_runnable` with an EMIT-shaped reason — mechanically safe, semantically
  stale, stated in the YAML notes, fixed in Stage B.
- **`location`/`bbox` are scan-derived** (anomaly-weighted window centroid;
  peak-day largest qualifying cluster) with provenance declared in-file —
  the references document the event; the geometry comes from committed data.
- **`location_precision_km: 300` is a placeholder** — centroid-distance recall
  is the wrong shape for area events; an ADR 0002 extension (overlap/IoU-based
  matching) is a flagged Stage B item.
- **`known_measurements` — no `comparable` reference exists at probe time**
  (same honest position Goturdepe and Permian ended in): the IMD all-India
  April anomaly (+1.36 K), the NW-India April average max (35.9 °C), and the
  Prayagraj/late-April station peak (45.9 °C) are `scope_mismatch` with
  machine-readable reasons (different region definitions, normals periods,
  windows, or waves); the March anomaly, the 100-year return period and the
  30× attribution factor are `context_only`. **The VALIDATED path for this
  event does not run through YAML reference values** — it runs through the
  Stage B in-situ comparison machinery against ISD stations (and the
  ERA5-independent IMD gridded product), per the dependency graph.
- **`attribution` is empty by design** — an area phenomenon has no
  operator/facility/sector; Stage C ranks contributing FACTORS instead.
- Every measurement note states whether the quantity is AIR temperature or
  LST (rule 2 applied at the data layer).

## Ontology probe — what an AREA phenomenon needs

The existing ontology already carries most of it (read-through of
`packages/ontology/aether_ontology/{base,entities,spatial,temporal}.py`):

**Fits as-is (no change):**
- `PhenomenonType.HEAT_WAVE` exists; `Phenomenon.region: BBox | GeoJSONGeometry` +
  `summary_measurements` fit an area event exactly.
- `SensorType.REANALYSIS` and `SensorType.GROUND_BASED` exist — ERA5 and ISD
  stations are first-class Observations already.
- `Detection.footprint: GeoJSONGeometry | None` carries the anomaly region;
  `measurements/units/uncertainty` parallel dicts carry the quantification
  analogues (peak anomaly K, extent km², duration days, UHI intensity K).
- `Hypothesis` needs **no ontology change** for factors: the methane pattern
  (candidate kind + claim + tiered confidence + score components, carried in the
  causal package's committed artifact) ports directly — candidates become
  factors. The factor evidence schema is a Stage C ADR in `packages/causal`,
  exactly as facility attribution lives today.

**Minimal evolution proposed (additive, no fork — to be implemented behind the
Stage B/C ADRs):**
1. **`BaselineDefinition`** (new small model in the ontology): dataset, normals
   period, day-of-year window, statistic (mean/percentile + which), hours used,
   note. An anomaly is only meaningful relative to a baseline; making the
   baseline a typed, mandatory part of an anomaly `Detection` is the heat
   vertical's structural-honesty move (the analogue of mandatory `Provenance`).
   Carried as `Detection.baseline: BaselineDefinition | None = None` with a
   model validator: anomaly-type detections MUST carry it; plume detections
   leave it `None`. Methane schemas unchanged.
2. **`DetectionType.AIR_TEMPERATURE_ANOMALY`** (additive enum value), with
   `THERMAL_ANOMALY` reserved for *skin/LST* anomalies. This puts the LST-vs-air
   distinction at the type level — a Detection structurally cannot blur the two
   quantities (cardinal rule 2 enforced by schema, not prose). A guard test will
   assert no single Detection mixes LST and 2 m-air measurement keys.
3. **Area-detection location semantic (documentation + guard, no schema change):**
   for area detections, `Detection.location` = the anomaly-weighted centroid
   (with the peak-anomaly cell carried in `measurements`), and `footprint`
   becomes mandatory-by-guard. No `source point S` exists in this domain — the
   attribution wedge machinery is NOT reused; factors don't have bearings.

**Harness generality finding (flagged for Stage B, not fixed here):**
`aether_eval.real_pipeline.check_runnable` assumes every event is an EMIT event —
the heat YAML is declared not-runnable with an EMIT-shaped reason (verified by
running `aether-eval run` with the new event present: "no EMIT coverage: the
event window predates EMIT's July 2022 launch" — true about EMIT, irrelevant
for a heat phenomenon; the harness reports `Events: 4 (2 runnable, 2
not_runnable)` with methane recall 2/2 and regression 10/10 unchanged).
Mechanically safe
(`not_runnable` events are excluded from the recall denominator, never silently
dropped — verified in the committed eval semantics), semantically wrong for a
non-EMIT phenomenon. Stage B must make runnability phenomenon-aware when it wires
the heat recipe into the `_RECIPES` registry (the registry itself is the right
extension point — same pattern as `scripts/run_event_quantification.py`'s
`EVENTS` registry). Until then the harness reports the heat event as
not_runnable with the stale reason; this is stated in the YAML's `notes` so the
eval scoreboard stays honest.

## What the probe decides for Stage B

- **Tier design:** VALIDATED earnable for 2 m air-temperature claims via ISD
  in-situ comparison (130 in-bbox stations) + IMD gridded as the
  ERA5-independent corroborator — under the dependency-graph framing (ERA5
  assimilates stations; agreement is ground-truth agreement, not independent
  verification). LST claims capped at CROSS-CHECKED; the tier rubric
  (`docs/science/validation_tiers.md`) gets its heat-vertical extension worded
  per-quantity, for the human gate to ratify.
- **Inputs confirmed present and accessible:** ERA5 (all variables, final-ERA5
  window), Terra MOD11A1 (72 granules; same `.netrc` auth as EMIT), Landsat
  8+9 C2L2 ST via Planetary Computer (131 scenes, median cloud 0%), ESA
  WorldCover v200/2021 (anonymous S3), ISD hourly (anonymous), IMD gridded
  Tmax (programmatic POST; layout verified). Stage B is unblocked.
- **Known constraints to carry:** Aqua LST gap Apr 1–16, 2022 (daytime LST =
  Terra 10:30 local only — anomaly definitions must be overpass-time-aware);
  WorldCover is the 2021 map (urban-fabric stationarity assumption for 2022 —
  small, but stated); ISD/IMD license handling per the interim ruling
  (cache-raw / commit-derived, provenance with verbatim license text).
- **Harness work owed by Stage B:** phenomenon-aware `check_runnable`; a heat
  recipe in the `_RECIPES` registry; the ADR 0002 area-event recall semantics
  (overlap-based matching); `BaselineDefinition` + its validator (ADR 0003);
  the no-staleness guard family extended to the new artifacts.
- **Out of scope, restated:** forecasts (rule 4), attribution/return-period
  analysis (the YAML carries both as context_only), Sentinel-3 (citation only,
  not a data source — the locked-source list grows by exactly the brief's
  heat-vertical sources, nothing else).

## Honest limits of this probe

- The percentile scan's proxy (2 hours/day), season (Mar–Jun), threshold
  (p95, area ≥ 0.10), and baseline (1991–2020) are all documented choices; a
  different defensible design could rank candidates differently. The scan finds
  *a* severe, well-documented event with strong data coverage — it does not claim
  the selected event is "the most severe Indian heat event," and no such
  superlative may appear in any artifact (the comparative-claims guard culture
  applies from day one).
- 2026 candidates rest on preliminary ERA5T data (final ERA5 ends 2025-12-31).
- The scan domain's land mask includes non-Indian territory in the bbox;
  reporting verification (§3) is what pins the event to India.
- Carbon Mapper, TROPOMI, and the O&G database are methane-vertical sources; they
  were not probed here and play no role in the heat vertical.

## STOP — for review

Next (gated on your review): Stage B — baseline/climatology definition at full
rigor (all 24 hours, sensitivity to the normals period and window), MODIS+Landsat
LST anomaly fields, urban–rural UHI delta against WorldCover with classification
uncertainty, the quantification analogues with budgeted uncertainty, and the
cross-checks the probe earned: ERA5-2m ↔ ISD stations (direct, ground truth),
ERA5-2m ↔ IMD gridded Tmax (ERA5-independent), LST ↔ ERA5-skin (related
separately, never conflated with air temperature).
