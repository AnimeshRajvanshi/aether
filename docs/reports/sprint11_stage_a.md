# Sprint 11 — Stage A: Site probe + claims ledger

**Stage:** A (probe + ledger). **Status:** complete, STOP for review. **No persuasive narrative written.**
**Ledger as-of aether SHA:** `59c4a98` (main, in sync with origin; working tree clean except this sprint's task brief).
**arkaneworks probed at:** `AnimeshRajvanshi/arkaneworks` HEAD `135d2ec` (live GitHub repo, cloned fresh — the `~/Documents/arkaneworks` folder on disk was a stale May-2025 unzip and is NOT the live site).

> This is the spec the next two stages are checked against. Every figure below was read
> fresh from the committed artifact it lives in (via `jq`/Read), never from the task brief
> or chat — cardinal rule 5. Where a figure's exact artifact home is not yet pinned, it is
> flagged as a Stage-B source-of-truth-snippet task, not asserted.

## Cardinal rules in force (Sprint 11 additions + the standing four)

1. Every factual claim traces to a committed artifact (no-fabrication applied to prose).
2. Shipped is not aspirational — the vision (`AI-native`, `10×`, `causal deduction engine`,
   `planetary engine`, `SDA`, `exoplanet`, multi-body/Moon/Mars) never appears as delivered;
   at most once, late, labeled "where this is headed."
3. Caveats survive the narrative (flux CROSS-CHECKED not VALIDATED; +1.46× reproduced not solved;
   C3/C4 failed; LST/UHI capped; sparse coverage stated).
4. Honest about the relationship to Carbon Mapper (complementary/inspired-by, not replication,
   not affiliated, not endorsed; shared JPL spectrometer heritage true, pipeline equivalence false).
5. Figures are sourced, not retyped; the brief is not a source; one Stage-B snippet feeds all three deliverables.

---

# PART 1 — arkaneworks.co site probe

The case-study page must adopt **the site's** design language (so it sits beside the other
projects), not the dashboard's. The dashboard's amber/cyan HUD appears only inside embedded
screenshots.

## How the site is built

- **Plain static HTML** — no Jekyll, no framework, no build step. No `_config.yml`, `_layouts`,
  `_includes`, `Gemfile`, or `.nojekyll`. Each page is a hand-authored `*.html` file at repo root.
- **One shared stylesheet** `styles.css` (1309 lines) and **one shared script** `script.js`
  (312 lines), linked by every page. Fonts via Google Fonts (`<link>` in each `<head>`).
- **Deploy:** GitHub Pages, **`build_type: legacy`**, **source = `main` branch, path `/`**
  (confirmed live via `gh api repos/AnimeshRajvanshi/arkaneworks/pages`). Push to `main` → auto-build.
- **Domain:** `CNAME` = `arkaneworks.co` (apex), `https_enforced: true`. (Re-confirms the Sprint 10
  knowledge: apex → GitHub Pages; the `aether.arkaneworks.co` subdomain is a *separate* Vercel
  target for the live dashboard, untouched here.)

## Design language (actual values, from `styles.css` `:root` and base rules)

Stated intent (file header): *"Monochrome industrial / technical-document aesthetic."*

| token | value | role |
|---|---|---|
| `--bg` | `#0d0d0d` | near-black page background |
| `--panel` | `#121212` | panel surface |
| `--panel-glass` | `rgba(13,13,13,0.84)` | translucent panel |
| `--paper` / `--ink` | `#e7e7e2` | off-white primary text / hover |
| `--ink-soft` | `#c8c8c2` | secondary text |
| `--ink-dim` | `#9c9c96` | microlabels |
| `--ink-faint` | `#61615c` | faint text |
| `--line` | `#262626` | hairlines |
| `--line-strong` | `#3d3d3d` | strong rules |
| `--font-display` | `'Space Grotesk', 'Helvetica Neue', sans-serif` | display + body (weights 300–700) |
| `--font-mono` | `'IBM Plex Mono', 'SFMono-Regular', monospace` | labels (weights 400/500) |
| `--header-h` | `56px` | fixed blurred header height |
| `--gutter` | `clamp(20px, 7vw, 96px)` | page gutter |
| `--notch` | `16px` | signature notched-corner cut (`.notched` clip-path) |
| `--ease` | `cubic-bezier(0.16,1,0.3,1)` | motion easing |

