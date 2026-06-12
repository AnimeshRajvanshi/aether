# Sprint 10 — Stage A: Deployment probe (gate report)

**Date:** 2026-06-12 · **Author:** Claude Code · **Status:** PROBE ONLY — nothing provisioned, no accounts touched, no deploys.
**Probed at commit:** `84e548c` (main == origin/main).

## 0. Precondition — main is green in CI (verified, not assumed)

- `git rev-parse HEAD origin/main` → both `84e548c490e0e41357aa63ae16e8294bf1e93f75` (local main in sync with origin).
- GitHub Actions run **27431975420** ("chore: Sprint 9 closeout", push to main): `headSha == 84e548c490e0e41357aa63ae16e8294bf1e93f75`, `status: completed`, `conclusion: success`; both jobs green (`python: success`, `web: success`). Verified via `gh run view` on 2026-06-12.

Precondition PASSES. (The prior run on main, Sprint 8 closeout, was a failure — fixed by `27377528637`; the failure predates the current HEAD and does not gate this sprint.)

## 1. Deployed artifact inventory + license audit

### 1.1 The route table (walked live, not from docs)

`uv run python -c "from aether_api.main import app; ..."` over `app.routes`:

| Route | Methods | Class (§4) | Payload source |
|---|---|---|---|
| `/openapi.json` | GET, HEAD | framework-generated | FastAPI schema |
| `/docs`, `/docs/oauth2-redirect`, `/redoc` | GET, HEAD | framework-generated | Swagger/ReDoc HTML |
| `/api/health` | GET | composed | in-code dict |
| `/api/events` | GET | composed | multi-file (YAML + stage A/B JSONs) |
| `/api/events/{event_id}` | GET | composed | multi-file (up to 9 committed files) |
| `/api/events/{event_id}/enhancement.png` | GET | **raw stream** (FileResponse) | `assets/<id>/enhancement.png` |
| `/api/events/{event_id}/nasa.png` | GET | **raw stream** | `assets/<id>/nasa.png` |
| `/api/events/{event_id}/diff.png` | GET | **raw stream** | `assets/<id>/diff.png` |
| `/api/events/{event_id}/bounds` | GET | **re-serializes ONE file** → Stage B: raw | `assets/<id>/bounds.json` |
| `/api/events/{event_id}/mask.geojson` | GET | **raw stream** | `assets/<id>/mask.geojson` |
| `/api/events/{event_id}/hypotheses` | GET | **re-serializes ONE file** (active path) | `attribution_outputs/<id>/hypotheses.json` |
| `/api/events/{event_id}/layers/{layer}.png` | GET | **raw stream** (bounds-whitelisted) | `assets/<id>/<layer>.png` |
| `/api/events/{event_id}/factor-hypotheses` | GET | **re-serializes ONE file** (active path) | `attribution_outputs/<id>/factor_hypotheses.json` |

Only GET (+ framework HEAD) routes exist today; the Stage B guard will machine-check that this stays true.

### 1.2 Served artifact set (route-reachable), measured

**Raw-artifact files reachable through the routes: 14 files, 7,929,533 bytes (7.56 MiB).**

| Event | Files | Notes |
|---|---|---|
| turkmenistan_goturdepe_2022_08_15 | enhancement.png (1.39 MB), nasa.png (0.95 MB), diff.png (2.34 MB), mask.geojson (191 KB), bounds.json (817 B) | the `_nasa_k/` sibling set (4.88 MB) is committed in the same tree but **route-unreachable** (path params cannot contain `/`); it ships in the image, license-identical (NASA-derived) |
| permian_basin_2022 | enhancement.png, nasa.png, diff.png, mask.geojson, bounds.json (34.7 KB total) | |
| india_nw_heatwave_2022_04 | lst_anomaly.png (3.02 MB), air_anomaly.png (6.2 KB), air_baseline.png (4.3 KB), bounds.json (1.6 KB) | no mask.geojson — heat renders a bbox outline |

