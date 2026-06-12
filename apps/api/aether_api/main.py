"""FastAPI app for the Aether dashboard.

Serves committed Stage A/B outputs as JSON + georeferenced rasters. The API is
a READ-ONLY artifact server (Sprint 10 hardening): only GET routes are
declared, CORS origins come from explicit environment config (loud failure in
production, never a silent default), single-file payloads stream raw committed
bytes (byte-identity through the stack), and every response carries a small
security-header set. The FastAPI docs endpoints stay ON in production — a
conscious decision recorded in docs/deployment.md (read-only public API;
transparency is part of the portfolio).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import __version__, config, loaders

# Headers on every response. Rationale in docs/deployment.md ("Security
# headers"): nosniff stops MIME guessing on served artifacts; DENY blocks
# clickjacking iframes (the API has no UI to embed); no-referrer because
# requests to a read-only artifact server need no referrer context.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def _validate_committed_artifacts() -> None:
    """Startup guard: every attribution artifact the API can stream must pass
    its own schema (extra="forbid") BEFORE the app serves a byte.

    Sprint 10 moved /hypotheses + /factor-hypotheses from per-request Pydantic
    round-trips to raw byte streaming; this check keeps the can-neither-add-
    nor-drop-a-field guarantee, just once at startup instead of per request.
    A failure here must crash the deploy loudly, not degrade silently.
    """
    for event_id in loaders.EVENT_IDS:
        try:
            loaders.get_hypotheses(event_id)  # validates via HypothesisSet
            loaders.get_factor_hypotheses(event_id)  # validates via FactorHypothesisSet
        except Exception as exc:  # pragma: no cover - re-raised with context
            raise config.ConfigError(
                f"Committed attribution artifact for {event_id!r} failed schema "
                f"validation at startup — refusing to serve it: {exc}"
            ) from exc


def create_app() -> FastAPI:
    """App factory. Reads env config ONCE, fails loudly on bad/missing config
    (the guard suite builds production-configured instances through this)."""
    origins = config.allowed_origins()  # raises ConfigError in misconfigured prod
    config.git_sha()  # fail at startup, not first /api/version request
    _validate_committed_artifacts()

    app = FastAPI(
        title="Aether Dashboard API",
        version=__version__,
        summary="Serves committed Stage A/B methane + heat outputs as JSON + rasters.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for key, value in _SECURITY_HEADERS.items():
            response.headers[key] = value
        return response

    _register_routes(app)
    return app


def _require_known_event(event_id: str) -> None:
    """Whitelist guard (Stage A finding F2): asset routes serve ONLY the
    registered events — never 'whatever path exists under assets/'."""
    if event_id not in loaders.EVENT_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown event_id: {event_id}")


def _asset(event_id: str, filename: str, media_type: str) -> FileResponse:
    _require_known_event(event_id)
    path = config.assets_dir(event_id) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No {filename} for {event_id}")
    return FileResponse(path, media_type=media_type)


def _register_routes(app: FastAPI) -> None:
    from .models import EventDetail, EventSummary  # local: keep module import light

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/version")
    def version() -> dict[str, str]:
        """Deployed-integrity anchor: the git SHA baked at build time (build
        arg → AETHER_GIT_SHA; never a runtime git call) + the app version. The
        web footer renders this SHA — fetched, not hardcoded."""
        return {"git_sha": config.git_sha(), "app_version": __version__}

    @app.get("/api/events", response_model=list[EventSummary])
    def get_events() -> list[EventSummary]:
        """All events as globe markers."""
        return loaders.list_events()

    @app.get("/api/events/{event_id}", response_model=EventDetail)
    def get_event(event_id: str) -> EventDetail:
        """Full inspector payload for one event."""
        detail = loaders.get_event_detail(event_id)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"Unknown event_id: {event_id}")
        return detail

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
    def bounds(event_id: str) -> FileResponse:
        """EPSG:4326 bounds + colormap window — the committed bounds.json bytes,
        streamed raw (Sprint 10: byte-identity instead of re-serialization)."""
        return _asset(event_id, "bounds.json", "application/json")

    @app.get("/api/events/{event_id}/mask.geojson")
    def mask_geojson(event_id: str) -> FileResponse:
        """Plume mask outline as a GeoJSON FeatureCollection (lon/lat)."""
        return _asset(event_id, "mask.geojson", "application/geo+json")

    @app.get("/api/events/{event_id}/hypotheses")
    def hypotheses(event_id: str) -> Response:
        """The committed Sprint 4 source-attribution artifact, streamed raw.

        The bytes on the wire ARE the committed file (schema validation runs at
        startup + in the guard suite). Events without a served artifact get an
        honest pending state — never fabricated hypotheses.
        """
        _require_known_event(event_id)
        path = loaders.hypotheses_path(event_id)
        if path is None:
            return JSONResponse(content={"hypotheses": None, "status": "pending"})
        return FileResponse(path, media_type="application/json")

    @app.get("/api/events/{event_id}/layers/{layer}.png")
    def layer_png(event_id: str, layer: str) -> FileResponse:
        """Generic per-event raster layer (heat: air_anomaly/air_baseline/lst_anomaly).

        Whitelisted against the event's own committed bounds.json layer list — the
        route serves exactly the layers the asset build declared, nothing else.
        """
        _require_known_event(event_id)
        bounds_path = config.assets_dir(event_id) / "bounds.json"
        if not bounds_path.exists():
            raise HTTPException(status_code=404, detail=f"No assets for {event_id}")
        allowed = json.loads(bounds_path.read_text()).get("layers", [])
        if layer not in allowed:
            raise HTTPException(status_code=404, detail=f"No layer {layer} for {event_id}")
        return _asset(event_id, f"{layer}.png", "image/png")

    @app.get("/api/events/{event_id}/factor-hypotheses")
    def factor_hypotheses(event_id: str) -> Response:
        """The committed Stage C multi-factor attribution artifact, streamed raw
        (verbatim bytes; heat events only; honest pending state otherwise)."""
        _require_known_event(event_id)
        path = loaders.factor_hypotheses_path(event_id)
        if path is None:
            return JSONResponse(content={"factors": None, "status": "pending"})
        return FileResponse(path, media_type="application/json")


app = create_app()
