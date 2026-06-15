# Task: Sprint 11 — The portfolio package

**Owner:** Claude Code
**Reviewer:** chat Claude + human
**Touches TWO repos:** `aether` (README + validation write-up + doc reconciliations) and `arkaneworks` (the case-study page; GitHub Pages, personal account, served at arkaneworks.co).
**Target reader (the one this must land with):** a Carbon Mapper-type hiring manager — a remote-sensing scientist who values quantification with honest uncertainty, source attribution, and transparency, and who will open the live dashboard and check whether the numbers are real.
**Three deliverables:** (1) `README.md` in the aether repo — the dev-facing front door; (2) a scientific validation write-up in the aether repo — the rigor story in depth; (3) a case-study page on arkaneworks.co/aether — the recruiter-facing narrative. **No CV work, no other portfolio pages, no new science.** Four gated stages, STOP at each, same discipline as Sprints 7–10.

**Precondition:** aether main is green in CI and in sync with origin (closed Sprint 10 state). If not, STOP and report.

## Why this sprint

Ten sprints built a methane+heat dashboard where every value traces to a committed artifact and the caveats survive to the screen. None of that rigor persuades anyone until it is *narrated* to the people it is meant to impress. This sprint is that narration — and it inverts the threat model one last time. Sprints 1–10 defended against fabrication in the *data*. This sprint must defend against fabrication in the *claims about the data*, which is harder because persuasive prose is the natural habitat of the overclaim. The temptation to write "real-time AI-powered methane monitoring platform" is enormous and every word of it would be a lie the dashboard itself refutes. A Carbon Mapper scientist who clicks from an overselling case study into an honest dashboard does not think "impressive" — they think "the copy oversold it," and on a project whose entire thesis is rigor, that is fatal. The no-fabrication rule does not relax for marketing copy. It tightens.

## Cardinal rules (additions for this sprint — the standing four still apply)

1. **Every factual claim traces to a committed artifact.** The Stage A claims ledger is the contract: a claim with no traceable source artifact is either cut or demoted to honest hedging. This is the no-fabrication rule applied to prose. Exactly as no value reaches the dashboard without provenance, no claim reaches the case study without it.
2. **Shipped is not aspirational.** The narrative NEVER presents the vision as delivered. "10×-better," "AI-native," "causal deduction engine," "planetary engine," "Space Domain Awareness," "exoplanet explorer," multi-body/Moon/Mars — none of these is shipped. What shipped: three events (Goturdepe, Permian, NW India heat), two phenomenon domains, a per-quantity validation rubric, a provenance-traceable pipeline, a deployed dashboard with a deployed-integrity guard. The vision may appear ONCE, late, explicitly labeled "where this is headed" / aspirational — never woven into the delivered-work narrative as if done.
3. **Caveats survive the narrative.** The flux is CROSS-CHECKED, not VALIDATED. The +1.46× is a reproduced systematic, not a solved problem. C3 (duration) and C4 (extent) FAILED their pre-registered criteria — that is a finding, not a thing to omit. Coverage is sparse where it is sparse. LST/UHI are capped at CROSS-CHECKED (no in-situ skin truth). These are not smoothed away for impact; for this audience they ARE the impact.
4. **Honest about the relationship to Carbon Mapper.** Aether uses public EMIT data; Carbon Mapper flies Tanager with proprietary JPL spectrometer heritage and publishes its own L1–L5 products. Aether is *complementary to / inspired by* that work — NOT a replication of their pipeline, NOT affiliated, NOT endorsed. "Carbon Mapper-style methane work" is an honest description of the problem domain; any implication of affiliation or of having reproduced their proprietary stack is not. State the lineage honestly (EMIT and the Tanager-class spectrometers share JPL imaging-spectrometer heritage — true and worth noting; equivalence of pipelines — false).
5. **Figures are sourced, not retyped — and the brief is not a source.** Do NOT copy any numeric figure from this brief or from the chat history into a deliverable. The brief author works from memory; memory is not a committed artifact. Every figure (flux Q, end-to-end Pearson r, the shape correlation, the +1.46×, the heat anomaly, the peak temperature, the tier outcomes, every date and DOI) is read fresh from the committed aether artifact it lives in, at a named SHA. Where a figure appears in more than one deliverable, it derives from ONE committed source-of-truth snippet (Stage B), not from independent retyping.

## STAGE A — Site probe + claims ledger (report, then STOP)

Two parts, both committed to `aether` `docs/reports/sprint11_stage_a.md`. Write nothing persuasive yet.

