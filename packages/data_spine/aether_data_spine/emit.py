"""EMIT L2B methane data access, caching, and loading.

Product specifications verified from:
- NASA EMIT-Data-Resources: https://github.com/nasa/EMIT-Data-Resources
- LP DAAC Product Page: https://www.earthdata.nasa.gov/data/catalog/lpcloud-emitl2bch4enh-002
- EMIT L2B GHG User Guide V2 (April 2025): https://lpdaac.usgs.gov/documents/2250/EMIT_L2B_GHG_User_Guide_V2.pdf

Product: EMITL2BCH4ENH.002
Collection ID: C3242680113-LPCLOUD
Format: Cloud Optimized GeoTIFF (COG), already orthorectified in EPSG:4326
Variables: EMIT_L2B_CH4ENH (ppm m), EMIT_L2B_CH4UNCERT (ppm m), EMIT_L2B_CH4SENS
Resolution: 60 meters
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import earthaccess
import numpy as np
import rioxarray as rxr
import xarray as xr
import zarr

from aether_ontology.base import Provenance

# Product constants verified from LP DAAC
# https://www.earthdata.nasa.gov/data/catalog/lpcloud-emitl2bch4enh-002
EMITL2BCH4ENH_CONCEPT_ID = "C3242680113-LPCLOUD"
EMITL2BCH4ENH_SHORT_NAME = "EMITL2BCH4ENH"
EMITL2BCH4ENH_VERSION = "002"

# Cache directory (gitignored)
DEFAULT_CACHE_DIR = Path.home() / ".aether_cache" / "emit"


def authenticate() -> None:
    """Authenticate with NASA Earthdata.

    Uses earthaccess.login() which prompts interactively and persists to ~/.netrc.
    The user must have created a free NASA Earthdata Login account at
    https://urs.earthdata.nasa.gov

    Raises:
        RuntimeError: If authentication fails.
    """
    auth = earthaccess.login()
    if not auth.authenticated:
        raise RuntimeError(
            "NASA Earthdata authentication failed. "
            "Create an account at https://urs.earthdata.nasa.gov and run earthaccess.login()"
        )


def search_granules(
    lat: float,
    lon: float,
    date_start: str,
    date_end: str,
    concept_id: str = EMITL2BCH4ENH_CONCEPT_ID,
) -> list[earthaccess.results.DataGranule]:
    """Search for EMIT granules covering a location and date range.

    Args:
        lat: Latitude in decimal degrees (WGS84).
        lon: Longitude in decimal degrees (WGS84).
        date_start: Start date in ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ).
        date_end: End date in ISO 8601 format.
        concept_id: NASA Earthdata collection concept ID. Defaults to EMITL2BCH4ENH.002.

    Returns:
        List of earthaccess DataGranule objects covering the location and date range.
        Empty list if no granules found.

    Notes:
        EMIT is on the ISS (not sun-synchronous) so coverage is opportunistic and gappy.
        From 2022-09-13 to 2023-01-06, EMIT had a power shutdown (no data acquired).
    """
    results = earthaccess.search_data(
        concept_id=concept_id,
        temporal=(date_start, date_end),
        point=(lon, lat),  # Note: earthaccess uses (lon, lat) order
    )
    return results


def _granule_to_cache_key(granule: earthaccess.results.DataGranule) -> str:
    """Generate a stable cache key from a granule's metadata."""
    # Use the granule's unique identifier
    granule_ur = granule["umm"]["GranuleUR"]
    return hashlib.sha256(granule_ur.encode()).hexdigest()[:16]


def _get_cache_path(granule: earthaccess.results.DataGranule, cache_dir: Path) -> Path:
    """Get the cache path for a granule's Zarr store."""
    cache_key = _granule_to_cache_key(granule)
    return cache_dir / f"{cache_key}.zarr"


