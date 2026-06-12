# Task: Sprint 10 — Deployment (the hosted URL)

**Owner:** Claude Code
**Reviewer:** chat Claude + human
**Scope:** Take the existing, finished application — FastAPI API + Next.js/Cesium web + committed artifacts for three events — and put it on a public URL with the same honesty guarantees it has locally. Four gated stages, probe-first, same rules as Sprints 7–9. **No new science, no new events, no new features.** This sprint is infrastructure: hardening, packaging, deploying, and proving the deployed thing is the committed thing.

**Precondition:** main is green in CI (Sprint 9 closeout pushed and Actions passing). If main is not green, STOP immediately and report — nothing in this brief runs against a red main.

## Why this sprint

Localhost is not a portfolio, and deployment is product work disguised as portfolio work: it forces the CORS/config/asset-serving hardening the product needs anyway, and it gets harder with every feature added to an undeployed app. But deployment also inverts the project's threat model. Every guard so far defends against fabrication and drift *inside the repo*. A hosted URL introduces a new failure surface *outside* it: build pipelines that transform assets, proxies that rewrite responses, environment drift between the deployed image and the committed tree, and — most important — the act of making public things that were only licensed for local use. The deliverable of this sprint is therefore not just a URL; it is a URL plus a machine-checked proof that what the URL serves is byte-identical to what the repo committed, plus a committed license audit of everything the URL exposes.

## Cardinal rules (additions for this sprint — the standing four still apply)

1. **The deployed app serves committed artifacts only.** No runtime data fetching, no live retrieval, no credentialed access to NASA/NOAA/anything from the deployed environment. If an endpoint cannot be served from the committed tree, it does not deploy.
2. **No secrets in the repo, the image, or the build logs — ever.** All credentials and account creation are the human's job, marked **[Human]** in your reports. You prepare configs that *reference* env vars; you never possess or write their values. If you find any secret-shaped string in the tree or in a build artifact, STOP and report it as a finding.
3. **Public means licensed-for-public.** Every artifact the deployed API can serve must pass a license audit (Stage A). The NOAA ISD raw station data is non-redistributable verbatim (WMO Res. 40) and must be *provably absent* from the deployed artifact set — verified by the audit, not assumed. Derived statistics are fine per the Sprint 9 probe decision. Imagery provider terms (ESRI World Imagery attribution requirements; Cesium ion token terms if used) are part of the audit.
4. **No fake liveness.** The deployed UI gets a footer/HUD line with the deployed git SHA (short) and the honest data-coverage statement that already exists. No "LIVE" indicators, no uptime theater, no invented status. The same rule that killed the LIVE dot in Sprint 3 applies to the hosted version.

## STAGE A — Deployment probe (report, then STOP)

Probe first; deploy nothing. Produce a committed probe report (`docs/reports/sprint10_stage_a_probe.md`) covering:

1. **Deployed artifact inventory + license audit.** Enumerate every file the API can serve and every static asset the web build ships (walk the actual route table and the actual build output, not the docs). For each: size, source dataset, license, redistribution status. Hard checks: (a) zero NOAA ISD raw files reachable; (b) zero `.netrc`/Earthdata-credentialed paths required at runtime; (c) total served-artifact size (this bounds the image size and host choice). Report any artifact whose license is unclear as a finding for human review — do not silently include or exclude it.
2. **Secrets inventory.** Everything the deployed system could conceivably need: Cesium ion token (currently optional — token-free ESRI default), API base URL, anything else found in `.env.example`/config. For each: is it required, is it public-by-design (e.g., a client-side imagery token is visible in the browser regardless — say so explicitly), where it will live (platform env var). Confirm the repo's gitignore actually covers every local env file pattern in use.
3. **Hosting candidates, verified not remembered.** Default architecture under evaluation: **web on Vercel, API as a Docker container on Fly.io or Render.** For each candidate, verify *current* terms via their live documentation (WebFetch): free/cheapest-tier pricing, idle/sleep behavior and measured-or-documented cold-start time, image size limits, region options, whether the platform applies any response transformation (asset optimization, minification, proxy rewriting) and how to disable it. Cold starts are a first-class finding: a demo that takes 30+ seconds to wake is a broken demo, and the human decides at this gate whether to pay for always-on.
4. **Byte-identity feasibility scan.** Identify every API endpoint and classify it: (a) raw-artifact endpoints that can stream committed file bytes unmodified, vs (b) composed endpoints that re-serialize (JSON key order/whitespace will differ from any single source file by construction). The deployed-integrity guard (Stage D) will hold class (a) to byte-identity and class (b) to deep-equality against the pinned commit. Report any endpoint that currently *re-serializes a single committed JSON file* — those should move to raw streaming in Stage B so byte-identity covers them.
5. **CI deploy-hook feasibility.** Can the chosen hosts deploy from a GitHub Actions job (deploy hooks / CLI with a platform token held as a GitHub secret)? The human will create those tokens; you verify the mechanism exists and document the exact steps the human will perform.

**Stop for review.** The human chooses hosts and pays-or-doesn't at this gate; nothing is provisioned before that decision.

## STAGE B — Hardening, pre-deploy (report, then STOP)

All local; no accounts touched. Everything here lands with tests/guards and must keep the full suite green.

