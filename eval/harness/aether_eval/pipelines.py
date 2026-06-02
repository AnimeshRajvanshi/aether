"""Concrete pipelines that consume a :class:`BenchmarkEvent` and emit
:class:`Detection` objects, for use with :func:`aether_eval.runner.run_evaluation`.

Stage B of Sprint 2 produces a Q estimate plus uncertainty written to
``stage_b_outputs/<event_id>/q_estimate.json`` by the driver
``scripts/run_stage_b_goturdepe.py``. The
:func:`stage_b_quantification_pipeline` reads that JSON for the event being
evaluated and returns a single :class:`Detection` carrying the quantified
emission rate and its uncertainty.

Two notes on scope:

* The Goturdepe benchmark's ``known_measurements.emission_rate_metric_tonnes_per_hr``
  is the *whole-cluster* total reported by Thorpe et al. 2023 (163 ± 18 t/hr
  across 12 sources). Our pipeline quantifies ONE source-connected plume,
  not the cluster. The pipeline therefore deliberately produces a value
  that is a *fraction* of the cluster total. The eval will report a large
  quantification MAPE; that is the expected outcome of a scope mismatch, not
  a pipeline failure. The scope caveat is documented in the benchmark YAML's
  ``known_measurements.emission_rate_metric_tonnes_per_hr.note`` field.

* The pipeline is deliberately cache-driven (it reads a JSON file) so the
  eval harness can run quickly and deterministically without network access
  in CI. The actual Stage B work — segmentation, IME, ERA5 wind fetch — is
  done once by the driver and persisted; the eval simply consumes the result.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from aether_ontology import Detection, DetectionType, Point, Provenance

from aether_eval.schema import BenchmarkEvent

# Where Stage B drivers write their q_estimate.json files. The Goturdepe
# driver pins this; future events follow the same convention.
DEFAULT_STAGE_B_DIR = Path("stage_b_outputs")

# Pipeline metadata recorded on each emitted Detection.
PIPELINE_NAME = "aether-stage-b-quantification"
PIPELINE_VERSION = "0.1.0"


def _granule_observation_uuid(granule_ur: str) -> UUID:
    """Mint a stable UUIDv5 from the granule UR.

    Using UUIDv5 with NAMESPACE_URL gives us a deterministic mapping: the
    same granule UR always produces the same UUID across runs, so the
    Detection's ``observation_ids`` is stable for downstream linking even
    though we have not (yet) materialised a Sprint-1-style Observation
    object in the harness.
    """
    return uuid5(NAMESPACE_URL, f"emit://{granule_ur}")


def stage_b_quantification_pipeline(
    event: BenchmarkEvent,
    stage_b_dir: Path | str = DEFAULT_STAGE_B_DIR,
) -> list[Detection]:
    """Pipeline that emits a single quantified-plume Detection for events
    that have a Stage B ``q_estimate.json`` on disk.

    Reads ``<stage_b_dir>/<event_id>/q_estimate.json``. Returns an empty list
    if the file does not exist — that lets the eval harness run cleanly on
    events that have not yet been processed.

    The Detection's measurements carry:
        emission_rate_metric_tonnes_per_hr (central, ours-calibrated)
        emission_rate_metric_tonnes_per_hr_nasa_calibrated
        emission_rate_metric_tonnes_per_hr_low
        emission_rate_metric_tonnes_per_hr_high
        ime_kg
        plume_area_km2

    Measurement uncertainty (1-σ-symmetric, Q × wind+mask fractional):
        emission_rate_metric_tonnes_per_hr → Q_central × σ_fractional
    """
    stage_b_dir = Path(stage_b_dir)
    json_path = stage_b_dir / event.event_id / "q_estimate.json"
    if not json_path.exists():
        return []

    with json_path.open() as f:
        rep = json.load(f)

    granule_ur = ""
    if event.canonical_acquisition is not None:
        granule_ur = event.canonical_acquisition.l1b_granule_ur or ""
    obs_uuid = _granule_observation_uuid(granule_ur or event.event_id)

    q_central = float(rep["q_central_t_hr"])
    q_sigma = q_central * float(rep["q_total_fractional_sigma"])

    measurements = {
        "emission_rate_metric_tonnes_per_hr": q_central,
        "emission_rate_metric_tonnes_per_hr_nasa_calibrated":
            float(rep["q_central_nasa_calibrated_t_hr"]),
        "emission_rate_metric_tonnes_per_hr_low": float(rep["q_low_t_hr"]),
        "emission_rate_metric_tonnes_per_hr_high": float(rep["q_high_t_hr"]),
        "ime_kg": float(rep["ime_central_kg"]),
        "plume_area_km2": float(rep["plume_cc_area_km2"]),
    }
    measurement_units = {
        "emission_rate_metric_tonnes_per_hr": "tonnes/hr",
        "emission_rate_metric_tonnes_per_hr_nasa_calibrated": "tonnes/hr",
        "emission_rate_metric_tonnes_per_hr_low": "tonnes/hr",
        "emission_rate_metric_tonnes_per_hr_high": "tonnes/hr",
        "ime_kg": "kg",
        "plume_area_km2": "km^2",
    }
    measurement_uncertainty = {
        "emission_rate_metric_tonnes_per_hr": q_sigma,
    }

    location = Point(
        lon=float(rep["plume_centroid_lon"]),
        lat=float(rep["plume_centroid_lat"]),
    )

    provenance = Provenance(
        source="aether_detection",
        source_id=granule_ur or event.event_id,
        pipeline=PIPELINE_NAME,
        pipeline_version=PIPELINE_VERSION,
        parents=[],
        notes=(
            f"Stage B IME quantification on plume CC {rep.get('plume_cc_label')}. "
            f"Scope: ONE plume of a multi-source cluster — not same-scope as the "
            f"benchmark's Thorpe 2023 cluster total."
        ),
    )

    detection = Detection(
        detection_type=DetectionType.METHANE_PLUME,
        observation_ids=[obs_uuid],
        location=location,
        time_range=event.date_range,
        measurements=measurements,
        measurement_units=measurement_units,
        measurement_uncertainty=measurement_uncertainty,
        algorithm=PIPELINE_NAME,
        algorithm_version=PIPELINE_VERSION,
        provenance=provenance,
    )
    return [detection]
