"""Spatial types for the ontology.

Geometry is stored in GeoJSON-compatible form on the Python side; PostGIS handles
storage and spatial queries on the database side. CRS defaults to WGS84 (EPSG:4326);
for non-Earth bodies, use the appropriate body-fixed CRS (e.g., 'IAU:30100' for Mars).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Point(BaseModel):
    """A single point. For non-Earth bodies, set `crs` accordingly."""

    model_config = ConfigDict(extra="forbid")

    lon: float = Field(..., ge=-180.0, le=180.0)
    lat: float = Field(..., ge=-90.0, le=90.0)
    elevation_m: float | None = None
    crs: str = "EPSG:4326"


class BBox(BaseModel):
    """Axis-aligned bounding box."""

    model_config = ConfigDict(extra="forbid")

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    crs: str = "EPSG:4326"

    @model_validator(mode="after")
    def _check_bounds(self) -> BBox:
        if self.min_lon > self.max_lon:
            raise ValueError(f"min_lon ({self.min_lon}) > max_lon ({self.max_lon})")
        if self.min_lat > self.max_lat:
            raise ValueError(f"min_lat ({self.min_lat}) > max_lat ({self.max_lat})")
        return self


class GeoJSONGeometry(BaseModel):
    """Loose GeoJSON-compatible geometry.

    We don't enforce the full coordinate-array shape at the Pydantic layer because
    GeoJSON nests differently for each type. Use shapely or the database layer for
    rigorous geometric validation.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"]
    coordinates: list[Any]
    crs: str = "EPSG:4326"