1. **Read-only enforcement.** The API is a read-only artifact server. Enforce it structurally: only GET/HEAD/OPTIONS routes exist; add a guard test that walks the live route table and fails if any mutating method appears. This is the cheapest hardening with the highest value and it should be machine-checked, not a convention.
2. **CORS, explicit and tight.** Allowed origins from an env var: the production web origin plus localhost dev origins. No `*`, no regex wildcards. Guard test: app configured with production env rejects a foreign origin.
3. **Config via environment, with honest failure.** All deploy-varying config (allowed origins, public API base URL for the web app, optional ion token) through env vars with a single documented schema (`docs/deployment.md` + `.env.example` updated). Missing required config fails loudly at startup with a clear message — never a silent default that "works" wrong.
4. **Raw streaming for single-file endpoints.** Per the Stage A scan: every endpoint whose payload is one committed file serves it as raw bytes (FileResponse/equivalent), preserving byte-identity through the stack. Composed endpoints keep their existing equality-to-source tests.
5. **Version + health endpoints.** `/api/version` returns the git SHA baked at build time (build arg → env, never a runtime `git` call) plus the app version; `/api/health` returns a minimal liveness body. The web footer renders the SHA from `/api/version` — fetched, not hardcoded.
6. **Integrity manifest + local guard.** A script generates `artifacts.manifest.json`: SHA-256 of every served committed artifact, keyed by serving path, stamped with the generating commit. The manifest is committed; a guard test regenerates it and fails on any diff (manifest staleness = the no-staleness rule applied to deployment). This manifest is the contract Stage D's live guard verifies against.
7. **Security headers + server posture.** Sensible header set on API responses (no-sniff, frame-deny; document what and why in `docs/deployment.md`); uvicorn production settings; FastAPI docs endpoints either disabled in production or consciously left on (state the decision and the reason — they're harmless for a read-only public API and arguably good portfolio transparency; make the case, human decides at the gate).
8. **Dockerfile for the API.** Multi-stage, pinned base, artifacts copied from the pinned checkout, git SHA as a build arg, no credentials at any layer, final image size reported. A local `docker run` must serve the full API with the suite's endpoint tests passing against the container.
9. **Web production build against a remote API.** `NEXT_PUBLIC_API_URL` wiring verified: production build pointed at the containerized API on a non-default port renders globe → all three events → inspector. Screenshot evidence per the standard shot list.

**Stop for review** with: diff stat, new guard inventory (each guard named, what it fails on), the Dockerfile, the manifest, image size, and the screenshots.

## STAGE C — Deploy (interactive; human-in-the-loop by design)

This stage is a choreography between you and the human; expect to pause for **[Human]** steps. Nothing in this stage is autonomous account work.

1. Produce a step-by-step runbook (`docs/deployment.md` final section): exact **[Human]** steps (account creation, token generation, env var entry into platform dashboards, GitHub secrets) and exact **[You]** steps (config files, deploy commands the human runs or platform-CLI invocations the human authorizes). Every secret value is entered by the human directly into the platform; none transit the repo or the chat.
2. Deploy the API container; deploy the web app; set CORS to the real web origin; verify `/api/version` returns the deployed SHA and the footer shows it.
3. Hosted smoke test, evidenced: globe loads, all three events (Goturdepe, Permian, NW India heat) fly-to and open their inspectors, toggles work, tier badges and caveats render — screenshots from the *hosted* URL per the standard shot list. The caveats surviving deployment is a gate check, not an assumption.
4. First-load performance note: report cold-start time actually observed and hosted first-paint time. If the free-tier sleep behavior makes the demo bad, that's a finding for the gate, with the always-on cost stated.

**Stop for review** with the URL, the runbook as executed, and the shot list.

## STAGE D — Deployed-integrity guard (the point of the sprint; report, then STOP)

The live API must provably serve byte-identical committed artifacts. Build the verifier and wire it into CI:

1. **The verifier** (`tools/verify_deployment.py` or equivalent): given the live base URL — (a) fetch `/api/version`, extract the deployed SHA; (b) check out / read the repo at *that* SHA (never `HEAD` — the pin is the guard's validity); (c) fetch every raw-artifact endpoint and compare SHA-256 of the **transport-decoded response body** against the manifest at the pinned SHA — gzip/br content-encoding is legitimate transport, so compare after decoding, and detect-and-fail on any platform-side transformation (length/hash mismatch after decoding = red, with the first differing bytes reported); (d) deep-equality check every composed endpoint against its committed sources at the pinned SHA; (e) verify the negative space: the NOAA ISD raw paths and any other audit-excluded artifacts return 404 from the live API.
2. **CI integration:** a post-deploy job (triggered on deploy completion or scheduled) runs the verifier against the production URL and goes red on any mismatch. The repo's main badge story becomes: tests green, guards green, *and the deployed instance is provably the committed one*.
3. **Failure semantics documented:** what a red verifier means (deploy drift, platform transformation, stale deploy vs new main — the SHA pin distinguishes the last case: a *stale-but-internally-consistent* deploy is a warning, a *byte mismatch at the pinned SHA* is red).
4. Run the verifier against the live deployment from Stage C; commit the run's output as the gate evidence.

**Stop for review.** I will read the verifier the way the Sprint 4/7C/9C gates were read — the guard's own honesty is the review target (no tolerance windows, no "close enough" hashing, no skipping endpoints).

## Out of scope

New events, new domains, new sensors. The chatbot. The portfolio package (README polish, video, outreach) — separately scheduled. Custom domain, analytics, auth, rate limiting beyond platform defaults, CDN tuning, uptime monitoring services. SDA. No LLM anywhere.

## Definition of done

A public URL serving the full globe → event → inspector experience for all three events, with: committed Stage A probe + license audit (ISD raw provably absent); read-only + CORS + config guards in the suite; secrets nowhere in repo/image/logs; deployed SHA visible in the UI and via `/api/version`; the integrity manifest committed and staleness-guarded; the deployed-integrity verifier green against the live URL at the pinned SHA, wired into CI; runbook committed; gate reports committed at every stage; full suite + CI green throughout; STOP at each gate.

## Build order

Stage A probe → STOP. Stage B hardening → STOP. Stage C deploy (human-in-the-loop) → STOP. Stage D verifier + CI → STOP, sprint close.
