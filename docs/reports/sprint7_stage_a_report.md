# Sprint 7 — Stage A — Reference-Data Probe — Gate Report

> Permian Basin / Carlsbad NM, EMIT granule **20220826T174642**. This is the
> reference-data probe: it establishes what actually exists for this granule so the
> validation design (Stage B) is decided by evidence, not asserted. **Probe only —
> no quantification, no k, no pipeline run here.** Committed gate report; STOP for
> review per the brief.

## Verdict — earnable validation tier: **CROSS-CHECKED** (not VALIDATED)

A NASA **EMIT L2B CH4ENH enhancement raster exists** for this exact granule, so a
Goturdepe-style spatial cross-check (Pearson of our retrieval vs NASA L2B) is
possible — the result can earn the **CROSS-CHECKED** tier. It **cannot** earn a
Goturdepe-grade VALIDATED tier: there is no peer-reviewed per-source flux reference;
the only emission figure (18.3 t/hr) is a press-release value with no method and no
uncertainty (see §3). The tier is set by this evidence, not by how close our Q lands
to 18.3.

## Probe results

### 1. NASA L2B products (CMR / LP DAAC, authenticated query)

| product | query | result |
|---|---|---|
| **L2B CH4ENH** | UR `EMIT_L2B_CH4ENH_002_20220826T174642_2223812_024` | **EXISTS — 1 granule, ~28.7 MB** (DOI 10.5067/EMIT/EMITL2BCH4ENH.002) |
| **L2B CH4PLM** | complexes by UR `..._000524`, `..._000525` | **BOTH EXIST** (1 each) |
| L1B RAD | UR `EMIT_L1B_RAD_001_20220826T174642_2223812_024` | EXISTS — 1 granule |
| L2A MASK | UR `EMIT_L2A_MASK_002_20220826T174642_2223812_024` | EXISTS — 1 granule |

- The CH4ENH raster's existence is the decisive finding — it is the cross-check
  reference. (Re-verified the salvaged finding from the prior session: confirmed,
  1 granule.)
- **Honest discrepancy, reconciled:** a CH4PLM query over the *tight* 0.1° plume
  bbox returned **0** complexes; widening the bbox (and a direct by-UR query) returns
  **both** complexes `000524` and `000525`. The complex footprints simply do not
  intersect the tight bbox — the granules are real and published. This matches the
  Permian YAML's prior claim. Lesson reinforced (per the brief): do not assume from a
  single bbox query; granule/footprint mismatches are real.

### 2. Carbon Mapper catalog (best-effort, unauthenticated) — INCONCLUSIVE

The public catalog API (`api.carbonmapper.org/api/v1/catalog/plumes/annotated`) is
reachable (HTTP 200 on the base endpoint), but the unauthenticated best-effort probe
**could not retrieve scene-specific results** for the EMIT 2022-08-26 Carlsbad
overpass: bbox/datetime filter parameters were either ignored (the base call returned
an unfiltered default page of unrelated Tanager-2026 entries with null datetimes) or
rejected (HTTP 422 for the filtered forms tried). **No Carbon Mapper entry for this
scene is confirmed or denied** — the probe is inconclusive, and Carbon Mapper is
**not** used as a validation reference. Resolving it would need the correct API
contract or an API key (out of scope for this probe; can revisit if a cross-check
beyond NASA L2B is wanted).

### 3. The 18.3 t/hr provenance — CONTEXT ONLY (WebFetch-confirmed verbatim)

