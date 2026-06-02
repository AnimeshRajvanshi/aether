"""ARCO-ERA5 10 m wind fetch and overpass-time interpolation.

We use the publicly accessible **Analysis-Ready Cloud-Optimized (ARCO) ERA5**
Zarr store hosted on Google Cloud Storage. It requires no credentials. The
underlying ERA5 data are the ECMWF reanalysis as distributed by Copernicus CDS;
ARCO-ERA5 republishes them in Zarr at hourly resolution on the native 0.25°
grid.

References:
- Google ARCO-ERA5 dataset (public, anonymous GCS read):
  https://cloud.google.com/storage/docs/public-datasets/era5
  gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3
- Hersbach et al. 2020, "The ERA5 global reanalysis", QJRMS 146, 1999-2049.
  doi:10.1002/qj.3803

Wind variables used here:
- ``10m_u_component_of_wind`` (zonal, m/s)
- ``10m_v_component_of_wind`` (meridional, m/s)
Both at 0.25° lat/lon, hourly. We extract a small patch around the source
location, then time-interpolate to the overpass UTC.

Important: ERA5's representativeness error vs local point measurements is
~1.6 m/s standard deviation per Varon et al. 2018 §7 (using GEOS-FP; ERA5 is
comparable). Plume lifetimes (1-60 min) are shorter than the 1 h sampling,
adding another 1-2 m/s in quadrature. Both errors propagate to U_eff and then
to the IME source rate Q; the quantification module owns that propagation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import xarray as xr

# Public GCS Zarr URI for hourly ERA5 on full vertical coverage at 0.25 deg.
# This dataset is anonymous-readable; no credentials needed.
ARCO_ERA5_GCS_URI: str = (
    "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
)
ARCO_ERA5_VAR_U10: str = "10m_u_component_of_wind"
ARCO_ERA5_VAR_V10: str = "10m_v_component_of_wind"

DEFAULT_CACHE_DIR = Path.home() / ".aether_cache" / "era5"


@dataclass(frozen=True)
class WindAtOverpass:
    """ERA5 10 m wind interpolated to a specific lat/lon and UTC moment.

    ``u_ms`` and ``v_ms`` are the linearly-time-interpolated components on the
    nearest 0.25° grid cell. ``speed_ms`` is the magnitude. ``hour_distance_h``
    reports how far the requested time was from the nearest ERA5 sampling slot;
    when this is more than ~30 min, the representativeness error grows because
    methane plume lifetimes are shorter than the ERA5 hourly cadence.
    """

    u_ms: float
    v_ms: float
    speed_ms: float
    source: str  # ERA5 dataset URI
    grid_lat: float
    grid_lon: float
    requested_lat: float
    requested_lon: float
    requested_utc: datetime
    nearest_hour_utc: datetime
    hour_distance_h: float


def open_arco_era5_wind(
    cache_dir: Path | None = None,
    consolidated: bool = True,
) -> xr.Dataset:
    """Open the ARCO-ERA5 Zarr store, lazily.

    Reads u10, v10 only; ARCO-ERA5 is huge, so we never materialize anything
    not asked for. xarray with the gcsfs filesystem handles anonymous reads.
    """
    if cache_dir is None:
        cache_dir = DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    # gcsfs is auto-resolved from the gs:// URI by xarray. ARCO-ERA5 is
    # anonymously readable so no token is needed.
    return xr.open_zarr(
        ARCO_ERA5_GCS_URI,
        consolidated=consolidated,
        storage_options={"token": "anon"},
    )


def get_wind_at_point(
    lat: float,
    lon: float,
    utc: datetime,
    dataset: xr.Dataset | None = None,
) -> WindAtOverpass:
    """Return ERA5 10 m wind at a point + time, time-linearly-interpolated.

    Strategy:
    1. Open ARCO-ERA5 (or use a provided dataset for tests).
    2. Select the nearest grid cell (xarray ``sel(method='nearest')``).
    3. Slice a 2-hour window bracketing ``utc`` and linear-interpolate in time.

    Returns:
        :class:`WindAtOverpass` carrying the interpolated u/v/speed plus
        provenance metadata (which grid cell, which hour, how far away).
    """
    if dataset is None:
        dataset = open_arco_era5_wind()

    # Normalize longitude to ERA5's convention. ARCO-ERA5 uses [0, 360); user
    # may pass either. ECMWF Zarrs sometimes use [-180, 180). We sniff once.
    era5_lon = _normalize_longitude_for_grid(lon, dataset)

    u_var = dataset[ARCO_ERA5_VAR_U10].sel(
        latitude=lat, longitude=era5_lon, method="nearest"
    )
    v_var = dataset[ARCO_ERA5_VAR_V10].sel(
        latitude=lat, longitude=era5_lon, method="nearest"
    )

    grid_lat = float(u_var.latitude.values)
    grid_lon_raw = float(u_var.longitude.values)
    grid_lon = grid_lon_raw if grid_lon_raw <= 180.0 else grid_lon_raw - 360.0

    requested_np = np.datetime64(utc.replace(tzinfo=None))
    # interp uses linear in time by default; we restrict to a 2-h window so
    # the lazy graph stays small.
    window = u_var.sel(time=slice(
        requested_np - np.timedelta64(1, "h"),
        requested_np + np.timedelta64(1, "h"),
    ))
    if window.time.size == 0:
        raise ValueError(
            f"No ERA5 samples within ±1 h of {utc.isoformat()} at "
            f"({grid_lat}, {grid_lon}); check date range coverage."
        )

    u_interp = float(
        u_var.interp(time=requested_np, kwargs={"fill_value": "extrapolate"}).values
    )
    v_interp = float(
        v_var.interp(time=requested_np, kwargs={"fill_value": "extrapolate"}).values
    )

    nearest_time_np = u_var.sel(time=requested_np, method="nearest").time.values
    nearest_utc = datetime.fromtimestamp(
        (nearest_time_np - np.datetime64("1970-01-01")) / np.timedelta64(1, "s"),
        tz=UTC,
    )
    hour_distance_h = abs(
        (nearest_time_np - requested_np) / np.timedelta64(1, "s")
    ) / 3600.0

    return WindAtOverpass(
        u_ms=u_interp,
        v_ms=v_interp,
        speed_ms=float(np.hypot(u_interp, v_interp)),
        source=ARCO_ERA5_GCS_URI,
        grid_lat=grid_lat,
        grid_lon=grid_lon,
        requested_lat=lat,
        requested_lon=lon,
        requested_utc=utc,
        nearest_hour_utc=nearest_utc,
        hour_distance_h=hour_distance_h,
    )


def _normalize_longitude_for_grid(lon: float, dataset: xr.Dataset) -> float:
    """Translate a user-supplied longitude into the dataset's lon convention.

    ERA5 historically uses 0..360; ARCO-ERA5's recent v3 chunk uses -180..180
    via the ``longitude`` coordinate. We sniff the coordinate range once to
    decide which convention the open store uses.
    """
    lon_coord = dataset["longitude"]
    hi = float(lon_coord.max())
    if hi > 180.5:  # 0..360 convention
        return lon if lon >= 0.0 else lon + 360.0
    return lon  # -180..180 convention; no translation needed