- **No accent color.** The palette is pure monochrome (near-black + off-white + greys). There is
  **no amber/cyan anywhere** — that aesthetic is the dashboard's and must stay inside screenshots.
- **Signature touches:** a faint drafting-grid background (`72px` grid, `rgba(255,255,255,0.035)`),
  uppercase letter-spaced mono microlabels (`.micro`, 10.5px, `0.16em`), the notched-corner clip,
  a fixed `backdrop-filter: blur(14px)` header, mono "doc-code" labels (e.g. `AW–P02 · Active Program`).
- **Voice:** humble and honesty-forward — index hero: *"documented as it happened, including the
  parts that didn't work"*; the program note: *"Disclosure is deliberately limited — details are
  published when milestones are met, not before."* **This register already matches Aether's
  rigor-first thesis** — a positive finding: the case study can speak in the site's own voice.

## How project pages are structured and routed

- **Flat routing.** Every page is `<name>.html` at the root → `arkaneworks.co/<name>.html`
  (also resolvable as `/<name>`). **No `/aether/index.html`, no Jekyll collection, no `aether/` dir.**
- **Nav** is a shared header with an `Index` dropdown partitioned **Present** (P-01…P-03) /
  **Past** (01…08), hard-coded identically in all 14 pages, plus a Home and About link.
- **Project-page pattern** (canonical example `cubesat.html`, itself a hyperspectral remote-sensing
  project — a close domain fit for Aether): `section.project-hero` (`.crumbs` → `.project-title` →
  `.hero-panel` paragraph → `.spec-row` of four `.spec` cells) → `.content-blocks` of
  `.content-block` (each `.panel-head` title + `.idx` + paragraph) → a **References** content-block
  with `ul.custom-list` of external links → `nav.pager` (prev / index / next) → `footer.site-footer`.
  Some pages add a `<canvas class="animation-canvas" data-frame-folder="…">` hero animation.

## The existing "Aether" placeholder — and the collision it creates (GATE DECISION)

There is **no `aether.html`**. The page the brief calls the "placeholder Aether page" is
**`ape.html`**, and it is **not about this project**:

- **`ape.html`** — title *"Aether Planetary Engine — Arkane Works"*, acronym **A.P.E.**, listed as
  **Active Program AW‑P02** (`<span class="dd-code">P-02</span>` in every nav; a card on
  `index.html`). Its body reads: *"A.P.E. is a simulation-first study of **planetary-surface
  infrastructure**, growing out of the **Moon Presence** work: power generation and distribution,
  regolith handling, and the thermal realities of operating machines through a **14-day lunar
  night**."* Spec row: Phase *Study*, **Lineage *Moon Presence***, links to `lunar.html`.

