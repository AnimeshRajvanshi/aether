# Task: Sprint 2 — Our own methane detection and quantification

**Owner:** Claude Code
**Reviewer:** chat Claude (science/architecture) + human (runs it, holds credentials)
**Scope:** Detection and quantification ONLY. No causal engine. No dashboard. No new benchmark events beyond what this task needs. One event (Permian Carlsbad 2022), validated hard.

## Goal

Stop rendering NASA's answer. Compute our own.

Take EMIT **L1B radiance** (the raw spectral cube, before any plume has been found) for the Permian Carlsbad granule used in Sprint 1, and:

**Stage A — Detection.** Run a columnwise matched filter to produce our own methane enhancement map (units: ppm·m or equivalent, with per-pixel uncertainty). Validate it densely against NASA's L2B `ch4_enhancement` product for the *same granule*.

**Stage B — Quantification.** Segment the plume, integrate enhancement into a total excess methane mass (IME), combine with ERA5 wind to produce an emission rate in tonnes/hour with propagated uncertainty. Validate against NASA's published 18.3 ± 2.0 t/hr.

Wire both into the eval harness so `aether-eval run` scores our quantification against the `permian_basin_2022` benchmark event.

## THE ANTI-FABRICATION RULE (read twice)

**Do not tune any parameter to make our number match NASA's.** Wind speed, plume mask threshold, calibration constants, and band selection must each be set by a principled, documented choice — a literature value, a physical argument, or a stated default — *before* looking at how close the resulting flux is to 18.3 t/hr. Whatever number falls out is the number we report. If it is off by 40%, report 40% off with honest uncertainty and a discussion of why. Tuning to the known answer silently destroys the benchmark's meaning and is treated as a critical failure, not a shortcut. The same applies to Stage A: do not fit our enhancement to NASA's raster.

## Prerequisites the human must do (not you)

- **EMIT L1B radiance access.** Same NASA Earthdata credentials as Sprint 1; L1B RAD is a different product than L2B CH4ENH. Confirm the human can download it.
- **ERA5 wind.** Two candidate sources — verify which is accessible and prefer the one needing no extra credential:
  - **ARCO-ERA5** (analysis-ready, cloud-optimized ERA5 on a public Google Cloud bucket, Zarr format) — likely needs no account. Confirm it carries 10 m u/v wind components at the time/location.
  - **Copernicus CDS API** — authoritative but requires a free CDS account and API key (the human must create it). Fall back to this only if ARCO-ERA5 doesn't have what we need.
  State which you used and why.

## Verify before you build (the physics that must be right)

Small errors here produce confident garbage. Confirm each against authoritative sources and cite what you found in code comments and your summary:

1. **EMIT L1B radiance product** — exact product short-name/version, the radiance variable name, units, wavelength array, and how the per-band data is laid out. Source: LP DAAC EMIT L1B product page + NASA EMIT-Data-Resources repo.
2. **The matched filter target signature.** This is the crux. The methane "unit absorption spectrum" (fractional change in radiance per unit CH4 column) must be physically correct and convolved to EMIT's spectral response in the relevant bands. Do NOT build a line-by-line radiative transfer model from scratch (out of scope, rabbit hole). Instead find a published/precomputed methane unit absorption spectrum for EMIT/AVIRIS-NG-class sensors, or a documented method to generate one (e.g., HITRAN-based cross-sections convolved to EMIT bands). Verify the sign convention and units. Cite the source.
3. **Which bands.** Methane's strong SWIR absorption feature is near 2.3 µm; the standard retrieval window is roughly 2100–2500 nm. Confirm the exact window used in the EMIT/AVIRIS-NG literature.
4. **IME unit conversion.** Converting enhancement (ppm·m or mol/m²) to mass column (kg/m²) requires a documented conversion. Get it right; cite it.
5. **The U_eff wind parameterization.** The IME method relates effective wind speed to the reanalysis 10 m wind via an empirical calibration (Varon et al. 2018). Use the published coefficients; cite them. Do not invent a relationship.

## Reference formulation (verify, don't trust this from memory)

**Columnwise matched filter** — for each cross-track column, using only the SWIR methane bands:

```
alpha(x) = [ (x - mu)^T  Sigma^-1  t ] / [ t^T  Sigma^-1  t ]
```

