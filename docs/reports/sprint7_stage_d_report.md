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
   - Goturdepe → **VALIDATED** (NASA-L2B-anchored; limit: single event, not in-situ).
   - Permian → **CROSS-CHECKED**, carrying BOTH cross-check facts: integrated mass
     agrees to **0.96×** over NASA's footprint AND pixel-level agreement is weak
     (**r = 0.137**). The badge styling is sober (cyan vs amber), not a triumphant
     "validated ✓" — per your "VALIDATED-style label for neither" steer.
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

- `uv run pytest` → **208 passed**, 6 deselected (exit 0). +2 vs 206 = the Stage D
  API tests (two active events + tiers; Permian active tier/cross-check/scope/
  localization/bias; served hypotheses; brief no-staleness). Rewrote the four old
  "Permian pending" tests to the two-active-event reality.
- `apps/web`: `pnpm typecheck` (tsc --noEmit) clean; `pnpm build` (next build) ✓
  compiled + linted + 5/5 static pages.
- `uv run ruff check .` → 72 pre-existing legacy errors (unchanged); every touched
  file lints clean.
- `uv run aether-eval run` → stub baseline 0/3 (unchanged).
- **Goturdepe untouched:** its committed assets, stage outputs, and attribution
  hypotheses are byte-identical (`git status` clean for all Goturdepe paths).

## Decisions flagged for review

- **Tier assignment.** Goturdepe = VALIDATED (kept as-is, NOT downgraded to
  CROSS-CHECKED); Permian = CROSS-CHECKED. I read "VALIDATED-style label for
  neither" as styling guidance (sober badges + a limits-first explainer), not as
  withholding Goturdepe's VALIDATED tier. Correct me if you meant otherwise.
- **Permian overlay = NASA's footprint.** Because self-segmentation failed (Stage C),
  the served plume outline is NASA's published footprint, not a self-derived CC. The
  mask.geojson `source` field says so; the inspector localization line says so.
- **Tier source.** Read from `stage_a_report.validation_tier` when present (Permian);
  Goturdepe's Sprint-6 report predates the field, so it falls back to a documented
  `_TIER_DEFAULT` map (VALIDATED). No tier is invented at render time.

## 6. Screenshot package — capture steps + shot list (for you to run)

Two terminals from the repo root:

```
# 1) API
uv run uvicorn aether_api.main:app --app-dir apps/api --port 8000
# 2) web (set NEXT_PUBLIC_API_BASE if the API isn't on :8000)
cd apps/web && pnpm dev          # http://localhost:3000
```

Shot list (save into `docs/reports/screenshots/`):

1. **globe-two-events.png** — globe with BOTH markers visible, each showing its tier
   badge (GOTURDEPE · VALIDATED, PERMIAN BASIN · CROSS-CHECKED) + headline rate.
2. **permian-inspector-header.png** — Permian inspector header: short name, chips,
   the amber **CROSS-CHECKED** badge, and the tier explainer carrying the 0.96×
   integrated-mass + r=0.137 pixel facts.
3. **permian-scope-context.png** — the "Scope · Read Before Citing" block showing the
   18.3 t/hr **context-only** text.
4. **permian-validation-provenance.png** — the Stage A Validation panel (dual
   cross-check facts) + the Provenance panel showing "Source localization:
   NASA-footprint-anchored".
5. **permian-plume-overlay.png** — fly-to Permian: the enhancement raster draped over
   the footprint with the cyan mask outline.
6. **goturdepe-inspector.png** — Goturdepe inspector header showing the cyan
   **VALIDATED** badge + its end-to-end-independent localization line (the
   side-by-side contrast with Permian).

## STOP — for final review

This completes Sprint 7's planned stages (A probe → B quantification → C attribution
→ D UI). Pending your review of the running app + screenshots, Sprint 7 is done.
