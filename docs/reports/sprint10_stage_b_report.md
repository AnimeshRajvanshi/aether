# Sprint 10 — Stage B: Hardening, pre-deploy (gate report)

**Date:** 2026-06-12 · **Status:** COMPLETE at gate — all local, no accounts, no deploys.
**Base:** gate ruling `115af07` → six commits, head `5eb65c4` (+ this report).
**Verification:** `uv run pytest` exit 0 — **370 passed, 5 skipped, 7 deselected** (the 5 skips are the live-container guards, which DID run against the container — §6); `uv run ruff check .` exit 0; `pnpm exec tsc --noEmit` clean; `pnpm build` OK (production, `NEXT_PUBLIC_API_BASE=http://localhost:8080`).

## 1. Diff stat (115af07..HEAD)

```
20 files changed, 1344 insertions(+), 142 deletions(-)   (apps/api: 7 files, +820/−123)
```

Commits: `84414c1` API hardening + guard suite · `fbc56b0` integrity manifest + guard · `c0f16d4` F1 dependency split · `048e01d` Dockerfile + live-container guard · `1052e39` web SHA chip + attribution · `5eb65c4` env schema + deployment doc.

## 2. Named guard inventory (each named for what it FAILS on)

`apps/api/tests/test_deploy_guards.py` (13 tests):

| Guard | Fails on |
|---|---|
| **read-only** | any route in the LIVE route table declaring a mutating method |
| **CORS-foreign** | a production app echoing a CORS grant to `https://evil.example.com` (simple request or preflight); also fails if the REAL origin is not granted (tight ≠ broken) |
| **CORS-wildcard** | `*` or `https://*.x` accepted in `AETHER_ALLOWED_ORIGINS` |
| **config-loud** ×3 | production starting without `AETHER_ALLOWED_ORIGINS`, without `AETHER_GIT_SHA`, or with a schemeless origin — must raise `ConfigError`, never default |
| **version-baked** ×2 | `/api/version` not reporting the baked SHA; dev reporting anything but an honest `dev` |
| **byte-identity** | any of the ≥14 single-file endpoints serving bytes ≠ the committed file |
| **schema-validation** | a streamable attribution artifact failing its `extra="forbid"` schema |
| **event-whitelist** | asset routes serving a PLANTED on-disk event not in `EVENT_IDS` (F2, negative-tested) |
| **security-headers** | 200 or 404 responses missing nosniff/frame-deny/no-referrer |
| **startup-schema** | `create_app()` succeeding while a (corrupted-copy) committed artifact violates its schema — the validation the raw-streaming split moved out of the request path |

`apps/api/tests/test_artifact_manifest.py` (3): **manifest-staleness** (regenerates; fails on any endpoint-table diff — commit stamp excluded by design so it is provenance, not a spurious-diff source), **manifest-coverage** (all three events present, ≥14 raw endpoints, enumeration collapse = red), **manifest-negative-space** (fails if `isd`/`noaa`/`global-hourly`/`.aether_cache` ever appears in the served contract).

`apps/api/tests/test_container_live.py` (5, env-gated on `AETHER_LIVE_BASE_URL`): **live-health**, **live-version-sha** (red on stale image vs expected SHA), **live-byte-identity** (every manifest raw endpoint hashed against the manifest), **live-composed-parity** (deep-equality vs the in-process app), **live-read-only+hardened** (405 on POST/DELETE, headers, whitelist 404). This is the local precursor of the Stage D verifier.

## 3. Endpoint changes (per the Stage A scan)

`/bounds`, `/hypotheses`, `/factor-hypotheses` moved from re-serialization to **raw byte streaming** (FileResponse) — all 17 raw endpoints now carry byte-identity end-to-end. The Pydantic `extra="forbid"` round-trip those endpoints performed per-request now runs **at startup** (app refuses to start on an invalid artifact — negative-tested) and in the suite. Pending fallbacks (`{"hypotheses": null, ...}`) are unchanged composed micro-payloads. Flag for review: these two routes no longer declare a `response_model`; the schema guarantee is the startup check + guards, and the wire bytes are exactly the committed artifact.

## 4. Integrity manifest

`artifacts.manifest.json` (committed, root): **17 raw endpoints** (serving path → source, SHA-256, bytes), **4 composed endpoints** with per-source hashes, **17 composed sources**. Generator: `scripts/build_artifact_manifest.py`, logic in `aether_api/manifest.py` so script + staleness guard + Stage D verifier share ONE enumeration. `generated_at_commit` is provenance; Stage D pins via `/api/version`.

## 5. F1 outcome — split SUCCEEDED, suite green

`aether-eval` base deps are now harness-only; the real-pipeline stack is the `aether-eval[pipeline]` extra. Every heavy import was verified lazy (grep over `aether_eval/`: zero top-level heavy imports). The workspace root already depends on `aether-detection`/`aether-data-spine` directly, so the dev/CI environment and every eval run are unchanged — full suite green before and after, lockfile delta is bookkeeping only. **In-image proof:** `scipy`, `rasterio`, `pandas`, `earthaccess` ABSENT; `numpy` present (a `shapely` dependency), `pyproj`/`shapely` present (aether-causal schema deps).

