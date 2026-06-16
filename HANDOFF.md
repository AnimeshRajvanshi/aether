# HANDOFF.md — cold-start handoff for the next session

> Session-retirement handoff. Written to let a brand-new session pick up cold.
> Pair this with `PROJECT_STATUS.md`, `CLAUDE.md`, and the committed gate reports.

## Re-verify before trusting anything

**Verification results must NOT be transcribed forward. The next session must re-run
pytest and ruff itself.** Before new work: `git status` + `git log --oneline -8`, then
`uv run pytest`, `uv run ruff check .`, and (only for `packages/detection`/`packages/causal`
changes) `uv run aether-eval run`. Last known good — Sprint 11 Stage B (2026-06-15, re-verify don't trust):
pytest **398 passed, 6 skipped, 7 deselected**; ruff **0**; mypy clean on the verifier. (The Sprint 10
closeout run was **389**, not the 388 first recorded — an environment miscount; Stage B adds the
key-results snippet guard + report-completeness cases over the new Sprint 11 reports.)

## Where things stand — SPRINT 10 (DEPLOYMENT) CLOSED

The finished app is **live on a public URL** with the same honesty guarantees it has locally.
Sprint 10 was infrastructure only — **no new science, events, or features**.

- **Live web:** https://aether.arkaneworks.co (Vercel Hobby, custom domain; Next.js/Cesium).
- **Live API:** https://aether-api-arkaneworks.fly.dev (Fly.io Docker container, **single always-on
  machine** in `lax`, `auto_stop="off"`). Serves committed artifacts only — no runtime data fetching.
- **Branch:** `main`, **in sync with `origin/main`** (everything pushed; CI green). HEAD is the
  closeout commit `15263f7`.
- **Deployed API SHA:** `1eeb176` (the closeout commit `15263f7` is **one docs-only commit ahead**,
  not present in the image — see the nuance below). `/api/version` and the footer BUILD chip both
  surface the deployed SHA.

All four stages + one out-of-band UI fix are reviewed and closed:
- **A** — deployment probe + license audit (hosts verified from live docs; NOAA ISD raw *provably
  absent*; secrets are [Human]).
- **B** — hardening: read-only/CORS/config guards, raw-streaming byte-identity, integrity manifest +
  staleness guard, image-inventory guard, multi-stage digest-pinned Dockerfile.
- **C** — deploy (web on Vercel, API on Fly); caveats survive deployment.
- **C fix** — heat factor-attribution cards were unstyled in prod *and* dev (missing `.hypo-*` CSS,
  not a prod-only bug); restyled to the design system, caveats verbatim, re-shot Chrome + WebKit.
- **D** — the deployed-integrity verifier (`tools/verify_deployment.py`): **GREEN** against the live
  API at the pinned SHA (0 failures across 17 raw ×2 transport paths + 4 composed + 10
  negative-space), wired into CI with the Fly machine-count==1 assertion.

## The one nuance to understand (not a bug)

The committed gate evidence (`docs/reports/sprint10_stage_d_verification.json`) is **GREEN**:
deployed == main HEAD == `1eeb176`, zero failures. But committing that evidence advanced `main` by
one **docs-only** commit (`15263f7`) that is **not in the image** — so a *scheduled* verifier run now
reads the live deploy as **stale-by-one** (a benign `WARNING`, never `RED`; the byte-integrity proof
is unaffected — the SHA pin is exactly what distinguishes "old deploy" from "drift"). An evidence
commit can't be its own ancestor; this is inherent. To get the scheduled verifier `GREEN`-at-rest,
one no-op `fly deploy --build-arg GIT_SHA=$(git rev-parse HEAD)` at the current HEAD does it.

## Open threads (priority order; none blocking)

1. **OPTIONAL [Human]:** redeploy the API at the current HEAD for scheduled-verifier GREEN-at-rest
   (above). Guard-verified no-op for artifacts.
2. **OPTIONAL [Human], per the Gate A amendment:** the `api.aether.arkaneworks.co` subdomain —
   **pending a LIVE check of Fly's current custom-domain certificate pricing** (never asserted from
   memory). The API stays on its `fly.dev` hostname until then.
