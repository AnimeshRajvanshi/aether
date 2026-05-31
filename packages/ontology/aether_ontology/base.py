"""Base types shared across all Aether ontology entities."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class PlanetaryBody(StrEnum):
    """The planetary body an entity belongs to. Earth is default; Moon/Mars are first-class."""

    EARTH = "earth"
    MOON = "moon"
    MARS = "mars"
    VENUS = "venus"
    EUROPA = "europa"
    TITAN = "titan"
    OTHER = "other"


class Confidence(BaseModel):
    """Structural representation of uncertainty for any quantitative claim.

    `value` is the point estimate in [0, 1]. `lower` and `upper` bound a confidence
    interval. `method` documents how the confidence was derived (e.g.,
    'bootstrap_n1000', 'expert_elicitation', 'calibrated_model_v2'). `note` is
    free-form context.
    """

    model_config = ConfigDict(extra="forbid")

    value: float = Field(..., ge=0.0, le=1.0)
    lower: float | None = Field(None, ge=0.0, le=1.0)
    upper: float | None = Field(None, ge=0.0, le=1.0)
    method: str | None = None
    note: str | None = None


class Provenance(BaseModel):
    """Where this entity came from and how it was produced.

    Provenance is mandatory on every Aether entity. Reproducibility depends on it.
    """

    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., description="e.g., 'EMIT L2B v1', 'TROPOMI CH4 L2', 'manual'")
    source_id: str | None = Field(None, description="Granule/scene/file identifier from the source")
    pipeline: str | None = Field(None, description="Name of the Aether pipeline that produced this")
    pipeline_version: str | None = None
    parents: list[UUID] = Field(
        default_factory=list,
        description="IDs of parent entities this was derived from",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str | None = None


class AetherBase(BaseModel):
    """Base class for every entity in the Aether ontology.

    Every entity has: stable UUID, planetary body, provenance, optional confidence, tags.
    Subclasses add their type-specific fields.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    planetary_body: PlanetaryBody = PlanetaryBody.EARTH
    provenance: Provenance
    confidence: Confidence | None = None
    tags: list[str] = Field(default_factory=list)
