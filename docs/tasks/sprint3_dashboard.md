# Task: Sprint 3 — The Dashboard (globe → event → inspector)

**Owner:** Claude Code
**Reviewer:** chat Claude (architecture/design/science) + human (runs it, reviews)
**Scope:** The first showable product surface. ONE event end-to-end (Goturdepe), rendered beautifully and interactively. No causal engine. No HITRAN target work. No new science. This sprint makes what we already have *legible*.

## Goal

A running web application that:

1. Opens on a **photoreal, fully-maneuverable globe** (Earth, with Moon/Mars selectable) carrying signal markers at real coordinates.
2. On clicking the Goturdepe signal, the camera **flies to the location, auto-orients, and zooms in**; the location settles as a dimmed backdrop; the **plume detail view fades in on top of it** (the location faintly visible behind the plume); and the **inspector panel slides in solid from the right**.
3. The inspector presents the real Stage B result — quantification, uncertainty budget, scope caveat, validation, geometry, atmospheric state, generated brief, provenance — exactly as in the approved mockup.
4. A back control reverses the whole transition to the globe.

**The approved visual reference is `docs/design/aether_photoreal_mockup.html`** (commit it into the repo). Match its aesthetic, layout, and interaction precisely. This brief is the spec; the mockup is the pixel-level target.

## The approved design — non-negotiable specifics

- **Aesthetic:** tactical/command-surface. Deep near-black base, amber + cyan duotone, the inferno methane colormap for plume rasters. Division-inspired, with restrained corner brackets, a faint scan/grid overlay, atmosphere limb-glow on the globe (the LeoLabs/Windy borrow). No game-y motion, no holographic kitsch.
- **Typography:** **Chakra Petch** for HUD headers/labels, **IBM Plex Mono** for all data/numbers, **IBM Plex Sans** for prose. (Self-host via a font package or Google Fonts; do not substitute Inter/system fonts.)
- **Wordmark:** "AETHER" left-aligned with an amber underline, no bullet; "PLANETARY ENGINE · v{version}" smaller beneath the underline.
- **Inspector contents (all real, from Stage B outputs):** event header + chips; emission rate headline with OURS-CAL / NASA-CAL toggle (27.1 / 16.3 t/hr); uncertainty budget bars (α₁ ±7.6%, ERA5 ±10.2%, mask ±2.0%, MF systematic +1.66×); the red "Scope · Read Before Citing" caveat block (1 of 12 sources; Thorpe 163±18); Stage A validation gauge (0.75 Pearson); plume geometry; atmospheric state; generated brief; provenance/references with DOIs.
- **Plume map toggle:** OUR RETRIEVAL / NASA L2B / Δ DIFF.

## Stack (the real one — replace the mockup's standalone HTML)

- **Frontend:** Next.js (App Router) + React + TypeScript. `apps/web`.
- **Globe:** **CesiumJS** (this is why we chose photoreal — real imagery + terrain + accurate geolocation + camera fly-to via `camera.flyTo`). Use Cesium's built-in fly-to for the location transition; pin markers as Entities at exact lon/lat.
- **Plume layer:** the orthorectified enhancement raster rendered over the location. For Sprint 3, rendering it as a georeferenced image overlay (Deck.gl `BitmapLayer` or a Cesium imagery/ground overlay) is sufficient — we are displaying the raster we already produced, not re-tiling it. Use the inferno colormap. The plume mask outline (CC 1213) as a GeoJSON polygon in cyan.
- **Charts/gauges:** lightweight (the uncertainty bars and Pearson gauge are simple SVG/CSS — no heavy charting lib needed yet).
- **Backend:** **FastAPI**, `apps/api`. Serves the event data and the rasters. Thin but real — it sets the pattern for every future event.
- **Monorepo:** register `apps/web` and `apps/api` in the workspace. Python deps via uv as usual; JS via pnpm.

## Backend (apps/api) — endpoints

Build a small FastAPI service that reads our existing Stage A/B outputs and benchmark events from disk and serves them as clean JSON + image assets:

