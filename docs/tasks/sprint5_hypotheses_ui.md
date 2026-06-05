# Task: Sprint 5 — Hypotheses in the Inspector (render the attribution engine)

**Owner:** Claude Code
**Reviewer:** chat Claude (honesty/design) + human
**Scope:** Surface the committed Sprint 4 attribution output (`hypotheses.json`) in the dashboard inspector as a **Source Attribution** section. This makes the differentiator showable. It is a *rendering* sprint: read and present the committed artifact. **No new computation, no new science, no LLM, no changes to the engine or its artifacts.** One event (Goturdepe).

## The cardinal rule for this sprint

The honesty already lives in the committed `hypotheses.json`. The only way this sprint fails is if the rendering **degrades** that honesty — a clean card UI that drops, detaches, or softens the caveats. Therefore:

1. **Every caveat renders, bound to the thing it qualifies.** The flaring evidence item's `temporal_caveat` (postdates the plume ~9 months, "NOT the located source") MUST render inline with that evidence item, visually distinct, never detached or omitted. If an evidence item has a `temporal_caveat`, the UI cannot show the evidence without showing the caveat.
2. **The confidence cap is visible, not collapsed.** H1 is MODERATE *capped from a high raw band* because facility-level attribution is impossible. The tier badge must communicate the cap (e.g. "MODERATE · capped") and the `confidence_rationale` must be reachable/visible — not hidden behind a clean badge that implies un-capped moderate confidence.
3. **The headline data-gap finding is a first-class element.** `headline_finding` (OGIM has no point infrastructure in Turkmenistan → attribution capped at field/sector level) renders as a prominent banner above the hypothesis cards — the same first-class treatment the scope caveat gets. It is the differentiating result, presented as a result, not an apology or a footnote.
4. **The scoring disclaimer is visible.** `scoring_disclaimer` ("documented heuristic, NOT calibrated probabilities") renders wherever scores appear. Scores must never be presented as probabilities or percentages.
5. **The UI renders the artifact's own strings; it does not author interpretation.** Claims, rationales, evidence statements, assumptions, counter-considerations, falsification text all come verbatim (or trivially formatted) from the committed JSON. The UI may add section labels and layout chrome, but it must NOT paraphrase, summarize, or "improve" the engine's language in any way that could change meaning or soften a caveat. No new interpretive prose.
6. **Nothing rendered that isn't in the artifact.** Same no-fabrication discipline as the engine: if a field is absent, show nothing, not a plausible default.

## Backend (apps/api)

- New endpoint `GET /api/events/{event_id}/hypotheses` — returns the committed `hypotheses.json` for the event, validated through a Pydantic model that mirrors the artifact structure (reuse/extend the `Hypothesis` ontology type where it fits). Source every value from the committed file; hardcode nothing.
- For events without an attribution artifact (Permian — pending), return an honest empty/absent state (e.g. 404 or `{ "hypotheses": null, "status": "pending" }`), NOT fabricated hypotheses.
- Endpoint test asserting the API response equals the committed `hypotheses.json` (same pattern as the existing endpoint tests that assert API JSON == source files), plus a guard that the API adds no fields not present in the artifact.

## Frontend (apps/web)

Add a **SOURCE ATTRIBUTION** section to the inspector, consuming `/api/events/{id}/hypotheses`, in the locked Tactical/Division aesthetic (Chakra Petch labels, IBM Plex Mono data, amber/cyan duotone, consistent with existing panels).

Layout guidance (you may refine, screenshot for review):
- A first-class **headline-finding banner** at the top of the section (distinct from the red "Scope · Read Before Citing" block — this is a *coverage-ceiling* statement, suggest a non-alarm treatment, e.g. cyan/neutral, but visually prominent).
- **Ranked hypothesis cards** (H1, H2, H3), collapsed by default showing: rank, candidate descriptor, confidence tier badge (with cap indicated for H1), and the one-line `claim`. The section is getting long — collapsed-by-default keeps the inspector navigable; consider whether the inspector needs a MEASUREMENT / ATTRIBUTION sub-toggle if it becomes too tall (optional, your call, screenshot it).
- **Expanded card** reveals: the transparent `score_components` (component name, value, weight, contribution, rationale — render as small bars or rows showing the weighting honestly), the `evidence` items (each with its `statement`, its `source` dataset/locator, and — flagged inline and visually distinct — any `temporal_caveat`), the `assumptions`, `counter_considerations`, and `falsification`. This expansion IS the "show the evidence behind this" affordance.
- The `scoring_disclaimer` visible wherever scores show.

## Out of scope (do NOT build)

- No new computation, science, or LLM. Render the committed artifact only.
- No changes to `hypotheses.json`, the engine, or any Stage A/B output.
- No second event; no multi-event comparison.
- No editing/interaction beyond expand/collapse and the existing inspector controls.
- Do not rework the existing quantification/uncertainty/validation panels (they passed review) beyond what's needed to slot the new section in.

## Definition of done

- `/api/events/{id}/hypotheses` serves the committed artifact, validated, nothing hardcoded; Permian returns an honest pending/absent state.
- Inspector renders the SOURCE ATTRIBUTION section: headline-finding banner, three ranked cards, expandable to full evidence/assumptions/components/counter-considerations/falsification.
- All six honesty constraints hold — verified specifically: the flaring `temporal_caveat` renders inline with its evidence; H1's cap is visible with rationale; the headline finding is a prominent banner; the scoring disclaimer shows; rendered text is the artifact's own strings; nothing absent is invented.
- Backend test (API == artifact) + frontend builds clean + tsc passes.
- Aesthetic consistent with the locked design.
- Commit at each step. Report, then STOP for review — I will check (via screenshot) that the caveats survived the rendering before we call it closed.

## Build order

1. Backend endpoint + Pydantic model + test (API == committed artifact). 
2. Frontend: headline-finding banner + collapsed ranked cards wired to the endpoint.
3. Card expansion: score components, evidence (with inline temporal caveats), assumptions, counter-considerations, falsification.
4. Verify the six honesty constraints against the rendered UI; build + tsc + tests; commit; report with a screenshot of an expanded H1 (so the flaring caveat and the cap are visible).

The review will not be "does it render" — it will be "did every caveat survive." Build it so the flaring temporal caveat, the H1 cap rationale, the H3 honesty admission, and the data-gap headline are all impossible to miss in the rendered UI.