3. **PORTFOLIO PACKAGE — NOW IN PROGRESS as Sprint 11** (`docs/tasks/sprint11_portfolio.md`): the
   README, the scientific validation write-up, and the source-of-truth key-results snippet
   (`docs/key_results.json` + `tools/build_key_results.py`) are done at the Stage B gate; the
   arkaneworks case-study page (revamp `ape.html` in place) is Stage C. Demo video + outreach remain
   separately scheduled.
4. **DEFERRED OPEN-THREAD — automated visual-fidelity verification harness** (recorded Sprint 11
   Stage B): an *automated* computed-style assertion or visual-diff baseline for the dashboard's
   inspector blocks, so an unthemed/unstyled block fails **RED** in CI without a human eye. **Distinct
   from** the completed Sprint 10 Stage C manual shot-list-criterion fix (a one-time human-eye fix, not
   a guard). The intent had been carried only in the reviewer's head and was never recorded until now.
5. **Deferred physics** for the 1.46×-vs-1.66× residual (a hypothesis: effective-layer/flat-continuum)
   — layered background, H₂O/SZA LUT, per-pixel sensitivity, RFM cross-check. See `docs/debt.md`.

`FLY_API_TOKEN` exists (the human created it at closeout) — the CI machine-count assertion is now
active. No secret is ever held by an agent.

## Deployment cardinal rules (still in force — `docs/tasks/sprint10_deployment.md`)

- The deployed app serves **committed artifacts only** — no runtime fetching, no credentialed access.
- **No secrets** in the repo, image, or build logs — ever. Account creation + secret values are
  **[Human]**; configs reference env vars, never their values.
- **Public means licensed-for-public** — NOAA ISD raw is non-redistributable (WMO Res. 40) and is
  provably absent (the verifier's negative-space checks enforce this live).
- **No fake liveness** — the footer shows the real deployed SHA + the honest data-coverage line; no
  "LIVE" theater.

## Relevant file paths (Sprint 10)

- **Task brief / gates:** `docs/tasks/sprint10_deployment.md` (+ Gate A amendment at the end).
- **Gate reports:** `docs/reports/sprint10_stage_{a_probe,a_gate,b_report,b_gate,c_report,c_fix,d_report}.md`;
  evidence `docs/reports/sprint10_stage_d_verification.json`; shots under
  `docs/reports/screenshots/sprint10_stage_c{,_fix}/`.
- **The verifier:** `tools/verify_deployment.py` (+ `tools/tests/test_verify_deployment.py`).
- **Integrity manifest:** `artifacts.manifest.json` (generator `scripts/build_artifact_manifest.py`,
  logic `apps/api/aether_api/manifest.py`, staleness guard `apps/api/tests/test_artifact_manifest.py`).
- **API hardening:** `apps/api/aether_api/{main,config,loaders}.py`;
  guards `apps/api/tests/test_deploy_guards.py`; live/image guards `test_container_live.py`,
  `test_image_inventory.py` (env-gated). Image-inventory tool `tools/verify_image_inventory.py`.
- **Container / deploy:** `Dockerfile`, `.dockerignore`, `fly.toml`, `.env.example`,
  `docs/deployment.md` (env schema + failure semantics + the executed runbook).
- **CI:** `.github/workflows/ci.yml` (tests/lint/build) + `verify-deployment.yml` (post-deploy guard).
- **Web:** `apps/web/src/components/Dashboard.tsx` (footer BUILD chip + attribution),
  `apps/web/src/app/globals.css` (the `.hypo-*` factor-card fix), `apps/web/src/lib/api.ts`.

## Environment notes (no secrets)

- `uv` workspace, Python 3.12 pinned. Frontend: `pnpm` in `apps/web` (`tsc --noEmit` + `next build`).
- The verifier reads the repo **at the deployed SHA** — it needs that SHA in local history (CI uses
  `fetch-depth: 0`). It needs no Fly token; only the machine-count CI step uses `FLY_API_TOKEN`.
- Caches in `~/.aether_cache/` (gitignored). NASA Earthdata auth via `~/.netrc` (never print it).
  Never commit raw data (`.tif`/`.zarr`/`.nc`/large `.npz`) — gitignored, and the Dockerfile's
  `.dockerignore` mirrors that so they cannot leak into the image.
- **Watcher hygiene:** any poller/watcher shell must be timeout-bounded, use a non-self-matching
  pgrep pattern, and be cleaned up at stage end.
