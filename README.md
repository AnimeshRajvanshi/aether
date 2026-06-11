# Aether Planetary Engine

[![CI](https://github.com/AnimeshRajvanshi/aether/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AnimeshRajvanshi/aether/actions/workflows/ci.yml)

AI-native dashboard and analysis engine for orbital and planetary monitoring data.

**Status:** Sprints 1–7 complete (end-to-end methane wedge on two real EMIT events —
detection, quantification, attribution, dashboard); Sprint 8 (verification
infrastructure) in progress. See `PROJECT_STATUS.md` for the verified current state.

## Verification scoreboard

`uv run aether-eval run` executes the **real pipeline** (per-granule HITRAN k →
matched filter → orthorectification → plume mask → IME → Q) end-to-end from cached
inputs and scores it with honest semantics (ADR 0002,
[`docs/science/eval_semantics.md`](docs/science/eval_semantics.md)). Last local run
2026-06-11, exit 0:

| Event | Status | Detection recall | Regression vs committed artifacts | Quantification vs external flux |
|---|---|---|---|---|
| Aliso Canyon 2015 | `not_runnable` — no EMIT coverage (event predates EMIT's July 2022 launch) | — | — | — |
| Goturdepe 2022-08-15 | ran | recalled (30.2 km, field-scale reference) | 5/5 green (Q ±1%, Pearson ±0.01, centroid ≤0.5 km) | `not_comparable(scope_mismatch)` — Thorpe 163±18 is a 12-source cluster total |
| Permian 2022-08-26 | ran | recalled (1.0 km) | 5/5 green | `not_comparable(context_only)` — 18.3 t/hr is press-release context |

**Detection recall 2/2 (runnable events); regression 10/10 green; no
quantification MAPE is claimable** — both external flux references are unusable
as targets by our own validation rulings, and the harness reports the reason
instead of fabricating a number. The full run needs the local granule cache +
ARCO-ERA5 network and is network-gated; CI runs the harness logic + regression
assertions (see the eval-semantics doc for the split). No event holds the
reserved VALIDATED tier (`docs/science/validation_tiers.md`).

## What this is

Aether ingests hyperspectral, thermal, atmospheric, oceanographic, and orbital-object data across planetary bodies, unifies it through a single ontology, and lets a user go from raw observation to a defensible, contextualized brief in minutes.

Earth-climate is the wedge. The platform is the ambition.

For the full product specification, see [`docs/aether_spec.md`](docs/aether_spec.md).

## Repository layout

```
aether/
├── apps/
│   ├── api/             FastAPI service
│   └── web/             Next.js + Deck.gl + Cesium frontend
├── packages/
│   ├── ontology/        Pydantic models for the planetary ontology  ← Sprint 1
│   ├── data_spine/      Ingestion, STAC catalog, COG/Zarr access
│   ├── detection/       Matched-filter, IME quantification, thermal
│   ├── causal/          Hypothesis surfacing engine
│   ├── ai/              Claude/Grok orchestration, prompts, tools
│   └── shared/          Common utilities, geometry, units
├── eval/                Benchmark events, null cases, harness, metrics
├── notebooks/           Exploration, validation, case studies
├── infra/               Deployment, IaC
├── prompts/             Versioned prompt files
└── docs/
    ├── adr/             Architectural Decision Records
    └── science/         Method notes, validation writeups
```

## Getting started

See [`SETUP.md`](SETUP.md) for first-time setup on macOS.

## License

TBD. Currently private.
