"""Command-line interface for the Aether evaluation harness.

Usage:
    aether-eval list
    aether-eval show <event_id>
    aether-eval run [--event <id>]
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aether_eval.loader import discover_events, load_event
from aether_eval.runner import run_evaluation, stub_pipeline

app = typer.Typer(
    name="aether-eval",
    help="Aether evaluation harness — benchmark events, metrics, and pipeline runs.",
    no_args_is_help=True,
)
console = Console()


@app.command("list")
def list_events() -> None:
    """List every benchmark event in eval/benchmark/."""
    events = discover_events()
    if not events:
        console.print("[yellow]No benchmark events found.[/yellow]")
        console.print("Add YAML files to eval/benchmark/ to populate the benchmark.")
        raise typer.Exit(code=0)

    table = Table(title=f"Benchmark events ({len(events)} total)")
    table.add_column("event_id", style="cyan", no_wrap=True)
    table.add_column("phenomenon", style="magenta")
    table.add_column("location")
    table.add_column("date range")
    table.add_column("name", overflow="fold")

    for e in events:
        loc = f"{e.location.lat:.3f}, {e.location.lon:.3f}"
        start = e.date_range.start.date().isoformat()
        end = e.date_range.end.date().isoformat() if e.date_range.end else "—"
        table.add_row(e.event_id, e.phenomenon_type.value, loc, f"{start} → {end}", e.name)

    console.print(table)


@app.command("show")
def show_event(event_id: str) -> None:
    """Show full details of one benchmark event."""
    try:
        event = load_event(event_id)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from None

    console.print(f"[bold cyan]{event.event_id}[/bold cyan] — {event.name}")
    console.print(f"  body: {event.planetary_body.value}")
    console.print(f"  phenomenon: {event.phenomenon_type.value}")
    console.print(f"  expected detections: {[d.value for d in event.expected_detection_types]}")
    console.print(f"  location: {event.location.lat:.4f}, {event.location.lon:.4f}")
    console.print(f"  date_range: {event.date_range.start.isoformat()} → "
                  f"{event.date_range.end.isoformat() if event.date_range.end else 'ongoing'}")

    if event.known_measurements:
        console.print("\n[bold]Known measurements:[/bold]")
        for name, m in event.known_measurements.items():
            unc = f" ± {m.uncertainty}" if m.uncertainty is not None else ""
            console.print(f"  {name}: {m.value}{unc} {m.unit}  ({m.note})")

    if event.attribution.operator or event.attribution.facility:
        console.print("\n[bold]Attribution:[/bold]")
        if event.attribution.operator:
            console.print(f"  operator: {event.attribution.operator}")
        if event.attribution.facility:
            console.print(f"  facility: {event.attribution.facility}")
        if event.attribution.sector:
            console.print(f"  sector: {event.attribution.sector}")

    if event.observed_by:
        console.print("\n[bold]Observed by:[/bold]")
        for o in event.observed_by:
            note = f"  ({o.note})" if o.note else ""
            console.print(f"  {o.sensor} [{o.sensor_type.value}]{note}")

    if event.references:
        console.print("\n[bold]References:[/bold]")
        for r in event.references:
            console.print(f"  • {r.citation}")
            if r.doi:
                console.print(f"    doi: {r.doi}")
            if r.url:
                console.print(f"    url: {r.url}")

    if event.notes:
        console.print(f"\n[bold]Notes:[/bold]\n{event.notes}")


@app.command("run")
def run(
    event: str | None = typer.Option(None, "--event", "-e", help="Single event_id to run (defaults to all)"),
    spatial_tolerance_m: float = typer.Option(5000.0, help="Spatial tolerance for matching, meters"),
    temporal_tolerance_minutes: float = typer.Option(60.0, help="Temporal tolerance for matching, minutes"),
) -> None:
    """Run the pipeline against the benchmark and print the score."""
    all_events = discover_events()

    if event is not None:
        selected = [e for e in all_events if e.event_id == event]
        if not selected:
            console.print(f"[red]No benchmark event with event_id={event!r} found.[/red]")
            raise typer.Exit(code=1)
    else:
        selected = all_events

    if not selected:
        console.print("[yellow]No benchmark events to run. Add YAML files to eval/benchmark/.[/yellow]")
        raise typer.Exit(code=0)

    report = run_evaluation(
        pipeline=stub_pipeline,
        events=selected,
        spatial_tolerance_m=spatial_tolerance_m,
        temporal_tolerance_minutes=temporal_tolerance_minutes,
        pipeline_name="stub_pipeline",
    )

    console.print("\n[bold]Evaluation report[/bold]")
    for line in report.summary_lines():
        console.print(f"  {line}")


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
