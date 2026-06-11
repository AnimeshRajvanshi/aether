# Sprint 7 — Stage D — UI integration — Gate Report

> Permian flipped from "pending" to a live, clickable event with a visible
> validation-tier badge; Goturdepe gains its tier label too. All from committed
> artifacts via the same API patterns. **STOP for final review.**
>
> **Environment note:** this run had no headless browser available, so the
> live-globe **screenshot package was not captured by me** — exact capture steps +
> a shot list are in §6 for you to run (`pnpm dev`). Everything else is built and
> verified (`tsc` + `next build` green).

## What was built

1. **Permian is now ACTIVE.** Committed dashboard render assets generated via the
   parameterized `scripts/build_dashboard_assets.py` (a `nasa_footprint` mask
   strategy, since Permian's self-segmentation could not isolate the weak plume —
   the served overlay is NASA's published complex-000524 footprint, the same one
   the flux was integrated over). `assets/permian_basin_2022/` now holds
   `enhancement.png`, `nasa.png`, `diff.png`, `mask.geojson`, `bounds.json`. The
   mask reconstruction asserts 123 px == `q_estimate.json` before writing.
2. **Activation gate honored.** The API treats an event as active only when BOTH
   `q_estimate.json` AND `assets/<id>/bounds.json` exist. Adding Permian's bounds
   flips it active; this is why Stages B/C kept it pending.
3. **Validation-tier badges (both events).** `EventSummary` + `EventDetail` carry
   `validation_tier`; the globe marker label and the inspector header render it.
   `EventDetail.tier_explainer` is a first-class sentence on what the tier means for
   THIS event **and its limits** (mirroring the scope-caveat treatment).
   - **Both events → CROSS-CHECKED** (per the Stage D review ruling + the rubric;
     VALIDATED is reserved — see the addendum). They differ in cross-check STRENGTH,
     carried in the explainer, not the badge: Goturdepe = `CROSS-CHECKED (strong)`
     (pixel r≈0.73, self-derived localization, k-shape r≈0.993); Permian carries BOTH
     facts — integrated mass **0.96×** over NASA's footprint AND weak pixel
     **r = 0.14**. Badge styling is sober (amber), not a triumphant "validated ✓".
4. **18.3 t/hr context-only block.** Permian's scope caveat is `kind: context_only`
   (no Thorpe cluster): it states the figure is a press-release value with no date /
   method / uncertainty, that intermittency makes same-site comparison meaningless,
   and that our estimate is cross-checked against NASA's L2B, not against 18.3.
5. **Provenance distinguishes localization.** `Provenance.localization`: Permian =
   "NASA-footprint-anchored (CH4PLM complex)"; Goturdepe = "end-to-end independent
   (self-derived S)". Rendered in the inspector's Provenance panel.
6. **Honest bias wording.** The OURS-CAL/NASA-CAL notes are direction-aware: for
   Permian (bias 0.96 < 1) the note says our amplitude is BELOW NASA and that the
   +1.46× Goturdepe over-amplitude does NOT transfer — never calls Permian an
   "over-amplitude".

## Two-event integrity

- The events list, globe markers, and inspector handle two active events. Selecting
  an event resets per-event view state in `Dashboard.tsx` (`setDetail`,
  `setHypotheses`, `setQcal("ours")`, `setLayer("enhancement")`), so no Goturdepe
  data bleeds into the Permian view or vice-versa; the raster/mask overlays are keyed
  by `event_id`.
- `get_hypotheses` is activation-gated, so Permian's Stage C hypotheses are served
  only now that it is live (they were correctly absent through Stages B/C).
- Known minor: the topbar "Acquired" readout shows the first active event's
  timestamp (a global HUD field); per-event acquisition is correct in each
  inspector. Flagged, not fixed (cosmetic, non-scientific).

## Verification

- `uv run pytest` → **212 passed**, 6 deselected (exit 0). Stage D added the
  two-active-event + Permian-active tier/cross-check/scope/localization/bias/brief
  tests and the tier-rubric guard (`test_tier_rubric.py`); rewrote the four old
  "Permian pending" tests to the two-active-event reality.
- `apps/web`: `pnpm typecheck` (tsc --noEmit) clean; `pnpm build` (next build) ✓
  compiled + linted + 5/5 static pages.
- `uv run ruff check .` → 72 pre-existing legacy errors (unchanged); every touched
  file lints clean.
- `uv run aether-eval run` → stub baseline 0/3 (unchanged).
- **Goturdepe untouched:** its committed assets, stage outputs, and attribution
  hypotheses are byte-identical (`git status` clean for all Goturdepe paths).

## Decisions (tier flagged in the original draft; RESOLVED by the review — see addendum)

- **Tier assignment.** The original draft proposed Goturdepe = VALIDATED; the Stage D
  review **reversed** it. Both events are now **CROSS-CHECKED** (VALIDATED is reserved
  for independent flux truth, held by no event). See the addendum + the rubric doc.
