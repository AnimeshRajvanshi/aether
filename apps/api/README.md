# aether-api — dashboard backend

A thin FastAPI service that reads the **committed Stage A/B outputs** and
benchmark events from disk and serves them as clean JSON + georeferenced rasters.
Every value it serves traces to a file — nothing is hardcoded (see
`aether_api/loaders.py` for the field-by-field mapping). This is the contract the
frontend (`apps/web`) consumes.

## Run

From the repo root (the uv workspace):

```bash
uv run uvicorn aether_api.main:app --reload --port 8000
```

Then visit http://localhost:8000/docs for the interactive OpenAPI UI.

`AETHER_DATA_ROOT` overrides where `stage_a_outputs/`, `stage_b_outputs/` and
`eval/benchmark/` are read from (defaults to the repo root).

## Endpoints

| Method | Path | Source files |
| --- | --- | --- |
| GET | `/api/events` | benchmark YAML + `q_estimate.json` (centroid, headline) |
| GET | `/api/events/{id}` | `q_estimate.json`, `stage_a_report.json`, benchmark YAML, `bounds.json` |
| GET | `/api/events/{id}/enhancement.png` | `assets/{id}/enhancement.png` (our retrieval, inferno) |
| GET | `/api/events/{id}/nasa.png` | NASA L2B on the same ortho grid |
| GET | `/api/events/{id}/diff.png` | ours − NASA (Δ toggle) |
| GET | `/api/events/{id}/bounds` | EPSG:4326 bounds + colormap window |
| GET | `/api/events/{id}/mask.geojson` | CC-1213 plume outline (lon/lat) |

`turkmenistan_goturdepe_2022_08_15` is `active` (full Stage B result).
`permian_basin_2022` is `pending` — its benchmark exists but Sprint 2 could not
quantify it (no granule-matched target spectrum), so the API returns
`quantification: null` and a `pending_reason`. **No fabricated numbers.**

## Raster assets

The PNG/GeoJSON/bounds the API serves live in
`aether_api/assets/<event_id>/` and are committed. They are derived from the
gitignored ortho `.npz` + NASA `.tif` by:

```bash
uv run python scripts/build_dashboard_assets.py
```

That script reconstructs the plume mask with Stage B's exact segmentation call
and asserts it equals the committed `q_estimate.json` (CC 1213, 68 382 px) before
writing — so the served outline is provably the quantified component.

## Tests

```bash
uv run pytest apps/api
```

The tests read the committed Stage A/B files directly and assert the API's JSON
equals them — the no-fabrication guarantee, enforced.
