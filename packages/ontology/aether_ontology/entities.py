"""Core Aether ontology entities."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from aether_ontology.base import AetherBase
from aether_ontology.spatial import BBox, GeoJSONGeometry, Point
from aether_ontology.temporal import TimeRange

# --------------------------------------------------------------------------- #
# Observation
# --------------------------------------------------------------------------- #


class SensorType(StrEnum):
    HYPERSPECTRAL = "hyperspectral"
    MULTISPECTRAL = "multispectral"
    THERMAL = "thermal"
    SAR = "sar"
    LIDAR = "lidar"
    GNSS_REFLECTOMETRY = "gnss_reflectometry"
    REANALYSIS = "reanalysis"
    GROUND_BASED = "ground_based"
    SPACE_OBJECT_CATALOG = "space_object_catalog"
    OTHER = "other"


class Observation(AetherBase):
    """A single scene or measurement from a sensor."""

    sensor: str = Field(
        ..., description="Human name, e.g., 'EMIT', 'TROPOMI', 'Landsat 8 OLI/TIRS'"
    )
    sensor_type: SensorType
    instrument_id: str | None = None
    granule_id: str | None = None
    time_range: TimeRange
    footprint: GeoJSONGeometry
    cloud_cover_pct: float | None = Field(None, ge=0.0, le=100.0)
    data_url: str | None = Field(
        None, description="Canonical access URL (COG, Zarr, HDF, S3, etc.)"
    )
    asset_paths: dict[str, str] = Field(
        default_factory=dict,
        description="Named asset paths, e.g., {'CH4ENH': 's3://...', 'L1B_RAD': 's3://...'}",
    )


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #


class DetectionType(StrEnum):
    METHANE_PLUME = "methane_plume"
    CO2_PLUME = "co2_plume"
    # THERMAL_ANOMALY is a *skin/LST* (land-surface temperature) anomaly;
    # AIR_TEMPERATURE_ANOMALY is a *2 m air* temperature anomaly. They are
    # different physical quantities and must never be conflated (ADR 0003).
    THERMAL_ANOMALY = "thermal_anomaly"
    AIR_TEMPERATURE_ANOMALY = "air_temperature_anomaly"
    SST_ANOMALY = "sst_anomaly"
    FIRE = "fire"
    LAUNCH_SIGNATURE = "launch_signature"
    EXPLOSION = "explosion"
    ORBITAL_OBJECT = "orbital_object"
    CONJUNCTION = "conjunction"
    OCEAN_COLOR_ANOMALY = "ocean_color_anomaly"
    OTHER = "other"


class Detection(AetherBase):
    """Something found in one or more observations.

    `measurements`, `measurement_units`, and `measurement_uncertainty` are parallel
    dicts keyed by the same measurement name. Example for a methane plume:
        measurements = {"emission_rate_kg_per_hr": 543.0, "ime_kg": 215.0}
        measurement_units = {"emission_rate_kg_per_hr": "kg/hr", "ime_kg": "kg"}
        measurement_uncertainty = {"emission_rate_kg_per_hr": 120.0, "ime_kg": 40.0}
    """

    detection_type: DetectionType
    observation_ids: list[UUID] = Field(..., min_length=1)
    location: Point
    footprint: GeoJSONGeometry | None = None
    time_range: TimeRange

    measurements: dict[str, float] = Field(default_factory=dict)
    measurement_units: dict[str, str] = Field(default_factory=dict)
    measurement_uncertainty: dict[str, float] = Field(default_factory=dict)

    algorithm: str = Field(..., description="Name of algorithm that produced this detection")
    algorithm_version: str


# --------------------------------------------------------------------------- #
# Entity (real-world objects)
# --------------------------------------------------------------------------- #


class EntityType(StrEnum):
    FACILITY = "facility"
    OPERATOR = "operator"
    SATELLITE = "satellite"
    SPACE_DEBRIS = "space_debris"
    VESSEL = "vessel"
    AIRCRAFT = "aircraft"
    CITY = "city"
    REGION = "region"
    INFRASTRUCTURE = "infrastructure"
    NATURAL_FEATURE = "natural_feature"
    LAUNCH_SITE = "launch_site"
    OTHER = "other"


class Entity(AetherBase):
    """A real-world object referenced by detections, phenomena, and hypotheses."""

    entity_type: EntityType
    name: str
    location: Point | None = None
    footprint: GeoJSONGeometry | None = None

    attributes: dict[str, str | float | int | bool] = Field(
        default_factory=dict,
        description="Free-form typed attributes (operator name, NORAD ID, facility subtype, etc.)",
    )
    external_ids: dict[str, str] = Field(
        default_factory=dict,
        description="IDs in external systems, e.g., {'norad': '25544', 'rystad': 'fac-123'}",
    )


# --------------------------------------------------------------------------- #
# Phenomenon
# --------------------------------------------------------------------------- #


class PhenomenonType(StrEnum):
    EMISSION_EVENT = "emission_event"
    HEAT_WAVE = "heat_wave"
    MARINE_HEAT_WAVE = "marine_heat_wave"
    WILDFIRE = "wildfire"
    SATELLITE_PASS = "satellite_pass"
    LAUNCH = "launch"
    REENTRY = "reentry"
    CONJUNCTION_EVENT = "conjunction_event"
    OTHER = "other"


class Phenomenon(AetherBase):
    """A temporally extended real-world thing that detections cluster into.

    For example: an ongoing methane leak observed across multiple EMIT overpasses
    is one Phenomenon with many Detections.
    """

    phenomenon_type: PhenomenonType
    name: str | None = None
    detection_ids: list[UUID] = Field(default_factory=list)
    time_range: TimeRange
    region: BBox | GeoJSONGeometry

    summary_measurements: dict[str, float] = Field(default_factory=dict)
    summary_units: dict[str, str] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Hypothesis
# --------------------------------------------------------------------------- #


class Hypothesis(AetherBase):
    """A proposed explanation linking a phenomenon to entities and context.

    Hypotheses are NEVER asserted as truth. They are ranked candidate explanations
    with explicit evidence, explicit assumptions, and an explicit falsification path.
    """

    phenomenon_id: UUID
    claim: str = Field(
        ...,
        description="Natural-language explanation, e.g., 'Source likely a fugitive emission "
        "from compressor station X operated by Y.'",
    )

    supporting_observation_ids: list[UUID] = Field(default_factory=list)
    supporting_detection_ids: list[UUID] = Field(default_factory=list)
    related_entity_ids: list[UUID] = Field(default_factory=list)

    assumptions: list[str] = Field(
        default_factory=list,
        description="Each assumption is a single sentence; missing assumptions are themselves "
        "a defect.",
    )
    falsification: str | None = Field(
        None,
        description="What evidence would change our mind about this hypothesis?",
    )

    score: float = Field(..., ge=0.0, le=1.0)
    rank: int = Field(..., ge=1)

    generation_method: str = Field(
        ...,
        description="How was this hypothesis generated? e.g., 'llm_claude_sonnet_4.6', "
        "'rule_based_v1', 'manual'",
    )


# --------------------------------------------------------------------------- #
# Brief
# --------------------------------------------------------------------------- #


class Brief(AetherBase):
    """Human-facing narrative artifact summarizing a phenomenon.

    Briefs are generated from Phenomena and their Hypotheses. Every claim in the
    narrative cites back to a specific Observation, Detection, or Hypothesis.
    """

    phenomenon_id: UUID
    title: str
    summary: str = Field(..., description="Short version (1-3 sentences) for surfacing in lists")
    body_markdown: str = Field(..., description="Full narrative; markdown is the canonical form")
    hypothesis_ids: list[UUID] = Field(default_factory=list)

    citations: list[dict[str, str]] = Field(
        default_factory=list,
        description="Claim-to-evidence citations: [{'claim': '...', 'evidence_id': '...', "
        "'evidence_type': 'observation|detection|hypothesis'}]",
    )

    rendered_url: str | None = Field(
        None,
        description="If exported (PDF, HTML), the URL where the rendered brief lives",
    )
