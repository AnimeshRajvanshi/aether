# Factor hypotheses — india_nw_heatwave_2022_04

**Headline.** F1 (Persistent synoptic ridge) leads F2 by 0.69 (>0.15) under the documented heuristic — a ranking, not an established apportionment. The expected ridge-vs-dry-soil entanglement did NOT materialize for this event because the diagnostics argue against several popular priors: antecedent soil moisture was near climatology (dryness rank 57% — the pre-dried-land narrative is unsupported), low-level flow was essentially climatological (anomaly 0.39 m/s), airmass humidity was near-normal (rank 47% dry), and the urban-fabric prior is argued AGAINST by the measured negative daytime surface UHI (-0.77 K). What remains, by these diagnostics, is a rare and persistent synoptic ridge (+61.6 m, above all 30 climatology windows, 10/10 days above the pooled p90) over a region whose in-window drying followed the heat.

**Attribution boundary.** This engine ranks PHYSICAL CONTRIBUTING FACTORS with computed diagnostics. It does NOT perform probabilistic extreme-event attribution (anthropogenic influence). The published attribution result below is cited external evidence — never computed here, never blended into factor scores.

**Scoring disclaimer.** Scores are documented heuristics over computed diagnostics — weighted presence/rarity/persistence indices, NOT calibrated probabilities and NOT contribution fractions. Use the tiers and the headline, not the decimals.

**Confidence cap.** Warming-contributor tiers are capped at moderate: diagnostics establish presence and rarity of co-varying factors but cannot causally separate them without counterfactual experiments (out of scope). HIGH is reserved and unearned.

## F1 (rank 1) — Persistent synoptic ridge / anticyclonic mid-troposphere

*Role:* warming_contributor · *Tier:* **moderate** · *Score:* 1.00 (heuristic)

A persistent mid-tropospheric ridge sat over the region: window-mean regional 500 hPa height 5875.8 m (cross-store-corrected from 5871.4 m) vs climatology 5814.2 m (+61.6 m, 100% percentile of 30 same-window years; 10/10 days above the pooled p90). Anticyclonic subsidence and clear skies under such ridges are an established heatwave driver; the diagnostic establishes presence and rarity, not a quantified temperature contribution.

