# Redesign v2 — "Instrument Data-Plate" (branch `redesign/v2`)

> **Status: built, machine-verified, held for your visual review.** This branch is
> the revert mechanism — `main` is untouched. Verification at the end of this
> report was run fresh on this branch: `tsc --noEmit` clean, `next build` OK,
> `uv run pytest` 235 passed (full guard suite included), `ruff` 0, and the
> committed Goturdepe/Permian artifacts are **byte-identical** (`git diff` = 0
> lines over `stage_a_outputs/ stage_b_outputs/ attribution_outputs/ apps/api/assets`).
> Scope of change: `apps/web/src/app/globals.css`, `apps/web/src/components/{Dashboard,Inspector}.tsx`,
> `apps/web/README.md`, this report. No API, no Python, no artifacts.

## 1. The thesis

The four references (`docs/design/references/IMG_3364.PNG`, `IMG_3367.JPG`,
`IMG_3370.PNG`, `IMG_3372.JPG`) all speak one design language: **industrial
spec-sheet / technical data-plate** — hairline frames, squared corners, indexed
sections (`.01 / .02 / .03`), flat ink fills with diagonal-hatch texture for
empty remainders, big confident numerals, vertical micro-type rails reading
bottom-up, document codes, and a departmental footer line. The Division HUD
(paramount, per direction) is itself squared, thin-lined, and flat-orange-on-dark
— it sits much closer to these references than v1's implementation did.

v1's CSS was "game-HUD soft": 4–8 px rounded corners, gradient fills, glows on
most accents, a radial gauge, backdrop blur everywhere. **The redesign moves the
surface from *game HUD* to *scientific instrument data-plate*** — the inspector
now reads as a numbered measurement report over committed artifacts, which is
exactly what it is. Every choice below was filtered through the governing
principle: legibility, data density, and credibility with skeptical domain
scientists. Atmosphere kept; theater removed.

What did **not** change: the amber–cyan duotone on deep near-black, the
photoreal Cesium globe, the AETHER wordmark with amber underline, the
synchronized camera-flight/panel-slide motion system (`lib/motion.ts`
untouched), and every honesty element (§4). The type stack was unchanged in
this first pass; the subsequent directed **typography pass (§8)** then evolved
it — Archivo joined as the UI grotesque and Chakra Petch was demoted to a
brand accent.

## 2. Deliberate evolutions of the locked identity

Each item is intentional and traceable to a reference or to the credibility
principle. Nothing else about the identity moved.

1. **Geometry: rounded → squared.** All border-radius removed (only the
   radar-ping ring and spinner remain circular, as motion). Hairline 1 px frames
   throughout. *(All four references; Division.)*
2. **Surfaces: gradients/glows → flat ink.** Panel gradients, bar gradients, and
   most text-shadows deleted. Glow survives in exactly three places, as signal
   emphasis: the wordmark underline, the headline emission numeral, and the
   marker dots. *(References are flat print; credibility.)*
