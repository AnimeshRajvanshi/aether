"""Reproduce benchmark events from EMIT data."""

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib import cm
from matplotlib.colors import Normalize

from aether_data_spine import emit
from aether_eval.loader import load_event


def reproduce_event(
    event_id: str,
    output_path: Optional[Path] = None,
    force: bool = False,
) -> Path:
    """Reproduce a benchmark event: download EMIT data and render PNG.

    Args:
        event_id: Benchmark event ID (e.g., "permian_basin_2022").
        output_path: Output PNG path. Defaults to ./<event_id>_plume.png.
        force: Force re-download even if cached.

    Returns:
        Path to the rendered PNG.

    Raises:
        FileNotFoundError: If the benchmark event file doesn't exist.
        ValueError: If no EMIT granules cover the event.
        RuntimeError: If download or rendering fails.
    """
    # Load the benchmark event
    event = load_event(event_id)

    # Extract location and date range
    if not hasattr(event, "location") or not hasattr(event, "date_range"):
        raise ValueError(f"Event '{event_id}' is missing location or date_range")

    lat = event.location.lat
    lon = event.location.lon
    date_start = event.date_range.start.isoformat()
    date_end = event.date_range.end.isoformat()

    # Search for EMIT granules
    print(f"Searching for EMIT granules covering ({lat}, {lon}) from {date_start} to {date_end}...")
    granules = emit.search_granules(lat, lon, date_start, date_end)

    if not granules:
        raise ValueError(
            f"No EMIT granules found for event '{event_id}'. "
            f"EMIT coverage is opportunistic (ISS orbit). "
            f"Note: EMIT had a power shutdown from 2022-09-13 to 2023-01-06."
        )

    print(f"Found {len(granules)} granule(s)")

    # Use the first granule (most events have one; if multiple, first is usually best)
    granule = granules[0]
    print(f"Using granule: {granule['umm']['GranuleUR']}")

    # Download and cache
    print("Downloading and caching EMIT data (this may take several minutes)...")
    cache_path = emit.download_and_cache(granule, force=force)
    print(f"Cached to: {cache_path}")

    # Load from cache
    print("Loading from cache...")
    ds = emit.load_from_cache(cache_path)

    # Extract methane enhancement
    ch4_enh = emit.extract_ch4_enhancement(ds)

    # Render as PNG
    if output_path is None:
        output_path = Path.cwd() / f"{event_id}_plume.png"
    else:
        output_path = Path(output_path)

    print(f"Rendering PNG to {output_path}...")
    render_plume_png(ch4_enh, output_path, event_id=event_id)

    return output_path


def render_plume_png(
    ch4_enh: xr.DataArray,
    output_path: Path,
    event_id: str,
    dpi: int = 150,
) -> None:
    """Render methane enhancement as a PNG map.

    Args:
        ch4_enh: Methane enhancement DataArray (ppm m).
        output_path: Output PNG file path.
        event_id: Event ID for the title.
        dpi: Output resolution (default 150).

    Notes:
        Uses a colormap that highlights plumes (enhanced values) against background.
        EMIT L2B CH4ENH is already orthorectified in EPSG:4326, so x/y are lon/lat.
    """
    # Replace NaN with 0 for visualization (background)
    data = ch4_enh.values
    data = np.nan_to_num(data, nan=0.0)

    # Get coordinate arrays (x=lon, y=lat)
    lons = ch4_enh.x.values
    lats = ch4_enh.y.values

    # Compute robust colormap limits (avoid outliers skewing the scale)
    valid_data = data[data > 0]  # Only enhanced pixels
    if len(valid_data) > 0:
        vmin = 0
        vmax = np.percentile(valid_data, 99)  # 99th percentile to avoid extreme outliers
    else:
        vmin, vmax = 0, 1

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 10), dpi=dpi)

    # Plot methane enhancement
    # Use 'hot' colormap (black -> red -> yellow -> white) which highlights plumes well
    norm = Normalize(vmin=vmin, vmax=vmax)
    im = ax.imshow(
        data,
        extent=[lons.min(), lons.max(), lats.min(), lats.max()],
        origin="upper",
        cmap="hot",
        norm=norm,
        interpolation="nearest",
        aspect="auto",
    )

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Methane Enhancement (ppm m)", fontsize=12)

    # Labels and title
    ax.set_xlabel("Longitude (°E)", fontsize=12)
    ax.set_ylabel("Latitude (°N)", fontsize=12)
    ax.set_title(
        f"EMIT Methane Plume: {event_id}\n"
        f"Product: EMITL2BCH4ENH.002 (60m resolution, orthorectified)",
        fontsize=14,
        fontweight="bold",
    )

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

    # Tight layout
    plt.tight_layout()

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    print(f"PNG rendered: {output_path}")
