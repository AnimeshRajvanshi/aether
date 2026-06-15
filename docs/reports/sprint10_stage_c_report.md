# Sprint 10 — Stage C: Deploy (gate report)

**Date:** 2026-06-15 · **Status:** COMPLETE at gate — the app is live on a public URL.
**Live URLs:** web **https://aether.arkaneworks.co** · API **https://aether-api-arkaneworks.fly.dev**
**Deployed SHA (pinned everywhere):** `c960cfd` (`c960cfdb7dfcd7249c83b7f000bd3d4e0221cd69`) — the CI-green head of main.

## 1. What was deployed, and how the SHA stays honest

- **API:** the Stage B Docker image, built remotely by Fly from the pushed checkout with
  `--build-arg GIT_SHA=$(git rev-parse HEAD)`. `/api/version` returns exactly `c960cfd`; the web
  footer renders that value (fetched, not hardcoded → **BUILD C960CFD** in shot 02).
- **Web:** Vercel built `apps/web` from the same repo head, `NEXT_PUBLIC_API_BASE` baked to the Fly
  URL before the first deploy.
- The footer chip shows the **API's** SHA (the artifact server is the thing Stage D will verify);
  it is absent, never invented, if `/api/version` is unreachable.

## 2. Runbook as executed (who did what)

| Step | Owner | Result |
|---|---|---|
| Push + CI green | [Human] | head `c960cfd`; Actions run `27444241481` green at that SHA (both jobs) — reverified before deploy |
| Fly account + card + `fly auth login` | [Human] | authenticated as `rajvanshianimesh@gmail.com` |
| `fly apps create aether-api-arkaneworks` | [Human] | app name as planned (no `fly.toml` edit needed) |
| Pre-deploy image-inventory guard | [You] | GREEN on a local twin at `c960cfd` (65 files under `/app/data`, all committed) |
| `fly deploy --remote-only --build-arg GIT_SHA=…` | [You] | deployed; **found-and-fixed:** Fly auto-spawned a 2nd machine "for HA" — `fly scale count 1` brought it back to the single always-on machine the gate accepted (status: 1 started machine in `lax`) |
| Vercel import (root `apps/web`, env before deploy), domain add, SSL | [Human] | `aether.arkaneworks.co` verified, SSL issued, Deployment Protection off for production |
| Namecheap CNAME `aether` → Vercel target | [Human] | value `43d9780654874000.vercel-dns-017.com` (the dashboard value; not the hardcoded guess) |
| Hosted verification | [You] | this report |

No account credential or secret ever transited the agent. `FLY_API_TOKEN` (the CI deploy token, step 9)
is a Stage D [Human] step and was deliberately NOT created here.

## 3. Independent verification (not "it loads for me")

- **DNS, looked up directly (not assumed):** `aether.arkaneworks.co` CNAME → `43d9780654874000.vercel-dns-017.com` → A `216.198.79.65` / `64.29.17.65`; **exact match** to the value the human reported from Vercel's dialog. Apex still GitHub Pages (`185.199.10x.153`), `www` still `animeshrajvanshi.github.io` — **untouched**, as the gate required.
- **Custom domain HTTPS:** HTTP 200, TLS verifies (`ssl_verify_result 0`).
- **API SHA pin:** `/api/version` = `c960cfd` (= the pushed head).
- **CORS, live:** `https://aether.arkaneworks.co` is granted (`access-control-allow-origin` echoed); `https://evil.example.com` gets **no** grant. The default `*.vercel.app` origin is, by design, NOT allowed — the custom domain is the canonical origin.
- **Read-only + headers, live:** `POST /api/events → 405`; `nosniff` / `DENY` / `no-referrer` present.
- **Full live-container guard set against the fly.dev URL: 5/5 PASSED** — health, version-SHA pin, **byte-identity of all 17 raw endpoints through Fly's proxy** (transport-decoded comparison vs the committed manifest), composed deep-equality vs the in-process app, read-only + hardening. (Run at deploy time; re-confirmable any time with `AETHER_LIVE_BASE_URL=https://aether-api-arkaneworks.fly.dev`.)

## 4. Hosted smoke test — caveats survived deployment (shot list)

Screenshots from the **hosted** URL (`docs/reports/screenshots/sprint10_stage_c/`), driven in headless Chrome clicking the real Cesium markers (no app-code test hooks):

