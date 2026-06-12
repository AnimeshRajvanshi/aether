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
    validation_tier: str | None = Field(
        None, description="VALIDATED | CROSS-CHECKED | DEMONSTRATION — None for pending"
    )
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
    # CROSS-CHECKED events (e.g. Permian) carry BOTH cross-check facts: the
    # integrated-mass ratio over the published footprint (≈agreement) AND the weak
    # pixel-level Pearson. None for events without a footprint-anchored cross-check.
    integrated_mass_ratio: float | None = None
    pixel_pearson: float | None = None


class ScopeCaveat(_Base):
    """The 'Read Before Citing' block.

    Two kinds, set by the reference's nature (Sprint 7 generality — the block is
    event-specific CONTENT, never a Thorpe template with swapped numbers):

    - ``cluster_fraction``: the reference is a peer-reviewed multi-source cluster
      total with an uncertainty (e.g. Goturdepe / Thorpe 2023). Single-plume vs
      cluster fraction is meaningful, so the numeric fields are populated.
    - ``context_only``: the reference is a press-release figure with no method,
      date, or uncertainty (e.g. Permian / 18.3 t/hr). There is NO cluster and no
      meaningful fraction; the numeric fields are null and the text explains why
      the figure is context, not a comparison target.
    """

    kind: str = "cluster_fraction"
    reference_total_t_hr: float
    reference_uncertainty_t_hr: float | None = None
    n_sources: int | None = None
    fraction_low_pct: float | None = None
    fraction_high_pct: float | None = None
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
    # How the plume's source point was localized — distinguishes Permian's
    # NASA-footprint-anchored S from Goturdepe's end-to-end self-derived S.
    localization: str | None = None


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
    validation_tier: str | None = None  # VALIDATED | CROSS-CHECKED | DEMONSTRATION
    tier_explainer: str | None = None  # what the tier means for THIS event + its limits

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
    # Heat vertical (Sprint 9 Stage D): populated for heat_wave events; None for
    # methane events — the methane payload is bit-identical to pre-Sprint-9.
    heat: HeatBlock | None = None


# --------------------------------------------------------------------------- #
# Heat vertical (Sprint 9 Stage D) — additive models; methane DTOs untouched
# --------------------------------------------------------------------------- #


class QuantityTierRow(_Base):
    """One per-quantity tier badge row (the heat vertical's tier extension).

    Tiers are PER QUANTITY for area events (docs/science/validation_tiers.md,
    heat extension): C1/C2 carry VALIDATED; C3/C4 carry their honest
    not-validated state with the criterion+dataset attached (Stage B gate
    rendering rule); LST quantities are capped at CROSS-CHECKED.
    """

    quantity: str  # "C1" | "C2" | "C3" | "C4" | "LST" | "UHI"
    label: str
    value_display: str
    tier: str  # VALIDATED | NOT VALIDATED | CROSS-CHECKED | CONSISTENCY NOT CLAIMED
    explainer: str
    criterion_dataset: str | None = None  # mandatory for duration/extent rows
    lane: str  # "AIR" | "LST"


class HeatLayerMeta(_Base):
    key: str
    label: str
    colormap: str
    vmin: float
    vmax: float
    unit: str
    lane: str


class HeatRasterMeta(_Base):
    """Bounds + layers for the heat overlay (air anomaly / baseline / LST)."""

    bounds: RasterBounds
    layers: list[str]
    layer_meta: list[HeatLayerMeta]
    lst_view_time_local_h: float
    rendering: str


class HeatEpisode(_Base):
    """Episode (criterion run) vs canonical analysis window — kept distinct."""

    window_start: str
    window_end: str
    episode_start: str
    episode_end: str
    episode_days: int
    criterion: str
    note: str


class HeatLstBlock(_Base):
    window_mean_anomaly_k: float
    view_time_local_h: float
    observation_time_statement: str  # first-class; from the committed artifact
    composite_baseline_residual_k: float
    uhi_window_mean_k: float
    uhi_window_std_k: float
    uhi_finding: str


class HeatBlock(_Base):
    """Everything heat-specific the inspector renders. All values from
    committed Stage B/C artifacts; nothing computed at render time."""

    peak_tmax_c: float
    peak_date: str
    window_mean_regional_anomaly_k: float
    peak_day_extent_km2: float
    episode: HeatEpisode
    quantity_tiers: list[QuantityTierRow]
    lst: HeatLstBlock
    lst_vs_air: str  # the first-class distinction block (verbatim framing)
    budget_terms: list[UncertaintyTerm]
    heat_raster: HeatRasterMeta


# HeatBlock is defined after EventDetail (additive section); resolve the
# deferred annotation now so validation works regardless of import order.
EventDetail.model_rebuild()
