# aether-web — dashboard frontend

The first showable product surface: a photoreal, maneuverable **CesiumJS** globe
carrying methane super-emitter signals. Click the Goturdepe signal and the camera
flies in, the real EMIT enhancement raster drapes on the globe at its true
coordinates, and the inspector slides in with the Stage B result. Next.js (App
Router) + React + TypeScript.

Visual target: `docs/design/aether_photoreal_mockup.html`. All displayed values
come from `apps/api` — nothing is hardcoded in the UI.

## Prerequisites

- Node ≥ 20, pnpm ≥ 9
- The API running on http://localhost:8000 (`apps/api` — see its README)

## Run

```bash
cd apps/web
pnpm install            # also copies Cesium static assets to public/cesium
pnpm dev                # http://localhost:3000
```

Start the backend in another terminal first:

```bash
uv run uvicorn aether_api.main:app --port 8000
```

## Globe imagery (token optional)

- **With a Cesium ion token** (best quality): set `NEXT_PUBLIC_CESIUM_ION_TOKEN`
  in `.env.local`. Earth uses Cesium World Imagery.
- **Without a token** (default): Earth falls back to **ESRI World Imagery**
  (`services.arcgisonline.com`, no key required). Still photoreal.

Moon/Mars in the body selector are honest placeholders — we have no data on
those bodies yet, so they render as tinted spheres with markers hidden.

`NEXT_PUBLIC_API_BASE` (default `http://localhost:8000`) points the client at the
API.

## Build / type-check

```bash
pnpm build        # prebuild copies Cesium assets, then next build
pnpm typecheck    # tsc --noEmit
```

Cesium is dynamically imported (`ssr: false`) so it stays out of the initial
bundle and never runs during SSR.

## Structure

```
src/
  app/
    layout.tsx        fonts (Chakra Petch / IBM Plex Mono / IBM Plex Sans) + globals
    globals.css       ported from the approved mockup
    page.tsx
  components/
    Dashboard.tsx     view-phase state machine (globe → flying → detail → returning)
    CesiumGlobe.tsx   Cesium viewer, markers, camera.flyTo, raster + mask overlay
    Inspector.tsx     the right-hand inspector, wired to /api/events/{id}
  lib/
    api.ts            typed API client (the only data source)
    types.ts          mirrors apps/api response models
```

## Notes on the production stack vs the mockup

The mockup is a standalone three.js sketch. This app replaces it with Cesium for
real imagery + accurate geolocation + `camera.flyTo`, and the inline plume SVG
with the actual orthorectified enhancement raster draped at its EPSG:4326 bounds.
The mockup's decorative Hassi/Delhi markers are intentionally dropped — only
signals backed by real data appear (Goturdepe active, Permian pending).
