# Task: Sprint 9 — The Heat Vertical (generalizing the loop)

**Owner:** Claude Code
**Reviewer:** chat Claude + human
**Scope:** Aether's second phenomenon domain: surface-temperature anomalies (heatwave / urban-heat events), built as an instantiation of the existing ontology and hypothesis machinery — NOT a parallel app bolted on. Four gated stages, probe-first, same rules as Sprint 7. Flagship case: a severe documented Indian heat event (the probe selects it from data, see Stage A).

## Why this sprint

Methane proved the loop on point sources. Heat is the generality test for the PLATFORM: an area phenomenon (no single source point), multi-factor causation (no OGIM polygon to blame), different sensors, different reference truth. If the ontology (Observation→Detection→Phenomenon→Hypothesis→Brief), the tier rubric, and the guard culture survive this domain, Aether is a platform; if they need forking, better to learn now. This vertical is also the prerequisite for the grounded-chatbot horizon: "why is this region hot" is the question the hypothesis engine v2 must answer with evidence before any LLM is allowed to narrate it.

## Cardinal rules (additions to the standing ones)

1. **No event from memory.** The flagship heat event is SELECTED BY THE PROBE from data and documented reporting — reanalysis percentiles, IMD bulletins/peer-reviewed event attribution if accessible — never asserted from the assistant's training knowledge. The event, window, and region must each carry provenance.
2. **LST is not air temperature.** Satellite land-surface (skin) temperature and 2 m air temperature are different physical quantities. Every comparison across them must state the distinction; no panel may imply a satellite LST "measures" the air temperature people experience. This is the heat vertical's version of the scope caveat.
3. **Multi-factor honesty.** Heat causation is entangled (synoptic pattern, soil-moisture deficit, urban fabric, advection, humidity). The hypothesis engine must rank CONTRIBUTING FACTORS with evidence, not crown a single cause — the dense-coverage lesson, ported: when factors can't be discriminated, that IS the finding.
4. **Forecasts remain out of scope.** Reanalysis (the past) yes; forecast products (the future) no — consumption of published forecasts is a later horizon, building them is never in scope.

## STAGE A — Data-spine + event probe (report, then STOP)

1. **Sensor/data access probe** (verify, don't assume, each access path token/cost-wise):
   - Landsat 8/9 Collection-2 Level-2 Surface Temperature (and access route: AWS open data / USGS M2M).
   - MODIS LST (MOD11A2/MYD11A2 or daily; LP DAAC route, same Earthdata auth as EMIT).
   - ERA5 via the existing ARCO path: 2 m temperature, soil moisture, geopotential (synoptic), winds, humidity.
   - Land-cover for urban/rural classification (ESA WorldCover or equivalent open product).
   - **In-situ stations — the VALIDATED question:** what Indian surface-station data is genuinely, legally accessible (IMD open data? GSOD/ISD via NOAA?)? If usable in-situ 2 m temperature exists for the event window, the tier rubric's VALIDATED becomes earnable for the first time — for the AIR-temperature claims specifically (rule 2). Report exactly what exists and its license.
2. **Event selection:** from ERA5 climatology percentiles + documented reporting, select ONE severe Indian heat event (region + window) with strong data coverage across the above sources. Justify the choice with the data, cite the reporting, record rejected alternatives briefly.
3. **Benchmark YAML** for the event, same schema (extended if needed via ADR): reference quantities (e.g., peak anomaly, duration), each with `reference_usability` declared honestly.
4. **Ontology probe:** what does the existing Pydantic ontology need for an AREA phenomenon (no source point S, no plume mask — instead a region, an anomaly field, a baseline definition)? Propose the minimal schema evolution; do not fork the ontology.
**Stop and report** (docs/reports/sprint9_stage_a_report.md). The probe decides the validation design and the earnable tier, exactly like Sprint 7.

## STAGE B — Anomaly detection + quantification (report, then STOP)

1. **Baseline/climatology definition** (the science heart, document the choice): anomaly = observation minus a defensible climatological baseline (e.g., same-period multi-year ERA5/MODIS mean). The baseline definition is a first-class assumption with sensitivity reported.
2. **Detection:** LST anomaly fields for the event window (MODIS for coverage, Landsat for resolution where available); urban-rural delta (UHI) computed against the land-cover classification, with the classification's own uncertainty noted.
3. **Quantification analogues:** peak anomaly (K), spatial extent (km² above threshold), duration (days), UHI intensity (K) — each with an uncertainty treatment appropriate to its sources (sensor, baseline, classification), budgeted like Q's budget.
4. **Cross-checks per the probe:** MODIS-vs-Landsat-vs-ERA5 consistency where they overlap (stated as cross-checks between non-independent-but-distinct products); in-situ comparison IF Stage A found usable stations — computed with the LST-vs-air-temp distinction explicit (compare ERA5 2m and stations directly; relate LST separately).
5. Shared-code discipline: extend the event registry/runner pattern — a heat event is an EVENT in the same system, not a new pipeline family. Report every methane-shaped assumption found.
**Stop for review.**

## STAGE C — Hypothesis engine v2: multi-factor attribution (report, then STOP)

The sprint's center of gravity. Generalize the engine from "which facility" to "which factors, with what weight":
1. **Phenomenon-agnostic evidence schema** (ADR): candidates become FACTORS (synoptic ridge/heat dome from ERA5 geopotential; soil-moisture deficit from ERA5; urban fabric from land cover + UHI delta; humidity's role in experienced severity), each with computed diagnostics as evidence — every factor claim grounded in a number from a committed artifact, the no-fabrication guard's analogue: no factor may be asserted that lacks a computed diagnostic behind it.
2. Same machinery, ported not forked: deterministic templating, assumptions, counter-considerations, falsification per factor, qualitative tiers reflecting DISCRIMINATION power, scoring disclaimer, confidence caps where factors can't be separated.
3. The Goturdepe/Permian lesson encoded from day one: if soil-moisture deficit and synoptic forcing can't be disentangled with this data, the engine says so as the headline, first-class.
4. Methane events untouched: Goturdepe/Permian attribution artifacts byte-identical; the facility-level builders keep passing their guards.
**Stop for review — I will read the factor hypotheses like the Sprint 4/7C gates.**

## STAGE D — UI integration (gated)

1. The heat event on the globe as a new phenomenon class (area glyph/heat field rendering, not a plume point), fly-to, inspector adapted: anomaly map with baseline toggle, the quantification analogues, the factor hypotheses with all honesty elements, tier badge per the probe's earned tier, the LST-vs-air-temp distinction as a first-class block.
2. The species/product HUD lines generalize (no longer CH4-only hardcoding) — report what was methane-shaped in the UI.
3. Two-domain integrity: methane events unchanged pixel-wise (regression screenshots), state isolation across phenomenon types.
4. Standard shot list for my review.

## Out of scope
Forecast products, the chatbot, ocean vertical, additional methane events, deployment (separately scheduled), SDA. No LLM anywhere in the engine.

## Definition of done
Probe-decided event + tier with full provenance; anomaly detection + budgeted quantification analogues + honest cross-checks (in-situ if earned); hypothesis engine v2 producing grounded multi-factor attribution under the full honesty machinery; heat live in the UI with methane untouched (byte-identical artifacts, regression screenshots); guards extended to the new domain (no-fabrication-for-factors, no-staleness for new docs, tier guard covering the new event); suite + CI green; gate reports committed at every stage; STOP at each gate.

## Build order
Stage A probe → STOP. Stage B detection/quantification → STOP. Stage C engine v2 → STOP. Stage D UI → STOP.
