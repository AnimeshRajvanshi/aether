"""Aether planetary ontology — typed entities for the platform."""

from aether_ontology.base import (
    AetherBase,
    Confidence,
    PlanetaryBody,
    Provenance,
)
from aether_ontology.entities import (
    ANOMALY_DETECTION_TYPES,
    BaselineDefinition,
    Brief,
    Detection,
    DetectionType,
    Entity,
    EntityType,
    Hypothesis,
    Observation,
    Phenomenon,
    PhenomenonType,
    SensorType,
)
from aether_ontology.spatial import BBox, GeoJSONGeometry, Point
from aether_ontology.temporal import TimeRange

__all__ = [
    "ANOMALY_DETECTION_TYPES",
    "AetherBase",
    "BBox",
    "BaselineDefinition",
    "Brief",
    "Confidence",
    "Detection",
    "DetectionType",
    "Entity",
    "EntityType",
    "GeoJSONGeometry",
    "Hypothesis",
    "Observation",
    "Phenomenon",
    "PhenomenonType",
    "PlanetaryBody",
    "Point",
    "Provenance",
    "SensorType",
    "TimeRange",
]

__version__ = "0.1.0"
