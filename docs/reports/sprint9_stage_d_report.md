# Sprint 9 — Stage D — Heat in the UI — Gate Report

> The heat vertical goes live in the dashboard: an AREA phenomenon rendered as
> a field (not a plume point), the Stage C factor hypotheses with every honesty
> element, per-quantity tier badges, and the LST-vs-air distinction as a
> first-class block — with the methane events untouched. **STOP at this gate.**

## Verdict

The heat event `india_nw_heatwave_2022_04` is **ACTIVE** in the dashboard:
three draped field layers (T2M anomaly / baseline-climatology toggle / LST
anomaly), an area-glyph marker and bbox outline (no plume point, no mask), the
full per-quantity tier table, the factor-attribution section with
counter-evidence styling and the cited-external block, and the two-lane
temperature framing rendered before any number. Methane is pixel- and
byte-identical: committed methane assets/artifacts show zero diff and every
methane API test passes unchanged. Suite: **351 passed**, ruff 0,
`tsc --noEmit` clean, `next build` OK.

## 1. Area-phenomenon rendering (anomaly field + baseline toggle)

- **Assets** (`scripts/build_heat_assets.py` →
  `apps/api/aether_api/assets/india_nw_heatwave_2022_04/`): `air_anomaly.png`
  (ERA5 window-mean Tmax anomaly, inferno 0–8 K, land cells only — the exact
  Stage B analysis field at native 0.25° resolution, honestly blocky),
  `air_baseline.png` (the 1991–2020 climatology the anomaly is measured
  against — the **baseline toggle** renders the baseline itself, so "anomaly
  relative to what?" is answerable on screen), `lst_anomaly.png` (MOD11A1
  Terra-only window-mean anomaly, QC-good pixels, native-sinusoidal mosaic
  warped to EPSG:4326; transparent where QC failed), `bounds.json` (per-layer
  colormaps/units/lanes + the measured 10.68 h view time, read from the
  committed `lst_lane.json` so the label cannot drift).
- **Globe:** the heat marker is a **square** area glyph (vs circular
  point-source markers); selecting it drapes the field and draws the bbox
  outline — `mask.geojson` is methane-only and is no longer assumed
  (a heat selection previously would have thrown).
- **Layer toggle** generalized: labels come from a keyed map with raw-key
  fallback; the default layer is the event's own first layer (the
  `"enhancement"` default was CH4-shaped).

## 2. API (additive; methane DTOs bit-identical)

- `EventDetail.heat: HeatBlock | None` — analogues, episode-vs-window (kept
  distinct, with the criterion string and the never-conflated note),
  per-quantity tier rows, the LST block (measured view time + the verbatim
  observation-time statement from the committed artifact), the UHI numbers,
  the anomaly budget bars (real K half-widths; bar width is visual scaling
  only), and `HeatRasterMeta`.
- `/api/events/{id}/factor-hypotheses` serves the committed Stage C artifact
  **verbatim** (guard: served JSON == committed file); methane events return
  an honest absent state.
- `/api/events/{id}/layers/{layer}.png` — generic raster route, whitelisted
  against the event's own committed `bounds.json` layer list (404 otherwise;
  tested including a methane-layer-name probe against the heat event).
- `_is_active` generalized: the quantification gate accepts `air_lane.json`
  for heat (was `q_estimate.json`-only — found methane-shaped, §5).
- Heat summary: headline `T2M +5.1 K · peak 46.7 °C` (from `air_lane.json`);
  the "Acquired" slot carries the **analysis window**, labeled as a window —
  an area event has no single overpass and the UI does not pretend it does.

## 3. Tier badges — per-quantity (the rubric extension)

- `docs/science/validation_tiers.md` gained the heat extension: **area events
  earn tiers per quantity**; the event-level badge is `PER-QUANTITY` — an
  event-level VALIDATED would overstate C3/C4, an event-level NOT-VALIDATED
  would bury C1/C2. The methane flux rubric is unchanged.
- The inspector renders seven rows: C1 **VALIDATED** and C2 **VALIDATED**
  (each explainer carries the pre-registration story: criteria committed
  before any station data was read, the V1/V3 numbers, and the
  dependency-graph framing), C3/C4 **NOT VALIDATED** rendered with
  **criterion + dataset attached** (`ERA5 vs IMD gridded` in the value
  itself) and the fragility finding as the explainer, V2 **CONSISTENCY NOT
  CLAIMED** (permanent, with the exploratory diagnosis labeled exploratory),
  LST and UHI **CROSS-CHECKED (ceiling)** with the 10.68 h / not-a-daily-max
  caveat in the explainer.
- **Guards extended** (`test_tier_rubric.py`): heat events must carry
  `PER-QUANTITY` at event level; VALIDATED may appear ONLY on quantity rows
  whose committed `validation.json` pass flags are true (render-time
  assertion against the artifact); C3/C4 must carry `criterion_dataset`; LST
  rows must be CROSS-CHECKED-capped; emission events still may never be
  VALIDATED. The pre-existing `test_every_tier_is_in_the_rubric` was updated
  deliberately (event-level set now includes PER-QUANTITY; emission events
  remain restricted to the original three).

## 4. Factor hypotheses in the UI (every honesty element)

`FactorAttribution.tsx` renders the committed artifact verbatim:
- **headline_finding** (the against-prior findings) and **confidence_cap**
  (the MODERATE-ceiling explainer) as always-visible first-class blocks;