## 6. Dockerfile + container evidence

`Dockerfile` (committed): multi-stage; both stages digest-pinned (`python:3.12-slim@sha256:a39549e2…`, uv `0.11.17@sha256:03bdc89b…` — digests read from the locally pulled images, matching the lockfile-writing uv version); `uv sync --frozen --no-dev --no-editable --package aether-api`; committed artifact tree at `/app/data` (`AETHER_DATA_ROOT`); `ARG GIT_SHA → AETHER_GIT_SHA`; `AETHER_ENV=production` baked; non-root user; no credentials at any layer; uvicorn `--proxy-headers --no-server-header`, port 8080, single worker (rationale in docs/deployment.md).

- **Image size: 105,670,783 bytes (~101 MiB) content / 447 MB unpacked** (Docker reports both; the unpacked figure is what Fly's 8 GB rootfs limit sees). Venv inside: 166 MB; artifact tree: 8.2 MB.
- **Runtime RAM: 48–50 MiB** under repeated detail+raster requests (`docker stats`, three measurement rounds) — comfortably inside Fly's smallest 256 MB machine.
- **Found-and-fixed during the build:** the first image leaked ~110 MB of **gitignored** `.npz` working files into `/app/data` (COPY takes the working tree, not the committed tree; a CI checkout is clean but the image must not depend on that). `.dockerignore` now mirrors the never-commit-data rule (`**/*.npz`, `*.tif`, `*.zarr`, `*.nc`, `*.h5`, `.DS_Store`, `_pre_loocv`); rebuilt image verified: `/app/data` = 8.2 MB, **0 leaked files** (in-container `find`).
- **Live-container guards: 5/5 passed** against `docker run` (`AETHER_LIVE_BASE_URL=http://localhost:8080`, expected SHA pinned to the build arg) — byte-identity for all 17 manifest endpoints, composed parity, version SHA, read-only, headers, whitelist.
- **Loud-failure proof:** `docker run` without `AETHER_ALLOWED_ORIGINS` crashes at startup with `ConfigError: AETHER_ALLOWED_ORIGINS is required when AETHER_ENV=production …` — no silent default in the deployed posture.

## 7. Web production build against the containerized API + screenshots

Production build with `NEXT_PUBLIC_API_BASE=http://localhost:8080` (the container — a non-default port; dev default is 8000), served via `pnpm start`. Driven in headless Chrome via Playwright (the driver clicks the REAL Cesium markers by projecting each event's lat/lon through the live viewer — no app-code test hooks were added). Shots committed under `docs/reports/screenshots/sprint10_stage_b/`:

1. `01_globe_three_markers.png` — globe, markers, HUD readout, statusbar.
2. `02_statusbar_attribution_build_sha.png` — **"POWERED BY ESRI · CONTAINS MODIFIED COPERNICUS CLIMATE CHANGE SERVICE INFORMATION (ERA5)"** + the honesty line + **BUILD 115AF07** (fetched from `/api/version`; the chip is absent, never invented, when the API is unreachable).
3. `03/04_goturdepe_*.png` — inspector (23.4 t/hr ours-cal, CROSS-CHECKED, scope caveat) + NASA layer toggle.
4. `05_permian_inspector.png` — 0.85 t/hr, CROSS-CHECKED, 18.3 t/hr context-only block intact.
5. `06–09_india_*.png` — heat inspector (PER-QUANTITY badge, two-lanes block before any number, +5.10 K), LST layer toggle, per-quantity tier table, factor attribution.

Attribution decision (flagged): the statusbar carries the manual **"Powered by Esri"** text + the ERA5 CC-BY line; the Esri **data-source credit** ("Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community") renders on Cesium's never-suppressed credit display — the first statusbar draft carried both and ellipsized the ERA5 line, which is worse than the split.

## 8. Notes for review

- **mypy:** the two new-module sets (`config`, `main`, `manifest`, guards, script) are strict-clean. Two **pre-existing** errors in `loaders.py` (the untouched pending-`EventSummary` branch, present at the gate commit) remain — out of Stage B scope, logged here rather than silently fixed alongside.
- **CI:** untouched this stage. The new live-container guards self-skip without `AETHER_LIVE_BASE_URL`; the deselected-count assertion is unaffected (7, unchanged). Deploy wiring is Stage D per the brief.
- **fly.toml** is deliberately NOT written yet — it belongs to the Stage C runbook with the [Human] choreography.
- The image bakes the full committed `stage_a_outputs`/`stage_b_outputs` trees (~8 MB incl. non-served committed diagnostics PNGs) rather than a curated served-only subset — all committed, license-audited content; curation would add a second enumeration to drift.
- Watcher hygiene: the web server (`pnpm start`) and the container were torn down at stage end; no orphaned processes.

## 9. STOP

Stage C (deploy choreography, human-in-the-loop) awaits the gate decision.