- `GET /api/events` — list of events (id, name, body, lat/lon, phenomenon type, status). Initially just Goturdepe (+ the deferred Permian as a "pending" entry; do NOT invent data for it).
- `GET /api/events/{event_id}` — full detail: quantification (ours-cal + nasa-cal, range, uncertainty budget terms), geometry (IME, area, length, centroid), atmospheric state (U10, U_eff), Stage A validation (Pearson), scope caveat text, provenance (granule URs, target source, references with DOIs). **Source every value from the committed `stage_b_outputs/.../q_estimate.json`, `stage_a_report.json`, segmentation report, and the benchmark YAML — do NOT hardcode numbers in the frontend, and do NOT fabricate any value not present in those files.**
- `GET /api/events/{event_id}/enhancement.png` — the colorized orthorectified enhancement raster (ours), georeferenced (return bounds alongside, or a small sidecar JSON with the EPSG:4326 bounds). Generate this PNG from the committed ortho `.npz` if not already a PNG.
- `GET /api/events/{event_id}/nasa.png` — NASA L2B enhancement, same bounds, for the toggle.
- `GET /api/events/{event_id}/mask.geojson` — the CC 1213 plume mask outline.

Pydantic response models, reusing `aether-ontology` / `aether-eval` types where they fit. The frontend consumes these; nothing is hardcoded client-side.

## Globe interaction (the heart of this sprint)

- Default view: photoreal globe, auto-rotating slowly, fully orbit/zoom controllable (Cesium handles this natively).
- Markers: Cesium Entities at exact lon/lat from `/api/events`. Pulsing/glow styling to match the mockup. Goturdepe is the active/clickable one; the Permian marker shows as "pending k" and is non-active (honest — we have no quantification for it yet). Markers only on Earth.
- On Goturdepe click: `camera.flyTo` the location (≈1.5s), then reveal the plume overlay + slide in the inspector. The dimmed zoomed globe stays faintly visible behind the semi-transparent plume terrain; the inspector is opaque.
- Back control: `camera.flyTo` back to the global view, hide overlay + inspector.
- Body selector (Earth/Moon/Mars) swaps Cesium imagery; markers hidden on non-Earth bodies (we have no data there).

## Out of scope (do NOT build)

- No causal/hypothesis engine, no LLM-generated brief (the brief is templated from the event JSON for now — a deterministic string assembled from real values, clearly the same content as the mockup).
- No new events, no new science, no HITRAN target, no detection changes.
- No auth, no multi-user, no deployment config beyond running locally (`uvicorn` + `next dev`). Deployment is a later sprint.
- No real-time data feeds.
- Do not re-run or alter any Stage A/B computation. This sprint only *reads and presents* committed outputs.

## Definition of done

- `apps/api` runs (`uv run uvicorn ...`) and serves all endpoints with real values sourced from committed Stage A/B outputs.
- `apps/web` runs (`pnpm dev`) and renders: photoreal maneuverable globe → click Goturdepe → fly-to/zoom → plume overlay on faint location → inspector slides in with the real numbers → back to globe.
- The OURS-CAL/NASA-CAL and OUR/NASA/DIFF toggles work against real data.
- Visual match to `docs/design/aether_photoreal_mockup.html`: aesthetic, fonts, layout, the scope caveat as a first-class element.
- Backend tests for the endpoints (mock the file reads or use the committed fixtures). Frontend: at minimum it builds clean and type-checks.
- A short `apps/web/README.md` and `apps/api/README.md` with run instructions.
- Nothing fabricated: every displayed value traces to a committed file. Where a value doesn't exist (e.g., Permian quantification), the UI shows "pending," not a made-up number.

## Build order (suggested)

1. Commit the approved mockup to `docs/design/`. Stand up `apps/api` with the events + detail endpoints reading real Stage B JSON. Verify values match the validation doc.
2. Generate the enhancement/NASA PNGs + bounds + mask GeoJSON from committed outputs; serve them.
3. Scaffold `apps/web` (Next.js + TS + Cesium). Get the photoreal globe rendering with a Cesium ion token (or an open imagery provider if avoiding tokens — document which).
4. Markers from the API; Goturdepe click → `camera.flyTo`.
5. Plume overlay (BitmapLayer/imagery) + mask outline, on the faint zoomed location.
6. Inspector panel — port the mockup's markup/styles to React components, wired to `/api/events/{id}`. Toggles functional.
7. Polish to match the mockup; write READMEs; ensure build + type-check + backend tests pass.

Stop and report after the API is serving real data and the globe→event→inspector flow works end-to-end. Commit at each meaningful step. Do not start any later sprint.