**Composed-endpoint source files: 17 files, 127,573 bytes (0.12 MiB)** — per event: `q_estimate.json` / `air_lane.json`, `stage_a_report.json`, `validation.json`, `lst_lane.json`, `uhi.json`, `diagnostics.json`, `hitran_k_sat_provenance.json`, `hypotheses.json` / `factor_hypotheses.json`, benchmark YAMLs.

**Total served-artifact set ≈ 7.7 MiB.** The web build's static assets: `public/` 13 MB (CesiumJS runtime assets) + `.next/static` 8.9 MB ≈ **22 MB** — comfortably inside every platform limit found in §3.

### 1.3 License audit, by source dataset

| Source | Served artifacts derived from it | License (how verified) | Redistribution status |
|---|---|---|---|
| NASA EMIT L1B/L2A/L2B | methane enhancement/nasa/diff PNGs, masks, q_estimate, stage_a_report | NASA Earth science data policy, fetched live 2026-06-12: "NASA commits to the full and open sharing of Earth science data obtained from NASA Earth observing platforms" (earthdata.nasa.gov data-information-policy) | ✅ open; standard citation |
| NASA MODIS MOD11A1 (Terra LST) | lst_anomaly.png, lst_lane.json, uhi.json | same NASA policy (above) | ✅ open |
| ERA5 (Copernicus CDS / ARCO mirror) | air_anomaly/air_baseline PNGs, air_lane.json, ERA5 fields in q_estimate | CDS dataset page fetched live 2026-06-12: licence listed as **CC-BY**; cite DOI 10.24381/cds.adbb2d47 + Copernicus/ECMWF credit | ✅ open with attribution — **attribution line required in the deployed UI/docs (Stage B item)** |
| NOAA ISD (non-US stations, WMO Res. 40) | **derived statistics only** in `validation.json` | license verbatim carried IN the served artifact itself: "The non-U.S. data in ISD are subject to WMO Resolution 40 restrictions, and cannot be redistributed to other users or customers." | ✅ derived-only per the Sprint 9 interim review ruling; **raw provably absent — see §1.4** |
| IMD Pune gridded daily Tmax | derived statistics only (regional-mean anomalies in air_lane.json/validation.json) | Sprint 9 Stage A probe + gate ruling: raw `.grd` in gitignored cache only, derived statistics committed | ✅ per the standing ruling (no new exposure: deployment serves the same committed files) |
| OGIM v2.7 | facility candidates inside hypotheses.json; committed regional subsets | Zenodo record 15103476 fetched live 2026-06-12: **"Creative Commons Attribution 4.0 International"** | ✅ CC BY 4.0; the served JSON already embeds the OGIM DOI (attribution present in-band) |
| ESA WorldCover v200 | urban/rural classification inside uhi.json (derived stats) | CC BY 4.0 (Sprint 9 Stage A probe, cited verbatim in artifacts) | ✅ |
| Landsat 8/9 C2L2 ST | sign-agreement stats inside uhi.json | USGS/NASA open policy | ✅ |
| HITRAN2020 via HAPI | hitran_k provenance JSON (line-list derived k) | HITRAN data are free for scientific use with citation (repo carries Gordon 2022 + Kochanov 2016 citations) | ✅ |
| Google Fonts (Archivo, Chakra Petch, IBM Plex) | self-hosted font files in the web build (`next/font` downloads at BUILD time, serves first-party) | OFL | ✅ no runtime fetch to Google |
| CesiumJS | `public/cesium` runtime assets (13 MB) | Apache 2.0 — github.com/CesiumGS/cesium LICENSE.md fetched live 2026-06-12 | ✅ |

**Imagery providers (browser-side, not our artifact set — audited per cardinal rule 3):**