Source: **NASA JPL press release, 25 October 2022** ("Methane 'Super-Emitters'
Mapped by NASA's New Earth Space Mission"). Verbatim:

> "the instrument detected a plume about 2 miles (3.3 kilometers) long southeast of
> Carlsbad, New Mexico, in the Permian Basin… Scientists estimate flow rates of about
> 40,300 pounds (18,300 kilograms) per hour at the Permian site."

40,300 lb/hr = **18,300 kg/hr = 18.3 metric t/hr**. The release gives **no
observation date, no granule, no method, and no uncertainty**. This is a
qualitative press-release figure. **It is context only — never a validation target
and never a tuning target.** (Note: the granule was pinned to 2022-08-26 by NASA's
L2B plume-complex catalogue + the Sept 13–Jan 6 EMIT power outage, not by the press
release, which names no date.)

### 4. ARCO-ERA5 wind availability — AVAILABLE

ARCO-ERA5 (token-free) returns hourly 10 m wind for the scene. Preliminary fetch at
the plume-bbox centroid (32.25 N, −104.15 E), 2022-08-26T17:46:42Z → grid cell
(32.25 N, −104.25 E): u = −2.03, v = 3.25, **|U₁₀| = 3.83 m/s**, nearest hour
18:00 UTC (13 min away). **Preliminary only** — Stage B re-fetches at the actual
plume centroid/source. Notably **3.83 m/s is inside the Varon 2–8 m/s U_eff
calibration range**, so the regime check looks promising (but is re-run in Stage B
at the true source per cardinal rule 4, not assumed here).

### 5. OGIM regional subset — extracted + committed (DENSE coverage)

- OGIM v2.7 global GeoPackage: **2.9 GB**, already in the gitignored cache
  (`~/.aether_cache/ogim/OGIM_v2.7.gpkg`, SHA-256 verified) — **no download
  needed**, nothing to clean up.
- Regional bbox chosen: **(−104.45, 31.95, −103.85, 32.55)** = the plume bbox
  buffered to ~±0.30° (~28–33 km half-width), a safe superset of the back-projection
  wedge search radius (Goturdepe's was ~25 km). Attribution (Stage C) filters this
  superset down to the computed wedge.
- **Feature counts (the grounding for Stage C):**

| OGIM layer | count |
|---|---:|
| Oil_and_Natural_Gas_Wells | **10,744** |
| Oil_Natural_Gas_Pipelines | 1,418 |
| Natural_Gas_Flaring_Detections | 91 |
| Natural_Gas_Compressor_Stations | 27 |
| Stations_Other | 2 |
| Gathering_and_Processing | 1 |
| Oil_and_Natural_Gas_Basins | 1 |
| **TOTAL** | **12,284** |

  Committed subset: `ogim_v2.7_permian_basin_region.geojson` (**12 MB** — wells
  ~7.5 MB, pipelines ~4.7 MB) + `ogim_v2.7_permian_basin_region.provenance.json`.
  Density gradient for sizing context: ±0.15° → 3,590 features; ±0.30° → 12,284;
  ±0.50° → 44,702.
- **This is the dense-coverage finding** the brief anticipated: Goturdepe's subset
  had **114** features (0 wells in Turkmenistan); Permian has **10,744 wells** in the
  wedge-scale region. Stage C must handle candidate volume honestly (rank
  transparently, cap the rendered list with the cutoff stated, and lead with
  discrimination power — "N candidates within the wedge; the data cannot discriminate
  the top M under current wind uncertainty" — not proximity). The 12 MB committed
  artifact is flagged for review: it is a one-time reproducibility cache (per CLAUDE.md
  the OGIM subset is committed); if you'd prefer a tighter bbox, it is one
  parameterized re-run away.

## Generality findings (Goturdepe-shaped assumptions)

Per cardinal rule 2, fixes go into the shared parameterized code path, never a
`_permian` fork. Every assumption found is reported.

**Found AND fixed this stage** (`scripts/acquire_ogim_subset.py`):
- `REGION_BBOX`, the output GeoJSON filename, and the provenance filename were all
  **hardcoded to Goturdepe**. Refactored to an `EVENTS` registry keyed by `event_id`
  (region bbox + output filenames per event) selected via `argv`; one shared code
  path. Goturdepe keeps its exact bbox + filenames, so its committed artifacts are
  **byte-reproducible and untouched** (verified: only the two new Permian files are
  added; the Goturdepe geojson/provenance are unchanged).

**Found, deferred to Stage B** (flagged now, to be parameterized when the pipeline
runs — listed so they are not silently carried):
- `scripts/run_stage_a_goturdepe.py` / `run_stage_b_goturdepe.py` — hardcoded granule
  URs, plume bbox, pixel size, L2B path, surface P/T, and output dir.
- `scripts/run_migration_v2_operational.py` — `EVENT_ID`, bbox, L2B path (Goturdepe).
- `packages/causal/aether_causal/attribution.py` — `EVENT_ID`, `_SUBSET_REL`,
  `_Q_REL`, `_WIND_REL`, `_STAGE_A_REL` all Goturdepe-pinned; the field-name lookups
  (`BARSAGELMEZ`, `GOTURDEPE`) are Goturdepe-specific.
- `scripts/build_dashboard_assets.py` — `EVENT_ID`, plume bbox.
- `apps/api/aether_api/loaders.py` — `_DISPLAY` labels; the scope-caveat assumes a
  Thorpe-cluster reference; the +1.46× MF-amplitude systematic is **Goturdepe-measured**
  and its transfer to Permian is itself unvalidated (Stage B carries it with an
  explicit assumption note per the brief).

## What the probe decides for Stage B

- **Tier:** CROSS-CHECKED is achievable (L2B CH4ENH raster exists). Stage B reports
  Pearson vs L2B as the cross-check; the flux remains press-release-context-only.
- **No NASA per-granule target spectrum** for this granule (as the YAML records) —
  exactly why Sprint 6's per-granule HITRAN k is the enabling capability. There is no
  NASA target to cross-check the k *shape* against (unlike Goturdepe's r=0.993);
  Stage B states this.
- **Inputs confirmed present:** L1B, L2A, L2B CH4ENH downloadable; ERA5 available;
  dense OGIM committed. Stage B is unblocked.

## STOP — for review

Next (gated on your review): Stage B — generate the Permian per-granule v2 HITRAN k,
run the shared parameterized pipeline, the mandatory scene checks (wind
source-vs-centroid ΔQ%, U_eff regime, mask sensitivity), a from-scratch uncertainty
budget (with the +1.46× carried as an explicitly-unvalidated transfer), and the
internal-consistency diagnostics — reported with the CROSS-CHECKED tier, and with
18.3 t/hr stated only as context.
