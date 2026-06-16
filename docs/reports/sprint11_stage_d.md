# Sprint 11 — Stage D: integrated read-through (final gate)

**Verdict: PASS.** Read in the hiring-manager's order — case study (`arkaneworks.co/ape`) → live demo
(`aether.arkaneworks.co`) → README (public aether repo) → validation write-up. Every check below is
GREEN; one cosmetic note and one carried performance flag, neither blocking.

**State verified against:** aether `origin/main` = `ea7e8de` (PUBLIC + pushed; local == origin),
arkaneworks `origin/main` = `435f887` (the layout revision is what is live at `arkaneworks.co/ape`).

**Scope correction applied (per the gate instruction):** Aether is intentionally a **multi-body**
planetary dashboard (Earth/Moon/Mars tabs), currently Earth-populated, with the other bodies honestly
shown empty. This is **not** flagged as an overclaim. The honesty bar used here is: *nothing claims a
capability or result that does not exist.* `lunar.html` (the unrelated Moon-Presence / NASA-HeroX
program) was not touched and is not conflated with Aether.

## 1. Cross-deliverable figure consistency — GREEN (no drift)

Every figure that appears in more than one deliverable carries an **identical value**, and all trace to
`docs/key_results.json` (whose snippet↔artifact integrity is guarded by `tools/tests/test_key_results.py`).
Spot-matrix across all four deliverables (key_results / README / write-up / ape.html):

| Figure | Consistent across | 
|---|---|
| Goturdepe flux **23.4 t/hr** ours-cal, **16.0 t/hr** NASA-anchored | all four |
| Goturdepe Pearson **0.731**; k-shape **0.993** | all four |
| **+1.46×** systematic | all four |
| Permian **0.85 t/hr**, integrated mass **0.96×** | all four (README/ape give 0.96×; the 0.88 t/hr companion is in key_results + write-up) |
| Permian pixel **0.137** | key_results / write-up / ape (README states it qualitatively as "weak", no conflicting number) |
| Heat C1 **46.68 °C**, C2 **+5.67 K** | all four |
| C3 **26 d** / C4 **889,700 km²** | all four |
| UHI **−0.77 K** | all four |

No figure appears with two different values anywhere. **Cosmetic note (not drift):** the validation
write-up uses a thin-space thousands separator (`889 700`, `887 700`, `606 300`) where
`key_results.json` and `ape.html` use a comma (`889,700`). Same values; presentation style only.
Trivially alignable at the human's discretion; not a gate blocker.

## 2. No overclaim (corrected scope) — GREEN

Re-walked the Stage A claims ledger against the finished prose:

- **No capability/result claimed that does not exist.** The README explicitly **denies** the tempting
  overclaims ("It is **not** a real-time platform, not an 'AI-native' product…") and states the AI
  orchestration layer is **specified, not built**. The live demo shows **"0 ACTIVE · 0 PENDING"** and
  **"NO LIVE TELEMETRY · ALL VALUES FROM COMMITTED, REVIEWED ARTIFACTS"** — no fake liveness.
- **Multi-body is honest, not an overclaim.** The demo's Earth/Moon/Mars tabs render an unmistakable
  empty state for the non-Earth bodies — **"NO DATA · EARTH MVP"** — corroborated in source:
  `apps/web/src/components/Dashboard.tsx` (the `nodata-msg`), `globals.css` ("non-Earth empty state
  (Moon/Mars are deferred)"), and `CesiumGlobe.tsx` ("Earth = photoreal; Moon/Mars are honest
  placeholders (we have no data there — markers are hidden too)"). Multi-body architecture with
  Earth-only data, truthfully labelled, is the intended design and stays.
- **Tiers not exceeded.** Flux is CROSS-CHECKED (never VALIDATED); heat is per-quantity with VALIDATED
  only on C1/C2 and C3/C4 explicitly *not validated*. The case study and README carry these exactly.
- **No implied Carbon Mapper affiliation.** Both the README and `ape.html` state Aether is
  "complementary to / inspired by … **not affiliated with, endorsed by, or a replication of**" Carbon
  Mapper, with shared JPL spectrometer *heritage* (true) but no pipeline equivalence.

## 3. Caveats present in the persuasive copy (`ape.html`) — GREEN

All survive into the case study (grep-confirmed occurrences):

- Flux **CROSS-CHECKED, not VALIDATED** — present (5× "CROSS-CHECKED", 3× "not VALIDATED").
- The **+1.46×** systematic, **left uncorrected** and **non-transferring** — present.
- The **C3/C4 pre-registered failures** — present (5× FAILED/not-validated).
- The **two-lanes** air-vs-skin separation ("the dashboard never merges …") — present.
- The **attribution boundary** ("presence and rarity, not a quantified causal share"; counter-evidence;
  external attribution kept "outside the engine's own scores") — present.
- **Coverage/ceiling** limits (weaker cross-check, capped, the negative "cool island") — present.

## 4. Link integrity (logged-out viewer) — GREEN (no 404s)

Fetched each as an unauthenticated viewer:

| Link | Result |
|---|---|
| `https://arkaneworks.co/ape` | **200** — title "Aether Planetary Engine — Arkane Works"; figures 23.4 t/hr, 46.68, 1.46, 0.137 present; "Open the live demo" link present |
| `https://aether.arkaneworks.co` | **200** — "AETHER — PLANETARY ENGINE · v0.3"; earth/moon/mars tabs; "NO LIVE TELEMETRY · ALL VALUES FROM COMMITTED, REVIEWED ARTIFACTS" |
| `https://github.com/AnimeshRajvanshi/aether` | **200 (public)** — README rendered, "Aether Planetary Engine (A.P.E.)" |
| `…/blob/main/README.md` | **200** — first heading "Aether Planetary Engine (A.P.E.)"; demo link + 23.4 present |
| `…/blob/main/docs/science/sprint11_validation_writeup.md` | **200** — "Aether — the scientific validation story"; 0.993, 46.68 present |

No sign-in walls, no 404s. The case study correctly distinguishes `arkaneworks.co/ape` (this write-up)
from `aether.arkaneworks.co` (the live demo).

## 5. Site integrity — GREEN

Diffing the live site `435f887` against the pre-Aether baseline `135d2ec`, **the only changed paths are**
`ape.html`, `assets/aether/*.png` (5), and `docs/sprint11_stage_c_gate.md`. Confirmed byte-identical to
baseline:

- **`lunar.html`** — `shasum 8ca7667…` baseline == live (untouched; the unrelated Moon-Presence program).
- **`styles.css`** (`4639bb5a…`) and **`script.js`** (`258e8417…`) — baseline == live.
- **`CNAME`** = `arkaneworks.co` — unchanged. No other project page touched; the shared nav untouched.
- The `aether.arkaneworks.co` subdomain (Vercel) and apex/www config are separate infrastructure — no
  DNS/Vercel changes were made in this sprint.

## Carried, non-blocking

- **Cosmetic:** write-up thousands-separator style (thin space) differs from the comma style elsewhere —
  same values.
- **Performance flag (from the layout revision):** `assets/aether/preview-hero.png` is ~4 MB; as the
  full-bleed first-paint hero it loads slowly. Recommend a ~200–400 KB / JPG drop-in at the same path.

## Gate

**Stage D PASSES. Sprint 11 (the portfolio package) is ready to close.** All four deliverables are live,
public, cross-consistent, caveat-preserving, overclaim-free under the corrected multi-body scope, and the
website's other pages + DNS config are intact. STOP at the gate; the sprint-close handoff follows on
approval.
