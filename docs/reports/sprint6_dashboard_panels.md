# Sprint 6 — Dashboard panel evidence (data-exact, from the live API)

> Rendered verbatim from `GET /api/events/turkmenistan_goturdepe_2022_08_15` after the v2 migration
> + the two review fixes (Provenance·References flip; H1 bearing-gap consistency).
> These are the exact values the React Inspector binds to. Browser PNGs require
> the app running locally (commands in the gate report) — no browser driver is installed here.

## 1. Headline Q — `Emission Rate · IME` panel
```
   OURS-CAL   23.4  t CH4 / hr   range 14.0 - 26.4   1sigma +/-12.8%
   NASA-CAL   16.0  t CH4 / hr   range 9.6 - 18.1
```

## 2. Uncertainty Budget panel
```
  α₁ wind parameterization             ±7.6%  |##################            |  (symmetric)
  ERA5 wind representativeness        ±10.2%  |########################      |  (symmetric)
  Plume-mask sensitivity               ±1.5%  |####                          |  (symmetric)
  MF amplitude (systematic)           +1.46×  |##############################|  (systematic)
```

## 3. Provenance line + References panel  [FIXED — escape #1]
```
  Pearson vs NASA L2B (bbox) : 0.7314   (NASA L2B CH4ENH)
  target_spectrum_source     :
    Independent HITRAN2020 line-by-line (HAPI) — saturation-aware unit
    absorption via finite-enhancement log-radiance regression (Thompson/EMIT-
    ATBD method). NASA per-granule target NOT used (shape cross-check only,
    r=0.993). See stage_a_outputs/turkmenistan_goturdepe_2022_08_15/hitran_k/h
    itran_k_sat.json and hitran_k/hitran_k_sat_provenance.json.

  Provenance · References (rendered list):
   - Thorpe, A. K., et al. (2023). Attribution of individual methane and
     carbon dioxide emission sources using EMIT observations from space.
     Science Advances, 9(46), eadh2391.
     [doi:10.1126/sciadv.adh2391]
   - NASA LP DAAC. EMIT L2B Estimated Methane Plume Complexes 60 m V002.
     Plume complex EMIT_L2B_CH4PLM_002_20220815T042838_000494 corresponds to
     this granule.
     [doi:10.5067/EMIT/EMITL2BCH4PLM.002]
   - NASA LP DAAC. EMIT L2B Methane Enhancement Data 60 m V002. The raster
     EMIT_L2B_CH4ENH_002_20220815T042838_2222703_003 is used as the Stage A
     spatial-agreement reference.
     [doi:10.5067/EMIT/EMITL2BCH4ENH.002]
   - Gordon, I. E., et al. (2022). The HITRAN2020 molecular spectroscopic
     database. Journal of Quantitative Spectroscopy and Radiative Transfer,
     277, 107949. Line-by-line CH4 source for our INDEPENDENTLY GENERATED
     matched-filter unit absorption spectrum k (the operational retrieval
     since the Sprint 6 migration).
     [doi:10.1016/j.jqsrt.2021.107949]
   - Kochanov, R. V., et al. (2016). HITRAN Application Programming Interface
     and efficient spectroscopic tools (HAPI). Journal of Quantitative
     Spectroscopy and Radiative Transfer, 177, 15-30. Computes the Voigt
     cross-sections used to build our independent k.
     [doi:10.1016/j.jqsrt.2016.03.005]
   - NASA EMIT-Data-Resources tutorial
     Generating_Methane_Spectral_Fingerprint.ipynb. Ships the per-granule
     methane target spectrum file emit20220815t042838_ch4_target, used as a
     SPECTRAL-SHAPE CROSS-CHECK ONLY (Pearson r = 0.993 vs our independent
     HITRAN2020 k) — NOT a pipeline input since the Sprint 6 migration. Our
     matched filter no longer reads this file.
```

## 4. Source Attribution — H1 (expanded)  [bearing gap FIXED — escape #2]
```
  H1 (rank 1) — O&G operations within the BARSAGELMEZ oil & gas field
  Confidence: MODERATE  ·  heuristic score 0.87

  Score components:
    spatial_consistency    value=0.85  weight=0.60  contrib=0.510
        The back-projected upwind source S sits well inside the BARSAGELMEZ
        field polygon (point-in-polygon = True; field area 133.0 km^2). S's
        exact position IS uncertain (the ~23 deg centroid/upwind bearing gap
        and the speed-derived wedge — the same uncertainty H2 rests on), but
        because S lies well within such a large field, that wobble is very
        unlikely to move it across the field boundary. High, not 1.0.
    type_prior             value=0.90  weight=0.25  contrib=0.225
        Active oil & gas field; ~23 t/hr point sources here are
        characteristically O&G (Thorpe 2023 attributes this cluster to O&G).
    magnitude_consistency  value=0.90  weight=0.15  contrib=0.135
        ~23 t/hr is within documented O&G super-emitter range and ~2x the
        per-source mean of the Thorpe 163 t/hr / 12-source cluster.

  Falsification:
    A facility-resolved inventory (or higher-resolution back-projection)
    placing the source outside BARSAGELMEZ, or evidence the plume originates
    from a non-O&G process, would falsify this.
```