- **ESRI World Imagery (the token-free default)** — verified live 2026-06-12: the keyless endpoint serves anonymously today (`f=pjson` loads, tile request returns 200/jpeg with no key; item is `access: "public"`, `contentStatus: "public_authoritative"` — not deprecated). Terms: Esri Master Agreement; **attribution required** — "Powered by Esri" text plus the data-source credit, which is now **"Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community"** (note: "Vantor", formerly Maxar — any hardcoded "Maxar" string would be stale; none found in the app). Cesium's default credit display renders the MapServer `copyrightText` automatically (the app does not suppress the credit container — verified), but **"Powered by Esri" needs manual addition → Stage B compliance item.** No bulk tile export (E300 footnote 10) — the app does none. CAVEAT, stated honestly: the endpoint is legacy-tier (Esri steers new development to token-based basemap services); no live page affirmatively blesses anonymous third-party use, and none prohibits it; Esri's lifecycle blog posts 403'd our fetches (flagged UNVERIFIED by the probe agent). Characterization: **permitted today, legacy-tier, migration encouraged** — human acknowledges at this gate.
- **Cesium ion (only if a token is provided)** — Community (free) plan fetched live 2026-06-12 explicitly covers "Non-commercial personal projects"; ToS §2.2.3 requires the Cesium ion logo "prominently viewable"; tokens are client-visible **by design** and should be URL-restricted ("Allowed URLs … recommended for a token added to a public client"). Default remains token-free ESRI; ion is optional.

**Runtime-fetch audit (cardinal rule 1):** the deployed API performs **zero** runtime data fetching — every endpoint reads committed files (verified by reading `main.py`/`config.py`/`loaders.py`: the import chain is `aether_eval.loader` (local YAML) + `aether_causal.schema` (pydantic) — no network module is imported at request time). The web client fetches exactly: our API, ESRI basemap tiles (browser-side, audited above), and nothing else (`grep` over `src/` external URLs: only `localhost:8000` default, `doi.org` anchor hrefs, the ArcGIS MapServer, and an SVG xmlns).

### 1.4 Hard checks

**(a) Zero NOAA ISD raw files reachable — PROVEN, three ways:**
1. **Committed-tree sweep:** `git ls-files | grep -iE 'isd|noaa|station'` → exactly three hits, all CODE (`packages/data_spine/aether_data_spine/isd.py`, its test, `scripts/sprint9_fetch_station_imd.py`). Zero data files. Raw ISD lives only in the gitignored `.aether_cache/`, which never enters git or the image.
2. **Served-set enumeration:** all 31 route-reachable files are listed in §1.2; none is a station observation file. The only ISD-derived served content is `validation.json`, whose `per_station` list carries **per-station derived summaries only** (inspected: `station_window_max_c` — a window aggregate — and `mean_bias_era5_minus_station_k`; never an observation series), exactly what the Sprint 9 interim review approved. The artifact carries the WMO Res. 40 license verbatim and its own handling statement in-band (`provenance.isd_handling`: "raw station files in gitignored cache only; this artifact carries derived comparison statistics … never a re-hosted observation series (interim review ruling)").
3. **Negative space, to be made permanent:** Stage D's verifier will assert ISD raw paths 404 on the live API (no such route exists today; the guard keeps it that way).

Sibling check: every other served list was inspected for hidden series — `air_lane.daily` (ERA5 regional aggregates), `air_lane.imd_lane_daily_window` (IMD regional-mean anomalies), `lst_lane.per_granule` (MODIS tile stats), `uhi.daily` (urban/rural means + pixel counts). All derived aggregates. **No raw observation series exists anywhere in the served set.**

**(b) Zero `.netrc`/Earthdata-credentialed paths at runtime — PASS.** The API import chain (above) touches no network. `earthaccess` is a dependency of `aether-data-spine` but no data-spine module is imported by `aether_api`. `git grep` hits for `.netrc` are all docs/fetch-scripts/data-spine code (fetch-time tooling, not serving paths). The container will carry no `.netrc` (Stage B Dockerfile: no credentials at any layer; `.dockerignore` exists).

**(c) Total served-artifact size:** 7.7 MiB API artifacts + 22 MB web static (§1.2). **The image-size driver is NOT artifacts — it is transitive scientific dependencies** (finding F1, §6).

