# Aether Planetary Engine — Product Specification v0.1

*Internal working document. Not for external distribution.*

---

## 1. What Aether is

Aether is an AI-native dashboard and analysis engine for orbital and planetary monitoring data. It ingests hyperspectral, thermal, atmospheric, oceanographic, and orbital-object data across planetary bodies (Earth first, then Moon and Mars), unifies them through a single planetary ontology, and lets a user go from raw observation to a defensible, contextualized, publication-quality brief in minutes rather than days.

The product's identity, in one sentence: *the analysis surface for everything happening on or above a planetary body — what was observed, what it likely means, and why.*

Earth-climate is the wedge. The platform is the ambition.

---

## 2. The MVP wedge

The first thing Aether does end-to-end, exceptionally well, is **super-emitter event reconstruction**.

Given a date and a region, or a known event, Aether:

1. Pulls the relevant hyperspectral and thermal scenes from public archives
2. Detects and quantifies methane (and where possible CO₂) plumes with stated uncertainty
3. Populates the planetary ontology with the detected entities (plume, source candidate, observation, operator)
4. Surfaces a ranked set of contextual hypotheses about the event (who, what kind of facility, what conditions, what history)
5. Produces an interactive dashboard view and a one-page brief that a domain scientist would actually use

Every later capability — heat anomaly detection, ocean monitoring, orbital object tracking, Mars/Moon — extends the same primitives: scenes, detections, entities, hypotheses, briefs.

---

## 3. Success metrics

We pick three quantitative axes and benchmark them honestly against the best available open baseline (Carbon Mapper portal workflow, EE-based scripts, published TROPOMI workflows).

1. **Time from question to brief.** Target: a user goes from "what happened at this lat/lon on this date" to a defensible brief in under 5 minutes. Baseline: hours to days.
2. **Detection performance on a held-out benchmark.** Recall ≥ 0.85, precision ≥ 0.80 on a curated set of 20+ published events. Quantification within ±30% of published IME values.
3. **Hypothesis quality on case studies.** External domain-expert review of 5 case studies rates the top-ranked hypothesis as "plausible and well-supported" in ≥ 4 of 5.

These are gates, not aspirations. If we miss them, we do not ship.

---

## 4. The Aether Planetary Ontology

This is the most important architectural decision in the spec. Everything else hangs off it.

The ontology is a typed graph of entities with provenance and confidence on every edge. Core entity types (all carry a `planetary_body` field, default `earth`):

- **Observation** — a single scene or measurement from a sensor at a time and place
- **Detection** — something found in an observation (a plume, a thermal anomaly, an orbital object, a launch signature)
- **Phenomenon** — a temporally extended thing that detections belong to (an emission event, a heat wave, a fire, a satellite pass)
- **Entity** — a real-world object in the world (a facility, an operator, a satellite, a vessel, a city, a region)
- **Hypothesis** — a proposed explanation linking detections and entities, with evidence, assumptions, and a confidence score
- **Brief** — a narrative artifact summarizing a phenomenon and its hypotheses for human consumption

Every entity has: a stable ID, a planetary body, a spatial footprint, a temporal extent, a provenance chain back to raw data, and a confidence/uncertainty representation.

The ontology lives in a Postgres database with PostGIS for geometry, with optional graph queries via a thin layer. Pydantic models on the Python side, generated TypeScript types on the frontend.

---

## 5. System architecture

Five layers, each independently testable:

**Layer 1 — Data Spine.** Ingestion, normalization, and caching of public datasets. Cloud-optimized formats (COG, Zarr) throughout. STAC catalog interface. Pulls from EMIT, Sentinel-5P, Landsat 8/9, MODIS, ERA5, Carbon Mapper open data, Space-Track, CelesTrak, USGS, VIIRS. One uniform API regardless of source.

**Layer 2 — Detection & Quantification.** Sensor-specific algorithms producing Detections in the ontology. Matched-filter methane detection on EMIT, downscaled TROPOMI for regional context, thermal anomaly detection on Landsat/MODIS, plume quantification via IME with explicit assumptions. Every output writes uncertainty.