def download_and_cache(
    granule: earthaccess.results.DataGranule,
    cache_dir: Path | None = None,
    force: bool = False,
) -> Path:
    """Download EMIT granule and cache as Zarr. Returns cached copy if available.

    Args:
        granule: earthaccess DataGranule object from search_granules().
        cache_dir: Directory for Zarr cache. Defaults to ~/.aether_cache/emit.
        force: If True, re-download even if cached copy exists.

    Returns:
        Path to the cached Zarr store.

    Notes:
        EMIT L2B CH4ENH granules are COGs (Cloud Optimized GeoTIFFs) already orthorectified.
        Each granule contains 3 GeoTIFFs: CH4ENH, CH4UNCERT, CH4SENS.
        We download via earthaccess.open() (streaming) and cache locally as Zarr for fast reuse.
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_path = _get_cache_path(granule, cache_dir)

    # Return cached copy if it exists and force=False
    if cache_path.exists() and not force:
        return cache_path

    # Configure GDAL environment variables for vsicurl (streaming COGs from HTTPS with auth)
    # Following NASA EMIT-Data-Resources tutorial pattern:
    # https://github.com/nasa/EMIT-Data-Resources/blob/main/python/tutorials/Visualizing_Methane_Plume_Timeseries.ipynb
    # Note: Using environment variables instead of direct GDAL config to avoid system-level GDAL dependency
    os.environ["GDAL_HTTP_COOKIEFILE"] = str(Path.home() / ".urs_cookies")
    os.environ["GDAL_HTTP_COOKIEJAR"] = str(Path.home() / ".urs_cookies")
    os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
    os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = "TIF"

    # Get the data links for this granule
    # earthaccess.open() returns file-like handles; we use rioxarray to stream the COGs
    file_handles = earthaccess.open([granule])

    # EMIT L2B CH4ENH granules have multiple GeoTIFF files: one per variable
    # We'll load them as separate data variables in the xarray Dataset
    datasets: dict[str, xr.DataArray] = {}

    for fh in file_handles:
        # Get the URL for rioxarray (earthaccess provides fsspec file handles)
        url = fh.url if hasattr(fh, "url") else str(fh)

        # Open the COG and squeeze the band dimension (single-band GeoTIFFs)
        da = rxr.open_rasterio(url).squeeze("band", drop=True)

        # Infer variable name from filename
        # Filename pattern: EMIT_L2B_CH4ENH_*.tif, EMIT_L2B_CH4UNCERT_*.tif, etc.
        if "CH4ENH" in url and "UNCERT" not in url:
            var_name = "ch4_enhancement"
            da.attrs["units"] = "ppm m"
            da.attrs["long_name"] = "Methane column enhancement"
        elif "CH4UNCERT" in url:
            var_name = "ch4_uncertainty"
            da.attrs["units"] = "ppm m"
            da.attrs["long_name"] = "Methane enhancement uncertainty"
        elif "CH4SENS" in url:
            var_name = "ch4_sensitivity"
            da.attrs["units"] = "dimensionless"
            da.attrs["long_name"] = "Methane retrieval sensitivity"
        else:
            # Skip unrecognized files
            continue

        datasets[var_name] = da

    # Combine into a single xarray Dataset
    ds = xr.Dataset(datasets)

    # Add global metadata
    ds.attrs["granule_ur"] = granule["umm"]["GranuleUR"]
    ds.attrs["product_short_name"] = EMITL2BCH4ENH_SHORT_NAME
    ds.attrs["product_version"] = EMITL2BCH4ENH_VERSION
    ds.attrs["concept_id"] = EMITL2BCH4ENH_CONCEPT_ID
    ds.attrs["temporal_start"] = granule["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]
    ds.attrs["temporal_end"] = granule["umm"]["TemporalExtent"]["RangeDateTime"]["EndingDateTime"]

    # Cache as Zarr
    ds.to_zarr(cache_path, mode="w", consolidated=True)

    # Close file handles
    for fh in file_handles:
        if hasattr(fh, "close"):
            fh.close()

    return cache_path


def load_from_cache(cache_path: Path) -> xr.Dataset:
    """Load a cached EMIT granule from Zarr.

    Args:
        cache_path: Path to the Zarr store (from download_and_cache).

    Returns:
        xarray Dataset with ch4_enhancement, ch4_uncertainty, ch4_sensitivity variables.
    """
    return xr.open_zarr(cache_path, consolidated=True)


def extract_ch4_enhancement(ds: xr.Dataset) -> xr.DataArray:
    """Extract the methane enhancement layer from an EMIT dataset.

    Args:
        ds: xarray Dataset from load_from_cache().

    Returns:
        DataArray with methane enhancement values (ppm m) and spatial coordinates.
    """
    return ds["ch4_enhancement"]


def build_provenance(
    granule: earthaccess.results.DataGranule,
    cache_path: Path,
) -> Provenance:
    """Build a Provenance object for an EMIT observation.

    Args:
        granule: earthaccess DataGranule object.
        cache_path: Path to the cached Zarr store.

    Returns:
        Provenance object with source, source_id, parents, etc.
    """
    granule_ur = granule["umm"]["GranuleUR"]
    temporal_start = granule["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]

    return Provenance(
        source=f"{EMITL2BCH4ENH_SHORT_NAME}.{EMITL2BCH4ENH_VERSION}",
        source_id=granule_ur,
        pipeline=None,  # Not produced by an Aether pipeline (raw ingestion)
        pipeline_version=None,
        parents=[],  # No parent UUIDs for raw observations
        notes=(
            f"Ingested from NASA LP DAAC (concept_id={EMITL2BCH4ENH_CONCEPT_ID}). "
            f"Observation time: {temporal_start}. Cached to {cache_path}."
        ),
    )
