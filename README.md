# Aether Planetary Engine (A.P.E.)

[![CI](https://github.com/AnimeshRajvanshi/aether/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AnimeshRajvanshi/aether/actions/workflows/ci.yml)

**An Earth-observation analysis engine that turns public satellite data into defensible,
uncertainty-quantified briefs — where every number on the screen traces back to a committed
artifact, and the caveats survive all the way to the dashboard.**

Live demo: **[aether.arkaneworks.co](https://aether.arkaneworks.co)** — three real events across two
phenomenon domains, served from committed artifacts (no runtime data fetching), with a machine-checked
[deployed-integrity verifier](tools/verify_deployment.py) proving the live API serves byte-identical
committed results at the git SHA it reports.

> **What this is — honestly.** Aether is a working analysis pipeline + dashboard for two kinds of
> Earth-observation event: methane super-emitter plumes (detect, quantify a flux, rank source
> hypotheses) and heat waves (anomaly detection, a pre-registered validation, multi-factor
> attribution). It is built around one typed ontology so cross-source reasoning and provenance are
> structural, not bolted on. It is **not** a real-time platform, not an "AI-native" product, and not a
> replication of any operational provider's pipeline — see *What is validated, and what is not* below.
> The roadmap (more events, more sensors) is real but is roadmap, not delivered work.

The figures quoted throughout this README come from **[`docs/key_results.json`](docs/key_results.json)**
— a committed source-of-truth snippet *extracted* from the validation artifacts (regenerate with
`uv run python tools/build_key_results.py`), stamped with the aether SHA it was read at. Nothing here
is retyped from memory.

## The three events (what the demo serves)

| Event | Sensor / date | What Aether produces | Tier |
|---|---|---|---|
| **Goturdepe, Turkmenistan** | EMIT 2022-08-15 | Methane flux **23.4 t/hr** (ours-cal) / **16.0 t/hr** (NASA-anchored); spatial agreement vs NASA L2B Pearson **0.731**; field/sector source attribution | **CROSS-CHECKED (strong)** |
| **Permian / Carlsbad NM** | EMIT 2022-08-26 | Methane flux **0.85 t/hr**; integrated mass vs NASA L2B **0.96×**; dense-coverage facility ranking | **CROSS-CHECKED (weaker)** |
| **NW/central India heat wave** | Mar–Apr 2022 (ERA5 / MODIS / stations) | Peak 2 m Tmax **46.68 °C**, regional anomaly **+5.67 K**; LST & UHI lanes; multi-factor attribution | **PER-QUANTITY** (C1/C2 VALIDATED) |

## The pipeline in brief

**Methane lane.** EMIT L1B radiance → an **independent matched-filter target spectrum** generated from
HITRAN2020 line-by-line data (via HAPI), saturation-aware (finite-enhancement log-radiance regression;
Thompson/EMIT-ATBD method) — **no MODTRAN, and NASA's per-granule target file is never read** (it is
retained only as a spectral-shape cross-check, Pearson **r = 0.993**) → per-column matched filter →
orthorectification → plume mask → integrated-mass-enhancement (IME, Varon 2018) flux **Q** with a
propagated uncertainty budget. Source attribution back-projects the plume against an oil-&-gas
infrastructure database (OGIM v2.7) and ranks **field/sector or facility** candidates with explicit
assumptions and a falsification path — never a single asserted source.

**Heat lane (two lanes, never conflated).** A **2 m air-temperature** lane (ERA5 reanalysis, validated
against NOAA ISD stations and the ERA5-independent IMD gridded product) and a separate **land-surface
(skin) temperature** lane (MODIS LST / Landsat) — these are different physical quantities and no LST
value is ever compared against an air-temperature claim. Multi-factor attribution ranks contributing
factors (synoptic ridge, soil moisture, advection, humidity, urban fabric) from computed ERA5
diagnostics; it establishes **presence and rarity**, not a quantified causal contribution.

## What is validated, and what is not

The validation tier is **earned by evidence, never asserted** (rubric:
[`docs/science/validation_tiers.md`](docs/science/validation_tiers.md)). This honesty *is* the product.

- **VALIDATED is reserved and held by no methane event** — it requires independent flux truth (a
  controlled release or peer-reviewed per-source flux) that none of these events has. The published
  references are at the wrong scope (Thorpe 2023 is a 12-source *cluster* total; the Permian 18.3 t/hr
  is a press-release figure) and are carried as context, never as a calibration target.
- **The methane flux is CROSS-CHECKED**, not validated: it agrees spatially / in integrated mass with
  NASA's independent L2B product, but absolute flux accuracy is unproven.
- **The +1.46× matched-filter amplitude systematic** (Goturdepe) is independently reproduced and
  **left uncorrected** — and it does **not** transfer to the Permian scene (flips to 0.96×). A finding,
  not a solved problem.
- **Heat C1 (peak 2 m Tmax, 46.68 °C) and C2 (regional anomaly, +5.67 K) are VALIDATED** under criteria
  **committed before the station data was read** (V1 vs ISD stations; V3 vs IMD). **C3 (duration) and
  C4 (extent) FAILED** their pre-registered criteria across two station datasets — that criterion-edge
  fragility is reported as the headline finding, not omitted. ERA5↔station consistency (V2) failed its
  pooled-r threshold and is permanently **not claimed** for this event.
- **LST and UHI are capped at CROSS-CHECKED** (no in-situ skin truth; daytime LST is a Terra
  ~10.7 h-local snapshot, never a daily maximum). The Delhi daytime **surface UHI is negative**
  (−0.77 K — an urban *cool* island), reported as counter-evidence to the urban-heat prior.
- **The AI orchestration layer is not built.** Attribution scores are documented deterministic
  heuristics — **not calibrated probabilities, not contribution fractions.** Use the tiers, not the
  decimals.

## Relationship to operational programs (e.g. Carbon Mapper)

Aether uses **public EMIT data** and open methods. It is **complementary to / inspired by** operational
methane-monitoring programs such as Carbon Mapper — it is **not affiliated with, endorsed by, or a
replication of** any of them. EMIT and the Tanager-class instruments share JPL imaging-spectrometer
*heritage* (true and worth noting); equivalence of pipelines or products is **not** claimed.

## Architecture

Five independently testable layers, all composing one ontology (ADR 0001):

```
aether/
├── apps/
│   ├── api/             FastAPI artifact server (serves committed Stage A/B + hypotheses; read-only)
│   └── web/             Next.js + CesiumJS dashboard (globe → fly-to → plume → inspector)
├── packages/
│   ├── ontology/        Pydantic v2 typed ontology (extra="forbid", mandatory Provenance)
│   ├── data_spine/      Ingestion / normalization / caching (EMIT, ERA5, MODIS; COG/Zarr/STAC)
│   ├── detection/       Matched-filter retrieval, IME quantification, independent HITRAN k
│   ├── causal/          Source-attribution + multi-factor-attribution engines (OGIM-backed)
│   ├── ai/              Claude/Grok orchestration — SPECIFIED, NOT BUILT
│   └── shared/          Common utilities
├── eval/                Benchmark events (real references) + the aether-eval harness
├── tools/               Deployed-integrity verifier, image-inventory guard, key-results snippet
├── stage_a_outputs/ stage_b_outputs/ attribution_outputs/   Committed real results (the demo's data)
└── docs/
    ├── adr/             Architectural Decision Records
    ├── science/         Method + validation + honesty write-ups (incl. the validation-tier rubric)
    └── reports/         Per-sprint gate reports
```

The deployed dashboard serves **committed artifacts only** — no runtime fetching, no credentialed
access. `tools/verify_deployment.py` (CI-wired) proves the live API serves byte-identical committed
results at the SHA it reports, and that non-redistributable raw data (NOAA ISD) is provably absent.

## Running it locally

```bash
uv sync                       # Python 3.12, uv workspace
uv run pytest                 # full suite (network-gated integration tests deselected by default)
uv run ruff check .           # lint (line length 100)
uv run aether-eval run        # the REAL detection pipeline on cached inputs, scored honestly
uv run python tools/build_key_results.py   # regenerate the source-of-truth figures snippet
```

The web app (`apps/web`) uses `pnpm` (`pnpm install`, `pnpm dev`, `pnpm typecheck`). The full eval run
needs a local granule cache + ARCO-ERA5 network access and is network-gated; CI runs the harness logic
+ regression assertions instead. See [`SETUP.md`](SETUP.md) and
[`docs/science/eval_semantics.md`](docs/science/eval_semantics.md).

**Reading the provenance.** Every ontology entity carries a `Provenance`. The dashboard renders the
committed artifacts verbatim; to verify a number, follow its `source` in
[`docs/key_results.json`](docs/key_results.json) to the artifact under `stage_a_outputs/`,
`stage_b_outputs/`, or `attribution_outputs/`, or read the in-depth
[scientific validation write-up](docs/science/sprint11_validation_writeup.md).

## Data sources & licenses

| Source | Use | License / terms |
|---|---|---|
| **EMIT** L1B/L2A/L2B (NASA LP DAAC) | methane radiance + NASA L2B cross-check | open; DOIs `10.5067/EMIT/EMITL2BCH4ENH.002`, `…CH4PLM.002` |
| **ARCO-ERA5** (ECMWF via Google) | reanalysis (air temp, winds, soil moisture, geopotential) | Copernicus / CC-BY |
| **MODIS** MOD11A1/A2 v061 (NASA) | land-surface temperature | open (via Microsoft Planetary Computer COGs) |
| **Landsat 8/9 C2L2** (USGS) | surface temperature cross-check | open (via Planetary Computer) |
| **ESA WorldCover** v200 (2021) | urban/rural classification for UHI | CC BY 4.0 |
| **NOAA ISD** stations | air-temperature validation anchor | **WMO Res. 40 — non-US raw is non-redistributable**; cached locally, only derived statistics committed |
| **IMD** gridded daily Tmax | ERA5-independent anomaly reference | station-derived product; license verified before committing derived artifacts |
| **OGIM** v2.7 | oil-&-gas infrastructure for attribution | CC BY 4.0; doi `10.5281/zenodo.15103476` |

## Key citations (full machine-readable list in [`docs/key_results.json`](docs/key_results.json))

- Thorpe, A. K., et al. (2023). *Attribution of individual methane and CO₂ emission sources using EMIT
  observations from space.* Science Advances 9(46), eadh2391. doi `10.1126/sciadv.adh2391`.
- Gordon, I. E., et al. (2022). *The HITRAN2020 molecular spectroscopic database.* JQSRT 277, 107949.
  doi `10.1016/j.jqsrt.2021.107949`. — Kochanov, R. V., et al. (2016). *HAPI.* JQSRT 177, 15–30.
  doi `10.1016/j.jqsrt.2016.03.005`.
- Zachariah, M., et al. (2023). *Attribution of the 2022 early-spring heatwave in India and Pakistan to
  climate change.* Env. Res.: Climate 2(4), 045005. doi `10.1088/2752-5295/acf4b6`. *(cited external —
  Aether does not perform extreme-event attribution.)*
- Srivastava, A., Kumar, N., & Mohapatra, M. (2024). *Unprecedented hot weather … March–April 2022.*
  MAUSAM 75(2), 551–558. doi `10.54302/mausam.v75i2.6196`.
- Duren, R. M., et al. (2019). *California's methane super-emitters.* Nature 575.
  doi `10.1038/s41586-019-1720-3`. — Cusworth, D. H., et al. (2021). doi `10.1021/acs.estlett.1c00173`.

## Status

Sprints 1–10 closed; the app is live with a machine-checked deployed-integrity proof. See
[`PROJECT_STATUS.md`](PROJECT_STATUS.md) and [`HANDOFF.md`](HANDOFF.md) for the verified current state,
and [`docs/aether_spec.md`](docs/aether_spec.md) for the full product specification (including the
roadmap, which is labeled as roadmap, not delivered work).

## License

TBD. Currently private.