- `x` — radiance spectrum at a pixel (methane bands only)
- `mu` — per-column mean radiance (background)
- `Sigma` — per-column background radiance covariance (regularize if ill-conditioned)
- `t` — target signature; standard construction is elementwise `t = mu ⊙ k`, where `k` is the methane unit absorption spectrum. **Verify the exact construction, sign, and units.**
- `alpha` — the methane column enhancement at that pixel

Per-column statistics are essential: EMIT is a push-broom sensor; a global covariance produces cross-track artifacts. Watch for false positives over bright/heterogeneous surfaces (Carbon Mapper's own QC docs flag soil artifacts).

**IME quantification** (Varon et al. 2018 framework):

```
IME = sum over plume pixels of ( mass_column[i] * pixel_area )      # total excess CH4 mass, kg
Q   = U_eff * IME / L                                                # emission rate, kg/s
```

- `L` — plume characteristic length (e.g., sqrt(plume area), or as defined in the reference)
- `U_eff` — effective wind from ERA5 10 m wind via the Varon 2018 parameterization
- Convert `Q` to tonnes/hr for comparison.

Propagate uncertainty from at least: wind speed, enhancement noise, and plume mask sensitivity. A single-overpass IME estimate honestly carries large uncertainty — report it.

## Key literature to consult (verify exact citation details before citing)

- Thompson et al. (~2015), matched-filter methane retrieval for imaging spectrometers, *Atmos. Meas. Tech.*
- Frankenberg et al. (2016), AVIRIS-NG Four Corners methane, *PNAS*.
- Varon et al. (2018), IME quantification of methane point sources, *Atmos. Meas. Tech.* — the quantification reference.
- Foote et al. (2020), matched filter with sparsity prior, *IEEE TGRS*.
- Thorpe et al. (2023), EMIT methane/CO2 source attribution from space — for EMIT-specific methodology.
- EMIT methane Algorithm Theoretical Basis Document (ATBD), if public.

Verify these exist and are cited correctly; do not reproduce text from them.

## Deliverables

1. **`packages/detection`** — real workspace package with: a `matched_filter` module (per-column MF producing an enhancement raster + uncertainty), a `target_signature` module (verified methane unit absorption spectrum), a `plume_segmentation` module (threshold/connected-components to mask the plume), all producing/consuming ontology types (`Observation`, `Detection`).
2. **`packages/detection` quantification** — an `ime` module computing IME and emission rate with uncertainty, consuming ERA5 wind.
3. **ERA5 wind ingestion** in `packages/data_spine` (ERA5 is one of our locked sources). Cache it.
4. **EMIT L1B ingestion** in `packages/data_spine` (extends the existing EMIT module).
5. **Eval wiring** — replace the stub pipeline so `aether-eval run` runs our detection+quantification on `permian_basin_2022` and scores quantification MAPE against the benchmark's `emission_rate_metric_tonnes_per_hr`.
6. **Validation writeup** in `docs/science/sprint2_validation.md` — Stage A: spatial agreement between our enhancement and NASA's L2B (a correlation/scatter, plume co-location). Stage B: our flux ± uncertainty vs NASA's 18.3 ± 2.0 t/hr, with discussion. Include the comparison honestly whatever it shows.
7. **Tests** — unit tests with synthetic data (inject a known plume into synthetic radiance, confirm the MF recovers it; confirm IME recovers a known mass). Mock all network in CI. Integration tests marked `@pytest.mark.integration`, skipped by default.

## Definition of done (the two gates)

**Stage A gate:** Our matched-filter enhancement, over the plume region of the Permian granule, shows strong spatial agreement with NASA's L2B `ch4_enhancement` (target: clear co-location of the plume and positive correlation over the plume area — propose a concrete threshold in the writeup and justify it). The synthetic-plume unit test passes.

**Stage B gate:** Our IME emission rate, with propagated uncertainty, is computed by principled choices (no tuning) and is *statistically consistent* with NASA's 18.3 ± 2.0 t/hr — i.e., the uncertainty intervals overlap, OR if they don't, the discrepancy is honestly characterized and explained. `aether-eval run` reports the quantification MAPE for the event.

**Both:** `uv run pytest` passes (integration skipped by default). You produce a summary stating every parameter choice, its source, what you assumed, and what you most want the reviewer to scrutinize.

## Out of scope (do NOT do these now)

- No causal/hypothesis engine.
- No dashboard, no web UI, no API.
- No additional benchmark events.
- No data sources beyond EMIT (L1B + L2B) and ERA5.
- No line-by-line radiative transfer model built from scratch.