## 2. Secrets inventory

| Name | Required? | Public-by-design? | Where it lives |
|---|---|---|---|
| `NEXT_PUBLIC_API_BASE` | YES for prod web (defaults to `http://localhost:8000`) | **Yes — baked into the client JS bundle at build time**; it is a URL, not a secret | Vercel project env var, set before build |
| `NEXT_PUBLIC_CESIUM_ION_TOKEN` | NO (token-free ESRI default) | **Yes — any client-side ion token is visible in the browser regardless**; Cesium's own docs say to scope it (assets:read) and URL-restrict it | Vercel env var, IF the human opts into ion |
| `AETHER_DATA_ROOT` | NO (path override for tests/alt layouts; container uses the baked repo layout) | not a secret (a filesystem path) | container env if ever needed |
| `AETHER_ALLOWED_ORIGINS` (Stage B, to be created) | YES in prod (CORS is currently hardcoded to localhost — Stage B item 2) | not a secret | API platform env var |
| Git SHA build arg (Stage B item 5) | YES at build | not a secret | CI build arg → container env |
| `FLY_API_TOKEN` **or** `RENDER_DEPLOY_HOOK_URL` | YES for CI deploy (per chosen host) | **NO — a real secret.** [Human] creates it and enters it as a GitHub Actions secret; it never transits the repo or this chat | GitHub repo secret |
| `VERCEL_TOKEN` + `VERCEL_ORG_ID` + `VERCEL_PROJECT_ID` | only if the Actions-CLI path is chosen (the native Git integration needs none) | NO — secrets | GitHub repo secrets, [Human] |

- **No `.env` file of any kind exists on disk today**, and **no `.env.example` exists yet** (the task brief assumed one — finding F4; Stage B creates it as the single documented schema).
- **Gitignore audit:** covers `.env`, `.env.local`, `.env.*.local` — **GAP: a plain `.env.production` / `.env.development` (non-`.local`) would NOT be ignored** (finding F5; Stage B closes it, e.g. `.env.*` + `!.env.example`).
- **Secret-shaped string sweep over the committed tree** (`git grep -E` for GitHub/AWS/Slack/Google/JWT/private-key patterns): **zero hits.**

## 3. Hosting candidates — verified from live documentation, 2026-06-12 (not memory)

All terms below were fetched live by probe agents with URLs recorded; anything not verifiable live is marked UNVERIFIED rather than filled in from memory.

### 3.1 Web — Vercel (Hobby)

- **Fit:** Hobby is free and "restricts users to non-commercial, personal use only" (vercel.com/docs/plans/hobby + fair-use guidelines, quoted) — a self-built, unmonetized portfolio demo fits; any paid-work/ads/payments angle would not.
- **Sleep/cold start:** no sleep mechanism is documented for Vercel at all; static assets are CDN-served (no compute), SSR functions get Fluid-compute cold-start mitigation by default. Effectively **no cold-start problem on the web side**.
- **Limits vs us:** CLI deploys cap at 100 MB / 15,000 source files on Hobby (our ~22 MB static is fine); the native **Git integration carries no such documented cap** and is the simpler path. 250 MB function-bundle and 4.5 MB function-response caps mean Cesium assets must stay in `public/` (they do) and never be proxied through a route.
- **Response transformation:** automatic gzip/brotli **content-encoding only**, on an allowlist of text/JS/JSON/wasm MIME types (vercel.com/docs/how-vercel-cdn-works/compression) — transport-layer, decoded bytes unchanged. Image optimization NEVER touches plain static requests (only the opt-in `next/image` pipeline; we can additionally set `images.unoptimized`). No minification of served assets is documented.
- **Hobby restriction that matters:** Hobby teams cannot connect repos owned by a GitHub **organization**. Our repo is `AnimeshRajvanshi/aether` — a personal account (currently PRIVATE; personal private repos are fine) → compatible.
- **Env vars:** dashboard → Project → Environment Variables; `NEXT_PUBLIC_*` values are **inlined at build time** — changing them requires a redeploy (nextjs.org env-vars guide, quoted).

