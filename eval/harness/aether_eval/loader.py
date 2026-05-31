"""Load benchmark events from YAML files in `eval/benchmark/`."""

from __future__ import annotations

from pathlib import Path

import yaml

from aether_eval.schema import BenchmarkEvent

# Default location: the eval/benchmark folder at repo root.
# Computed relative to this file's location: .../eval/harness/aether_eval/loader.py
# parents[0]=aether_eval, [1]=harness, [2]=eval → eval/benchmark
_DEFAULT_BENCHMARK_DIR = Path(__file__).resolve().parents[2] / "benchmark"


def default_benchmark_dir() -> Path:
    """Return the canonical benchmark directory location."""
    return _DEFAULT_BENCHMARK_DIR


def load_event_file(path: Path | str) -> BenchmarkEvent:
    """Load a single YAML file as a `BenchmarkEvent`.

    Raises pydantic.ValidationError if the file fails schema validation.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Benchmark file {path} did not contain a YAML mapping at the top level.")
    return BenchmarkEvent.model_validate(data)


def discover_events(directory: Path | str | None = None) -> list[BenchmarkEvent]:
    """Load every `*.yaml` benchmark event in `directory` (recursively).

    `directory` defaults to `eval/benchmark/` at the repo root. Files starting
    with `_` or `.` are skipped (treated as drafts or hidden).
    """
    directory = Path(directory) if directory is not None else default_benchmark_dir()
    if not directory.exists():
        return []

    events: list[BenchmarkEvent] = []
    for path in sorted(directory.rglob("*.yaml")):
        if path.name.startswith(("_", ".")):
            continue
        events.append(load_event_file(path))
    return events


def load_event(event_id: str, directory: Path | str | None = None) -> BenchmarkEvent:
    """Load a single benchmark event by `event_id`, searching `directory`.

    Raises FileNotFoundError if no matching event exists.
    """
    for event in discover_events(directory):
        if event.event_id == event_id:
            return event
    raise FileNotFoundError(f"No benchmark event with event_id={event_id!r} found.")
