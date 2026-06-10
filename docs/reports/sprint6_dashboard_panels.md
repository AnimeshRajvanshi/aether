# Sprint 6 — Dashboard panel evidence (data-exact, from the live API)

> Rendered verbatim from `GET /api/events/turkmenistan_goturdepe_2022_08_15` after the v2 migration.
> These are the exact values the React Inspector binds to. Browser PNGs require
> the app running locally (commands at the bottom) — no browser driver is installed here.

## 1. Headline Q — `Emission Rate · IME` panel

```
            [ OURS-CAL ]   [ NASA-CAL ]

   OURS-CAL   23.4  t CH4 / hr
              range 14.0 - 26.4 t/hr   1sigma +/-12.8%
              Central estimate from our INDEPENDENT retrieval — matched filter on a methane absorption spectrum generated from HITRAN2020 via HAPI (NASA's per-granule target is not used). The +1.46× MF over-amplitude vs NASA L2B is now reproduced independently — a real MF systematic, not a NASA-convention artifact — and carried one-sided.

   NASA-CAL   16.0  t CH4 / hr
              range 9.6 - 18.1 t/hr
              Our IME divided by the independently-measured 1.46× MF amplitude ratio vs NASA L2B (ours/NASA over the plume CC), anchoring the rate to NASA's enhancement amplitude for direct comparison to NASA-derived rates.
```

## 2. Uncertainty Budget panel

```
  α₁ wind parameterization             ±7.6%  |##################            |  (symmetric)
  ERA5 wind representativeness        ±10.2%  |########################      |  (symmetric)
  Plume-mask sensitivity               ±1.5%  |####                          |  (symmetric)
  MF amplitude (systematic)           +1.46×  |##############################|  (systematic)
```

## 3. Provenance line (Stage A Validation + Provenance)

```
  Pearson vs NASA L2B (bbox) : 0.7314   (NASA L2B CH4ENH)
  target_spectrum_source     : Independent HITRAN2020 line-by-line (HAPI) — saturation-aware unit absorption via finite-enhancement log-radiance regression (Thompson/EMIT-ATBD method). NASA per-granule target NOT used (shape cross-check only, r=0.993). See stage_a_outputs/turkmenistan_goturdepe_2022_08_15/hitran_k/hitran_k_sat.json and hitran_k/hitran_k_sat_provenance.json.
  L1B granule                : EMIT_L1B_RAD_001_20220815T042838_2222703_003
  bands used                 : 49

  Generated brief:
    EMIT imaged a coherent methane plume over the Goturdepe gas field on
    2022-08-15. Our independent retrieval — a matched filter on a methane
    absorption spectrum generated from HITRAN2020 via HAPI, with no NASA per-
    granule target — reproduces NASA's L2B enhancement at r = 0.73 and yields 35.7
    t integrated mass over a 193.8 km² mask. With a 6.9 m/s wind this implies ≈23
    t CH₄/hr from this single source — one of 12 Thorpe et al. quantify at 163 ±
    18 t/hr.

  Scope (read before citing):
    This is one source-connected plume. Thorpe et al. 2023 report 163 ± 18 t/hr
    for the full 12-source cluster. A single-plume estimate is not comparable to
    the cluster total — expected ≈10–14% of it.
```

## 4. Source Attribution — H1 (expanded)

```
  H1 (rank 1) — O&G operations within the BARSAGELMEZ oil & gas field
  Confidence: MODERATE  ·  heuristic score 0.87

  Claim:
    The ~23 t/hr methane plume most plausibly originates from oil & gas
    operations within the BARSAGELMEZ field, inside which the back-projected
    upwind source falls. Field/sector-level only: no specific facility can be
    named because OGIM has no point infrastructure in this region.

  Score components:
    spatial_consistency    value=0.85  weight=0.60  contrib=0.510
    type_prior             value=0.90  weight=0.25  contrib=0.225
    magnitude_consistency  value=0.90  weight=0.15  contrib=0.135

  Evidence:
    (spatial_containment) The back-projected upwind source S (39.3338 N,
    53.9884 E) lies inside the BARSAGELMEZ field polygon (OGIM_ID 2017938,
    133.0 km^2).
    (field_context) BARSAGELMEZ is an active OIL & GAS field (OGIM
    RESERVOIR_TYPE 'OIL & GAS', SRC_DATE 2014-01-01).
    (magnitude_range) Emission rate 23.4 t/hr (OURS-CAL) is a plausible
    single-source super-emitter magnitude within the Thorpe 163 +/- 18 t/hr,
    12-source cluster.
    (flaring_corroboration) A VIIRS flaring detection (OGIM_ID 141883,
    'UPSTREAM OIL') lies 3.2 km from S within the 2-sigma wedge, corroborating
    ONGOING upstream O&G activity in the area.
      CAVEAT: This VIIRS flaring detection is dated 2023-05-26, ~9 months
      AFTER the 2022-08-15 plume overpass. It is evidence of PERSISTENT O&G
      activity in the area, NOT evidence about this specific plume, and is NOT
      the located source.

  Falsification:
    A facility-resolved inventory (or higher-resolution back-projection) placing
    the source outside BARSAGELMEZ, or evidence the plume originates from a
    non-O&G process, would falsify this.
```