**Diagnostics (every claim binds to these):**
- `z500_window_mean_anomaly` = 61.6 m — 2022 window-mean regional z500 minus 1991-2020 same-window mean (source: attribution_outputs/india_nw_heatwave_2022_04/diagnostics.json#z500)
- `z500_percentile_vs_30_window_means` = 1.0 fraction — rank of the 2022 window mean among 30 climatology window means (source: attribution_outputs/india_nw_heatwave_2022_04/diagnostics.json#z500)
- `z500_days_above_pooled_p90` = 10.0 days — window days with daily regional z500 above the pooled clim p90 (source: attribution_outputs/india_nw_heatwave_2022_04/diagnostics.json#z500)

**Assumptions:**
- ERA5 z500 is well constrained by assimilated upper-air observations over South Asia (radiosondes, aircraft, satellites).
- The 2022 value (0.25-deg store) and the climatology (1.5-deg conservative store) are comparable as regional MEANS; conservative regridding preserves area means (cross-store caveat stated in diagnostics.json).
- 06:00 UTC sampling represents the window's synoptic state (ridges evolve on multi-day timescales).

**Counter-considerations:**
- Ridge presence co-occurs with (and is amplified by) dry land surfaces — presence does not apportion contribution.
- A single regional-mean index can under-represent ridge structure (amplitude vs extent).

**Falsification:** Independent upper-air analyses (radiosonde geopotential heights) or a higher-resolution reanalysis showing no anomalous ridge over the region during the window would falsify the presence claim.

## F2 (rank 2) — Antecedent soil-moisture deficit (land-surface preconditioning)

*Role:* warming_contributor · *Tier:* **low** · *Score:* 0.31 (heuristic)

The popular pre-dried-soil narrative is NOT supported by this diagnostic: March 2022 regional soil moisture was near climatology (dryness rank 57%). In-window soil moisture was drier than 87% of years, but in-window drying is concurrent with — and plausibly caused by — the heat itself, so it cannot establish preconditioning. Dry soils amplify heat via suppressed evaporative cooling; for THIS event the antecedent diagnostic carries the preconditioning question, and it reads near-normal.

**Diagnostics (every claim binds to these):**
- `antecedent_march_soil_moisture` = 0.1565 m3/m3 — March 2022 mean volumetric soil water (0-7 cm), bbox land (source: attribution_outputs/india_nw_heatwave_2022_04/diagnostics.json#soil_moisture)
- `antecedent_dryness_percentile` = 0.567 fraction — 1 - percentile of 2022 March soil moisture among 1991-2020 (source: attribution_outputs/india_nw_heatwave_2022_04/diagnostics.json#soil_moisture)

**Assumptions:**
- ERA5 volumetric soil water is a land-surface-model product, only weakly constrained by observations — treated as a physically consistent index, not a measurement.
- Layer 1 (0-7 cm) dryness is representative of the evaporative regime at event timescales.

**Counter-considerations:**
- Soil dryness is partly CAUSED by the same circulation pattern (rainfall deficit under persistent ridging) — circularity with F1 is intrinsic and is why the engine does not claim discrimination.
- No in-situ or independent satellite soil-moisture diagnostic was computed in this stage (SMAP/ASCAT are out of the locked source list).

**Falsification:** Independent soil-moisture observations (in-situ networks, satellite retrievals) showing anomalously DRY antecedent soils over the region would overturn this against-prior finding (and would support the preconditioning narrative this diagnostic does not).

## F3 (rank 3) — Low-level advection from the arid continental sector

*Role:* warming_contributor · *Tier:* **low** · *Score:* 0.28 (heuristic)

Window-mean near-surface flow was FROM 265.6 deg at 1.41 m/s, vs climatology FROM 267.5 deg — anomaly vector magnitude 0.39 m/s: essentially climatological flow — no anomalous advective contribution is indicated. The arid-sector direction is the climatological norm here and is reported as state, not as event evidence (no trajectory analysis in scope).

**Diagnostics (every claim binds to these):**
- `window_from_direction` = 265.6 deg — meteorological FROM-direction of the window-mean 10 m wind (source: attribution_outputs/india_nw_heatwave_2022_04/diagnostics.json#winds)
- `wind_anomaly_magnitude` = 0.39 m/s — magnitude of (2022 window-mean vector - climatology vector) (source: attribution_outputs/india_nw_heatwave_2022_04/diagnostics.json#winds)

**Assumptions:**
- A bbox-mean 10 m vector meaningfully summarizes low-level flow at synoptic scale (it averages over sea-breeze and orographic detail).
- The W-N sector proxies arid-source advection (Thar/Baluchistan) without an explicit trajectory model.

**Counter-considerations:**
- 10 m winds under a ridge are weak; advection may be secondary to subsidence + local heating.
- No air-mass trajectory analysis was computed — sector membership is a coarse proxy.

**Falsification:** Back-trajectory analysis (e.g., HYSPLIT on reanalysis winds) demonstrating anomalously strong or persistent transport from the arid sector relative to climatology would overturn the no-anomalous-advection finding.

## F4 (rank 4) — Airmass humidity (severity framing, not a warming driver)

*Role:* severity_framing · *Tier:* **insufficient** · *Score:* 0.07 (heuristic)

Airmass humidity was near climatology (dewpoint anomaly +0.13 K, dryness rank 47%). Neither a dry-heat mitigation nor a humid-heat amplification of experienced severity is indicated by this diagnostic — the framing factor is NOT active for this event at the sampled hour. This factor frames experienced severity and is NOT ranked as a temperature driver.

**Diagnostics (every claim binds to these):**
- `dewpoint_window_anomaly` = 0.13 K — 2022 window-mean 2 m dewpoint minus 1991-2020 same-window mean (source: attribution_outputs/india_nw_heatwave_2022_04/diagnostics.json#dewpoint)

**Assumptions:**
- ERA5 2 m dewpoint is adequate for a regional-mean dryness index (assimilation-constrained like t2m).

**Counter-considerations:**
- Dryness interacts with the soil-moisture factor (same land-atmosphere coupling); it is not independent evidence.

**Falsification:** Station humidity observations (dewpoint/wet-bulb) showing an anomalously dry or anomalously humid airmass during the window would overturn the not-active finding.

## F5 (rank 5) — Urban fabric (daytime surface signal NEGATIVE at the observed time)

*Role:* counter_evidence · *Tier:* **insufficient** · *Score:* 0.00 (heuristic)

The measured Delhi daytime SURFACE urban-rural delta during the window is NEGATIVE: -0.77 K (±0.8 K day-to-day, n=10; sign robust across sensitivity range -1.05..-0.74 K) at Terra ~10:30 local snapshot (the only observed daytime LST time). The data therefore argues AGAINST urban heat as a daytime warming factor for this event at the only observed time — the urban core read COOLER than its dry rural surroundings. The nighttime and 2 m air-temperature urban roles are EXPLICITLY UNASSESSED: no diagnostic for them exists in this stack (no nighttime analysis, no intra-urban air-temperature network).

**Diagnostics (every claim binds to these):**
- `window_mean_daytime_surface_uhi` = -0.77 K — Delhi urban-core minus rural-ring MODIS LST, window mean, Terra ~10:30 local (committed Stage B artifact) (source: stage_b_outputs/india_nw_heatwave_2022_04/uhi.json)

**Assumptions:**
- The Stage B UHI definition (WorldCover masks, 20/20-40 km geometry) represents Delhi's urban fabric adequately at 1 km.
- Skin temperature is the relevant quantity for a *surface* urban signal (2 m air is a different quantity — cardinal rule 2).

**Counter-considerations:**
- Urban heat islands are classically strongest at NIGHT and in 2 m air — neither was observed in this stack; absence of a daytime surface signal does not refute a nighttime/air urban contribution.
- One city (Delhi) is not the whole event region.

**Falsification:** The committed daytime-surface finding would be OVERTURNED by an independent LST analysis of the same window (different masks, sensors, or QC) showing a positive daytime urban-rural delta. Separately, the UNASSESSED nighttime/air-temperature roles would be ESTABLISHED (not overturned) by a nighttime LST analysis (MOD11A1 LST_Night) or an intra-urban air-temperature comparison showing a positive urban signal.

## External published attribution (cited, never scored)

- Zachariah et al. (2023): human-induced climate change made the March-April 2022 India-Pakistan heatwave about 30 times more likely and ~1 degC hotter than in a preindustrial climate (~1-in-100-year event in the 2022 climate). CITED EXTERNAL RESULT — not computed by Aether, not part of any factor score.
  - Source: Zachariah, M., et al. (2023). Environmental Research: Climate, 2(4), 045005. doi:10.1088/2752-5295/acf4b6
