"""Aether CLI — reproduce benchmark events, ingest data, run analysis."""

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn

from aether_cli import reproduce
from aether_data_spine import emit

app = typer.Typer(
    name="aether",
    help="Aether Planetary Engine CLI",
    no_args_is_help=True,
)


@app.command()
def reproduce_cmd(
    event_id: Annotated[str, typer.Argument(help="Benchmark event ID to reproduce")],
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output PNG path (default: ./<event_id>_plume.png)"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force re-download even if cached"),
    ] = False,
) -> None:
    """Reproduce a benchmark event: download EMIT data, render methane plume PNG.

    This is the Sprint 1 gate command. Given a benchmark event that was observed by EMIT:
    1. Resolves which EMIT granule(s) cover the event's location and date
    2. Downloads the EMIT L2B methane data (with NASA Earthdata credentials)
    3. Caches it locally in Zarr format under ~/.aether_cache/
    4. Loads it, and renders the methane enhancement layer as a static PNG
    5. Saves the PNG and prints where it went

    Example:
        aether reproduce permian_basin_2022
    """
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            # Authenticate
            progress.add_task(description="Authenticating with NASA Earthdata...", total=None)
            emit.authenticate()

            # Load and reproduce
            progress.add_task(description=f"Reproducing event '{event_id}'...", total=None)
            png_path = reproduce.reproduce_event(event_id, output_path=output, force=force)

        rprint(f"[green]✓[/green] Successfully reproduced event '{event_id}'")
        rprint(f"[blue]→[/blue] PNG saved to: {png_path}")

    except FileNotFoundError as e:
        rprint(f"[red]✗[/red] Benchmark event not found: {e}")
        sys.exit(1)
    except ValueError as e:
        rprint(f"[red]✗[/red] Invalid event: {e}")
        sys.exit(1)
    except RuntimeError as e:
        rprint(f"[red]✗[/red] Error: {e}")
        sys.exit(1)
    except Exception as e:
        rprint(f"[red]✗[/red] Unexpected error: {e}")
        raise


if __name__ == "__main__":
    app()
