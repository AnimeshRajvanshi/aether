# CLAUDE.md — Operating manual for the Aether Planetary Engine

You are working on **Aether**, an AI-native dashboard and analysis engine for orbital and planetary monitoring data. Read this file fully before doing anything. For deeper context, read `docs/aether_spec.md` and the ADRs in `docs/adr/`.

## What Aether is

Aether ingests hyperspectral, thermal, atmospheric, oceanographic, and orbital-object data across planetary bodies, unifies it through one typed ontology, and turns raw observation into defensible, contextualized briefs in minutes. Earth-climate emissions monitoring is the wedge; the platform is built for far more.

The MVP wedge is **super-emitter event reconstruction**: detect and quantify a methane plume, populate the ontology, surface ranked contextual hypotheses, render it on a dashboard, produce a one-page brief.

## Where we are

- **Sprint 1, items 1–4: DONE.** Ontology package (`packages/ontology`), eval harness (`eval/harness`), Aliso Canyon seed benchmark event. 54 tests passing.
- **Sprint 1, item 5: IN PROGRESS.** EMIT proof-of-life. See `docs/tasks/` for the active brief.
- The Sprint 1 gate: `aether reproduce <event_id>` renders a real methane plume on a map locally.

## Architecture (five layers, each independently testable)

1. **Data Spine** (`packages/data_spine`) — ingestion, normalization, caching of public datasets. COG/Zarr formats. STAC where possible.
2. **Detection & Quantification** (`packages/detection`) — sensor-specific algorithms producing `Detection`s with uncertainty.
3. **Causal Suggestion Engine** (`packages/causal`) — ranked `Hypothesis` objects with evidence, assumptions, falsification.
4. **AI Orchestration** (`packages/ai`) — Claude/Grok tool-use over the ontology; NL queries, brief generation, adversarial critique.
5. **Presentation** (`apps/web`, `apps/api`) — Deck.gl/MapLibre/Cesium dashboard + FastAPI backend.

Everything hangs off the **ontology** (`packages/ontology`). See ADR 0001. Do not invent parallel schemas — extend or compose the existing entities (`Observation`, `Detection`, `Phenomenon`, `Entity`, `Hypothesis`, `Brief`).

## Repo conventions

- **uv workspace.** Packages live in `packages/*`, apps in `apps/*`, the eval harness in `eval/harness`. Each is its own package with a `pyproject.toml`. Register new workspace members in the root `pyproject.toml` under `[tool.uv.workspace]`, `[tool.uv.sources]`, and (if it has tests) `[tool.pytest.ini_options] testpaths`.
- **Python 3.12** pinned (`>=3.12,<3.13`). Do not loosen this without a reason — the scientific stack (rasterio/GDAL, xarray) has the broadest wheel support here.
- **Never commit data.** Raw scenes, caches, `.tif`, `.zarr`, `.nc`, `.h5` are all gitignored. Caches go in `.aether_cache/`.
- **No `__init__.py` in `tests/` directories.** It causes pytest module-name collisions across parallel test dirs. Tests are discovered by rootdir.

## Code standards

- **Pydantic v2 for all data models**, with `model_config = ConfigDict(extra="forbid")`. Unknown fields must fail loudly.
- **Type hints everywhere.** `mypy` runs in strict mode.
- **Ruff** for linting and import sorting. Line length 100.
- **Mandatory provenance.** Every ontology entity carries `Provenance`. Reproducibility depends on it.
- **Uncertainty is structural.** Detections and measurements carry uncertainty; don't drop it.
- Prefer small, composable functions with docstrings that explain *why*, not just *what*.

## Testing discipline (non-negotiable)

- Run `uv run pytest` before declaring any task done. All tests must pass.
- Any change to `packages/detection` or `packages/causal` must also run the eval harness: `uv run aether-eval run`. Detection performance regressions are blockers.
- New behavior gets new tests. Bug fixes get a regression test that fails before the fix.
- When tests fail, fix the code or the test deliberately — never delete a test to make the suite pass.

## Scientific integrity (the thing that makes this defensible)

- **Never fabricate data, granule IDs, plume coordinates, emission rates, or citations.** If a real value is needed and not available, say so and leave a clearly-marked TODO. Fabricated ground truth destroys the meaning of the benchmark.
- **Every benchmark event needs a real reference** (peer-reviewed paper, official report, or authoritative dataset). The schema enforces this.
- **Hypotheses are never asserted as truth.** They are ranked candidates with explicit assumptions and a falsification path. Frame outputs accordingly.
- When unsure about a current product spec (e.g., an EMIT product short-name or variable), verify against authoritative documentation before hardcoding it. Note the source.

## Scope discipline

- MVP data sources are **locked**: EMIT, Sentinel-5P TROPOMI, Landsat 8/9 ST, ERA5, Carbon Mapper catalog, a global oil & gas infrastructure database. Do not add a seventh without explicit instruction.
- Ocean/marine, the 3D explorer, and SDA/orbital modules are deferred. The architecture supports them (`planetary_body` is first-class) but we do not build them in Sprint 1.

## Commits

- Small, focused commits with clear messages. Conventional style preferred (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`).
- Run the full test suite before committing.
- Never commit secrets, API tokens, or `.netrc`. They are gitignored; keep it that way.

## How to work a task

1. Read the active task brief in `docs/tasks/`.
2. Read the relevant ADR(s) and the section of `docs/aether_spec.md` it touches.
3. Plan the change. State assumptions you're making.
4. Implement with tests.
5. Run `uv run pytest` (and `aether-eval run` if detection/causal changed).
6. Summarize what you did, what you assumed, and what you'd flag for human review.
