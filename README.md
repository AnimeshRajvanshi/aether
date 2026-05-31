# Aether Planetary Engine

AI-native dashboard and analysis engine for orbital and planetary monitoring data.

**Status:** Pre-MVP. Sprint 1 in progress.

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