- **Permian overlay = NASA's footprint.** Because self-segmentation failed (Stage C),
  the served plume outline is NASA's published footprint, not a self-derived CC. The
  mask.geojson `source` field says so; the inspector localization line says so.
- **Tier source.** Read from `stage_a_report.validation_tier` when present (Permian =
  CROSS-CHECKED); Goturdepe's Sprint-6 report predates the field, so it falls back to
  the documented `_TIER_DEFAULT` map (now CROSS-CHECKED). No tier is invented at render
  time; criteria live in `docs/science/validation_tiers.md`.

## 6. Screenshot package — capture steps + shot list (for you to run)

Two terminals from the repo root:

```
# 1) API
uv run uvicorn aether_api.main:app --app-dir apps/api --port 8000
# 2) web (set NEXT_PUBLIC_API_BASE if the API isn't on :8000)
cd apps/web && pnpm dev          # http://localhost:3000
```

Shot list (save into `docs/reports/screenshots/`):

1. **globe-two-events.png** — globe with BOTH markers visible, each showing its
   CROSS-CHECKED badge + headline rate (GOTURDEPE 23.4 t/hr, PERMIAN BASIN 0.85 t/hr).
2. **permian-inspector-header.png** — Permian inspector header: short name, chips,
   the **CROSS-CHECKED** badge, and the tier explainer carrying the 0.96×
   integrated-mass + r=0.14 pixel facts.
3. **permian-scope-context.png** — the "Scope · Read Before Citing" block showing the
   18.3 t/hr **context-only** text.
4. **permian-validation-provenance.png** — the Stage A Validation panel (dual
   cross-check facts) + the Provenance panel showing "Source localization:
   NASA-footprint-anchored".
5. **permian-plume-overlay.png** — fly-to Permian: the enhancement raster draped over
   the footprint with the cyan mask outline.
6. **goturdepe-inspector.png** — Goturdepe inspector header showing the
   **CROSS-CHECKED** badge + the "(strong)" explainer (r≈0.73, k-shape r≈0.993,
   self-derived localization) — the side-by-side strength contrast with Permian.
   *(This is the one shot the review asked for to close Sprint 7.)*

## STOP — for final review

This completes Sprint 7's planned stages (A probe → B quantification → C attribution
→ D UI). Pending your review of the running app + screenshots, Sprint 7 is done.

## Addendum — Stage D review: tier ruling reversed (Goturdepe → CROSS-CHECKED)

The Stage D review ruled the other way on the flagged tier question: **VALIDATED is
the reserved top tier (independent flux truth: controlled release, in-situ, or
peer-reviewed per-source flux), currently held by NO event.** Goturdepe's only flux
reference (Thorpe 163 ± 18 t/hr) is a scope-mismatched **cluster** total — Sprint 2's
validation doc explicitly cannot claim agreement/disagreement with it — so Goturdepe
does not qualify. **Both events are therefore CROSS-CHECKED**, differing in cross-check
**strength**, which lives in the explainer, not the badge:

- **Goturdepe** — `CROSS-CHECKED (strong)`: pixel-level spatial agreement r ≈ 0.73,
  fully self-derived localization, methane k-shape verified vs NASA's per-granule
  target (r ≈ 0.993), NASA-cal anchored; limit = single overpass, no independent flux
  reference (Thorpe is scope-mismatched).
- **Permian** — unchanged: integrated mass 0.96× over NASA's footprint, weak pixel
  r ≈ 0.14, NASA-anchored localization, no k-shape check; limit = no flux reference,
  18.3 t/hr is press-release context.

Encoded: the new **rubric doc** `docs/science/validation_tiers.md` (the single source
of tier criteria); `_TIER_DEFAULT["…goturdepe…"] = "CROSS-CHECKED"`; the
strength-differentiated explainer (keys on cluster-vs-context + reads the committed
k-shape r ≈ 0.993 from `hitran_k_sat_provenance.json`); the badge (both amber now;
the cyan `tier-validated` style remains for the reserved tier); and a new guard
`apps/api/tests/test_tier_rubric.py` (no active event may be VALIDATED; tiers trace to
the rubric; CROSS-CHECKED rests on a real NASA-L2B reference + the no-flux limit).

**Cosmetic:** sub-1 t/hr headline rates now show two decimals (Permian **0.85**, not
0.9) — marker headline (API) + inspector hero number (frontend).

The topbar "Acquired" readout stays as logged tech debt (cosmetic, non-scientific).

Re-verified: `pytest` green (incl. the tier-rubric guard), `tsc --noEmit` clean,
`next build` OK, Goturdepe artifacts byte-identical. **One screenshot of the corrected
Goturdepe badge + explainer closes Sprint 7.**
