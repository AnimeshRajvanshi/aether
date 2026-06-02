"""EMIT L2A mask ingestion.

The L2A mask (EMITL2AMASK.001) provides per-pixel cloud, surface water, and
spacecraft-saturation flags that the EMIT GHG matched filter consumes to
exclude bad pixels from the per-column μ/Σ estimates and from the published
enhancement product (see EMIT GHG ATBD §4.1, §4.2.1).

Product reference:
- NASA Earthdata catalog EMITL2AMASK.001
  https://www.earthdata.nasa.gov/data/catalog/lpcloud-emitl2amask-001
- EMIT L2A ATBD (Apr 2025), §5 "Cloud, Cirrus, Water, Spacecraft and Aggregate
  Flags" — defines the 7-band mask cube.

Band layout (band index → meaning), per the L2A User Guide:
    0  cloud
    1  cirrus
    2  water
    3  spacecraft (saturation / out-of-range)
    4  aggregate flag (any of the above)
    5  AOD550 (optional, may be NaN)
    6  H2O vapor (g/cm²)

For the matched filter we treat the aggregate flag (band 4 != 0) as "bad",
matching the EMIT GHG operational behavior.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import earthaccess
import numpy as np
import xarray as xr

# --------------------------------------------------------------------------- #
# Product constants
# --------------------------------------------------------------------------- #
# Verified via CMR: short_name=EMITL2AMASK&version=002 returns C3882545269-LPCLOUD.
# The L2A mask product is now at v002 (the v001 collection was retired); using
# v001 returns no results for 2022-08-15 onward.
EMITL2AMASK_CONCEPT_ID = "C3882545269-LPCLOUD"
EMITL2AMASK_SHORT_NAME = "EMITL2AMASK"
EMITL2AMASK_VERSION = "002"

# Mask cube band indices (verified against EMIT L2A user guide and the
# emit-sds/emit-ghg masking code, which thresholds the aggregate band).
MASK_BAND_CLOUD = 0
MASK_BAND_CIRRUS = 1
MASK_BAND_WATER = 2
MASK_BAND_SPACECRAFT = 3
MASK_BAND_AGGREGATE = 4

DEFAULT_CACHE_DIR = Path.home() / ".aether_cache" / "emit_l2a_mask"


def search_l2a_mask_granules(
    lat: float, lon: float, date_start: str, date_end: str
) -> list[earthaccess.results.DataGranule]:
    return earthaccess.search_data(
        concept_id=EMITL2AMASK_CONCEPT_ID,
        temporal=(date_start, date_end),
        point=(lon, lat),
    )


def _granule_to_cache_key(granule: earthaccess.results.DataGranule) -> str:
    return hashlib.sha256(granule["umm"]["GranuleUR"].encode()).hexdigest()[:16]


def download_and_cache_l2a_mask(
    granule: earthaccess.results.DataGranule,
    cache_dir: Path | None = None,
    force: bool = False,
) -> Path:
    """Download an L2A mask granule and cache it as Zarr.

    The mask product is a single NetCDF-4 file with a 7-band ``mask`` variable.
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{_granule_to_cache_key(granule)}.zarr"

    if cache_path.exists() and not force:
        return cache_path

    download_dir = cache_dir / "downloads" / _granule_to_cache_key(granule)
    download_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("EARTHACCESS_LOCAL_PATH", str(download_dir))
    paths = earthaccess.download([granule], local_path=str(download_dir))
    mask_path = paths[0]

    ds = xr.open_dataset(mask_path, engine="netcdf4")
    ds.attrs["granule_ur"] = granule["umm"]["GranuleUR"]
    ds.attrs["product_short_name"] = EMITL2AMASK_SHORT_NAME
    ds.attrs["product_version"] = EMITL2AMASK_VERSION
    ds.attrs["concept_id"] = EMITL2AMASK_CONCEPT_ID
    ds.to_zarr(cache_path, mode="w", consolidated=True)
    return cache_path


def load_l2a_mask_from_cache(cache_path: Path) -> xr.Dataset:
    return xr.open_zarr(cache_path, consolidated=True)


def build_bad_pixel_mask(
    mask_ds: xr.Dataset,
    use_aggregate: bool = True,
) -> np.ndarray:
    """Return a 2-D boolean array; True = exclude pixel from MF μ/Σ + output.

    If ``use_aggregate=True`` (default), pixels are flagged when the aggregate
    band (index 4) is non-zero. Otherwise, the cloud, cirrus, water, and
    spacecraft bands are OR-combined.
    """
    mask_var_name = _detect_mask_variable_name(mask_ds)
    mask_cube = np.asarray(mask_ds[mask_var_name].values)
    if mask_cube.ndim != 3:
        raise ValueError(
            f"Expected 3-D mask cube (downtrack, crosstrack, mask_band); "
            f"got shape {mask_cube.shape}"
        )

    if use_aggregate:
        if mask_cube.shape[-1] <= MASK_BAND_AGGREGATE:
            raise ValueError(
                f"Mask cube has only {mask_cube.shape[-1]} bands; "
                f"need at least {MASK_BAND_AGGREGATE + 1} to read the aggregate band"
            )
        bad = mask_cube[..., MASK_BAND_AGGREGATE] != 0
    else:
        bad = np.zeros(mask_cube.shape[:2], dtype=bool)
        for band in (MASK_BAND_CLOUD, MASK_BAND_CIRRUS, MASK_BAND_WATER, MASK_BAND_SPACECRAFT):
            if mask_cube.shape[-1] > band:
                bad |= mask_cube[..., band] != 0
    return bad


def _detect_mask_variable_name(mask_ds: xr.Dataset) -> str:
    """The 3-D variable carrying the multi-band mask cube.

    The EMIT L2A mask product uses ``mask`` for the multi-band cube; if NASA
    renames it in a future version we fall back to picking the first 3-D
    data variable.
    """
    if "mask" in mask_ds.data_vars:
        return "mask"
    for name, var in mask_ds.data_vars.items():
        if var.ndim == 3:
            return name
    raise ValueError(
        f"No 3-D variable found in mask dataset (vars: {list(mask_ds.data_vars)})"
    )