So the slot the brief expects to "replace" currently describes a **lunar/planetary-surface
infrastructure concept** — a *different thing* from the shipped Earth methane+heat dashboard, and it
is written entirely in the frame **cardinal rule 2 forbids presenting as delivered** ("planetary
engine," lunar/Moon, multi-body). The aether repo's own `CLAUDE.md` *also* calls the methane
project "the Aether Planetary Engine," so the name is genuinely shared/ambiguous.

**This is the one mismatch that forces a design decision at the gate. Options:**

- **(A) Replace `ape.html` in place** — keep the route `/ape`, the **P‑02 Active-Program** slot and
  the "Aether" name; swap the lunar-infra placeholder body for the honest Earth methane+heat case
  study; demote "planetary engine / multi-body / lunar" to the single labeled aspirational horizon
  (rule 2). Minimal disruption (one file + the four-line hero/spec, nav untouched).
- **(B) Create `aether.html`** at `/aether` (the brief's literal target) and decide `ape.html`'s
  fate — redirect it, retire it, or keep it as a genuinely separate lunar program. Requires editing
  the shared nav dropdown + the index card in **all 14 pages** (every page hard-codes `ape.html`).

**Recommendation (for the human to confirm, not to decide unilaterally):** Option **A** — the
shipped work and the site placeholder already share the "Aether" name and the P‑02 slot, and the
brief's intent is "replace the placeholder." Reframe A.P.E. from the lunar cover-story to the
delivered Earth methane+heat monitoring work, with the planetary/multi-body ambition as the
labeled "where this is headed" footnote. **But this hinges on a fact only the human knows:** is the
lunar "Aether Planetary Engine" a real separate program, or was it always a placeholder name for
*this* project? **Do not proceed to Stage C until this is settled.**

## Other site-fit notes / mismatches flagged for the gate

- **Routing string in the brief** (`arkaneworks.co/aether`) ≠ the site's reality (`/ape`). Resolve
  with the option above. If `/aether` is mandatory, the all-pages nav edit (B) is the cost.
- **Design contrast is real but not a conflict:** site monochrome vs dashboard amber/cyan — handled
  by keeping the page in the site's palette and confining HUD color to screenshots (rule already in
  the brief). The case-study page must **not** import any dashboard CSS.
- **CV is out of scope** (`assets/Animesh_Rajvanshi_CV.pdf` exists; untouched).
- **Apex/www/`aether.` subdomain config untouched** — only the one project page changes in Stage C.

---

# PART 2 — Claims ledger

Every factual claim that may appear in any of the three deliverables, partitioned by tier, each
traced to the committed artifact + locator + the **exact** figure/string as it appears there. Built
by walking the artifacts at SHA `59c4a98`; not populated from memory or the brief.

Path key: `SB/<event>` = `stage_b_outputs/<event>/`, `SA/<event>` = `stage_a_outputs/<event>/`,
`AO/<event>` = `attribution_outputs/<event>/`, `BM` = `eval/benchmark/`.
Events: `got` = `turkmenistan_goturdepe_2022_08_15`, `perm` = `permian_basin_2022`,
`india` = `india_nw_heatwave_2022_04`.

## Partition 1 — SHIPPED & VALIDATED (strongest tier; criterion stated)

VALIDATED is earned **per-quantity** and only for the heat air-temperature claims, against
**pre-registered criteria committed before the station data was read** (`docs/science/sprint9_heat_validation.md`;
`validation.json#computed_after_pre_registration_commit = true`). The methane flux is **not** here
(no independent flux truth — see Partition 2). Event-level VALIDATED is **reserved and held by no
event** (`docs/science/validation_tiers.md`).

| # | Claim | Exact figure (as in artifact) | Source artifact # locator | Tier / criterion |
|---|---|---|---|---|
| V1 | NW-India heat peak 2 m Tmax | `46.68` °C, date `2022-04-10`, cell `29.0 N, 72.5 E` | `SB/india/air_lane.json # c1_peak_tmax` | **C1 VALIDATED** via pre-registered **V1**: ERA5 peak `46.68` vs max station `45.0` °C, bracket Δ `1.68 K ≤ 2.5 K`, `pass_v1=true` (`SB/india/validation.json # v1_station_peak_bracket`); stations are truth |
| V2 | NW-India peak regional-mean 2 m Tmax anomaly | peak `5.67 K` (`2022-04-08`); window-mean `5.103 K`; peak cell `11.88 K`; vs own 1991–2020 ±10 d clim | `SB/india/air_lane.json # c2_anomaly` | **C2 VALIDATED** via pre-registered **V3**: ERA5 `4.501 K` vs **IMD** `4.307 K` common-grid (|Δ| `0.194 K < 1.0`), pattern r `0.874 > 0.6`, `pass_v3a/b=true` (`SB/india/validation.json # v3_imd_anomaly_agreement`); IMD is an ERA5-independent station-gridded product |

> Note the dependency honesty that must survive: V1/V3 anchor against stations / IMD-gridded; ERA5
> assimilates synoptic stations, so V2-type ERA5↔station agreement is *consistency, not independent
> verification* (see HN4). C1/C2 VALIDATED rests on the *station/IMD* anchors, which are independent
> of ERA5 for the anomaly pattern (V3).

## Partition 2 — SHIPPED & CROSS-CHECKED / weaker (capped below VALIDATED; ceiling + why)

| # | Claim | Exact figure (as in artifact) | Source artifact # locator | Tier / ceiling reason |
|---|---|---|---|---|
| X1 | Goturdepe displayed methane flux (ours-cal) | `23.40` t/hr (`q_central_t_hr = 23.404806417186464`) | `SB/got/q_estimate.json` | **CROSS-CHECKED (strong)**; v2 saturation-aware HITRAN k (operational, Sprint 6) |
| X2 | Goturdepe flux NASA-anchored cross-check | `16.03` t/hr (`q_central_nasa_calibrated_t_hr = 16.027941696603943`) | `SB/got/q_estimate.json` | NASA-cal anchor; internally consistent, **not** flux truth |
| X3 | Goturdepe flux uncertainty | range `[13.97, 26.40]` t/hr; `q_total_fractional_sigma = 0.12813126…` (±12.8 %) | `SB/got/q_estimate.json # q_low/high_t_hr, q_total_fractional_sigma` | structural uncertainty (carried, not dropped) |
| X4 | Goturdepe end-to-end spatial agreement vs NASA L2B | Pearson bbox `0.7314199…`, full-scene `0.7153957…`, strong-signal `0.3428231…` | `SA/got/stage_a_report.json # pearson_in_bbox / pearson_full_scene / pearson_in_bbox_strong_signal` | the cross-check evidence for CROSS-CHECKED-strong |
| X5 | Independent methane target-spectrum shape vs NASA per-granule target | r `= 0.993` (shape cross-check only; NASA target **not** a pipeline input) | `SA/got/stage_a_report.json # target_spectrum_source`; `docs/science/validation_tiers.md:34`; `BM/turkmenistan…yaml` refs | HITRAN2020/HAPI independence; NASA file never read (`k_nasa_target_used=false`) |
| X6 | Permian methane flux (ours-cal) over NASA footprint | `0.85` t/hr (`q_central_t_hr = 0.8505414104…`) | `SB/perm/q_estimate.json` | **CROSS-CHECKED (weaker)** (`validation_tier`) |
| X7 | Permian flux vs NASA-own L2B same footprint+method | NASA `0.8849812…` t/hr; ratio ours/NASA `0.96×` (IME `77.548…` vs `80.688…` kg) | `SB/perm/q_estimate.json # q_nasa_l2b_same_footprint_t_hr, ime_*` | clean integrated-mass agreement (~4 %) |
| X8 | Permian full-scene spatial agreement | Pearson full-scene `0.5269452…`, bbox `0.5184744…` | `SA/perm/stage_a_report.json # pearson_full_scene / pearson_in_bbox` | weaker than Goturdepe |
| X9 | Permian plume-scale **pixel** agreement is weak | r ≈ `0.14` (exact `0.137` to be pinned in the Stage-B snippet — see F4) | `docs/science/validation_tiers.md:35` | why Permian is the weaker cross-check |
| X10 | Goturdepe surface emitter flux uses ERA5 wind | `era5_u10_speed_ms = 6.9347755…`; plume centroid `39.371 N, 53.690 E`; CC area `193.82 km²` | `SB/got/q_estimate.json` | |
| X11 | Permian surface state from ERA5 (not sea-level default) at ~1 km elevation | P `90896.7 Pa`, T `303.50 K`, scene elev `1086.36 m` | `SB/perm/q_estimate.json # surface_*`; `SA/perm/stage_a_report.json # scene_mean_elevation_m` | generality finding (ported method) |
| X12 | LST window-mean anomaly (NW India) | `+4.60 K` window-mean bbox; daily over 10 days | `SB/india/lst_lane.json # window_mean_bbox_anomaly_k` | **≤ CROSS-CHECKED** — no in-situ skin truth |
| X13 | Goturdepe attribution: H1 field-level | **BARSAGELMEZ** O&G field, score `0.87` (band high) **CAPPED to MODERATE** | `AO/got/hypotheses.json # hypotheses[0]` | field/sector only; cap is the honesty (see HN5) |
| X14 | Permian attribution: H1 facility-level | **GOONCH FEDERAL COM 0409** pad (NOVO OIL & GAS), score `0.6325` (band moderate) **CAPPED to LOW** | `AO/perm/hypotheses.json # hypotheses[0]` | LOW; ranks but cannot establish (see HN6) |
| X15 | Heat factor F1 ranked first | persistent synoptic ridge, heuristic score `1.00` (band high) **CAPPED to moderate** | `AO/india/factor_hypotheses.json # factors[0]` | ranking-not-apportionment; HIGH reserved |

## Partition 3 — HONEST NEGATIVES / FINDINGS (these ship; they are the point)

| # | Claim (the finding) | Exact figure (as in artifact) | Source artifact # locator |
|---|---|---|---|
| HN1 | C3 duration **FAILED** its pre-registered criterion | ERA5 `26 days` (`2022-03-26..04-20`) vs IMD `7 days`; `pass_v4a=false` | `SB/india/air_lane.json # c3_duration`; `SB/india/validation.json # v4_duration_extent` |
| HN2 | C4 extent **FAILED** its pre-registered criterion | ERA5 `889,700 km²` (`area_frac 0.4748`); common-grid ERA5 `887,700` vs IMD `606,300 km²`, rel diff `0.464 > 0.30`; `pass_v4b=false` | `SB/india/air_lane.json # c4_extent`; `SB/india/validation.json # v4_duration_extent` |
| HN3 | The C3/C4 failures are a **criterion-edge fragility finding**, always rendered with criterion + dataset | (tier rows: "C3/C4 NOT VALIDATED … always rendered with criterion + dataset attached") | `docs/science/validation_tiers.md:68` |
| HN4 | ERA5↔station **consistency NOT CLAIMED** (V2 failed; permanently for this event) | median bias `0.37 K` (ok), RMSD `1.05 K` (ok), pooled r `0.728 < 0.85`; `pass_v2=false` | `SB/india/validation.json # v2_era5_station_consistency` |
| HN5 | Goturdepe: **no facility-level attribution possible** — OGIM has zero point infrastructure in Turkmenistan (first-class finding, not a gap) | "OGIM v2.7 contains NO facility-level point infrastructure … anywhere in Turkmenistan … capped at FIELD/SECTOR level" | `AO/got/hypotheses.json # headline_finding, confidence_cap` |
| HN6 | Permian: **no facility above LOW** — favored pad wins on angle only; ARTEMIS is distance-closer; 21 wells in the 2σ wedge | nearest-centerline `0.4°, 0.6 km`; nearest-by-distance ARTEMIS `0.3 km, 35.9°`; `21` wells in 2σ (`14` in 1σ) | `AO/perm/hypotheses.json # headline_finding, plume_summary` |
| HN7 | The **+1.46× MF-amplitude systematic** is independently reproduced, **not corrected** | `enhancement_bias_factor = 1.4602502841737661` ("INDEPENDENTLY MEASURED … not the NASA-k run's hand-carried 1.66×") | `SB/got/q_estimate.json # enhancement_bias_factor, _source` |
| HN8 | The +1.46× **does NOT transfer** to a new scene (flips to 0.96×) | `carried_goturdepe_mf_bias = 1.46`; "this scene's measured 0.96× … does NOT transfer (sign flips)" | `SB/perm/q_estimate.json # carried_goturdepe_mf_bias_note` |
| HN9 | Our self-segmentation **could not isolate the weak Permian plume** (grabbed a confuser) → mask anchored to NASA's footprint | `self_segmentation_isolated_plume = false`; `plume_mask_method = "NASA-L2B-footprint-anchored (CROSS-CHECKED)"` | `SB/perm/q_estimate.json # self_segmentation_*` |
| HN10 | No k-shape cross-check exists for Permian (no NASA per-granule target) | `k_shape_crosscheck_available = false` | `SA/perm/stage_a_report.json` |
| HN11 | Forward scale `1.0` — scaling derived forward from physics, **never reverse-fit** to a target flux | `ppm_scaling_factor_forward = 1.0` | `SA/got/stage_a_report.json` |
| HN12 | **Negative** daytime surface UHI (urban cool island) — counter to the urban-heat prior | window-mean `−0.77 ± 0.80 K` (10 days); robust across sensitivities `−1.05 … −0.74`; Landsat sign-agrees 2 of 3 scenes (`−6.75`, `+0.13`, `−2.31` K) | `SB/india/uhi.json # window_mean_uhi_k, sensitivities, landsat_cross_check` |
| HN13 | Heat F5 (urban fabric) is **COUNTER_EVIDENCE**, score `0.00` | role `counter_evidence`, score `0.0` | `AO/india/factor_hypotheses.json # factors[4]` |
| HN14 | Heat engine **argues against popular priors**: dry-soil F2 LOW (antecedent near-normal), advection F3 LOW (climatological), humidity F4 insufficient | F2 `0.314` (soil pct `0.433`), F3 `0.277` (wind anom `0.39 m/s`), F4 `0.066` (dewpoint anom `+0.13 K`, pct `0.533`) | `AO/india/factor_hypotheses.json # factors[1..3]`; `AO/india/diagnostics.json # soil_moisture/winds/dewpoint` |
| HN15 | Attribution scores are heuristics, **not calibrated probabilities / not contribution fractions** | "Scores are documented heuristics … NOT calibrated probabilities and NOT contribution fractions. Use the tiers … not the decimals." | `AO/india/factor_hypotheses.json # scoring_disclaimer`; `AO/{got,perm}/hypotheses.json # scoring_disclaimer` |
| HN16 | LST is late-morning, **never a daily maximum**; Aqua absent | Terra view time `10.68 h` local; Aqua gap `2022-04-01..16`; L3 MODIS−ERA5skt `−5.31 ± 1.32 K` (coherence, not validation) | `SB/india/lst_lane.json # observation_time_caveat, l3_product_consistency` |
| HN17 | Sub-field localization rests on a **weakest-link** wedge (speed-derived, not measured direction variance); ~23° bearing gap (Goturdepe) | wedge `14.5° / 27.3°`; centroid↔S bearing gap ~`23°` | `AO/got/hypotheses.json # hypotheses[0].assumptions` |

## Partition 4 — CITED-EXTERNAL (not computed by Aether; DOI + boundary)

| # | Item (carried as citation, never as an Aether result) | Exact figure / value | Source artifact # locator | DOI / locator |
|---|---|---|---|---|
| C1 | Thorpe 2023 cluster total (why Goturdepe is **not** VALIDATED — scope mismatch) | `163 ± 18` t/hr, `12` sources, `reference_usability: scope_mismatch` | `BM/turkmenistan…yaml # known_measurements, references` | doi:`10.1126/sciadv.adh2391` |
| C2 | Permian `18.3` t/hr is **press-release context only** | `value: 18.3`, `reference_usability: context_only` (NASA JPL, Oct 2022; no method/date/uncertainty) | `BM/permian…yaml # known_measurements, references` | NASA JPL press release (Oct 2022) |
| C3 | Zachariah 2023 climate-attribution (external; never blended into factor scores) | "~30× more likely, ~1 °C hotter … ~1-in-100-year"; `reference_usability: context_only` | `AO/india/factor_hypotheses.json # external_published_attribution`; `BM/india…yaml` | doi:`10.1088/2752-5295/acf4b6` |
| C4 | IMD/MAUSAM all-India monthly anomalies (context / scope mismatch) | March `+1.61 °C` (context_only), April `+1.36 °C` (scope_mismatch); "highest in 122 years" | `BM/india…yaml # known_measurements, references` | doi:`10.54302/mausam.v75i2.6196` |
| C5 | Moderate-source priors for Permian magnitude | Duren 2019 + Cusworth 2021 (single-well/equipment plausible at ~0.85 t/hr) | `AO/perm/hypotheses.json # hypotheses[0]` | Cusworth doi:`10.1021/acs.estlett.1c00173`; Duren doi `10.1038/s41586-019-1720-3` (confirm exact string at Stage B from `docs/science/sprint7_permian.md` — see F4) |
| C6 | Spectroscopy citations (method provenance) | HITRAN2020 (Gordon 2022); HAPI (Kochanov 2016) | `BM/turkmenistan…yaml # references`; `docs/science/sprint6_hitran_independence.md:19-21` | doi:`10.1016/j.jqsrt.2021.107949`; doi:`10.1016/j.jqsrt.2016.03.005` |
| C7 | Infrastructure database | OGIM v2.7 (Oil & Gas Infrastructure Mapping) | `packages/causal/aether_causal/resources/ogim/provenance.json` | doi:`10.5281/zenodo.15103476` |
| C8 | NASA EMIT L2B reference products | CH4ENH (spatial-agreement reference); CH4PLM (plume complexes) | `BM/{turkmenistan,permian}…yaml # references` | doi:`10.5067/EMIT/EMITL2BCH4ENH.002`; doi:`10.5067/EMIT/EMITL2BCH4PLM.002` |
| C9 | **Carbon Mapper / Tanager relationship** (rule 4) | EMIT (public) vs Tanager (proprietary JPL spectrometer heritage; CM publishes own L1–L5); complementary/inspired-by, **not** affiliated/endorsed/a replication | **No Aether artifact backs this** — external public facts | **FLAG (F5):** write at Stage B/C from public CM/JPL docs, cited, with the non-affiliation boundary explicit |

## Partition 5 — ASPIRATIONAL (parked; must NOT migrate into the delivered narrative)

These exist in the architecture/spec as ambition only. They may appear **once, late, labeled
"where this is headed"** (rule 2) — never woven into shipped-work prose.

| item | status / why aspirational | source |
|---|---|---|
| "AI-native" / AI orchestration layer (`packages/ai`) | **not built** | `PROJECT_STATUS.md` ("AI orchestration layer: not built"); `CLAUDE.md` layer 4 |
| "planetary engine" / multi-body / `planetary_body` first-class | **architecture only**; Earth is the only body shipped | `CLAUDE.md`; ADR 0001 |
| Space Domain Awareness / orbital-object / SDA | **deferred** (explicitly out of Sprint scope) | `CLAUDE.md` scope discipline |
| Ocean/marine, exoplanet explorer, 3D explorer | **deferred** | `CLAUDE.md` scope discipline |
| "10×-better", "causal deduction engine" | vision framing; the engine ships as a **deterministic ranking heuristic**, not calibrated causal inference | `AO/*` `scoring_disclaimer` (HN15) |
| The site's `ape.html` "Aether Planetary Engine / lunar night / regolith / Moon Presence" copy | **the placeholder is itself written in the aspirational frame** — must be reframed to the shipped Earth work in Stage C | `arkaneworks ape.html` (Part 1) |

## What SHIPPED actually is (rule 2 anchor for the writers)

Three real events — **Goturdepe** (EMIT 2022-08-15), **Permian/Carlsbad** (EMIT 2022-08-26),
**NW/central India heat wave** (Mar–Apr 2022). Two phenomenon domains — methane super-emitter
emission + heat. A per-quantity validation rubric (`docs/science/validation_tiers.md`). A
provenance-traceable pipeline (EMIT L1B/L2A/L2B → independent HITRAN2020/HAPI saturation-aware k →
matched filter → IME flux; heat lane: ERA5 / MODIS LST / ISD + IMD air temperature, two lanes never
conflated). A **deployed dashboard** (web `aether.arkaneworks.co`, API on Fly.io) serving committed
artifacts only, with a **machine-checked deployed-integrity verifier** GREEN at the pinned SHA
(`tools/verify_deployment.py`; evidence `docs/reports/sprint10_stage_d_verification.json`).

---

# Findings for the gate (decisions / Stage-B tasks before any narrative)

- **F1 — NAME/ROUTING COLLISION (blocking Stage C).** The "placeholder" is `ape.html` = "Aether
  Planetary Engine," a *lunar-infrastructure* concept in the P‑02 Active slot, written in the
  forbidden aspirational frame. Decide Option **A** (replace in place at `/ape`, reframe to the
  Earth methane+heat work) vs **B** (new `/aether`, edit nav in all 14 pages, decide `ape.html`'s
  fate). Needs the human's intent: is the lunar A.P.E. a real separate program or always this one's
  placeholder name? **Recommendation: A.**
- **F2 — No untraceable shipped/validated claim found.** Every figure in Partitions 1–3 traces to a
  committed artifact at SHA `59c4a98`. Nothing in those partitions needs cutting or demotion.
- **F3 — Two flux calibrations both ship** (ours-cal `23.40` + NASA-anchored `16.03` for Goturdepe).
  The Stage-B snippet must carry both with their exact provenance so neither deliverable picks one
  silently; the headline framing is CROSS-CHECKED-strong, never VALIDATED.
- **F4 — Pin two exact strings into the Stage-B source-of-truth snippet:** Permian plume-scale pixel
  r (`0.137`, currently sourced as ≈0.14 from `validation_tiers.md:35`) and Duren 2019's exact DOI
  string (`docs/science/sprint7_permian.md`). Both are *traceable*; only the exact literal needs
  lifting from its artifact, not inventing.
- **F5 — Carbon Mapper statements have no Aether artifact** (C9). They must be written at Stage B/C
  from public CM/JPL sources, cited, with the "not affiliated / not a replication / shared JPL
  *heritage* only" boundary explicit — never implied as an Aether-measured fact.
- **F6 — Design:** the case-study page adopts the monochrome site palette (tokens above); the
  dashboard's amber/cyan stays inside screenshots; do not import dashboard CSS.

**STOP. The human + reviewer approve this ledger and the site-fit plan (especially F1) before a word
of narrative is written.** No README, validation write-up, or case-study prose has been started.