**Layer 3 — Causal Suggestion Engine.** Given a Phenomenon, surface ranked Hypotheses by combining (a) contextual layer joins (infrastructure databases, ERA5 winds, operator data, prior detections), (b) statistical scoring with explicit assumption flags, and (c) LLM-driven hypothesis generation grounded in retrieved evidence. Every hypothesis carries its evidence, its assumptions, and a sensitivity note.

**Layer 4 — AI Orchestration.** The conversational and agentic layer. Claude API + tool-use over the ontology and pipelines. Handles natural-language queries, decomposes them into pipeline calls, produces narrative briefs, runs the multi-agent causal debate, performs vision-based plume sanity checks, computes embeddings for similarity search ("plumes that look like this one").

**Layer 5 — Presentation.** The dashboard. Deck.gl + MapLibre for primary map, CesiumJS for the 3D and orbital views, Plotly for spectra and time series, a chat surface for conversational analysis, a brief generator that renders to web and PDF.

---

## 6. Data sources for MVP

Locked for MVP:

- **EMIT (NASA/JPL) L2B CH₄ enhancement and L1B radiance** — primary high-resolution methane detection
- **Sentinel-5P TROPOMI CH₄** — regional context and screening
- **Landsat 8/9 Surface Temperature (Collection 2 L2)** — facility-scale thermal context
- **ERA5 reanalysis** — wind fields for plume quantification and dispersion
- **Carbon Mapper public catalog** — ground-truth events for the benchmark set
- **Global Oil & Gas Infrastructure Database (Rystad/SkyTruth/public alternatives)** — operator and facility attribution

Deferred but architected for:

- MODIS LST, VIIRS active fire, sea surface temperature products, ocean color, AIS maritime, Space-Track TLEs, CelesTrak, USGS seismic, NOTAM feeds, PDS (Mars/Moon imagery and hyperspectral)

---

## 7. The Causal Suggestion Engine

Internally we call this the Causal Engine and we mean it. Externally — in any pitch, README, or demo narration — outputs are framed as *ranked hypotheses with evidence and assumptions*, never as "the cause is X." This is not just hedging; it is what scientists actually want and what survives peer review.

Mechanism for a single Phenomenon (e.g., a detected plume):

1. **Evidence retrieval.** Pull every contextual layer that intersects the phenomenon's spatiotemporal footprint: infrastructure within radius R, wind at altitude and time, prior detections at the location, operator history, regulatory filings if available.
2. **Hypothesis generation.** A constrained LLM call (Claude) generates a candidate set of explanations, each as a structured object: claim, supporting evidence IDs, required assumptions, suggested falsification.
3. **Scoring.** A deterministic scorer ranks hypotheses by evidence weight (number and quality of supporting observations), prior probability (base rates from training data), and assumption fragility (penalty for unverifiable assumptions).
4. **Adversarial pass.** A second LLM call plays skeptic, attempting to falsify each top hypothesis; the score adjusts.
5. **Brief generation.** The top N hypotheses with their evidence chains are passed to a narrative generator (also Claude) that writes the human-facing brief — with every claim cited back to specific observations and assumptions.

Every brief includes a "what would change my mind" section. Every hypothesis is reproducible: same inputs, same evidence, same ranking.

---

## 8. The dashboard

Three persistent surfaces, always linked:

- **Map.** Deck.gl + MapLibre. Layered: hyperspectral enhancement, thermal anomalies, infrastructure overlays, wind vectors, detection markers. Time slider. Click-to-inspect.
- **Inspector.** Whatever is selected on the map, fully expanded: spectra, time series, raw radiance access, evidence chain, related entities, related hypotheses.
- **Chat.** Conversational analysis. "Show me EMIT detections near Permian operators in the last 30 days over 500 kg/hr." "Why did this plume appear?" "Compare this event to the three nearest in space and time." The chat surface is not a chatbot bolted on — it is a primary interaction modality with full tool-use access to the platform.

