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

What did **not** change: the Chakra Petch / IBM Plex Mono / IBM Plex Sans stack,
the amber–cyan duotone on deep near-black, the photoreal Cesium globe, the
AETHER wordmark with amber underline, the synchronized camera-flight/panel-slide
motion system (`lib/motion.ts` untouched), and every honesty element (§4).

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
   meter numeral) moved from Plex Mono to Chakra Petch semibold — the references'
   "big confident numeral". Plex Mono remains the face for *all* tabular data,
   ranges, coordinates, and codes.
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

**None imported.** No new fonts, icon sets, textures, images, or dependencies.
- Fonts: the pre-existing Chakra Petch, IBM Plex Mono, IBM Plex Sans, self-hosted
  via `next/font/google` (all SIL Open Font License 1.1) — unchanged from v1.
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
