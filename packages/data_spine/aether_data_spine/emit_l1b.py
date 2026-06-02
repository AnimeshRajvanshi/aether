"""EMIT L1B At-Sensor Calibrated Radiance ingestion.

Product specifications verified from:
- EMIT L1B User Guide (Nov 2022, JPL D-107862):
  https://lpdaac.usgs.gov/documents/1568/EMITL1BRAD_User_Guide_v1.pdf
- EMIT L1B ATBD (April 2025):
  https://lpdaac.usgs.gov/documents/1570/EMITL1B_ATBD_v1.pdf
- NASA Earthdata catalog: EMITL1BRAD.001 (DOI 10.5067/EMIT/EMITL1BRAD.001):
  https://www.earthdata.nasa.gov/data/catalog/lpcloud-emitl1brad-001

Product layout:
    EMITL1BRAD.001 granules contain TWO NetCDF-4 files:
    - EMIT_L1B_RAD_{...}.nc   — radiance cube + sensor band parameters
    - EMIT_L1B_OBS_{...}.nc   — observation geometry & topography
    Each has 285 bands (~381-2493 nm, ~7.5 nm bandpass) at 60 m GSD.
    Radiance is in raw (non-orthorectified) sensor geometry; lon/lat are in
    the `location` group of the RAD file. Orthorectification is performed
    downstream via the GLT.

Radiance variable:
    /radiance           shape (downtrack, crosstrack, bands) — float32
                        units W m⁻² sr⁻¹ μm⁻¹  (also published as
                        µW cm⁻² sr⁻¹ nm⁻¹ in some EMIT tooling — they are
                        equivalent up to scale)
    /sensor_band_parameters/wavelengths  shape (bands,) nm
    /sensor_band_parameters/fwhm         shape (bands,) nm
    /location/lon                        shape (downtrack, crosstrack)
    /location/lat                        shape (downtrack, crosstrack)
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
# Verified via CMR: https://cmr.earthdata.nasa.gov/search/collections.umm_json?short_name=EMITL1BRAD
EMITL1BRAD_CONCEPT_ID = "C2408009906-LPCLOUD"
EMITL1BRAD_SHORT_NAME = "EMITL1BRAD"
EMITL1BRAD_VERSION = "001"

DEFAULT_CACHE_DIR = Path.home() / ".aether_cache" / "emit_l1b"


# --------------------------------------------------------------------------- #
# Granule search and pinning
# --------------------------------------------------------------------------- #


def search_l1b_granules(
    lat: float,
    lon: float,
    date_start: str,
    date_end: str,
) -> list[earthaccess.results.DataGranule]:
    """Search NASA Earthdata for EMIT L1B radiance granules covering a point.

    The L1B concept_id is different from the L2B concept_id; otherwise the
    search shape mirrors the L2B path in :mod:`emit`. Coverage is opportunistic
    (ISS orbit, not sun-synchronous).
    """
    return earthaccess.search_data(
        concept_id=EMITL1BRAD_CONCEPT_ID,
        temporal=(date_start, date_end),
        point=(lon, lat),
    )


def select_granule_by_ur(
    granules: list[earthaccess.results.DataGranule],
    granule_ur: str,
) -> earthaccess.results.DataGranule:
    """Pick a granule by its exact GranuleUR string.

    We never silently fall back to a different granule when a pin is requested —
    using a different acquisition would invalidate the per-granule unit
    absorption spectrum that the matched filter is parameterized with.
    """
    for g in granules:
        if g["umm"]["GranuleUR"] == granule_ur:
            return g
    raise ValueError(
        f"Pinned granule {granule_ur!r} not in search results. "
        f"Got {[g['umm']['GranuleUR'] for g in granules]}."
    )


def _granule_to_cache_key(granule: earthaccess.results.DataGranule) -> str:
    granule_ur = granule["umm"]["GranuleUR"]
    return hashlib.sha256(granule_ur.encode()).hexdigest()[:16]


def _cache_path_for_granule(granule: earthaccess.results.DataGranule, cache_dir: Path) -> Path:
    return cache_dir / f"{_granule_to_cache_key(granule)}.zarr"


# --------------------------------------------------------------------------- #
# Granule download and cache
# --------------------------------------------------------------------------- #


def download_and_cache_l1b(
    granule: earthaccess.results.DataGranule,
    cache_dir: Path | None = None,
    force: bool = False,
) -> Path:
    """Download an EMIT L1B granule and cache it as a Zarr store.

    EMIT L1B granules are two NetCDF-4 files (RAD + OBS). The RAD file is
    cached as a single Zarr store with its sensor_band_parameters group
    flattened in. The OBS file has its own "bands" dimension of length 11
    (geometry layers — solar zenith, view zenith, glint angle, ...), which
    collides with the RAD radiance cube's "bands" dimension of length 285.
    We rename the OBS bands dim before merging so both can live in the same
    Zarr store side by side. Without that rename, xarray raises
    AlignmentError on the assign() because the same dim name resolves to
    two different sizes.
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_path_for_granule(granule, cache_dir)

    if cache_path.exists() and not force:
        return cache_path

    # earthaccess streams NetCDFs via fsspec; we need them on local disk for
    # xarray + netcdf4 to memory-map cleanly. Tell earthaccess where to put them.
    download_dir = cache_dir / "downloads" / _granule_to_cache_key(granule)
    download_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("EARTHACCESS_LOCAL_PATH", str(download_dir))
    paths = earthaccess.download([granule], local_path=str(download_dir))

    rad_path = _find_file_with_substring(paths, "RAD")
    obs_path = _find_file_with_substring(paths, "OBS")

    rad_ds = _open_l1b_radiance(rad_path)
    if obs_path is not None:
        obs_ds = _open_l1b_obs(obs_path)
        # Rename the OBS bands dim so it does not collide with the RAD
        # radiance cube's 285-band axis. After this rename, OBS variables
        # live under their own dim and can be assigned in safely.
        if "bands" in obs_ds.sizes and obs_ds.sizes["bands"] != rad_ds.sizes.get("bands", -1):
            obs_ds = obs_ds.rename_dims({"bands": "obs_bands"})
        rad_ds = rad_ds.assign(
            {f"obs_{name}": obs_ds[name] for name in obs_ds.data_vars}
        )

    rad_ds.attrs["granule_ur"] = granule["umm"]["GranuleUR"]
    rad_ds.attrs["product_short_name"] = EMITL1BRAD_SHORT_NAME
    rad_ds.attrs["product_version"] = EMITL1BRAD_VERSION
    rad_ds.attrs["concept_id"] = EMITL1BRAD_CONCEPT_ID
    rad_ds.to_zarr(cache_path, mode="w", consolidated=True)
    return cache_path