### 3.2 API — Fly.io

- **Pricing:** **no free tier for new customers**; pure usage-based. Cheapest always-on machine: shared-cpu-1x / 256 MB ≈ **$2.02/month** (pricing page figure, Amsterdam; US same ballpark — exact US figure UNVERIFIED). Stopped machines cost only rootfs storage ($0.15/GB-mo). Credit card required.
- **Sleep/wake (documented):** auto-stop/auto-suspend via `fly.toml` (`auto_stop_machines = "off"|"stop"|"suspend"`, `min_machines_running`). **Resume from suspend: "a few hundred ms"; cold start from stopped: "~2+ seconds"** (fly.io/docs/reference/suspend-resume). Fully disableable.
- **Image limit:** **8 GB rootfs** for standard machines (fly.io troubleshooting doc, verbatim) — our image fits even un-trimmed (§6 F1).
- **US regions:** dfw, ewr, iad, lax, ord, sjc.
- **Response transformation — IMPORTANT:** Fly's proxy **compresses response bodies at the edge by default** (zstd/brotli/gzip negotiated via Accept-Encoding) and injects headers. Documented escape hatches: the proxy passes through any response that already has a `Content-Encoding` header; `http_service.http_options.response.pristine = true` stops Fly header injection. Decoded payload remains the original bytes; the Stage D verifier compares **transport-decoded** bodies by design, and can additionally send `Accept-Encoding: identity`.
- **CI deploy:** official GitHub Actions guide — `superfly/flyctl-actions/setup-flyctl` + `flyctl deploy --remote-only` with `FLY_API_TOKEN`. **[Human] steps:** `fly tokens create deploy -x 999999h` in the app dir → copy the full token (including the `FlyV1 ` prefix) → GitHub repo Settings → Secrets and variables → Actions → new secret `FLY_API_TOKEN`.

### 3.3 API — Render

- **Pricing:** free tier = 750 instance-hours/month (suspends when exhausted; "Do not use them for production applications" per Render's own docs). Cheapest always-on: **Starter, $7/month per third-party trackers — the live pricing page is JS-rendered and could not be fetched; [Human] should eyeball render.com/pricing before relying on it** (live corroboration: Render's own Heroku comparison states 2 GB RAM = $25/mo Standard).
- **Sleep/wake (documented, verbatim):** free services spin down after **15 minutes** idle; wake "takes about one minute" with a loading page. **A ~60 s first load is a broken demo** — free Render is effectively eliminated unless the human accepts that.
- **Image limit:** 10 GB compressed (prebuilt-image deploys); linux/amd64 required.
- **Regions:** Oregon, Ohio, Virginia, Frankfurt, Singapore.
- **Response transformation:** automatic Brotli/gzip compression at the proxy; **no documented way to disable it** — same transport-decoded-comparison answer as Fly. No body rewriting/minification documented. Free tier has no edge caching.
- **CI deploy:** documented deploy hooks — a secret per-service URL curl'd from Actions. **[Human] steps:** Render Dashboard → service → Settings → copy Deploy Hook URL → GitHub secret `RENDER_DEPLOY_HOOK_URL`. (Render also auto-deploys on push when the repo is linked.)

### 3.4 Cold-start comparison and recommendation (human decides at this gate)

| Option | Always-on cost | Idle wake | Verdict |
|---|---|---|---|
| Fly.io, always-on (`auto_stop="off"`) | ≈ $2/mo | n/a | **recommended default** |
| Fly.io, suspend | ≈ storage-only floor | few hundred ms (documented) | acceptable fallback; cheapest viable |
| Render Starter | $7/mo ([Human] verify price) | n/a | works; pricier than Fly |
| Render free | $0 | **~60 s** (documented) | broken demo; not recommended |
| Vercel Hobby (web) | $0 | none documented | recommended for web |

