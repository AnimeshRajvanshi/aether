# Benchmark events

Every YAML file in this directory is a known phenomenon with peer-reviewed or otherwise authoritative ground truth, used to score Aether's detection pipelines.

## Format

See `aether_eval/schema.py` (the `BenchmarkEvent` model) for the canonical schema. Every event must have:

- `event_id` — stable, filename-safe identifier (matches the YAML filename minus `.yaml`)
- `name` — human-readable name
- `phenomenon_type` — one of the `PhenomenonType` enum values
- `expected_detection_types` — what a pipeline should produce when given this event
- `date_range`, `location`, `bbox` — when and where (and `location` must lie inside `bbox`)
- `references` — at least one citation. **An event with no references is not ground truth.**

Optional but encouraged:

- `known_measurements` — typed measurements with `value`, `uncertainty`, `unit`, `note`
- `attribution` — operator / facility / sector if known
- `observed_by` — list of sensors that observed the event
- `notes`, `tags`

## Adding an event

1. Copy an existing YAML as a template.
2. Set `event_id` and the filename to the same value.
3. Fill in real numbers from peer-reviewed sources or official reports.
4. Cite everything in `references`.
5. Run `aether-eval show <event_id>` and `aether-eval list` to confirm it loads.

## What's here

| File                            | Source                  | EMIT-observable? |
|---------------------------------|-------------------------|------------------|
| `aliso_canyon_2015.yaml`        | Conley et al. 2016, *Science* | No (pre-EMIT) |

The Aliso Canyon event is our schema-validation reference. It is *not* suitable for EMIT detection benchmarking (the event predates EMIT's launch). Sprint 2 will add EMIT-observable events from Carbon Mapper's public API.

## Why we don't generate fake events for testing

Every value in this directory is real and traceable. Fake test events erode the meaning of "the benchmark passed." If you need to test the harness logic itself in isolation, do it in `tests/` with explicit fixtures.