**Part 1 — arkaneworks.co site probe (so the page MATCHES the site, not the dashboard).**
Clone/read the `arkaneworks` repo. Report: how the site is built (Jekyll? plain HTML? a framework? — read it, do not assume); the design language (fonts, color system, layout grid, nav structure) as actual CSS/markup values, not impressions; how existing project pages and the *placeholder* Aether page are structured and routed (is arkaneworks.co/aether a `/aether/index.html`, an `aether.html`, a Jekyll collection item?); how it deploys (GitHub Pages branch/source); and the existing CNAME/Pages config (apex → GitHub Pages, `www` → the Pages site — already known from Sprint 10, re-confirm). The case-study page must adopt the SITE's design language for consistency with the other projects; the Aether dashboard's amber/cyan HUD aesthetic appears only inside the embedded screenshots. Flag any mismatch that would force a design decision at the gate.

**Part 2 — the claims ledger (the heart of the stage).**
Before any narrative, build a committed table: every factual claim that will appear in ANY of the three deliverables → the committed artifact it traces to → the exact figure/string as it appears there → its tier/caveat. Walk the actual artifacts; do not populate from memory or this brief. The ledger must explicitly partition:
- **SHIPPED & VALIDATED** — claims that hold at the strongest tier (e.g. the pre-registered heat C1/C2 under their committed-before-data criteria). State the criterion alongside.
- **SHIPPED & CROSS-CHECKED / weaker** — the methane flux, LST/UHI, anything capped below VALIDATED. The ledger records the ceiling and why.
- **HONEST NEGATIVES / FINDINGS** — C3/C4 failed; counter-evidence (F5 negative daytime UHI); the +1.46× systematic; sparse coverage; F1 CAPPED. These are claims TOO, and they ship.
- **CITED-EXTERNAL** — anything not computed by Aether (e.g. the published attribution multiplier), carried as a citation with DOI and an explicit "not computed by Aether" boundary.
- **ASPIRATIONAL (not claimed as delivered)** — the vision items, parked here so the writer can see exactly what must NOT migrate into the delivered-work narrative.

Any intended claim with no traceable artifact is reported as a finding for the gate: cut it, or demote it to honest hedging. **Report the as-of aether SHA** the ledger was built against.

**Stop for review.** The human + reviewer approve the ledger and the site-fit plan before a word of narrative is written. The ledger is the spec the next two stages are checked against.

## STAGE B — README + validation write-up + doc reconciliations (aether repo; report, then STOP)

Built before the case study because they are the source of truth it will summarize and link to. Everything here is aether-repo, where figures sit next to their artifacts.

1. **Source-of-truth key-results snippet.** A single committed artifact (e.g. `docs/key_results.json` or a generated fragment) extracting the headline figures from the validation artifacts — one place the README, the write-up, and (Stage C) the case study all draw from, stamped with the generating SHA. Prefer extraction over retyping; if a tiny script generates it, the script is committed and the snippet is regenerable. This is the cross-repo staleness defense, kept deterministic and minimal (a full cross-repo CI guard between arkaneworks and aether is explicitly OUT of scope — overkill for a static portfolio page; the snippet + SHA stamp + the Stage D consistency read is the proportionate control).

2. **README.md (dev-facing front door).** What Aether is, in honest one-paragraph terms; the live demo link (aether.arkaneworks.co) and what it serves (three events, two domains); the pipeline in brief (EMIT L1B/L2A/L2B → HITRAN2020/HAPI-derived independent target spectrum → saturation-aware retrieval → flux; the heat lane: MODIS LST / ERA5 / station + IMD air-temperature, two lanes never conflated); the architecture (FastAPI artifact server + Next.js/Cesium web + committed artifacts; the deployed-integrity verifier); how to run it locally and how to read the provenance; what is validated and what is not (the tier rubric, honestly); the data sources with licenses; citations (HITRAN, OGIM, the IMD/MAUSAM reference, etc.) with DOIs. Honest, reproducible, no marketing register. A technical reviewer who wants to verify the rigor lands here and finds it verifiable.

3. **Scientific validation write-up (the rigor story, in depth).** The differentiator for this audience. Sourced entirely from committed artifacts. Covers: the independent methane target spectrum (why HITRAN-derived rather than the per-granule NASA file; NASA repositioned as spectral-shape cross-check); the saturation-aware k derivation; the shape correlation and end-to-end fidelity figures with their exact definitions; the +1.46× systematic — found, independently reproduced, NOT corrected, with the honest interpretation of what it means for the flux; the per-quantity validation rubric and why event-level VALIDATED is deliberately reserved; the pre-registration discipline (criteria committed before station data was read) and the honest C3/C4 failures as the headline demonstration of method maturity; the two-lanes air-vs-skin separation; the factor-attribution boundary (diagnostics establish presence and rarity, not quantified causal contribution; counter-evidence reported; external attribution cited, not claimed). Uncertainty and coverage stated as findings.