def _find_file_with_substring(paths: list[str | Path], substr: str) -> Path | None:
    for p in paths:
        if substr in Path(p).name:
            return Path(p)
    return None


def _open_l1b_radiance(path: Path) -> xr.Dataset:
    """Open an EMIT_L1B_RAD NetCDF-4 file with its nested groups flattened.

    EMIT L1B uses NetCDF groups: the root has /radiance; sensor_band_parameters
    and location are sub-groups. xarray's open_dataset reads one group at a
    time, so we open each and merge into a flat Dataset.

    The location group carries six variables on two distinct dimension axes:
      - lon, lat, elev: on (downtrack, crosstrack) — per-pixel geolocation in
        raw sensor geometry.
      - glt_x, glt_y: on (ortho_y, ortho_x) — Geographic Lookup Table mapping
        each ortho grid pixel back to a 1-based (crosstrack, downtrack) source
        index. Value 0 marks ortho pixels with no source coverage. Use
        :func:`orthorectify_raw_raster` to apply.
    """
    ds_root = xr.open_dataset(path, engine="netcdf4")
    ds_band = xr.open_dataset(path, engine="netcdf4", group="sensor_band_parameters")
    ds_loc = xr.open_dataset(path, engine="netcdf4", group="location")
    merged = ds_root.assign(
        wavelengths_nm=ds_band["wavelengths"],
        fwhm_nm=ds_band["fwhm"],
        lon=ds_loc["lon"],
        lat=ds_loc["lat"],
        elev=ds_loc["elev"],
        glt_x=ds_loc["glt_x"],
        glt_y=ds_loc["glt_y"],
    )
    return merged