1. `01_globe_three_markers.png` — globe, three markers (two methane CROSS-CHECKED, one heat PER-QUANTITY), HUD readout; Cesium's "Data attribution" credit visible bottom-left (carries the Esri source credit — never suppressed).
2. `02_statusbar_attribution_build_sha.png` — "POWERED BY ESRI · CONTAINS MODIFIED COPERNICUS CLIMATE CHANGE SERVICE INFORMATION (ERA5)" + "ALL VALUES FROM COMMITTED, REVIEWED ARTIFACTS · NO LIVE TELEMETRY" + **BUILD C960CFD**.
3. `03_goturdepe_inspector.png` — 23.4 t/hr OURS-CAL, CROSS-CHECKED badge, uncertainty budget, the "Read Before Citing" scope block.
4. `04_goturdepe_nasa_layer.png` — NASA L2B retrieval layer toggled (cross-check view).
5. `05_permian_inspector.png` — 0.85 t/hr, CROSS-CHECKED, the 18.3 t/hr context-only "Read Before Citing" block intact.
6. `06_india_heat_inspector.png` — PER-QUANTITY badge, the "Two Temperatures — Read Before Anything Else" lane block rendered BEFORE the +5.10 K headline; C1 VALIDATED row.
7. `07_india_lst_layer.png` — MODIS LST mosaic layer toggled.
8. `08_india_tier_table.png` — per-quantity tiers: C2 VALIDATED (green); C3 duration & C4 extent NOT VALIDATED (red) with criterion lines; V2 CONSISTENCY NOT CLAIMED (amber); LST & UHI CROSS-CHECKED-ceiling (teal). With C1 in shot 06 this is all seven rows.
9. `09_india_factor_attribution.png` — attribution-boundary caveat; F1 ridge 1.00 MODERATE·CAPPED; F2 antecedent soil-moisture as counter-evidence with diagnostics; the "diagnostics establish presence and rarity but cannot causally separate without counterfactuals (out of scope); V25H reserved and unearned" warning.
10. `10_india_cited_external_references.png` — the CITED-EXTERNAL block (Zachariah et al. WWA "~30× more likely", explicitly "NOT computed by Aether — NOT in factor scope") + the references panel with DOIs.

Every honesty surface the local app carries — tier badges, the reserved-VALIDATED ceiling, context-only framing, the two-lanes separation, counter-evidence, the external-attribution boundary — renders identically on the public URL.

## 5. First-load performance (measured twice; honest about Cesium)

Headless Chrome, hosted URL. FCP from the Paint Timing API (same-origin, reliable); byte totals from CDP `Network.loadingFinished` (true on-the-wire bytes — Resource Timing alone zeroes cross-origin responses lacking `Timing-Allow-Origin`, e.g. the ESRI tiles and the API JSON).

| Metric | Cold (empty cache) | Warm (cached) |
|---|---|---|
| First Contentful Paint | **692 ms** | 252 ms |
| DOMContentLoaded | 598 ms | 212 ms |
| `load` | 1047 ms | 212 ms |
| Wall-clock to globe-ready (canvas + BUILD chip) | ~1.3 s | ~0.36 s |
| Total transfer | ~3.4 MB | ~4 KB |

True cold breakdown (CDP, by origin): **Cesium 2.69 MB**, ESRI basemap tiles 0.51 MB, Next.js app 0.24 MB, Fly API JSON ~1 KB.

**The "~13 MB Cesium" stated honestly:** the on-disk `public/cesium` folder is ~13 MB, but only **~2.7 MB across 12 requests actually transfers on the initial globe render** — Cesium lazy-loads the remaining workers/assets on demand, most of which this dashboard never triggers. So the real cold first-load is ~3.4 MB total, not 13 MB. **There is no cold-start delay** to report: the Fly machine is always-on (`auto_stop = "off"`, `min_machines_running = 1`), so the first API request is warm (~0.10 s observed at deploy time) — the gate's pay-for-always-on decision is doing exactly its job.

## 6. Notes / honesty flags

- **Fly auto-HA machine:** corrected to one machine immediately (§2); worth knowing Fly re-adds a second on some deploy paths — `fly scale count 1` after deploy, or watch the machine count, is the standing fix. Stage D's CI deploy job should assert count == 1.
- **Fly proxy `Server:` header:** Fly injects `Server: Fly/…` (its own banner; our app sends none via `--no-server-header`). Cosmetic; `pristine = true` in `fly.toml` would remove it if desired. Does not affect body byte-identity (verified).
- **Web build SHA:** only the API SHA is surfaced (the API is the artifact server Stage D verifies). The web is a static client built by Vercel from the same head; it carries no separate integrity claim, which is correct for Stage D's scope.
- **Watcher hygiene:** the headless browser runs were one-shot (no daemon); no orphaned processes; the local twin image and any test containers were not left running.

## 7. STOP — Stage C gate

Live URL delivered, runbook executed, integrity verified live, caveats confirmed surviving deployment, performance measured. Stage D (the deployed-integrity verifier wired into CI + the `FLY_API_TOKEN` [Human] step) awaits the gate decision.