4. **Doc reconciliations (housekeeping, this stage):**
   - Fix the stated test count to current (the 388→389 drift Claude Code flagged).
   - Add the **automated visual-fidelity verification harness** as a genuine deferred open-thread in HANDOFF.md/PROJECT_STATUS.md: computed-style assertions or a visual-diff baseline for inspector blocks, so an unthemed block fails red without a human eye — distinct from the completed Stage C manual-criterion fix. (This intent was carried only in the reviewer's head and never recorded; recording it is the correction.)

**Stop for review.** The reviewer reads the write-up the way the science gates were read — every figure checked against its artifact, every caveat present, no claim exceeding its tier.

## STAGE C — Case-study page on arkaneworks.co (arkaneworks repo; report, then STOP)

The recruiter narrative, built last, summarizing B and linking down to it. Adopts the SITE design language from the Stage A probe.

1. **Structure for the target reader:** the honest hook (rigor + traceability as the thesis) → the problem (methane super-emitter detection / heat attribution, why it's hard) → what was built (three events, the pipeline, the dashboard) → the rigor (pre-registration, the tier rubric, the honest failures, the deployed-integrity guard) → a clearly-demarcated, brief "where this is headed" horizon (the vision, labeled aspirational, NOT delivered) → links out. Lead with discipline; the vision is a footnote, not the headline (per cardinal rule 2).
2. **Figures** come from the Stage B source-of-truth snippet, stamped "as of aether `<SHA>`." No retyping.
3. **Screenshots** from the live dashboard (the themed, post-fix inspector — the three events, the tier table, the two-lanes block, the factor attribution with its counter-evidence and external-attribution boundary). The screenshots carry the dashboard's HUD aesthetic; the page around them carries the site's.
4. **Links, all verified live at Stage D:** the live demo (aether.arkaneworks.co), the GitHub repo, the README, the validation write-up. Distinguish clearly: arkaneworks.co/aether is the *case study*; aether.arkaneworks.co is the *live demo* — different things, the page links to the demo.
5. **Deploy** via the site's existing GitHub Pages mechanism (push to the Pages source → auto-build). The placeholder Aether page is replaced in the site's own page pattern (from Stage A). Apex/www/the aether subdomain are untouched.

**Stop for review** with the deployed page URL, the screenshots, and the figure-provenance note.

## STAGE D — Integrated read-through as the target reader (report, then STOP, sprint close)

Read all three deliverables in the order the hiring manager will: case study → click to live demo → click to README → click to validation write-up. Verify, and commit `docs/reports/sprint11_stage_d.md`:
1. **Cross-deliverable consistency:** every figure that appears in more than one place is identical and matches the Stage B snippet and its artifact. Any drift is RED (the cross-repo staleness this sprint was built to prevent).
2. **No overclaim slipped in:** re-walk the claims ledger against the finished prose — every claim still traces, no aspirational item migrated into the delivered narrative, no tier exceeded, no implied Carbon Mapper affiliation.
3. **Caveats present:** the flux ceiling, the +1.46×, the C3/C4 failures, the coverage limits, the lane separation, the attribution boundary — all survive into the persuasive copy.
4. **Link integrity:** every link resolves (demo loads, repo/README/write-up reachable); the demo still shows markers + BUILD chip (CORS origin still matched).
5. **Site integrity:** the new page matches the site design; other placeholders and the apex/www/subdomain config are untouched.

**Stop for review**, then the sprint-close handoff.

## Out of scope

CV edits (the Aether entry and the relevant hyperspectral-CubeSat prior art are a natural follow-on, separately scheduled). Other portfolio project pages. A video walkthrough (can be a later add; not this sprint). Any new science, event, domain, or dashboard feature. A cross-repo automated figure-integrity CI guard (rejected as disproportionate; the snippet + SHA stamp + Stage D read is the control). The optional API redeploy for scheduled-verifier GREEN-at-rest, the api.aether subdomain, residual physics — all remain their own deferred items, not touched here.

## Definition of done

A committed Stage A claims ledger partitioning shipped/validated, cross-checked, honest-negatives, cited-external, and aspirational, with every claim traced to an artifact at a named SHA. An honest, reproducible README and an in-depth validation write-up in the aether repo, every figure sourced from committed artifacts via the one source-of-truth snippet, doc reconciliations done. A live case-study page at arkaneworks.co/aether that leads with the discipline, demotes the vision to a labeled horizon, sources its figures from the snippet, links to the live demo + repo + README + write-up, and matches the site design. A Stage D integrated read confirming cross-deliverable consistency, zero overclaim, caveats surviving, links resolving, site integrity intact. Both repos' main green and in sync; STOP at every gate.

## Build order

Stage A probe + ledger → STOP. Stage B README + write-up + reconciliations → STOP. Stage C case-study page + deploy → STOP. Stage D integrated read → STOP, sprint close.
