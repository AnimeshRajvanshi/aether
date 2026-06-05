"""FastAPI app for the Aether dashboard.

Serves committed Stage A/B outputs as JSON + georeferenced rasters. Thin but
real: it sets the pattern for every future event. CORS is open to localhost so
``next dev`` (port 3000) can call ``uvicorn`` (port 8000) in development.
"""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import __version__, config, loaders
from .models import EventDetail, EventSummary

app = FastAPI(
    title="Aether Dashboard API",
    version=__version__,
    summary="Serves committed Stage A/B methane-plume outputs as JSON + rasters.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_PNG_LAYERS = {"enhancement": "enhancement.png", "nasa": "nasa.png", "diff": "diff.png"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/events", response_model=list[EventSummary])
def get_events() -> list[EventSummary]:
    """All events as globe markers (Goturdepe active, Permian pending)."""
    return loaders.list_events()


@app.get("/api/events/{event_id}", response_model=EventDetail)
def get_event(event_id: str) -> EventDetail:
    """Full inspector payload for one event."""
    detail = loaders.get_event_detail(event_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Unknown event_id: {event_id}")
    return detail


def _asset(event_id: str, filename: str, media_type: str) -> FileResponse:
    path = config.assets_dir(event_id) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No {filename} for {event_id}")
    return FileResponse(path, media_type=media_type)


@app.get("/api/events/{event_id}/enhancement.png")
def enhancement_png(event_id: str) -> FileResponse:
    """Our orthorectified MF enhancement, inferno-colorized (georef in /bounds)."""
    return _asset(event_id, "enhancement.png", "image/png")


@app.get("/api/events/{event_id}/nasa.png")
def nasa_png(event_id: str) -> FileResponse:
    """NASA L2B CH4ENH on the same ortho grid/bounds — for the retrieval toggle."""
    return _asset(event_id, "nasa.png", "image/png")


@app.get("/api/events/{event_id}/diff.png")
def diff_png(event_id: str) -> FileResponse:
    """(ours − NASA) difference, diverging colormap — for the Δ DIFF toggle."""
    return _asset(event_id, "diff.png", "image/png")


@app.get("/api/events/{event_id}/bounds")
def bounds(event_id: str) -> JSONResponse:
    """EPSG:4326 bounds + colormap window for the raster overlay."""
    path = config.assets_dir(event_id) / "bounds.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No bounds for {event_id}")
    return JSONResponse(content=json.loads(path.read_text()))


@app.get("/api/events/{event_id}/mask.geojson")
def mask_geojson(event_id: str) -> FileResponse:
    """CC-1213 plume mask outline as a GeoJSON FeatureCollection (lon/lat)."""
    return _asset(event_id, "mask.geojson", "application/geo+json")


@app.get("/api/events/{event_id}/hypotheses")
def hypotheses(event_id: str) -> JSONResponse:
    """The committed Sprint 4 source-attribution artifact (validated, verbatim).

    Events without an attribution artifact (e.g. pending Permian) get an honest
    absent state — never fabricated hypotheses.
    """
    if event_id not in loaders.EVENT_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown event_id: {event_id}")
    result = loaders.get_hypotheses(event_id)
    if result is None:
        return JSONResponse(content={"hypotheses": None, "status": "pending"})
    return JSONResponse(content=result.model_dump(mode="json"))
