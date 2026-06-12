# Sprint 10 — Stage A gate ruling (recorded verbatim from review, 2026-06-12)

Ruling on `docs/reports/sprint10_stage_a_probe.md` (probe at `84e548c`, report committed at `e6b22f8`).

## Hosts

- **Web: Vercel Hobby**, native Git integration.
- **API: Fly.io** Docker container, **always-on** (`auto_stop_machines = "off"`), the ~$2/mo cost **accepted**.
- **Render: eliminated** — 60 s wake on free is a broken demo; Starter ($7/mo) is dominated by Fly.

## Imagery posture (F3)

- **ESRI keyless endpoint retained.** "Powered by Esri" text + the current Vantor-era credit line ("Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community") are a **Stage B compliance item**.
- **Cesium ion NOT provisioned** — avoids carrying a secret and the ion-logo ToS requirement. The in-code ion fallback (`NEXT_PUBLIC_CESIUM_ION_TOKEN`) is retained but unused.

## Attribution

- **ERA5 CC-BY attribution line** is a Stage B UI/docs item.

## Findings rulings

- **F1:** evaluate the `aether-eval[pipeline]` dependency split **with the full suite green**; fall back to the fat image if it ripples.
- **F2:** whitelist `event_id` on asset routes, guard-tested.
- **F4/F5:** create `.env.example`; close the `.env.production`/`.env.development` gitignore gap.
- **F7:** FastAPI docs endpoints **stay ON in production**; reason recorded in `docs/deployment.md`.
- **F8:** repo stays **private** this sprint.

## Scope amendment (recorded in the task brief as "Gate A amendment")

- **Custom domain IN scope:** the web app deploys to **https://aether.arkaneworks.co** (CNAME at the human's registrar → Vercel; a **[Human]** Stage C step; registrar identity TBD from the human).
- **Path-based hosting under `arkaneworks.co/aether` explicitly rejected** (proxy fragility, Next.js basePath/Cesium asset-path ripple, coupling to the portfolio site).
- **API stays at its fly.dev hostname**; `api.aether.arkaneworks.co` is an optional Stage C add **pending a live check of Fly certificate pricing — never asserted from memory**.
- Production CORS origin and `NEXT_PUBLIC_API_BASE` in the Stage B env schema reflect these hostnames.
- `docs/deployment.md` records: **Vercel Hobby is non-commercial; any future commercial turn of Aether requires a plan upgrade.**

## Effect

Stage B is unblocked: hardening, all local, no accounts, no deploys, suite green throughout, STOP at the Stage B gate.