def orthorectify_raw_raster(
    raw: np.ndarray,
    glt_x: np.ndarray,
    glt_y: np.ndarray,
    fill_value: float = np.nan,
) -> np.ndarray:
    """Project a raw-geometry 2-D raster onto EMIT's ortho grid via the GLT.

    Args:
        raw: 2-D array of shape ``(downtrack, crosstrack)`` in raw sensor
            geometry — e.g. our matched-filter enhancement output.
        glt_x: GLT cross-track lookup, shape ``(ortho_y, ortho_x)``. 1-based
            indices into the cross-track axis; 0 means no source pixel.
        glt_y: GLT down-track lookup, same shape; 1-based; 0 means no source.
        fill_value: value written to ortho pixels with no source coverage.
            Defaults to NaN.

    Returns:
        2-D array of shape ``(ortho_y, ortho_x)``, on the same EPSG:4326 grid
        as NASA's L2B GeoTIFFs for this granule.
    """
    gx = np.asarray(glt_x)
    gy = np.asarray(glt_y)
    if gx.shape != gy.shape:
        raise ValueError(f"glt_x and glt_y shape mismatch: {gx.shape} vs {gy.shape}")
    if raw.ndim != 2:
        raise ValueError(f"raw must be 2-D (downtrack, crosstrack); got shape {raw.shape}")

    out = np.full(gx.shape, fill_value, dtype=np.float64)
    valid = (gx > 0) & (gy > 0)
    src_rows = (gy[valid].astype(np.int64) - 1).clip(0, raw.shape[0] - 1)
    src_cols = (gx[valid].astype(np.int64) - 1).clip(0, raw.shape[1] - 1)
    out[valid] = raw[src_rows, src_cols]
    return out


def _open_l1b_obs(path: Path) -> xr.Dataset:
    """Open an EMIT_L1B_OBS NetCDF-4 file."""
    return xr.open_dataset(path, engine="netcdf4")


# --------------------------------------------------------------------------- #
# Cache load + radiance accessor
# --------------------------------------------------------------------------- #


def load_l1b_from_cache(cache_path: Path) -> xr.Dataset:
    """Load a cached EMIT L1B granule from Zarr."""
    return xr.open_zarr(cache_path, consolidated=True)


def get_radiance_cube(ds: xr.Dataset) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(radiance_cube, wavelengths_nm, fwhm_nm)`` as plain numpy.

    The matched filter takes a numpy radiance cube of shape
    ``(downtrack, crosstrack, bands)``. EMIT's NetCDF layout is exactly that
    when we treat sensor_band_parameters as the band axis.
    """
    radiance = np.asarray(ds["radiance"].values, dtype=np.float64)
    if radiance.ndim != 3:
        raise ValueError(
            f"Expected 3-D radiance (downtrack, crosstrack, bands); got shape {radiance.shape}"
        )
    wavelengths_nm = np.asarray(ds["wavelengths_nm"].values, dtype=np.float64)
    fwhm_nm = np.asarray(ds["fwhm_nm"].values, dtype=np.float64)
    if wavelengths_nm.shape != (radiance.shape[-1],):
        raise ValueError(
            f"wavelengths_nm shape {wavelengths_nm.shape} does not match band axis "
            f"of radiance shape {radiance.shape}"
        )
    return radiance, wavelengths_nm, fwhm_nm