- **attribution_boundary** as its own block (what the engine does NOT do);
- **scoring disclaimer** above the cards;
- per-factor **role chips** — warming contributor / severity framing /
  **counter-evidence** — with F5 (urban fabric) styled distinctly
  (counter-evidence border + chip) so the data-against-the-prior reading
  cannot be mistaken for a ranked contributor;
- **diagnostics rendered with every factor** (the no-fabrication bind made
  visible: the numbers behind each claim are on screen, with definitions);
- tier badges show "· CAPPED" whenever the rationale says so; rationale is
  always visible;
- the **cited external attribution** (WWA/Zachariah, DOI) renders in a
  visually distinct CITED-EXTERNAL block labeled "NOT computed by Aether ·
  NOT in factor scores", separated from the computed factors.

## 5. Species/product HUD generalization + methane-shaped findings

Found and fixed this stage (per the brief's "report what was methane-shaped"):

1. Globe HUD hardcoded `Species: CH₄ · HYPERSPECTRAL` and
   `Product: EMIT · L2B CH4ENH` → now derived from the live catalog
   (`Quantities: CH₄ PLUME · T2M / LST ANOM`, `Products: EMIT L2B · ERA5 ·
   MOD11A1 · ISD`).
2. `_is_active` required `q_estimate.json` (plume-shaped quantification gate).
3. The layer-toggle default was `"enhancement"`; `RETRIEVAL_LABELS` was a
   closed methane enum.
4. `CesiumGlobe` unconditionally loaded `mask.geojson` (would throw for a
   maskless area event).
5. `RasterMeta.vmin_ppm_m/vmax_ppm_m` is methane-unit-shaped — left untouched
   for methane; heat uses its own `HeatRasterMeta` with per-layer units.
   Renaming the methane fields would churn the frozen methane payload for
   cosmetics; logged here instead.
6. The "Acquired" topbar slot assumes a single overpass — heat passes a
   labeled window string; a structural `acquisition_kind` field is a candidate
   future cleanup, logged here.

## 6. Two-domain integrity

- **Methane byte-identity:** `git status` over both methane asset dirs and
  both methane attribution dirs = zero lines; all methane API tests (which
  assert served JSON == committed files) pass unchanged; the methane payload
  gained only `heat: null`.
- **State isolation:** layer state resets to the selected event's own first
  layer; factor state is cleared on return (heat artifacts can never bleed
  into a methane selection and vice versa — `test_methane_details_have_no_heat_block`,
  `test_methane_events_have_no_factor_artifact`).
- **Heat payload carries no plume blocks** (quantification/geometry/
  atmosphere/validation/scope_caveat all null — guard-tested), and the heat
  event's own no-staleness/no-fabrication guards (Stage B/C suites) all pass
  against the served values.

## 7. Screenshots

No headless browser is available in this environment (no playwright/puppeteer/
chromium — same constraint as the Sprint 7 Stage D close, which the reviewer
accepted with a preserved shot list). The dashboard runs with
`uvicorn aether_api.main:app --port 8000` + `pnpm dev` in `apps/web`.

**Standard shot list (for your review):**

1. **Globe** — three markers: two circular methane (CROSS-CHECKED badges), one
   square heat area glyph (PER-QUANTITY badge, headline `T2M +5.1 K · peak
   46.7 °C`); HUD shows the generalized Quantities/Products lines.
2. **Heat fly-to** — bbox outline + draped T2M anomaly field; layer toggle
   showing `T2M Anomaly · Baseline 1991-2020 · LST Anomaly`; "Region
   Centroid · Area Event" coordinate box (no "Plume Origin").
3. **Baseline toggle** — the climatology layer rendered (the anomaly's
   denominator on screen).
4. **LST layer** — the MODIS mosaic; inspector LST panel in shot with the
   measured `~10.68 h local solar` row and the Observation Time caveat block.
5. **Inspector top** — PER-QUANTITY badge + tier explainer + the Two
   Temperatures lane block above all numbers.
6. **Per-quantity tier table** — all seven rows visible: green VALIDATED ×2,
   red NOT VALIDATED ×2 with criterion lines, amber CONSISTENCY NOT CLAIMED,
   teal CROSS-CHECKED ×2.
7. **Factor attribution** — headline + boundary + disclaimer blocks; F1 card
   expanded (diagnostics visible, MODERATE · CAPPED badge); F5 with
   counter-evidence styling; the CITED-EXTERNAL block at the bottom.
8. **Episode vs window** — the Air Lane panel rows showing both ranges + the
   never-conflated note.
9. **Methane regression** — Goturdepe selected: pixel-identical inspector and
   plume drape (compare against the Sprint 7 Stage D shots); Permian likewise.
10. **Back-to-globe** — state isolation: re-selecting Goturdepe after the heat
    event shows no heat residue (no factor panel, methane layers only).

## STOP — for review

Stage D closes the Sprint 9 build order (A probe → B detection/quantification
→ C factor engine → D UI). Sprint 9's definition of done is met pending this
review: probe-decided event + tier with provenance; budgeted analogues +
pre-registered validation (first VALIDATED claims); grounded multi-factor
attribution under the full honesty machinery; heat live in the UI with methane
untouched; guards extended across the new domain; suite + CI-shaped checks
green; gate reports at every stage.