3. **Indexed sections.** Inspector sections are auto-numbered (`01`–`09`) via CSS
   counters on the section headers — conditional sections (brief, attribution,
   references, pending) renumber correctly. Indices are muted gray; the scope
   caveat's index inherits alert red, making the warning a numbered, first-class
   section of the document. *(IMG_3364's `.01/.02/.03`.)*
4. **Hatched remainders.** Uncertainty bars, the validation meter, and
   score-component bars are now flat fills inside hairline frames, with the
   *unfilled* remainder carrying a diagonal hatch. *(IMG_3370's bar treatment.)*
5. **Radial gauge → spec-sheet meter.** The Stage A Pearson donut is now a big
   numeral + framed horizontal meter. Same value, reference-style presentation —
   and the panel now also surfaces the API's other validation numbers (§4.8).
6. **Icon rail → data spine.** v1's left rail was four **non-functional** nav
   buttons (Layers/Spectra/Catalog/Settings). Fake affordances in a credibility
   instrument — removed. The replacement is a vertical micro-type spine reading
   bottom-up: `SUPER-EMITTER EVENT RECONSTRUCTION // DETECTION · QUANTIFICATION ·
   ATTRIBUTION · BRIEF` (the real pipeline), bracketed by registration crosses.
   *(IMG_3372's rotated sidebar strip; honesty improvement.)*
7. **New status bar (footer).** A persistent 26 px strip:
   `AETHER · PLANETARY ENGINE` / `ALL VALUES FROM COMMITTED, REVIEWED ARTIFACTS ·
   NO LIVE TELEMETRY`. The no-live-feed honesty rule is now permanent chrome,
   visible in every screen and state. *(IMG_3370's departmental footer line.)*
8. **Headline numerals: mono → display face.** The big emission rate (and the
   meter numeral) moved from Plex Mono to the display face — the references'
   "big confident numeral" (initially Chakra Petch semibold; **superseded by
   §8**: now Archivo 700, tight-tracked, tabular numerals). Plex Mono remains
   the face for *all* tabular data, ranges, coordinates, and codes.
9. **Neutrals: blue-cool → graphite-neutral.** Backgrounds nudged from blue-tinted
   (`#06080c/#10141b`) to near-neutral graphite (`#050708/#0e1114`); primary text
   warmed slightly toward the references' cream (`#e8edf2 → #e9eae4`). The duotone
   accents are unchanged.
10. **Color discipline codified** (header of `globals.css`): amber = measurement
    emphasis + selected interactive state; cyan = reference/cross-check/validation
    data, links, mask outline; alert red = caveats only; everything else neutral.
    Consequences: layer/body toggles' active state unified to amber (v1 mixed
    cyan/amber); the globe hint accent is amber. Tier-badge colors untouched
    (cyan VALIDATED / sober amber CROSS-CHECKED / gray DEMONSTRATION — the
    Sprint 7 review ruling).
11. **Selected-state motif:** active toggles carry a 2 px inset amber baseline —
    an echo of the wordmark's amber underline. *(System-internal rhyme.)*
12. **Markers:** square dot + squared targeting reticle (was circle); the v1
    "bob" idle animation deleted (gamey); the label is now a mini data-plate
    (framed, amber left edge, dark fill) instead of glow-shadowed floating text.
    The radar ping ring stays — it's the one Division flourish kept on the globe.
13. **Document codes, real ones only.** The inspector header shows the event's
    actual `event_id` as its document code. No invented codes (no fake `DF.505`s),
    no fake progress meters, no invented classification stamps — those reference
    artifacts were deliberately **not** copied, both for honesty and IP reasons.
14. **Ambient dot grid** behind the globe (visible only around the limb — the
    Cesium canvas is alpha-transparent in space, so it never overlays imagery).
    Scanline overlay kept, dialed down 0.022 → 0.018. *(Atmosphere, not theater.)*
15. **Micro-interaction system:** two timing tokens (120 ms / 200 ms, ease-out)
    replace v1's scattered 0.15 s/0.18 s/0.2 s; `:focus-visible` amber outlines
    (keyboard a11y); `::selection` in amber; `prefers-reduced-motion` stops the
    decorative ping (functional camera/panel sync transitions are kept, since the
    Cesium flight can't be disabled symmetrically). The Cesium imagery credit now
    tracks the panel slide so attribution is never covered, and its position
    follows the live panel width (was hardcoded to the old 392 px default).

## 3. What was *not* adopted from the references

- **Chartreuse/lime palette** (IMG_3367/3370) — rejected; the amber–cyan duotone
  is locked identity and closer to Division.
- **Barcodes, fake lab codes, "INTERNAL USE ONLY" stamps, progress ticks**
  (IMG_3370/3372) — rejected as invented data / fiction. The aesthetic was taken
  (frames, indices, footers); the fictional artifacts were not.
- **Oversized editorial headline type** (IMG_3364's "CARGO") — rejected; this is
  a working instrument, not a poster. Its *stat-block* grammar (label, rule, big
  number, side caption) was adopted instead.
- No asset, logo, layout, or recognizable element was copied from any reference
  or from The Division; inspiration only.

## 4. Honesty-element inventory (hard constraints — all verified present)

| # | Element | Where it lives now | Prominence vs v1 |
|---|---------|--------------------|------------------|
| 1 | Scope / READ-BEFORE-CITING block | Numbered red-framed caveat section, directly after the rate + uncertainty it qualifies (`Inspector.tsx` `renderActive`) | **Improved** — alert-red index + 3 px left rule; part of the numbered document flow |
| 2 | Coverage-ceiling banner (`headline_finding` + `confidence_cap`) | First block inside Source Attribution, cyan-framed, verbatim (`SourceAttribution.tsx`) | Intact |
| 3 | Validation-tier badges + explainers | Marker labels (globe) + inspector header chips + first-class `tier_explainer` paragraph | Intact (marker badge now sits in a framed plate — more legible over imagery) |
| 4 | Temporal caveats inline with evidence | Still nested *inside* the evidence item (structurally inseparable), amber-framed | Intact |
| 5 | Scoring disclaimer | Both appearances (set-level + per-card score components), verbatim | Intact |
| 6 | Confidence caps | `· CAPPED` derived from the artifact's own rationale text; rationale always visible, collapsed too | Intact |
| 7 | Provenance / localization distinction | `Source localization:` line atop the numbered References section | Intact |
| 8 | Uncertainty budgets | Numbered section, hatched-frame bars, systematic terms in amber | **Improved** — framed bars are more legible; nothing dropped |
| 9 | No fake telemetry / no implied live feed | **New status bar**: `ALL VALUES FROM COMMITTED, REVIEWED ARTIFACTS · NO LIVE TELEMETRY`, persistent in every state; `Acquired` chip remains per-selected-event only | **Improved** |
| 10 | Pending honesty / non-Earth empty state | Pending badge + verbatim `pending_reason` caveat; `NO DATA · EARTH MVP` overlay | Intact |
| 11 | Removed fake affordances | v1's four non-functional rail buttons deleted (§2.6) | **Improved** |
| 12 | Every number from the API | Unchanged data path (`lib/api.ts` untouched). **New in v2:** the Stage A Validation panel now *additionally* renders `reference_product`, `pearson_full_scene`, `n_pixels_bbox`, and (when present) `integrated_mass_ratio` + `pixel_pearson` — values the API already served but v1 buried in prose. Permian's dual cross-check facts (0.96× mass, weak pixel r) are now explicit data rows | **Improved** |

## 5. Imported resources & licenses

**First pass: none imported.** No new icon sets, textures, images, or
dependencies. **Typography pass (§8) added exactly one face: Archivo**
(SIL OFL 1.1, Omnibus-Type, via Google Fonts, self-hosted at build through
`next/font/google`) — full ledger in §8.1.
- Fonts: Chakra Petch, IBM Plex Mono, IBM Plex Sans (all SIL OFL 1.1),
  self-hosted via `next/font/google` — carried over from v1; roles re-assigned
  in §8.
- All new texture/ornament (hatch, dot grid, crosses, frames) is hand-written CSS.
- Globe imagery providers unchanged (Cesium ion token / ESRI World Imagery
  fallback); the imagery credit remains visible in all states (§2.15).

## 6. Verification (run fresh on this branch, 2026-06-11)

| Check | Result |
|---|---|
| `pnpm typecheck` (`tsc --noEmit`) | clean |
| `pnpm build` (`next build`) | ✓ Compiled, 5/5 static pages |
| `uv run pytest` (full suite incl. guard suites, no-staleness, no-fabrication, tier rubric) | **235 passed**, 7 deselected (the integration-marked set) |
| `uv run ruff check .` | 0 errors |
| Committed artifacts (`stage_a_outputs/ stage_b_outputs/ attribution_outputs/ apps/api/assets`) | `git diff` = **0 lines** (byte-identical) |
| `aether-eval` | not run — no `packages/detection`/`packages/causal` change (frontend-only sprint) |

## 7. Walkthrough shot list (for your visual review)

Two terminals from the repo root:

```bash
# 1) API
uv run uvicorn aether_api.main:app --app-dir apps/api --port 8000
# 2) web
cd apps/web && pnpm dev          # http://localhost:3000
```

Capture into `docs/reports/screenshots/redesign_v2/`. Review notes per shot:
check spacing rhythm, hairline alignment, type hierarchy, and that nothing reads
"gamey".

**A. Globe (idle)**
1. `a1-globe-overview.png` — full window: topbar (wordmark + amber underline,
   `BODY EARTH` chip), left data spine (rotated text reads bottom-up, crosses top
   and bottom), top-center body selector, top-right readout plate
   (SIGNALS/SPECIES/PRODUCT rows), bottom hint, **status bar with the
   NO LIVE TELEMETRY declaration**, dot grid faintly visible around the limb,
   slow auto-rotation.
2. `a2-marker-hover-goturdepe.png` — hover the Goturdepe marker: square amber
   dot scales, framed label plate (amber left edge) with name, CROSS-CHECKED
   badge, headline rate `23.4 t/hr`.
3. `a3-marker-pending.png` — hover a pending marker (gray dot/edge, PENDING
   semantics, not clickable).
4. `a4-markers-both.png` — both active markers in frame with badges + rates
   (GOTURDEPE 23.4, PERMIAN BASIN 0.85).

**B. Fly-to + plume (Goturdepe)**
5. `b1-flyto-midflight.png` — click Goturdepe; capture mid-flight: camera and
   inspector move as ONE (same 1.5 s curve), plume HUD fading in, globe controls
   fading out, Cesium credit sliding left with the panel.
6. `b2-plume-arrived.png` — arrival: enhancement raster draped at true coords,
   cyan mask outline, dimmed base imagery, corner brackets, coord plate
   (PLUME ORIGIN), back button, layer toggle top-right.
7. `b3-layer-nasa.png` / `b4-layer-diff.png` — toggle NASA L2B and Δ Diff:
   active segment = amber fill + inset amber baseline.

**C. Goturdepe inspector (the numbered spec-sheet)**
8. `c1-inspector-header.png` — header plate: GOTURDEPE, real `event_id` as the
   document code (top right), location, chips, sober CROSS-CHECKED badge, tier
   explainer ("strong": r≈0.73, k-shape 0.993, self-derived localization).
9. `c2-emission-rate.png` — section `01`: OURS-CAL/NASA-CAL toggle, the big
   Chakra numeral `23.4 t CH₄/hr` (amber, the one glowing number), range row
   above a hairline, note text. Toggle to NASA-CAL (16.0) for a second capture.
10. `c3-uncertainty-scope.png` — sections `02` + `03` together: hatched-remainder
    uncertainty bars (systematic = amber), then the red-framed
    `03 SCOPE · READ BEFORE CITING` block — confirm the warning is *more*
    prominent than v1, not less.
11. `c4-validation.png` — section `04`: Pearson meter (0.73 numeral + hatched
    meter), data rows (reference product, full-scene r, pixels), note.
12. `c5-geometry-atmosphere-brief.png` — sections `05`–`07`: data rows + brief.
13. `c6-attribution-collapsed.png` — section `08`: cyan coverage-ceiling banner
    (verbatim headline + confidence cap), italic scoring disclaimer, hypothesis
    cards with rank, tier chips, always-visible rationale (incl. `· CAPPED` red).
14. `c7-attribution-expanded.png` — expand H1: score components (hatched bars +
    rationales + second disclaimer), evidence with `↳ dataset — locator` and the
    **amber temporal-caveat block nested inside its evidence item**, assumptions,
    counter-considerations, falsification.
15. `c8-references.png` — section `09`: source-localization line + citations with
    cyan DOI links.

**D. Permian (second event + honesty deltas)**
16. `d1-permian-header.png` — CROSS-CHECKED badge + explainer carrying BOTH facts
    (0.96× integrated mass, weak pixel r=0.137).
17. `d2-permian-rate-scope.png` — `0.85` (two decimals) + the **context-only 18.3
    t/hr scope block**.
18. `d3-permian-validation.png` — meter (0.52) + the new explicit rows:
    `Integrated mass (ours/NASA) 0.96×`, `Plume-pixel Pearson 0.14`.
19. `d4-permian-provenance.png` — `Source localization: NASA-footprint-anchored…`
    vs Goturdepe's end-to-end independent line (capture both for contrast).
20. `d5-permian-plume.png` — Permian fly-to: raster + NASA-footprint mask outline.

**E. Interaction states**
21. `e1-resize.png` — drag the inspector's left edge (handle glows amber-dim):
    panel widens, plume stage and Cesium credit reflow live; clamps at 320/620 px.
22. `e2-backout-midflight.png` — BACK TO GLOBE mid-flight: panel slides out with
    the camera pull-back, one motion; controls fade back in after.
23. `e3-body-moon.png` — switch to MOON: neutral sphere, `NO DATA · EARTH MVP`
    plate, markers hidden; selector active state amber. Back to EARTH.
24. `e4-error-state.png` — stop the API, reload: red-framed
    `API UNREACHABLE` plate.
25. `e5-resize-window.png` — shrink the browser window (~1100×700): topbar,
    spine, status bar, readout hold; no overlap; status-bar text ellipsizes
    before colliding.
26. `e6-keyboard-focus.png` — Tab through controls: amber focus-visible outlines.

**Merge/revert gate:** you capture and review; `main` is untouched until you
merge. Revert = delete the branch.

## 8. Typography pass (directed refinement, post-approval)

A second look at the references with a typographic eye shows a **two-voice
system**: one industrial grotesque doing *both* the wide-tracked uppercase
labels and the heavy, tight display numerals across weights (IMG_3364's stat
blocks; IMG_3370's `RANGE`/`95.6%`), plus a squared techno-display face reserved
for brand moments only (IMG_3372's `ISC`/`PGE`/`24:B`). v2's first pass kept
Chakra Petch — a techno face — on *every* label, which at 8–9 px reads
decorative rather than instrumental. This pass aligns the whole app to the
references' structure.

**Licensing.** The references' actual faces (game-UI faces in particular) are
proprietary and were neither obtained nor imitated by name. Faces below were
chosen by *character class* (industrial grotesque, fixed-width data face, etc.),
are all **SIL Open Font License 1.1**, sourced from Google Fonts, and
**self-hosted** via `next/font/google` (downloaded at build, served first-party
— no runtime Google request).

### 8.1 The stack (what replaced what, and why)

| Role | Face (license, foundry) | Replaces | Why |
|---|---|---|---|
| UI grotesque — all labels, buttons, chips, badges, section headers, **display numerals** | **Archivo** (OFL 1.1, Omnibus-Type) 400/500/600/700 — *new* | Chakra Petch in all UI-label/display roles | The references set wayfinding and numerals in a neutral industrial grotesque, not a techno face; Archivo is the closest OFL Helvetica-class grotesque with the full weight range, and it stays legible at 8.5 px caps |
| Data values, codes, tables | **IBM Plex Mono** (OFL 1.1, IBM) — *kept* | — | Hard rule: data stays monospaced (inherently tabular) |
| Prose + honesty text | **IBM Plex Sans** (OFL 1.1, IBM) — *kept* | — | Hard rule: honesty blocks are the most readable text on screen |
| Brand accent ONLY — AETHER wordmark, planetary watermark (`MOON`/`MARS`) | **Chakra Petch** (OFL 1.1, Cadson Demak) 700 — *demoted* | itself, everywhere else | Mirrors IMG_3372: the techno voice appears only at reserved display moments; identity continuity for the wordmark |

CSS variables: `--font-label` (Archivo), `--font-mono`, `--font-sans`,
`--font-brand` (Chakra; the old `--font-hud` is gone). Chakra's loaded weights
trimmed to 700 (its only remaining uses), so the font payload stays flat.

### 8.2 The scale + tracking system

Em-based tracking tokens in `:root` — the references' rule is *caps run wider as
they get smaller; display numerals run tight*:

- `--track-tight: -0.01em` — display numerals ≥ 28 px (emission rate, Pearson),
  Archivo 700, plus `font-variant-numeric: tabular-nums` (no width jitter when
  toggling OURS-CAL/NASA-CAL).
- `--track-ui: 0.12em` — interactive caps + badges/chips (buttons, toggles,
  tier badges, marker labels), Archivo 500–600.
- `--track-label: 0.18em` — non-interactive micro labels (section headers,
  readout keys, evidence kinds, caveat headers), Archivo 600.
- `--track-wide: 0.28em` — frame microtype (spine, status bar, wordmark
  sub-line, NO-DATA plate) — IMG_3372's sidebar-strip language.
- Two deliberate exceptions: the wordmark keeps its locked 6 px tracking; the
  event name uses 0.04em (19 px caps need a little air, not label tracking).
- Mono *values* are now untracked (readout values, marker rates, hint) —
  tracking belongs to labels, never to data; mono *codes* keep a slight 0.08em.

### 8.3 Legibility floor + honesty-text bumps (type-forced adjustments)

- Smallest type floor raised to **8.5 px** (topbar labels 8→8.5, marker tier
  badge 8→8.5); everything ≤ 9.5 px is either Archivo 500+ or Plex Mono.
- **Scoring disclaimer** de-stylized: was 10 px italic mono fine-print → now
  11 px IBM Plex Sans regular at brighter `--text-2`. (Both appearances.)
- **Scope/pending caveat body** 11.5→12 px, line-height 1.6; **tier explainer**
  11.5→12 px; **validation note** 11→11.5 px; **confidence rationale** (carries
  the CAPPED reasoning) 10→10.5 px and `--text-3`→`--text-2`; **calibration
  note** brightened to `--text-2`. Net: every honesty element is *more*
  readable than before this pass; none was stylized into texture.
- Label/value hierarchy sharpened reference-style: labels are now bold-ish
  (Archivo 600) caps vs plain mono values — IMG_3370's bold-label grammar.

### 8.4 Verification (re-run after the pass)

`tsc --noEmit` clean · `next build` ✓ (Archivo self-hosted at build) ·
`uv run pytest` **235 passed**, 7 deselected · `ruff` 0 · committed artifacts
`git diff` = **0 lines**. Scope: `globals.css`, `layout.tsx`, this report —
nothing else moved.

### 8.5 Re-capture shot list (typography-affected surfaces)

Same two-terminal setup as §7. Priority shots where type changed most:

1. `t1-globe-chrome.png` — globe overview: topbar (Chakra wordmark vs Archivo
   `BODY` label), body selector + readout (Archivo 600 keys, untracked mono
   values), spine + status bar at `--track-wide`.
2. `t2-marker-labels.png` — hovered Goturdepe marker: Archivo 600 label plate +
   8.5 px tier badge; mono rate untracked.
3. `t3-inspector-top.png` — header + section 01: event name (Archivo 700,
   0.04em), chips/badge at `--track-ui`, the 50 px Archivo 700 emission numeral
   (capture both OURS-CAL/NASA-CAL — no width jitter), section header
   label weight.
4. `t4-honesty-blocks.png` — scope caveat (12 px body) + uncertainty labels:
   confirm the caveat is visibly among the most readable text on the panel.
5. `t5-validation-meter.png` — Pearson numeral (Archivo 700 tight) + meter cap
   label + data rows.
6. `t6-attribution-type.png` — attribution panel: de-italicized 11 px sans
   scoring disclaimer (both appearances), hypothesis descriptor (Archivo 500),
   brighter 10.5 px rationale with `· CAPPED`, evidence kind labels at
   `--track-label`, temporal caveat tag.
7. `t7-references-pending.png` — references/DOIs (unchanged mono, for contrast)
   + the pending badge; plus `MOON` empty state (Chakra brand watermark vs
   Archivo `NO DATA` plate).
8. `t8-smallest-type.png` — close crop of the densest small type (evidence
   source locators, readout, evt-code) to judge the 8.5 px floor.