A fourth surface, the Brief View, is generated on demand: a publication-quality one-pager that can be exported to PDF and shared.

Visual design target: dense without being cluttered, scientifically credible (not gamified), and beautiful enough that a screenshot in a job application stops the scroll. Reference aesthetic: Bloomberg Terminal × Google Earth × Stripe documentation.

---

## 9. AI integration patterns

Specific places AI lives, and what shape it takes:

- **Hypothesis generation and adversarial critique** — Claude with structured outputs (see §7).
- **Natural-language interface to the platform** — Claude with tool-use over a defined API surface (query ontology, run detection, fetch scene, compute statistic, generate brief).
- **Brief authoring** — Claude with evidence bundle as context, output constrained to cite back to evidence IDs.
- **Vision validation** — multimodal Claude (or comparable) given the false-color enhancement image to sanity-check whether a detection looks like a real plume vs. an artifact.
- **Similarity search** — embeddings over phenomenon descriptions and plume morphology features, for "find me events like this one."
- **Research synthesis** — for new data sources and methods, an agent loop using Grok DeepSearch for current literature + Claude for synthesis into design briefs.

All AI calls log their prompt, model, inputs, and outputs to a reproducibility ledger. Prompt versions are checked into the repo.

---

## 10. Evaluation harness

Built in week 1. Lives in `/eval`. Contains:

- **Benchmark events** — 20+ curated published plume events with known location, time, operator, and reported emission rate
- **Null cases** — 10+ regions/times with no known events, to measure false positive rate
- **Detection metrics** — recall, precision, quantification error vs. published values
- **Hypothesis metrics** — top-1 and top-3 accuracy against known attribution where available
- **Latency metrics** — end-to-end time from query to brief

Every PR runs the eval. Regressions block merge. This is the single most important habit for scientific defensibility.

---

## 11. Repository structure

```
aether/
├── apps/
│   ├── api/                 # FastAPI service
│   └── web/                 # Next.js + Deck.gl + Cesium frontend
├── packages/
│   ├── ontology/            # Pydantic models + generated TS types
│   ├── data_spine/          # Ingestion, STAC catalog, COG/Zarr access
│   ├── detection/           # Matched filter, IME quantification, thermal
│   ├── causal/              # Hypothesis surfacing engine
│   ├── ai/                  # Claude/Grok orchestration, prompts, tools
│   └── shared/              # Common utilities, geometry, units
├── eval/
│   ├── benchmark/           # Curated events
│   ├── nulls/               # Null cases
│   └── harness/             # Runner + metrics
├── notebooks/               # Exploration, validation, case studies
├── infra/                   # Deployment, IaC
├── prompts/                 # Versioned prompt files
└── docs/
    ├── adr/                 # Architectural decision records
    └── science/             # Method notes, validation writeups
```

Python 3.12, TypeScript 5, uv for Python deps, pnpm for JS, Postgres+PostGIS for storage, Modal or Fly.io for deployment, Vercel for the frontend.

---

## 12. Sprint 1 — what we build this week

Concrete, in order:

1. **Repo skeleton** with the structure in §11, CI, linting, type-checking, pre-commit hooks
2. **Ontology models v0.1** — Observation, Detection, Phenomenon, Entity, Hypothesis, Brief, with PostGIS geometry and provenance
3. **Eval harness skeleton** — runner that takes an event ID, runs the (empty for now) pipeline, computes metrics
4. **Benchmark seed** — 5 known Carbon Mapper events ingested into the eval set, with reported values
5. **EMIT ingestion proof-of-life** — given a granule ID, pull L2B CH₄ enhancement, load as xarray, write to local Zarr cache, render as a static map. Reproduce one published plume visually.

Pass/fail gate: by end of sprint 1, we can `aether reproduce <event_id>` and get the published plume on a map locally. If yes, we proceed to detection. If no, we stop and fix.

---

*End of v0.1. Expected to be torn apart.*
