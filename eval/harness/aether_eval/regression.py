"""REGRESSION metric family (ADR 0002): fresh pipeline values vs committed artifacts.

A regression check asserts one thing only: the pipeline, re-run end-to-end from
cached inputs, still reproduces the committed, gate-reviewed result within a
stated tolerance. Green means "the pipeline still produces the reviewed
science" — it claims nothing about external validity (that is the tier
system's job, and no event is VALIDATED).

The committed sources of truth are:
    stage_b_outputs/<event_id>/q_estimate.json     (Q values, centroid)
    stage_a_outputs/<event_id>/stage_a_report.json (Pearson vs NASA L2B)

Tolerances (docs/science/eval_semantics.md):
    Q (ours- and NASA-calibrated)   ±1% fractional
    Pearson vs L2B (full + bbox)    ±0.01 absolute
    plume centroid                  ≤0.5 km haversine
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aether_eval.metrics import haversine_meters

# eval/harness/aether_eval/regression.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]

Q_FRACTIONAL_TOL = 0.01
PEARSON_ABS_TOL = 0.01
CENTROID_KM_TOL = 0.5


@dataclass(frozen=True)
class RegressionCheck:
    """One fresh-vs-committed comparison."""

    name: str
    committed: float
    fresh: float
    tolerance: float
    kind: str  # "fractional" | "absolute" | "distance_km"
    passed: bool

    def describe(self) -> str:
        if self.kind == "distance_km":
            return (
                f"{self.name}: offset {self.fresh:.3f} km from committed "
                f"(tol ≤{self.tolerance} km) {'PASS' if self.passed else 'FAIL'}"
            )
        delta = self.fresh - self.committed
        if self.kind == "fractional":
            frac = delta / self.committed if self.committed else float("inf")
            return (
                f"{self.name}: {self.fresh:.4f} vs committed {self.committed:.4f} "
                f"({frac:+.2%}, tol ±{self.tolerance:.0%}) {'PASS' if self.passed else 'FAIL'}"
            )
        return (
            f"{self.name}: {self.fresh:.4f} vs committed {self.committed:.4f} "
            f"({delta:+.4f}, tol ±{self.tolerance}) {'PASS' if self.passed else 'FAIL'}"
        )


def _fractional(name: str, committed: float, fresh: float, tol: float) -> RegressionCheck:
    passed = committed != 0 and abs(fresh - committed) / abs(committed) <= tol
    return RegressionCheck(name, committed, fresh, tol, "fractional", passed)


def _absolute(name: str, committed: float, fresh: float, tol: float) -> RegressionCheck:
    return RegressionCheck(name, committed, fresh, tol, "absolute", abs(fresh - committed) <= tol)


# Heat (area-event) regression tolerances: the heat lane re-runs from cached
# reanalysis inputs and is deterministic, so the tolerances are tight — they
# exist to catch logic drift, not numerical noise.
HEAT_PEAK_TMAX_ABS_TOL_C = 0.05
HEAT_ANOM_ABS_TOL_K = 0.02
HEAT_EXTENT_FRACTIONAL_TOL = 0.01


def compare_heat_to_committed(
    event_id: str,
    fresh: dict[str, float],
    repo_root: Path | None = None,
) -> list[RegressionCheck]:
    """Heat-event regression: fresh AIR-lane values vs committed air_lane.json.

    `fresh` must carry: c1_peak_c, c2_window_mean_anomaly_k, c3_duration_days,
    c4_extent_km2.
    """
    root = repo_root or _REPO_ROOT
    air_path = root / "stage_b_outputs" / event_id / "air_lane.json"
    air = json.loads(air_path.read_text())
    duration_fresh = fresh["c3_duration_days"]
    duration_committed = float(air["c3_duration"]["n_days"])
    return [
        _absolute(
            "c1_peak_tmax_c",
            float(air["c1_peak_tmax"]["value_c"]),
            fresh["c1_peak_c"],
            HEAT_PEAK_TMAX_ABS_TOL_C,
        ),
        _absolute(
            "c2_window_mean_regional_anomaly_k",
            float(air["c2_anomaly"]["window_mean_regional_mean_anomaly_k"]),
            fresh["c2_window_mean_anomaly_k"],
            HEAT_ANOM_ABS_TOL_K,
        ),
        RegressionCheck(
            name="c3_duration_days",
            committed=duration_committed,
            fresh=duration_fresh,
            tolerance=0.0,
            kind="absolute",
            passed=duration_fresh == duration_committed,
        ),
        _fractional(
            "c4_extent_km2",
            float(air["c4_extent"]["extent_km2"]),
            fresh["c4_extent_km2"],
            HEAT_EXTENT_FRACTIONAL_TOL,
        ),
    ]


def compare_to_committed(
    event_id: str,
    fresh: dict[str, float],
    repo_root: Path | None = None,
) -> list[RegressionCheck]:
    """Compare a fresh run's values against the committed artifacts for `event_id`.

    Dispatches on the committed artifact shape: a heat event commits
    air_lane.json (compare_heat_to_committed); methane events commit
    q_estimate.json + stage_a_report.json and `fresh` must carry:
    q_central_t_hr, q_central_nasa_calibrated_t_hr, pearson_full_scene,
    pearson_in_bbox, centroid_lat, centroid_lon.
    Raises FileNotFoundError if the event has no committed artifacts — regression
    against nothing is meaningless, and silently passing would hide that.
    """
    root = repo_root or _REPO_ROOT
    if (root / "stage_b_outputs" / event_id / "air_lane.json").exists():
        return compare_heat_to_committed(event_id, fresh, repo_root=root)
    q_path = root / "stage_b_outputs" / event_id / "q_estimate.json"
    a_path = root / "stage_a_outputs" / event_id / "stage_a_report.json"
    committed_q = json.loads(q_path.read_text())
    committed_a = json.loads(a_path.read_text())

    checks = [
        _fractional(
            "q_central_t_hr",
            float(committed_q["q_central_t_hr"]),
            fresh["q_central_t_hr"],
            Q_FRACTIONAL_TOL,
        ),
        _fractional(
            "q_central_nasa_calibrated_t_hr",
            float(committed_q["q_central_nasa_calibrated_t_hr"]),
            fresh["q_central_nasa_calibrated_t_hr"],
            Q_FRACTIONAL_TOL,
        ),
        _absolute(
            "pearson_full_scene",
            float(committed_a["pearson_full_scene"]),
            fresh["pearson_full_scene"],
            PEARSON_ABS_TOL,
        ),
        _absolute(
            "pearson_in_bbox",
            float(committed_a["pearson_in_bbox"]),
            fresh["pearson_in_bbox"],
            PEARSON_ABS_TOL,
        ),
    ]

    offset_km = haversine_meters(
        fresh["centroid_lon"],
        fresh["centroid_lat"],
        float(committed_q["plume_centroid_lon"]),
        float(committed_q["plume_centroid_lat"]),
    ) / 1000.0
    checks.append(RegressionCheck(
        name="plume_centroid",
        committed=0.0,
        fresh=offset_km,
        tolerance=CENTROID_KM_TOL,
        kind="distance_km",
        passed=offset_km <= CENTROID_KM_TOL,
    ))
    return checks
