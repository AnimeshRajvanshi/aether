"""Pydantic v2 response models for the dashboard API.

These shape the JSON the frontend consumes. They are presentation DTOs, not
ontology entities — but they reuse ontology enums (``PhenomenonType``,
``PlanetaryBody``) where they fit so the vocabulary stays consistent. Every
field is populated from a committed file in ``loaders.py``; nothing is set to a
literal scientific value here.
"""

from __future__ import annotations

from enum import StrEnum

from aether_ontology import PhenomenonType, PlanetaryBody
from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventStatus(StrEnum):
    """Whether we have a quantified Stage B result for this event."""

    ACTIVE = "active"  # full Stage A/B result available
    PENDING = "pending"  # benchmark exists, no quantification yet (honest gap)


class EventSummary(_Base):
    """One marker on the globe / one row in the catalog."""

    event_id: str
    name: str
    short_name: str
    planetary_body: PlanetaryBody
    phenomenon_type: PhenomenonType
    lat: float
    lon: float
    status: EventStatus
    sensor: str
    headline: str | None = Field(None, description="e.g. 'CH₄ · 27.1 t/hr' or 'pending'")
    acquisition_utc: str | None = Field(
        None,
        description=(
            "Acquisition timestamp of the processed overpass (from "
            "stage_a_report.json). None for pending events — we have not run a "
            "retrieval, so we don't imply one. This is a static historical event."
        ),
    )


class CalibratedRate(_Base):
    """An emission rate under one calibration with its symmetric range."""

    label: str  # "OURS-CAL" | "NASA-CAL"
    value_t_hr: float
    range_low_t_hr: float
    range_high_t_hr: float
    sigma_fractional: float
    note: str


class Quantification(_Base):
    """Headline emission rate, both calibrations, from q_estimate.json."""

    ours_cal: CalibratedRate
    nasa_cal: CalibratedRate
    enhancement_bias_factor: float
    central_p_value: float


class UncertaintyTerm(_Base):
    """One bar in the uncertainty budget.

    ``value_pct`` is the real one-sigma fractional term (×100); ``factor`` is set
    instead for the one-sided systematic. ``bar_fraction`` is a unitless 0..1 used
    only for bar width — a visual scaling of the real percentage, not new data.
    """

    key: str
    label: str
    kind: str  # "symmetric" | "systematic"
    value_pct: float | None = None
    factor: float | None = None
    display: str
    bar_fraction: float


class Geometry(_Base):
    ime_t: float
    area_km2: float
    length_km: float
    centroid_lat: float
    centroid_lon: float


class Atmosphere(_Base):
    u10_speed_ms: float
    u_eff_ms: float
    era5_grid_lat: float
    era5_grid_lon: float
    era5_nearest_hour_utc: str


class Validation(_Base):
    pearson_in_bbox: float
    pearson_full_scene: float
    n_pixels_bbox: int
    reference_product: str
    note: str


class ScopeCaveat(_Base):
    """The red 'Read Before Citing' block — single-plume vs cluster total."""

    reference_total_t_hr: float
    reference_uncertainty_t_hr: float
    n_sources: int
    fraction_low_pct: float
    fraction_high_pct: float
    text: str


class Reference(_Base):
    citation: str
    doi: str | None = None
    url: str | None = None


class Provenance(_Base):
    acquisition_utc: str
    l1b_granule_ur: str | None = None
    l2a_mask_granule_ur: str | None = None
    l2b_ch4_granule_ur: str | None = None
    target_spectrum_source: str | None = None
    bands_used: int | None = None


class RasterBounds(_Base):
    west: float
    south: float
    east: float
    north: float


class RasterMeta(_Base):
    """Bounds + available layers for the plume image overlay."""

    bounds: RasterBounds
    colormap: str
    vmin_ppm_m: float
    vmax_ppm_m: float
    layers: list[str]  # ["enhancement", "nasa", "diff"]


class EventDetail(_Base):
    """Full event payload for the inspector. Science blocks are null when pending."""

    event_id: str
    name: str
    short_name: str
    planetary_body: PlanetaryBody
    phenomenon_type: PhenomenonType
    lat: float
    lon: float
    status: EventStatus
    location_label: str
    chips: list[str]

    quantification: Quantification | None = None
    uncertainty_budget: list[UncertaintyTerm] = Field(default_factory=list)
    geometry: Geometry | None = None
    atmosphere: Atmosphere | None = None
    validation: Validation | None = None
    scope_caveat: ScopeCaveat | None = None
    brief: str | None = None
    raster: RasterMeta | None = None

    provenance: Provenance | None = None
    references: list[Reference] = Field(default_factory=list)
    pending_reason: str | None = None
