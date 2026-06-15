# Sprint 10 — Stage C out-of-band fix: heat factor-attribution visual regression

**Date:** 2026-06-15 · **Scope:** web-only. API, committed artifacts, manifest, and every integrity
guard untouched. **Commit:** `4c27e2c` (CI green, both jobs). **Deployed:** live on
https://aether.arkaneworks.co (Vercel auto-redeploy; CSS chunk now carries the fix).

## Diagnosed mechanism (root cause, not a guess)

`FactorAttribution.tsx` (the heat factor cards F1–F5 + the cited-external block) renders its
**card container, header `<button>`, factor name, claim, rationale, expanded body, sub-headings,
and score components** through a `.hypo-*` / `.scomp` class family that **`globals.css` never
defined** — only the `.hypo.counter-evidence` modifier existed. The accent classes it *does* use
(`.role-chip`, `.attr-tier`, `.attr-boundary`, `.diag-*`, `.ext-attr*`, `.attr-headline`) **are**
defined. So the styling split exactly along defined-vs-undefined lines:

| Element | Class | Defined before? | Rendered |
|---|---|---|---|
| Factor header row | `.hypo-head` (a `<button>`) | **No** | native button: `background rgb(239,239,239)`, `color black`, `appearance auto`, 2px native border |
| Factor name / claim / rationale / body / sub | `.hypo-name/.hypo-claim/.hypo-rationale/.hypo-body/.hypo-sub` | **No** | unstyled — wrong face/size, no card padding |
| Card container | `.hypo` | only `.counter-evidence` | no border/bg/padding |
| Score components | `.scomp`, `.scomp .k/.v` | **No** | unstyled |
| Diagnostic keys | `.diag-name` | **Yes** (but `var(--mono)`, undefined → generic monospace) | cyan, but generic mono not IBM Plex Mono |
| Role / tier pills | `.role-chip`, `.attr-tier` | **Yes** | correctly themed |
| Cited-external | `.ext-attr*` | **Yes** | themed (the reviewer grouped it with the broken cards visually; its own rules were present) |

That is precisely the reported symptom: the header is a light native button, the prose is
unstyled, while the data-key spans and pills inside render correctly. The methane
`SourceAttribution` looks right because it uses the **fully-defined `.attr-card*` family**; the heat
component was authored by analogy but its renamed `.hypo-*` rules were never written (a half-finished
Sprint 9 Stage D styling pass).

## dev/prod branch — the "prod-only" hypothesis was WRONG

The regression is **identical in dev and prod**, proven by computed style, not assumption:

```
.hypo-head  background-color  →  rgb(239, 239, 239)   in BOTH `pnpm dev` and `pnpm build && start`
            color             →  rgb(0, 0, 0)         (native button; `font:inherit` doesn't reset color)
            appearance        →  auto
```

There is no environment-specific mechanism: single global `globals.css` imported in `layout.tsx`,
**no Tailwind, no CSS modules, no styled-jsx** — so nothing purges or scope-hashes a class, and the
rules are simply absent in both builds. It went unseen because (a) the factor section is **heat-only**
and deep in the inspector, and (b) every prior gate — including Stage C — checked **caveat presence**,
not visual fidelity, so the light-grey buttons sat in-frame (Stage C shot 09) without being flagged.
The case-sensitive-import / uncommitted-asset branch does not apply (no second stylesheet exists).

## The fix (restyle only)

CSS-only, `apps/web/src/app/globals.css` (+160 / −10). Added the missing `.hypo-*` and `.scomp`
rules **mirroring the methane `.attr-card*` family exactly** (same design tokens: `--font-label`
Archivo for labels, `--font-mono` IBM Plex Mono for data, `--font-sans` for prose, the amber/cyan
duotone on `--bg-panel`/`--border`). Also corrected `.diag-name`'s `var(--mono)` (undefined → generic
monospace) to `var(--font-mono)` (IBM Plex Mono), and harmonized `.role-chip` with the `.tier-badge`
family (font-label, track-ui, flex-pinned). No `FactorAttribution.tsx` change; **no text touched**.

**Hard constraint honored — every caveat verbatim, fully legible, no clamp/ellipsis/collapse:**
- F1 confidence rationale: *"Heuristic score 1.00 (band above ceiling, CAPPED to moderate) — the
  ridge is present, rare, and persistent by diagnostic, but diagnostics cannot separate its
  contribution from the co-varying land-surface state (see headline)."* — rendered in full.
- F5 counter-evidence card with its distinct cyan left-border and the negative-UHI reasoning — in full.
- Cited-external: *"NOT computed by Aether · NOT in factor scores"* + *"…not part of any factor
  score."* + the DOI — in full.
- The attribution-boundary "out of scope" / "reserved and unearned" warnings — in full.

## Verification (the new bar: visual fidelity, both engines)

- **Computed styles after fix:** `.hypo-head` background `rgba(0,0,0,0)` (transparent — native box
  gone) in Chrome and WebKit; prose IBM Plex Sans, rationale/data IBM Plex Mono, diagnostics cyan.
- **Local prod build** (`pnpm build && start`, API → live Fly), full-resolution crops in **Chrome and
  WebKit**: F1–F5 and cited-external match the theme of the 01/02/03/08 blocks.
- **Suite green throughout:** `pytest` 373 passed / 6 skipped / 7 deselected; `ruff` clean; `tsc` clean.
- **Hosted, after redeploy:** re-shot the panel on https://aether.arkaneworks.co.

### Before / after (hosted, both browsers)

`docs/reports/screenshots/sprint10_stage_c_fix/`:
- `zoom_F1_before-hosted-chromium.png` / `...-webkit.png` — the bug in production (Chrome: light-grey
  button header; WebKit: rank glued to the name, no card chrome).
- `zoom_F1_after-hosted-chromium.png` / `...-webkit.png` — themed card: amber mono rank, Archivo name,
  WARMING CONTRIBUTOR / MODERATE·CAPPED badges, Plex-Sans claim, Plex-Mono rationale, cyan diagnostics.
- `zoom_ext_before-hosted-chromium.png` / `zoom_ext_after-hosted-chromium.png` — cited-external block.

### Re-shot Stage C panels (hosted, themed) — visual-fidelity is now a shot-list criterion

`docs/reports/screenshots/sprint10_stage_c/`:
- `09_india_factor_attribution.png` — **replaced**, themed (F1/F2/F3 cards).
- `10_india_cited_external_references.png` — **re-shot**, themed (cited-external purple block + references).
- `11_india_factor_f4_f5.png` — **added**, F4 (severity-framing) + F5 (counter-evidence, cyan border).

The Stage C shot-list criterion is hereby extended: a panel passes only if it both **survives
deployment with caveats intact AND matches the design system** — not caveat survival alone.

## SHA note

The web is now at `4c27e2c`; the Fly API remains at `c960cfd` (this fix does not touch the API,
its artifacts, or the manifest). The footer BUILD chip reads the **API** SHA (`c960cfd`) from
`/api/version` — honest, since the artifact-serving API is genuinely unchanged. The human may
realign by redeploying the API at the new SHA during Stage D (a no-op for artifacts — byte-identity
is guard-guaranteed); it is not required by this fix.
