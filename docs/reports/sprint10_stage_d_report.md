# Sprint 10 — Stage D: Deployed-integrity verifier (gate report)

**Date:** 2026-06-15 · **Status:** COMPLETE at gate — verifier built, unit-tested, CI-wired, run
against the live deployment. **STOP** for review.

## The verifier — `tools/verify_deployment.py`

Given a live base URL, it proves the deployed API serves byte-identical committed artifacts **at the
SHA it reports** — never HEAD. The pin is the guard's validity.

| Brief requirement | Implementation |
|---|---|
| (a) deployed SHA from `/api/version` | parsed + validated as 40-hex; a non-SHA aborts the run |
| (b) read the repo **at that SHA**, never HEAD | every committed source + the manifest read via `git show <sha>:<path>`; if the SHA is absent from local history → RED (unverifiable pin), never a silent HEAD fallback |
| (c) raw endpoints, transport-decoded SHA-256 vs manifest, two paths | each of the 17 raw endpoints fetched twice — default (server may gzip/br; httpx decodes) **and** `Accept-Encoding: identity` — both hashed against the manifest at the pinned SHA; mismatch is RED with the **first differing byte offset + hex windows** |
| (d) composed endpoints deep-equal vs committed sources at the pinned SHA | the pinned tree is extracted (`git archive <sha>`) and its **own** code is run (PYTHONPATH-imported, asserted to load from the extract — proven, not assumed) over the pinned data to reconstruct the expected payload; live JSON deep-equals it, RED carries the exact divergent key path |
| (e) negative space 404 | 10 audit-excluded paths — NOAA ISD raw (WMO Res. 40), the route-unreachable `_nasa_k` siblings, composed-source files, non-whitelisted event/layer — must 404; a 200 is a RED `negative_space_leak` |

No tolerance windows, no "close enough" hashing, no skipped endpoints. The transport-decoded
comparison plus the `identity` second path together prove Fly's compression proxy is legitimate
transport (decoded body unchanged), not a content transformation.

## Failure semantics (also in `docs/deployment.md`)

- **GREEN** — pinned SHA == main HEAD and every check passes; exit 0.
- **WARNING** — every integrity check passes but the deploy is not main HEAD: *stale* (pinned SHA is
  an ancestor of HEAD) or *diverged*. Internally consistent; **not a drift**; exit 0 + `::warning::`.
- **RED** — any raw byte mismatch (real platform transformation / deploy drift), composed
  deep-equality failure, negative-space leak, or unverifiable pin; exit 1.

**The SHA pin is what separates WARNING from RED.** A stale deploy passes every byte check because
it is checked against *its own* SHA's manifest — so "old deploy" surfaces as a warning, while "serves
bytes that differ from what that SHA committed" is red. `--strict` makes WARNING fail too.

## Unit tests — the RED paths proven without breaking the live deploy

`tools/tests/test_verify_deployment.py` (14 tests, run in the normal pytest job):
- `classify()` — GREEN, WARNING (stale), WARNING (diverged), RED (failure outranks staleness).
- `_first_diff()` / `_json_diff()` — the byte-offset and key-path detail a RED carries.
- `verify_raw()` — serving the committed bytes at HEAD via `httpx.MockTransport` passes; **flipping a
  single byte mid-file is caught** as `raw_byte_mismatch` with the exact offset.
- `verify_negative_space()` — a single leaked (200) audit-excluded path is caught.

## CI wiring — `.github/workflows/verify-deployment.yml`

Scheduled (daily) + manual dispatch; `fetch-depth: 0` (the deployed SHA is usually an ancestor of
HEAD). Two assertions:
1. **Fly machine count == 1** — the Stage C auto-HA re-add finding, machine-checked via `fly machines
   list --json` (needs `FLY_API_TOKEN`; if absent, the step emits a notice and skips — the verifier
   itself needs no token and still runs).
2. **The verifier** against production — RED fails the job, WARNING annotates and passes, GREEN
   passes. The JSON report is uploaded as an artifact.

Chain it after an automated deploy job once the human creates `FLY_API_TOKEN` (the deploy job is the
[Human] step enumerated in `docs/deployment.md`; not created here).

## Gate evidence — live run (committed: `sprint10_stage_d_verification.json`)

```
base_url   : https://aether-api-arkaneworks.fly.dev
pinned SHA : c960cfdb7dfcd7249c83b7f000bd3d4e0221cd69
main HEAD  : c1e900703fcc0f61e967774ce617f12f84acd988
checked    : 17 raw (x2 transport paths) + 4 composed + 10 negative-space
RESULT     : WARNING   (failures: 0)
reason     : Deploy is internally consistent at c960cfdb7dfc but STALE: it is an ancestor of
             main HEAD c1e900703fcc. Redeploy to advance; not a drift.
```

**Integrity is GREEN — zero failures across all 31 checks.** The overall WARNING is *only* the
staleness signal: the Stage C UI fix advanced `main` (Vercel redeployed the web) while the Fly API
stayed at its prior SHA `c960cfd`. This is the failure-semantics distinction doing its job — the
verifier neither false-GREENs a stale deploy nor false-REDs it as drift. It clears the moment the
API is next deployed (the first automated deploy after the human creates `FLY_API_TOKEN`, or a
manual `fly deploy --build-arg GIT_SHA=$(git rev-parse HEAD)` — a guard-verified no-op for
artifacts, since the API Python is byte-identical between `c960cfd` and HEAD).

> The committed evidence JSON is a point-in-time run captured before the Stage D commit; its
> `head_sha` is the pre-Stage-D HEAD. The relationship it records (deployed SHA is an ancestor of
> main; 0 integrity failures) is the gate fact.

## Verification

- `uv run pytest` — **388 passed, 6 skipped, 7 deselected** (the 6 skips are the env-gated live
  guards; the 14 new verifier tests are in the count). `ruff` clean; `mypy` clean on the verifier.
- The deselected count is unchanged (7) — the new tests are not integration-marked, so the CI
  deselection assertion still holds.

## STOP — Stage D gate

The deployed-integrity verifier is built, unit-tested (incl. the RED byte-mismatch path), CI-wired
with the machine-count assertion, its failure semantics documented, and run against the live
deployment with the output committed as evidence. This is the final stage; the sprint's definition
of done is met (a public URL serving all three events, committed Stage A probe + license audit with
ISD raw provably absent, read-only/CORS/config guards, secrets nowhere, deployed SHA in the UI and
`/api/version`, the integrity manifest committed and staleness-guarded, and the deployed-integrity
verifier green-on-integrity against the live URL at the pinned SHA, wired into CI).