**Recommended architecture: web on Vercel Hobby (Git integration), API on Fly.io** — always-on at ≈$2/mo, or suspend-mode at near-zero with sub-second wake. RAM note: the API imports only fastapi/pydantic/yaml at runtime (heavy scientific deps are install-time baggage, not imported), so 256 MB is plausible — to be **measured** against the local container in Stage B, not assumed.

## 4. Byte-identity feasibility scan

Classification of every route (from the walked table in §1.1):

**Class (a) — raw-streaming today (byte-identity holds end-to-end):** `enhancement.png`, `nasa.png`, `diff.png`, `mask.geojson`, `layers/{layer}.png` — all `FileResponse` over a single committed file.

**Re-serializers of a single committed file — move to raw streaming in Stage B (per brief §A.4):**
1. `/api/events/{event_id}/bounds` — `json.loads` → `JSONResponse` re-serialization of `bounds.json`.
2. `/api/events/{event_id}/hypotheses` (active path) — `HypothesisSet.model_validate_json` → `model_dump`; single source file.
3. `/api/events/{event_id}/factor-hypotheses` (active path) — same pattern over `factor_hypotheses.json`.

For (2)/(3) the Pydantic round-trip is a real guard (extra="forbid" means the API can neither add nor drop a field). Stage B proposal: **stream the raw bytes, keep the validation as a startup check + suite guard** — same guarantee, byte-identity gained. Their `pending` fallbacks (`{"hypotheses": null, "status": "pending"}`) are in-code micro-payloads and stay class (b). Decision lands at the Stage B gate.

**Class (b) — composed (deep-equality against the pinned commit, per brief):** `/api/events`, `/api/events/{event_id}`, `/api/health`, plus the framework-generated `/openapi.json`, `/docs`, `/redoc` (whose production fate is the Stage B item-7 decision).

**Transport caveat for the Stage D verifier (now verified against all three platforms):** every candidate proxy applies content-encoding compression by default (Fly: zstd/br/gzip, escape hatches documented; Render: br/gzip, no documented off-switch; Vercel: allowlisted MIME types only). The verifier therefore hashes **transport-decoded bodies** (already mandated by the brief) and should ALSO send `Accept-Encoding: identity` as a second probe — two independent paths to the same bytes.

## 5. CI deploy-hook feasibility — VERIFIED for all three platforms

- Current CI: a single `ci.yml` (push/PR on main; `python` + `web` jobs). A deploy job can be appended, gated on the existing jobs' success.
- **Fly:** official Actions guide (flyctl + `FLY_API_TOKEN` deploy token as a GitHub secret). [Human]: create the scoped token, add the secret. [Claude]: the workflow job + `fly.toml`.
- **Render:** official deploy-hook guide (secret URL as GitHub secret, curl on success). [Human]: copy hook URL from dashboard, add secret. [Claude]: the workflow step.
- **Vercel:** native Git integration deploys on push with no Actions work at all ([Human]: one-time project import + env vars); the token+CLI Actions path also exists if build-order control is needed.

## 6. Findings (for human review at this gate)

