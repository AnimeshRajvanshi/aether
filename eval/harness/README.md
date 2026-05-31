# aether-eval

The evaluation harness. Every detection or hypothesis claim Aether makes has to survive this package.

## What lives here

- **`schema.py`** — `BenchmarkEvent` Pydantic model. A typed, validated description of a known phenomenon with ground-truth measurements and references.
- **`loader.py`** — load YAML benchmark events from `eval/benchmark/` into `BenchmarkEvent` instances.
- **`metrics.py`** — match detections against benchmark events; compute recall, precision, quantification error, latency.
- **`runner.py`** — orchestrates: load events, run a pipeline against each, score the results, emit a report.
- **`cli.py`** — `aether-eval` command-line entry point.

## How an event is structured

A benchmark event lives as a YAML file in `eval/benchmark/`. It records:

- The phenomenon (type, name, date range, location, bbox)
- Known measurements with uncertainty and units (the ground truth we score against)
- Attribution where known (operator, facility, sector)
- Which sensor(s) observed it (for pipeline routing in Sprint 2+)
- Authoritative references (peer-reviewed papers, DOIs, official reports)
- Notes about caveats

See `eval/benchmark/aliso_canyon_2015.yaml` for a complete example.

## How matching works

Given a list of `Detection` objects produced by a pipeline and a `BenchmarkEvent`, a detection is considered a **match** if all three hold:

1. **Spatial:** detection location is within `spatial_tolerance_m` of the event's location (haversine distance).
2. **Temporal:** detection time overlaps a window of ±`temporal_tolerance_minutes` around the event's date range.
3. **Type:** the detection's `detection_type` is in the event's `expected_detection_types`.

Tolerances are configurable per evaluation run. Defaults: 5000 m spatial, 60 min temporal.

## Metrics

- **Recall** — fraction of benchmark events that have ≥1 matching detection.
- **Precision** — fraction of detections that match a benchmark event (events with no benchmark are false positives).
- **Quantification error** — for matched pairs, mean absolute percentage error between detection's measurement and event's known measurement, computed per measurement name.
- **Latency** — wall-clock time per event for the pipeline to run.

## CLI

```bash
aether-eval list                          # list benchmark events
aether-eval show aliso_canyon_2015        # show one event's details
aether-eval run --event aliso_canyon_2015 # run pipeline against one event
aether-eval run --all                     # run pipeline against all events
```

The pipeline is stubbed in Sprint 1 — it returns no detections. Sprint 2 wires up real detection and the harness starts scoring meaningfully.

## Why this comes before detection

If detection is built before the harness, every change requires manually eyeballing results. With the harness in place, every PR runs against a fixed benchmark and regressions are caught automatically. This is the single highest-leverage habit for scientific defensibility.