- **F1 — image size is dependency-driven, not artifact-driven.** `aether-api` transitively requires `aether-eval` → `aether-detection` + `aether-data-spine` → scipy (81 MB), rasterio (67 MB), pandas (48 MB), numpy (25 MB), pyproj (19 MB), netcdf4, gcsfs, zarr, earthaccess… (sizes measured in the local venv). None of these is **imported** by the API at runtime — `aether_eval.real_pipeline` imports lazily by design; the API touches only `aether_eval.loader`/`schema` and `aether_causal.schema`. Estimated image: roughly 0.5–1 GB uncompressed unless trimmed — within every platform limit, but fat. Stage B options (decision at the Stage B gate, not now): (i) accept the weight — zero code change; (ii) split `aether-eval` deps so the heavy recipes become an extra (`aether-eval[pipeline]`) — small, honest pyproject change, no science touched. The probe recommends (ii) be *evaluated* in Stage B with the suite green, falling back to (i) if it ripples.
- **F2 — asset endpoints do not whitelist `event_id`.** The PNG/bounds/mask routes serve any existing path under `assets/` for whatever `{event_id}` matches the route segment. Traversal is structurally blocked (path params cannot contain `/`, so `..%2F` cannot escape and `_nasa_k` is unreachable), and the assets tree contains only committed render sets — but defense-in-depth says validate `event_id ∈ EVENT_IDS` like the JSON endpoints already do. Cheap Stage B hardening, guard-tested.
- **F3 — ESRI World Imagery: keyless access verified live but legacy-tier.** Serving anonymously today, item public/authoritative, attribution mandatory ("Powered by Esri" + the Vantor-updated credit line). The "Powered by Esri" text is not currently rendered → Stage B compliance item. Esri's lifecycle posts could not be fetched (403) — the migration-pressure characterization is search-snippet-sourced and marked UNVERIFIED. Risk acknowledgment for the human: the endpoint could someday require tokens; the app's ion fallback already exists.
- **F4 — no `.env.example` exists** (the brief assumed one). Stage B creates it as the single documented config schema.
- **F5 — gitignore gap:** `.env.production`/`.env.development` (non-`.local`) would not be ignored today. One-line Stage B fix.
- **F6 — Render free tier is a broken demo** (documented ~60 s wake). Eliminated unless the human overrides; the real choice is Fly (~$2/mo or suspend-mode) vs Render Starter ($7/mo, price needs a human eyeball).
- **F7 — FastAPI docs endpoints** (`/docs`, `/redoc`, `/openapi.json`) are live by default. The Stage B brief (item 7) already frames the decision: for a read-only public artifact API they are harmless and arguably good portfolio transparency. Recommendation: leave ON, stated in `docs/deployment.md`; human decides at the Stage B gate.
- **F8 — repo is currently PRIVATE.** Vercel Hobby handles personal private repos, so deployment is not blocked; making the repo public is the portfolio sprint's decision, not this sprint's.

## 7. What was NOT done (cardinal-rule compliance)

No accounts created, no tokens generated, no platforms provisioned, no deploys, no Dockerfile written, no code changed. The probe read the repo, walked the live route table in-process, measured sizes, and fetched public documentation. All account creation and every secret value are **[Human]** steps, enumerated in §2/§3/§5.

## 8. Decision items for this gate

1. **Hosts:** web on Vercel Hobby + API on Fly.io (recommended), or Render Starter for the API instead?
2. **Pay-or-not:** Fly always-on ≈$2/mo vs suspend-mode (few-hundred-ms wake, near-zero cost) vs Render free (60 s wake — recommend NO).
3. **ESRI posture (F3):** accept keyless legacy endpoint + add "Powered by Esri" attribution in Stage B, or provision a Cesium ion token ([Human]) instead?
4. **Sign-off to enter Stage B** (hardening, all local, no accounts).

---
*Verification appendix: precondition via `gh run view 27431975420` (success, headSha 84e548c…); route table walked in-process; sizes via filesystem enumeration at HEAD; ISD sweep via `git ls-files`/`git grep` at HEAD; license fetches: zenodo.org/records/15103476, cds.climate.copernicus.eu (ERA5 dataset page), earthdata.nasa.gov data-information-policy, github.com/CesiumGS/cesium LICENSE.md, developers.arcgis.com attribution doc + arcgis.com item JSON + live keyless tile probe, esri.com E204/E300 PDFs, cesium.com pricing/ToS/token docs, fly.io pricing/autostop/suspend-resume/troubleshooting/regions/content-encoding/configuration/GHA docs, render.com free/deploying-an-image/docker/regions/native-runtimes/deploy-hooks docs, vercel.com hobby/fair-use/limits/compression/image-optimization/env-vars/git/GHA docs, nextjs.org env-vars guide. Full agent reports with verbatim quotes preserved in the session transcript.*
